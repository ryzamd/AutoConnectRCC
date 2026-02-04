#!/usr/bin/env python3

import sys
import os
import logging
from datetime import datetime
from typing import Optional, List

from .config import get_config, SecureConfig
from .discovery import discover_broker, verify_broker, DiscoveredBroker
from .wifi_manager import get_wifi_manager, WiFiNetwork
from .shelly_api import check_shelly_ap_mode
from .provisioner import create_provisioner, ProvisionedDevice
from .mqtt_client import MQTTVerifier
from .ui import RCCConsole, print_banner, print_section, print_divider


# Configure logging (no credentials logged)
def setup_logging() -> logging.Logger:
    log_dir = os.path.expanduser("~/.rcc/logs")
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(
        log_dir,
        f"rcc_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    )
    
    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format='[%(asctime)s] %(levelname)s  %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    logger = logging.getLogger("rcc")
    logger.info("RCC v1.0.0 started")
    
    return logger


class RCCApp:
    def __init__(self):
        self.console = RCCConsole()
        self.config = get_config()
        self.logger = setup_logging()
        self.provisioner = None
        self._original_wifi: Optional[str] = None
    
    def run(self) -> int:
        try:
            self.console.show_banner()
            
            if not self.config.is_ready():
                self._setup_configuration()
            
            while True:
                choice = self.console.show_main_menu(
                    broker_status=self.config.get_status_string()
                )
                
                if choice == "1":
                    self._discover_broker()
                elif choice == "2":
                    self._scan_devices()
                elif choice == "3":
                    self._provision_devices()
                elif choice == "4":
                    self._verify_connections()
                elif choice == "Q":
                    break
            
            self._cleanup()
            
            self.console.print("\n[dim]Goodbye![/dim]\n")
            return 0
            
        except KeyboardInterrupt:
            self.console.print("\n\n[notice]Interrupted by user[/notice]")
            self._cleanup()
            return 1
        except Exception as e:
            self.logger.exception("Unexpected error")
            self.console.print_error(f"Unexpected error: {str(e)}")
            self._cleanup()
            return 1
    
    def _cleanup(self) -> None:
        self.logger.info("Cleaning up...")
        self.config.clear_credentials()
        self.logger.info("Credentials cleared")
    
    # ═══════════════════════════════════════════════════════════════
    # Configuration Setup - SIMPLIFIED VERSION
    # ═══════════════════════════════════════════════════════════════
    
    def _setup_configuration(self) -> None:
        self.console.clear()
        self.console.show_banner()
        
        print_section("Initial Setup")
        self.console.print()
        self.console.print("[text]Simplified setup - only WiFi configuration needed[/text]")
        self.console.print()
        
        port = self.console.prompt_int(
            "  Server port",
            default=self.config.broker.port,
            min_val=1,
            max_val=65535
        )
        self.config.broker.port = port
        
        self.console.print()
        
        self.console.print_info(f"Auto-discovering server...")
        
        broker = discover_broker("RCCServer")
        
        if broker:
            self.console.print_success(f"Found server at {broker.ip} via {broker.method}")
            self.config.broker.ip = broker.ip
            self.logger.info(f"Auto-discovered broker: {broker.ip} ({broker.method})")
        else:
            self.console.print_warning("Could not auto-discover server")
            self.console.print("[dim]Note: Discovery will retry when needed[/dim]")
        
        self.console.print()
        
        self.console.print("[primary]Target WiFi Configuration[/primary]")
        print_divider()
        
        ssid = self.console.prompt_text(
            "  WiFi SSID",
            default=""
        )
        self.config.wifi.ssid = ssid
        
        wifi_password = self.console.prompt_text(
            "  WiFi Password",
            password=False
        )
        self.config.wifi.password = wifi_password
        
        self.console.print()
        
        self.logger.info(f"Broker: {self.config.broker.address}:{self.config.broker.port}")
        self.logger.info(f"MQTT User: {self.config.broker.username} (password: ****)")
        self.logger.info(f"Target WiFi: {self.config.wifi.ssid} (password: ****)")
        self.logger.info(f"Device prefix: {self.config.naming.prefix}")
        
        self.console.wait_for_key()
    
    # ═══════════════════════════════════════════════════════════════
    # Menu Actions
    # ═══════════════════════════════════════════════════════════════
    
    def _discover_broker(self) -> None:
        self.console.clear()
        self.console.show_banner()
        print_section("Discover Server")
        
        self.console.print()
        self.console.print_info(f"Searching for server: ...")
        
        broker = discover_broker("RCCServer")
        
        if broker:
            self.console.print_success(f"Found server at {broker.ip} via {broker.method}")
            self.config.broker.ip = broker.ip
            self.logger.info(f"Discovered broker: {broker.ip} ({broker.method})")
            
            if verify_broker(broker.ip, self.config.broker.port):
                self.console.print_success(f"Server is accessible on port {self.config.broker.port}")
            else:
                self.console.print_warning(f"Server found but port {self.config.broker.port} not responding")
        else:
            self.console.print_error("Could not auto-discover server")
            
            ip = self.console.prompt_text(
                "Enter server IP manually",
                default=self.config.broker.ip or ""
            )
            
            if ip:
                if verify_broker(ip, self.config.broker.port):
                    self.config.broker.ip = ip
                    self.console.print_success(f"Server verified at {ip}")
                    self.logger.info(f"Manual broker: {ip}")
                else:
                    self.console.print_error(f"Cannot connect to {ip}:{self.config.broker.port}")
        
        self.console.wait_for_key()
    
    def _scan_devices(self) -> None:
        self.console.clear()
        self.console.show_banner()
        print_section("Scan Devices")
        
        self.console.print()
        self.console.print_info("Scanning for WiFi networks...")
        
        try:
            wifi_manager = get_wifi_manager()
            networks = wifi_manager.scan_shelly_networks()
            
            if networks:
                self.console.print_success(f"Found {len(networks)} device(s)")
                self.logger.info(f"Found {len(networks)} devices")
                
                devices = []
                for n in networks:
                    display_ssid = n.ssid
                    if n.ssid.lower().startswith("shelly") and "-" in n.ssid:
                        parts = n.ssid.split("-")
                        if len(parts) >= 2:
                            dev_id = parts[-1]
                            display_ssid = f"Device - {dev_id}"
                    
                    devices.append({
                        "ssid": display_ssid,
                        "signal": n.signal,
                        "model": n.shelly_model
                    })
                self.console.show_device_table(devices)
            else:
                self.console.print_warning("No devices found")
                self.console.print()
                self.console.print("[dim]Make sure:[/dim]")
                self.console.print("[dim]  • Devices are powered on[/dim]")
                self.console.print("[dim]  • Devices are in Factory mode[/dim]")
                self.console.print("[dim]  • You are within WiFi range[/dim]")
                
        except NotImplementedError as e:
            self.console.print_error(str(e))
        except Exception as e:
            self.console.print_error(f"Scan failed: {str(e)}")
            self.logger.exception("Scan failed")
        
        self.console.wait_for_key()
    
    def _provision_devices(self) -> None:
        self.console.clear()
        self.console.show_banner()
        
        if not self.config.is_ready():
            self.console.print_error("Configuration incomplete. Please set up first.")
            self.console.wait_for_key()
            self._setup_configuration()
            return
        
        if not self.config.broker.ip:
            self.console.print_warning("Server IP not set. Running discovery...")
            self._discover_broker()
            if not self.config.broker.ip:
                return
        
        choice = self.console.show_provision_menu()
        
        if choice == "B":
            return
        
        self.console.print()
        self.console.print_info("Scanning for devices...")
        
        try:
            wifi_manager = get_wifi_manager()
            networks = wifi_manager.scan_shelly_networks()
            
            if not networks:
                self.console.print_warning("No devices found")
                self.console.wait_for_key()
                return
            
            self.console.print_success(f"Found {len(networks)} device(s)")
            
            items = []
            for n in networks:
                display_ssid = n.ssid
                if n.ssid.lower().startswith("shelly") and "-" in n.ssid:
                    parts = n.ssid.split("-")
                    if len(parts) >= 2:
                        dev_id = parts[-1]
                        display_ssid = f"Device - {dev_id}"
                
                items.append((display_ssid, f"{n.shelly_model} ({n.signal}dBm)"))
            
            if choice == "1":
                selected = self.console.prompt_selection(
                    items,
                    prompt="Select device to provision",
                    allow_all=False
                )
            else:
                selected = self.console.prompt_selection(
                    items,
                    prompt="Select devices (comma-separated) or [A]ll",
                    allow_all=True
                )
            
            if not selected:
                return
            
            selected_networks = [networks[i] for i in selected]
            self.console.print()
            self.console.print(f"[text]Will provision {len(selected_networks)} device(s)[/text]")
            
            if not self.console.prompt_confirm("Continue?", default=True):
                return
            
            self._original_wifi = wifi_manager.get_current_network()
            
            self.provisioner = create_provisioner()
            
            def on_step(step: str, status: str):
                self.console.print_step(step, status)
            
            def on_device_complete(device: ProvisionedDevice):
                if device.state == "completed":
                    self.console.print_success(f"Device provisioned: {device.assigned_name}")
                else:
                    self.console.print_error(f"Device failed: {device.error_message}")
            
            self.provisioner.on_step_update = on_step
            self.provisioner.on_device_complete = on_device_complete
            
            def progress_callback(current: int, total: int, network: WiFiNetwork):
                display_ssid = network.ssid
                if network.ssid.lower().startswith("shelly") and "-" in network.ssid:
                    parts = network.ssid.split("-")
                    if len(parts) >= 2:
                        dev_id = parts[-1]
                        display_ssid = f"Device - {dev_id}"
                
                self.console.print()
                self.console.print(
                    f"[primary][{current}/{total}][/primary] "
                    f"[text]Provisioning {display_ssid}[/text]"
                )
            
            results = self.provisioner.provision_batch(
                selected_networks,
                progress_callback=progress_callback
            )
            
            success_count = sum(1 for r in results if r.state == "completed")
            fail_count = len(results) - success_count
            
            summary_devices = [
                {
                    "mac": r.mac,
                    "name": r.assigned_name,
                    "ip": r.final_ip or "DHCP",
                    "status": "OK" if r.state == "completed" else "FAILED"
                }
                for r in results
            ]
            
            self.console.show_summary(success_count, fail_count, summary_devices)
            
            self.logger.info(f"Provisioning complete: {success_count} success, {fail_count} failed")
            
            if self._original_wifi:
                self.console.print()
                self.console.print_info(f"Original network: {self._original_wifi}")
                if self.console.prompt_confirm(f"Reconnect to {self._original_wifi}?"):
                    wifi_password = self.console.prompt_text(
                        f"Password for {self._original_wifi}",
                        password=False
                    )
                    if wifi_manager.connect(self._original_wifi, wifi_password):
                        self.console.print_success("Reconnected to original network")
                        
                        self.console.print()
                        self.console.print_info("Scanning for device IPs on local network...")
                        
                        from .discovery import resolve_hostname
                        import time
                        
                        for device in results:
                            if device.state == "completed":
                                self.console.print(f"  Looking for IP of {device.assigned_name}...")
                                found_ip = None
                                for i in range(5):
                                    found_ip = resolve_hostname(device.assigned_name, device.mac)
                                    if found_ip:
                                        break
                                    time.sleep(2)
                                
                                if found_ip:
                                    device.final_ip = found_ip
                                    self.console.print_success(f"Found IP: {found_ip}")
                                    self.logger.info(f"Resolved IP for {device.assigned_name}: {found_ip}")
                                else:
                                    self.console.print_warning(f"Could not resolve IP for {device.assigned_name}")
                        
                        self.console.print()
                        self.console.print_info("Updated Summary:")
                        
                        updated_summary = [
                            {
                                "mac": r.mac,
                                "name": r.assigned_name,
                                "ip": r.final_ip or "DHCP",
                                "status": "OK" if r.state == "completed" else "FAILED"
                            }
                            for r in results
                        ]
                        self.console.show_summary(success_count, fail_count, updated_summary)
                                
                    else:
                        self.console.print_error("Failed to reconnect")
            
        except NotImplementedError as e:
            self.console.print_error(str(e))
        except Exception as e:
            self.console.print_error(f"Provisioning failed: {str(e)}")
            self.logger.exception("Provisioning failed")
        
        self.console.wait_for_key()
    
    def _verify_connections(self) -> None:
        self.console.clear()
        self.console.show_banner()
        print_section("Verify Connections")
        
        self.console.print()
        
        if not self.config.broker.ip:
            self.console.print_warning("Server IP not configured")
            self.console.wait_for_key()
            return
        
        self.console.print_info(
            f"Checking server at {self.config.broker.address}:{self.config.broker.port}..."
        )
        
        if verify_broker(self.config.broker.address, self.config.broker.port):
            self.console.print_success("Server is accessible")
            
            self.console.print()
            self.console.print_info("Listening for MQTT announcements (30s timeout)...")
            
            verifier = MQTTVerifier(
                self.config.broker.ip,
                self.config.broker.port,
                self.config.broker.username,
                self.config.broker.password
            )
            
            found_devices = verifier.verify(timeout=30)
            
            if found_devices:
                found_devices.sort(key=lambda x: x.get("id", ""))
                
                self.console.print_success(f"Found {len(found_devices)} devices broadcasting on MQTT:")
                self.console.print()
                
                self.console.print("[bold]ID[/bold] | [bold]MAC[/bold] | [bold]IP[/bold] | [bold]Model[/bold]")
                self.console.print("[dim]" + "-" * 50 + "[/dim]")
                
                for device in found_devices:
                    dev_id = device.get("id", "Unknown")
                    mac = device.get("mac", "Unknown")
                    ip = device.get("ip", "Unknown")
                    model = device.get("model", "Unknown")
                    self.console.print(f"{dev_id:<20} | {mac:<12} | {ip:<15} | {model}")
            else:
                self.console.print_warning("No devices detected broadcasting on MQTT yet.")
                self.console.print("[dim]Note: Devices might take a moment to connect and announce.[/dim]")
        else:
            self.console.print_error("Server is not accessible")
        
        self.console.wait_for_key()


def main() -> int:
    app = RCCApp()
    return app.run()


if __name__ == "__main__":
    sys.exit(main())