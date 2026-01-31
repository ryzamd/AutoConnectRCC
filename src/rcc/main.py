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
from .ui import RCCConsole, print_banner, print_section, print_divider


# Configure logging (no credentials logged)
def setup_logging() -> logging.Logger:
    """Setup logging to file"""
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
    """
    Main RCC Application
    
    Handles the CLI interface and orchestrates all operations.
    """
    
    def __init__(self):
        self.console = RCCConsole()
        self.config = get_config()
        self.logger = setup_logging()
        self.provisioner = None
        self._original_wifi: Optional[str] = None
    
    def run(self) -> int:
        """
        Main application loop
        
        Returns:
            Exit code (0 for success)
        """
        try:
            # Show banner
            self.console.show_banner()
            
            # Check if configuration is needed
            if not self.config.is_ready():
                self._setup_configuration()
            
            # Main menu loop
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
            
            # Cleanup
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
        """Cleanup resources and clear credentials"""
        self.logger.info("Cleaning up...")
        
        # Clear credentials from memory
        self.config.clear_credentials()
        
        self.logger.info("Credentials cleared")
    
    # ═══════════════════════════════════════════════════════════════
    # Configuration Setup
    # ═══════════════════════════════════════════════════════════════
    
    def _setup_configuration(self) -> None:
        """Interactive configuration setup"""
        self.console.clear()
        self.console.show_banner()
        
        print_section("Initial Setup")
        self.console.print()
        self.console.print("[text]Please provide the following configuration:[/text]")
        self.console.print()
        
        # MQTT Broker Configuration
        self.console.print("[primary]MQTT Broker Configuration[/primary]")
        print_divider()
        
        # Hostname
        hostname = self.console.prompt_text(
            "Broker hostname",
            default=self.config.broker.hostname
        )
        self.config.broker.hostname = hostname
        
        # IP (optional - can auto-discover)
        ip = self.console.prompt_text(
            "Broker IP (or Enter to auto-discover)",
            default=""
        )
        if ip:
            self.config.broker.ip = ip
        
        # Port
        port = self.console.prompt_int(
            "Broker port",
            default=self.config.broker.port,
            min_val=1,
            max_val=65535
        )
        self.config.broker.port = port
        
        # Username
        username = self.console.prompt_text(
            "MQTT username for devices",
            default=""
        )
        self.config.broker.username = username
        
        # Password
        password = self.console.prompt_text(
            "MQTT password for devices",
            password=True
        )
        self.config.broker.password = password
        
        self.console.print()
        
        # WiFi Configuration
        self.console.print("[primary]Target WiFi Configuration[/primary]")
        print_divider()
        
        ssid = self.console.prompt_text(
            "WiFi SSID",
            default=""
        )
        self.config.wifi.ssid = ssid
        
        wifi_password = self.console.prompt_text(
            "WiFi Password",
            password=True
        )
        self.config.wifi.password = wifi_password
        
        self.console.print()
        
        # Device Naming
        self.console.print("[primary]Device Naming[/primary]")
        print_divider()
        
        prefix = self.console.prompt_text(
            "Device name prefix",
            default=self.config.naming.prefix
        )
        self.config.naming.prefix = prefix
        
        start_num = self.console.prompt_int(
            "Start number",
            default=self.config.naming.start_number,
            min_val=1
        )
        self.config.naming.start_number = start_num
        self.config.naming.reset()
        
        self.console.print()
        print_divider()
        self.console.print_success("Configuration stored in memory (session only)")
        self.console.print_success("Credentials will be cleared on exit")
        print_divider()
        
        # Log configuration (without credentials)
        self.logger.info(f"Broker: {self.config.broker.address}:{self.config.broker.port}")
        self.logger.info(f"MQTT User: {self.config.broker.username} (password: ****)")
        self.logger.info(f"Target WiFi: {self.config.wifi.ssid} (password: ****)")
        self.logger.info(f"Device prefix: {self.config.naming.prefix}")
        
        self.console.wait_for_key()
    
    # ═══════════════════════════════════════════════════════════════
    # Menu Actions
    # ═══════════════════════════════════════════════════════════════
    
    def _discover_broker(self) -> None:
        """Discover MQTT broker on network"""
        self.console.clear()
        self.console.show_banner()
        print_section("Discover MQTT Broker")
        
        self.console.print()
        self.console.print_info(f"Searching for broker: {self.config.broker.hostname}")
        
        # Try discovery
        broker = discover_broker(self.config.broker.hostname)
        
        if broker:
            self.console.print_success(f"Found broker at {broker.ip} via {broker.method}")
            self.config.broker.ip = broker.ip
            self.logger.info(f"Discovered broker: {broker.ip} ({broker.method})")
            
            # Verify connection
            if verify_broker(broker.ip, self.config.broker.port):
                self.console.print_success(f"Broker is accessible on port {self.config.broker.port}")
            else:
                self.console.print_warning(f"Broker found but port {self.config.broker.port} not responding")
        else:
            self.console.print_error("Could not auto-discover broker")
            
            # Prompt for manual IP
            ip = self.console.prompt_text(
                "Enter broker IP manually",
                default=self.config.broker.ip or ""
            )
            
            if ip:
                if verify_broker(ip, self.config.broker.port):
                    self.config.broker.ip = ip
                    self.console.print_success(f"Broker verified at {ip}")
                    self.logger.info(f"Manual broker: {ip}")
                else:
                    self.console.print_error(f"Cannot connect to {ip}:{self.config.broker.port}")
        
        self.console.wait_for_key()
    
    def _scan_devices(self) -> None:
        """Scan for Shelly devices"""
        self.console.clear()
        self.console.show_banner()
        print_section("Scan Shelly Devices")
        
        self.console.print()
        self.console.print_info("Scanning for Shelly WiFi networks...")
        
        try:
            wifi_manager = get_wifi_manager()
            networks = wifi_manager.scan_shelly_networks()
            
            if networks:
                self.console.print_success(f"Found {len(networks)} Shelly device(s)")
                self.logger.info(f"Found {len(networks)} Shelly devices")
                
                # Display as table
                devices = [
                    {
                        "ssid": n.ssid,
                        "signal": n.signal,
                        "model": n.shelly_model
                    }
                    for n in networks
                ]
                self.console.show_device_table(devices)
            else:
                self.console.print_warning("No Shelly devices found")
                self.console.print()
                self.console.print("[dim]Make sure:[/dim]")
                self.console.print("[dim]  • Shelly devices are powered on[/dim]")
                self.console.print("[dim]  • Devices are in AP mode (unconfigured)[/dim]")
                self.console.print("[dim]  • You are within WiFi range[/dim]")
                
        except NotImplementedError as e:
            self.console.print_error(str(e))
        except Exception as e:
            self.console.print_error(f"Scan failed: {str(e)}")
            self.logger.exception("Scan failed")
        
        self.console.wait_for_key()
    
    def _provision_devices(self) -> None:
        """Provision Shelly devices"""
        self.console.clear()
        self.console.show_banner()
        
        # Check configuration
        if not self.config.is_ready():
            self.console.print_error("Configuration incomplete. Please set up first.")
            self.console.wait_for_key()
            self._setup_configuration()
            return
        
        # Check broker
        if not self.config.broker.ip:
            self.console.print_warning("Broker IP not set. Running discovery...")
            self._discover_broker()
            if not self.config.broker.ip:
                return
        
        # Show provision menu
        choice = self.console.show_provision_menu()
        
        if choice == "B":
            return
        
        # Scan for devices
        self.console.print()
        self.console.print_info("Scanning for Shelly devices...")
        
        try:
            wifi_manager = get_wifi_manager()
            networks = wifi_manager.scan_shelly_networks()
            
            if not networks:
                self.console.print_warning("No Shelly devices found")
                self.console.wait_for_key()
                return
            
            self.console.print_success(f"Found {len(networks)} device(s)")
            
            # Select devices
            items = [
                (n.ssid, f"{n.shelly_model} ({n.signal}dBm)")
                for n in networks
            ]
            
            if choice == "1":
                # Single device
                selected = self.console.prompt_selection(
                    items,
                    prompt="Select device to provision",
                    allow_all=False
                )
            else:
                # Batch
                selected = self.console.prompt_selection(
                    items,
                    prompt="Select devices (comma-separated) or [A]ll",
                    allow_all=True
                )
            
            if not selected:
                return
            
            # Confirm
            selected_networks = [networks[i] for i in selected]
            self.console.print()
            self.console.print(f"[text]Will provision {len(selected_networks)} device(s)[/text]")
            
            if not self.console.prompt_confirm("Continue?", default=True):
                return
            
            # Save original WiFi
            self._original_wifi = wifi_manager.get_current_network()
            
            # Initialize provisioner
            self.provisioner = create_provisioner()
            
            # Set up progress callbacks
            def on_step(step: str, status: str):
                self.console.print_step(step, status)
            
            def on_device_complete(device: ProvisionedDevice):
                if device.state == "completed":
                    self.console.print_success(f"Device provisioned: {device.assigned_name}")
                else:
                    self.console.print_error(f"Device failed: {device.error_message}")
            
            self.provisioner.on_step_update = on_step
            self.provisioner.on_device_complete = on_device_complete
            
            # Run provisioning
            def progress_callback(current: int, total: int, network: WiFiNetwork):
                self.console.print()
                self.console.print(
                    f"[primary][{current}/{total}][/primary] "
                    f"[text]Provisioning {network.ssid}[/text]"
                )
            
            results = self.provisioner.provision_batch(
                selected_networks,
                progress_callback=progress_callback
            )
            
            # Show summary
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
            
            # Log results
            self.logger.info(f"Provisioning complete: {success_count} success, {fail_count} failed")
            
            # Prompt to reconnect to original WiFi
            if self._original_wifi:
                self.console.print()
                self.console.print_info(f"Original network: {self._original_wifi}")
                if self.console.prompt_confirm(f"Reconnect to {self._original_wifi}?"):
                    wifi_password = self.console.prompt_text(
                        f"Password for {self._original_wifi}",
                        password=True
                    )
                    if wifi_manager.connect(self._original_wifi, wifi_password):
                        self.console.print_success("Reconnected to original network")
                    else:
                        self.console.print_error("Failed to reconnect")
            
        except NotImplementedError as e:
            self.console.print_error(str(e))
        except Exception as e:
            self.console.print_error(f"Provisioning failed: {str(e)}")
            self.logger.exception("Provisioning failed")
        
        self.console.wait_for_key()
    
    def _verify_connections(self) -> None:
        """Verify device connections"""
        self.console.clear()
        self.console.show_banner()
        print_section("Verify Connections")
        
        self.console.print()
        
        # Check broker
        if not self.config.broker.ip:
            self.console.print_warning("Broker IP not configured")
            self.console.wait_for_key()
            return
        
        self.console.print_info(
            f"Checking broker at {self.config.broker.address}:{self.config.broker.port}..."
        )
        
        if verify_broker(self.config.broker.address, self.config.broker.port):
            self.console.print_success("Broker is accessible")
            
            # TODO: Add MQTT connection to verify device subscriptions
            self.console.print()
            self.console.print("[dim]Note: Full device verification requires MQTT subscription[/dim]")
            self.console.print("[dim]Devices should appear in broker within 30 seconds of provisioning[/dim]")
        else:
            self.console.print_error("Broker is not accessible")
        
        self.console.wait_for_key()


def main() -> int:
    """Main entry point"""
    app = RCCApp()
    return app.run()


if __name__ == "__main__":
    sys.exit(main())
