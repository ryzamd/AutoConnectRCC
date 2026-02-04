import socket
import subprocess
import platform
import re
import time
import concurrent.futures
from typing import Optional, List, Tuple
from dataclasses import dataclass

from .ui import get_console

try:
    from zeroconf import Zeroconf, ServiceBrowser, ServiceListener
except ImportError:
    pass


@dataclass
class DiscoveredBroker:
    ip: str
    hostname: Optional[str] = None
    port: int = 1883
    method: str = "unknown"


class BrokerDiscovery:
    def __init__(self):
        self.console = get_console()
        self._system = platform.system().lower()
    
    def discover(self, hostname: str = "RCCServer") -> Optional[DiscoveredBroker]:
        result = self._try_ping_discovery(hostname)
        if result:
            return result
        
        result = self._try_mdns(hostname)
        if result:
            return result
        
        result = self._try_zeroconf()
        if result:
            return result
        
        result = self._try_network_scan(hostname)
        if result:
            return result
        
        return None
    
    def _try_ping_discovery(self, hostname: str) -> Optional[DiscoveredBroker]:
       
        mdns_name = f"{hostname}.local"
        
        try:
            if self._system == "windows":
                cmd = ["ping", "-n", "1", "-4", mdns_name]
            else:
                cmd = ["ping", "-c", "1", mdns_name]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                output = result.stdout
                
                ip_pattern = r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
                matches = re.findall(ip_pattern, output)
                
                if matches:
                    ip = matches[0]
                    
                    if not ip.startswith('127.') and not ip.startswith('0.'):
                        return DiscoveredBroker(
                            ip=ip,
                            hostname=hostname,
                            method="ping"
                        )
        except subprocess.TimeoutExpired:
            pass
        except Exception:
            pass
        
        return None
    
    def _try_mdns(self, hostname: str) -> Optional[DiscoveredBroker]:
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
        try:
            if 'Zeroconf' not in globals():
                return None
            
            import threading
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
        local_ip = self._get_local_ip()
        if not local_ip:
            return None
        
        network_prefix = ".".join(local_ip.split(".")[:-1])
        
        result = self._scan_arp_table(hostname)
        if result:
            return result
        
        result = self._scan_network(network_prefix, hostname)
        return result
    
    def _get_local_ip(self) -> Optional[str]:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return None
    
    def _scan_arp_table(self, hostname: str, mac_address: Optional[str] = None) -> Optional[DiscoveredBroker]:
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
            
            target_mac = None
            if mac_address:
                target_mac = mac_address.lower().replace(":", "").replace("-", "")
            
            pi_mac_prefixes = ["b8:27:eb", "dc:a6:32", "e4:5f:01", "28:cd:c1"]
            
            for line in result.stdout.lower().split("\n"):
                clean_line = line.replace("-", ":")
                
                if target_mac:
                    line_hex = re.sub(r'[^a-f0-9]', '', line)
                    if target_mac in line_hex:
                        ip_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', line)
                        if ip_match:
                            return DiscoveredBroker(
                                ip=ip_match.group(1),
                                hostname=hostname,
                                method="ARP MAC match"
                            )
                
                elif any(prefix in clean_line for prefix in pi_mac_prefixes):
                    ip_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', line)
                    if ip_match:
                        ip = ip_match.group(1)
                        if self._verify_hostname(ip, hostname):
                            return DiscoveredBroker(
                                ip=ip,
                                hostname=hostname,
                                method="ARP scan"
                            )
        except Exception:
            pass
        
        return None
    
    def _ping_host(self, ip: str) -> None:
        try:
            if self._system == "windows":
                cmd = ["ping", "-n", "1", "-w", "200", ip]
            else:
                cmd = ["ping", "-c", "1", "-W", "1", ip]
                
            subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=1
            )
        except Exception:
            pass

    def _populate_arp_table(self, timeout: float = 2.0) -> None:
        local_ip = self._get_local_ip()
        if not local_ip:
            return

        network_prefix = ".".join(local_ip.split(".")[:-1])
        
        ips = [f"{network_prefix}.{i}" for i in range(1, 255)]
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            executor.map(self._ping_host, ips)

    def verify_broker_connection(self, ip: str, port: int = 1883) -> bool:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2.0)
            s.connect((ip, port))
            s.close()
            return True
        except Exception:
            return False
    
    def _verify_hostname(self, ip: str, hostname: str) -> bool:
        return self.verify_broker_connection(ip)

    def _scan_network(self, network_prefix: str, hostname: str) -> Optional[DiscoveredBroker]:
        found_broker = None
        
        def check_host(ip):
            nonlocal found_broker
            if found_broker:
                return
            
            try:
                if self._system == "windows":
                    cmd = ["ping", "-n", "1", "-w", "200", ip]
                else:
                    cmd = ["ping", "-c", "1", "-W", "1", ip]
                    
                result = subprocess.run(
                    cmd, 
                    stdout=subprocess.DEVNULL, 
                    stderr=subprocess.DEVNULL,
                    timeout=1
                )
                
                if result.returncode == 0:
                    if self._verify_hostname(ip, hostname):
                        found_broker = DiscoveredBroker(
                            ip=ip,
                            hostname=hostname,
                            method="Deep Network Scan"
                        )
            except Exception:
                pass

        ips = [f"{network_prefix}.{i}" for i in range(1, 255)]
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            list(executor.map(check_host, ips))
            
        return found_broker


def resolve_hostname(hostname: str, mac_address: Optional[str] = None) -> Optional[str]:
    discovery = BrokerDiscovery()
    if mac_address:
        res = discovery._scan_arp_table(hostname, mac_address)
        if res:
            return res.ip
        
        discovery._populate_arp_table()
        
        res = discovery._scan_arp_table(hostname, mac_address)
        if res:
            return res.ip
    
    res = discovery._try_ping_discovery(hostname)
    if res:
        return res.ip
        
    res = discovery._try_mdns(hostname)
    if res:
        return res.ip
        
    if not mac_address:
        res = discovery._scan_arp_table(hostname)
        if res:
            return res.ip
    return None


def discover_broker(hostname: str = "RCCServer") -> Optional[DiscoveredBroker]:
    discovery = BrokerDiscovery()
    return discovery.discover(hostname)


def verify_broker(ip: str, port: int = 1883) -> bool:
    discovery = BrokerDiscovery()
    return discovery.verify_broker_connection(ip, port)