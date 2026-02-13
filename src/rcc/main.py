#!/usr/bin/env python3

import sys
import os
import logging
from datetime import datetime
from typing import Optional, List
from .config import get_config, SecureConfig
from .discovery import discover_broker, verify_broker, DiscoveredBroker
from .wifi_manager import get_wifi_manager, WiFiNetwork
from .shelly_api import check_shelly_ap_mode, ShellyAPI
from .provisioner import create_provisioner, ProvisionedDevice
from .ui import RCCConsole, print_banner, print_section, print_divider


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
                    self._reset_devices()
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
        self.console.print("[primary]Target WiFi Configuration[/primary]")
        print_divider()
        
        ssid = self.console.prompt_text(
            "  WiFi Name",
            default=""
        )
        self.config.wifi.ssid = ssid
        
        wifi_password = self.console.prompt_text(
            "  WiFi Password",
            password=False
        )
        self.config.wifi.password = wifi_password
        
        self.console.print()
        
        port = self.console.prompt_int(
            "  Server port",
            default=self.config.broker.port,
            min_val=1,
            max_val=65535
        )
        self.config.broker.port = port
        
        self.console.print()
        
        self.console.print_info(f"Connecting to {ssid}...")
        try:
            wifi_manager = get_wifi_manager()
            if wifi_manager.connect(ssid, wifi_password):
                self.console.print_success(f"Connected to {ssid}")
            else:
                self.console.print_error(f"Failed to connect to {ssid}")
                if not self.console.prompt_confirm("Continue anyway?", default=False):
                    return
        except Exception as e:
            self.console.print_error(f"Connection error: {str(e)}")
            if not self.console.prompt_confirm("Continue anyway?", default=False):
                return
        
        self.console.print()
        
        self.console.print_info(f"Auto-discovering server...")
        
        broker = discover_broker("RCCServer")
        
        if broker:
            self.console.print_success(f"Found server at {broker.ip}")
            self.config.broker.ip = broker.ip
            self.logger.info(f"Auto-discovered server: {broker.ip}")
        else:
            self.console.print_warning("Could not auto-discover server")
            self.console.print("[dim]Note: Discovery will retry when needed[/dim]")
        
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
            self.console.print_success(f"Found server at {broker.ip}")
            self.config.broker.ip = broker.ip
            self.logger.info(f"Discovered Server: {broker.ip}")
            
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
        
        self.console.clear()
        self.console.show_banner()
        print_section("Provision Devices")
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
            
            self.logger.info(f"Provisioning complete: {success_count} success, {fail_count} failed")
            
            #self.console.clear()
            #self.console.show_banner()
            print_section("Provisioning Complete")
            
            if self._original_wifi:
                self.console.print()
                self.console.print_info(f"Reconnecting to {self._original_wifi}...")
                
                wifi_password = self.config.wifi.password
                if wifi_manager.connect(self._original_wifi, wifi_password):
                    self.console.print_success("Reconnected to original network")
                    
                    from .discovery import resolve_hostname
                    import time
                    
                    for device in results:
                        if device.state == "completed":
                            found_ip = None
                            for i in range(5):
                                found_ip = resolve_hostname(device.assigned_name, device.mac)
                                if found_ip:
                                    break
                                time.sleep(2)
                            
                            if found_ip:
                                device.final_ip = found_ip
                                self.logger.info(f"Resolved IP for {device.assigned_name}: {found_ip}")
                else:
                    self.console.print_error("Failed to reconnect to original network")
            
            self.console.print()
            updated_summary = []
            for r in results:
                ip_addr = r.final_ip or "DHCP"
                formatted_ip = ip_addr
                if ip_addr and ip_addr != "DHCP" and ip_addr.count('.') == 3:
                    parts = ip_addr.split('.')
                    formatted_ip = f"***.***.{parts[2]}.{parts[3]}"
                
                updated_summary.append({
                    "mac": r.mac,
                    "name": r.assigned_name,
                    "ip": formatted_ip,
                    "status": "OK" if r.state == "completed" else "FAILED"
                })
            
            self.console.show_summary(success_count, fail_count, updated_summary, ip_col_name="Address")
            
        except NotImplementedError as e:
            self.console.print_error(str(e))
        except Exception as e:
            self.console.print_error(f"Provisioning failed: {str(e)}")
            self.logger.exception("Provisioning failed")
        
        self.console.wait_for_key()
    
    def _reset_devices(self) -> None:
        choice = self.console.show_reset_menu()
        
        if choice == "B":
            return
        
        self.console.clear()
        self.console.show_banner()
        print_section("Reset Device")
        self.console.print()
        self.console.print_info("Scanning for online devices...")
        
        try:
            from .mqtt_client import MQTTVerifier
            
            if not self.config.broker.ip:
                self.console.print_warning("Server IP not configured")
                self.console.wait_for_key()
                return
            
            verifier = MQTTVerifier(
                self.config.broker.ip,
                self.config.broker.port,
                self.config.broker.username,
                self.config.broker.password
            )
            
            found_devices = verifier.verify(timeout=10)
            
            if not found_devices:
                self.console.print_warning("No online devices found")
                self.console.print("[dim]Note: Devices might take a moment to connect and announce.[/dim]")
                self.console.wait_for_key()
                return
            
            found_devices = [d for d in found_devices if d.get("id", "").startswith("RCC-Device")]
            
            if not found_devices:
                self.console.print_warning("No RCC provisioned devices found")
                self.console.print("[dim]Only devices with 'RCC-Device' prefix are shown.[/dim]")
                self.console.wait_for_key()
                return
            
            found_devices.sort(key=lambda x: x.get("id", ""))
            self.console.print_success(f"Found {len(found_devices)} RCC device(s)")
            
            items = []
            for device in found_devices:
                dev_id = device.get("id", "Unknown")
                items.append((dev_id, ""))
            
            if choice == "1":
                selected = self.console.prompt_selection(
                    items,
                    prompt="Select device to reset",
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
            
            selected_devices = [found_devices[i] for i in selected]
            
            self.console.print()
            if len(selected_devices) == 1:
                warning_msg = "This action will reset the device you selected and disconnect it from the Server. You will need to provision it again."
            else:
                warning_msg = f"This action will reset {len(selected_devices)} devices and disconnect them from the Server. You will need to provision them again."
            
            self.console.print_warning(warning_msg)
            
            if not self.console.prompt_confirm("Are you sure?", default=False):
                self.console.print_info("Reset cancelled")
                self.console.wait_for_key()
                return
            
            self.console.print()
            success_count = 0
            fail_count = 0
            
            for device in selected_devices:
                dev_id = device.get("id", "Unknown")
                ip = device.get("ip", None)
                
                if not ip:
                    self.console.print_error(f"{dev_id}: No IP address")
                    fail_count += 1
                    continue
                
                self.console.print_info(f"Resetting {dev_id}...")
                
                try:
                    api = ShellyAPI(ip, timeout=10.0)
                    api.factory_reset()
                    self.console.print_success(f"{dev_id}: Reset command sent")
                    success_count += 1
                except Exception as e:
                    if "Connection" in str(e) or "Timeout" in str(e):
                        self.console.print_success(f"{dev_id}: Reset command sent (device disconnected)")
                        success_count += 1
                    else:
                        self.console.print_error(f"{dev_id}: Failed - {str(e)}")
                        fail_count += 1
            
            self.console.print()
            if success_count > 0:
                self.console.print_success(f"Reset success devices: {success_count}")
            if fail_count > 0:
                self.console.print_error(f"Reset failed devices: {fail_count}")
            
        except Exception as e:
            self.console.print_error(f"Reset failed: {str(e)}")
            self.logger.exception("Reset failed")
        
        self.console.wait_for_key()


def main() -> int:
    app = RCCApp()
    return app.run()


if __name__ == "__main__":
    sys.exit(main())