import socket
import subprocess
import platform
import re
import time
from typing import Optional, List, Tuple
from dataclasses import dataclass

from .ui import get_console


@dataclass
class DiscoveredBroker:
    """Discovered MQTT broker information"""
    ip: str
    hostname: Optional[str] = None
    port: int = 1883
    method: str = "unknown"  # How it was discovered


class BrokerDiscovery:
    """
    Discover MQTT broker on the network
    
    Uses multiple methods with fallback:
    1. mDNS (hostname.local) resolution
    2. Network scanning with hostname detection
    3. Manual IP input
    """
    
    def __init__(self):
        self.console = get_console()
        self._system = platform.system().lower()
    
    def discover(self, hostname: str = "raspi-RCC") -> Optional[DiscoveredBroker]:
        """
        Attempt to discover broker using all available methods
        
        Args:
            hostname: Expected hostname of the Raspberry Pi
        
        Returns:
            DiscoveredBroker if found, None otherwise
        """
        # Method 1: Try mDNS resolution
        result = self._try_mdns(hostname)
        if result:
            return result
        
        # Method 2: Try zeroconf service discovery
        result = self._try_zeroconf()
        if result:
            return result
        
        # Method 3: Try network scan
        result = self._try_network_scan(hostname)
        if result:
            return result
        
        return None
    
    def _try_mdns(self, hostname: str) -> Optional[DiscoveredBroker]:
        """Try to resolve hostname via mDNS (.local domain)"""
        mdns_name = f"{hostname}.local"
        
        try:
            ip = socket.gethostbyname(mdns_name)
            return DiscoveredBroker(
                ip=ip,
                hostname=hostname,
                method="mDNS"
            )
        except socket.gaierror:
            return None
        except Exception:
            return None
    
    def _try_zeroconf(self) -> Optional[DiscoveredBroker]:
        """Try to discover broker using Zeroconf/Bonjour"""
        try:
            from zeroconf import Zeroconf, ServiceBrowser, ServiceListener
            import threading
            
            class MQTTListener(ServiceListener):
                def __init__(self):
                    self.brokers: List[DiscoveredBroker] = []
                    self.event = threading.Event()
                
                def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
                    info = zc.get_service_info(type_, name)
                    if info:
                        addresses = info.parsed_addresses()
                        if addresses:
                            self.brokers.append(DiscoveredBroker(
                                ip=addresses[0],
                                hostname=info.server,
                                port=info.port,
                                method="Zeroconf"
                            ))
                            self.event.set()
                
                def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
                    pass
                
                def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
                    pass
            
            zc = Zeroconf()
            listener = MQTTListener()
            
            # Search for MQTT service
            browser = ServiceBrowser(zc, "_mqtt._tcp.local.", listener)
            
            # Wait up to 5 seconds for discovery
            listener.event.wait(timeout=5.0)
            
            zc.close()
            
            if listener.brokers:
                return listener.brokers[0]
            
        except ImportError:
            # Zeroconf not installed
            pass
        except Exception:
            pass
        
        return None
    
    def _try_network_scan(self, hostname: str) -> Optional[DiscoveredBroker]:
        """Scan local network for the broker"""
        # Get local IP to determine network range
        local_ip = self._get_local_ip()
        if not local_ip:
            return None
        
        # Extract network prefix (e.g., "192.168.1")
        network_prefix = ".".join(local_ip.split(".")[:-1])
        
        # Try ARP table first (faster)
        result = self._scan_arp_table(hostname)
        if result:
            return result
        
        # Try ping scan with hostname check
        result = self._scan_network(network_prefix, hostname)
        return result
    
    def _get_local_ip(self) -> Optional[str]:
        """Get local IP address"""
        try:
            # Create a socket to determine local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))  # Doesn't actually connect
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return None
    
    def _scan_arp_table(self, hostname: str) -> Optional[DiscoveredBroker]:
        """Check ARP table for the device"""
        try:
            if self._system == "windows":
                result = subprocess.run(
                    ["arp", "-a"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
            else:
                result = subprocess.run(
                    ["arp", "-a"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
            
            # Parse ARP output and look for Raspberry Pi MAC addresses
            # Raspberry Pi MACs start with: b8:27:eb, dc:a6:32, e4:5f:01
            pi_mac_prefixes = ["b8:27:eb", "dc:a6:32", "e4:5f:01", "28:cd:c1"]
            
            for line in result.stdout.lower().split("\n"):
                for prefix in pi_mac_prefixes:
                    if prefix in line:
                        # Extract IP from line
                        ip_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', line)
                        if ip_match:
                            ip = ip_match.group(1)
                            # Verify this is our broker by checking hostname
                            if self._verify_hostname(ip, hostname):
                                return DiscoveredBroker(
                                    ip=ip,
                                    hostname=hostname,
                                    method="ARP scan"
                                )
        except Exception:
            pass
        
        return None
    
    def _scan_network(self, network_prefix: str, hostname: str) -> Optional[DiscoveredBroker]:
        """Scan network range for the broker"""
        # Quick ping scan of common addresses
        common_ips = [1, 2, 50, 100, 111, 150, 200, 254]
        
        for last_octet in common_ips:
            ip = f"{network_prefix}.{last_octet}"
            if self._is_host_alive(ip):
                if self._verify_hostname(ip, hostname):
                    return DiscoveredBroker(
                        ip=ip,
                        hostname=hostname,
                        method="Network scan"
                    )
        
        return None
    
    def _is_host_alive(self, ip: str) -> bool:
        """Check if host responds to ping"""
        try:
            if self._system == "windows":
                cmd = ["ping", "-n", "1", "-w", "500", ip]
            else:
                cmd = ["ping", "-c", "1", "-W", "1", ip]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=2
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def _verify_hostname(self, ip: str, expected_hostname: str) -> bool:
        """Verify the hostname of a discovered IP"""
        try:
            # Try reverse DNS lookup
            hostname, _, _ = socket.gethostbyaddr(ip)
            return expected_hostname.lower() in hostname.lower()
        except Exception:
            # If reverse lookup fails, try connecting to check if it's a Mosquitto broker
            return self._check_mqtt_port(ip)
    
    def _check_mqtt_port(self, ip: str, port: int = 1883) -> bool:
        """Check if MQTT port is open"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((ip, port))
            sock.close()
            return result == 0
        except Exception:
            return False
    
    def verify_broker_connection(self, ip: str, port: int = 1883) -> bool:
        """Verify broker is accessible"""
        return self._check_mqtt_port(ip, port)


def discover_broker(hostname: str = "raspi-RCC") -> Optional[DiscoveredBroker]:
    """
    Convenience function to discover MQTT broker
    
    Args:
        hostname: Expected hostname of the Raspberry Pi
    
    Returns:
        DiscoveredBroker if found, None otherwise
    """
    discovery = BrokerDiscovery()
    return discovery.discover(hostname)


def verify_broker(ip: str, port: int = 1883) -> bool:
    """
    Verify broker is accessible
    
    Args:
        ip: Broker IP address
        port: MQTT port (default 1883)
    
    Returns:
        True if broker is accessible
    """
    discovery = BrokerDiscovery()
    return discovery.verify_broker_connection(ip, port)
