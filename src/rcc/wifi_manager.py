import subprocess
import platform
import time
import re
from typing import List, Optional, Tuple
from dataclasses import dataclass
from abc import ABC, abstractmethod

from .ui import get_console


@dataclass
class WiFiNetwork:
    """Represents a WiFi network"""
    ssid: str
    signal: int  # Signal strength in dBm or percentage
    security: str = "Open"
    bssid: Optional[str] = None
    
    @property
    def is_shelly(self) -> bool:
        """Check if this is a Shelly AP"""
        return self.ssid.lower().startswith("shelly")
    
    @property
    def shelly_model(self) -> str:
        """Extract Shelly model from SSID"""
        if not self.is_shelly:
            return "Unknown"
        
        # Parse model from SSID like "ShellyPlus1-A8032ABE54DC"
        ssid_lower = self.ssid.lower()
        
        if "plus1pm" in ssid_lower:
            return "Plus 1PM"
        elif "plus1" in ssid_lower:
            return "Plus 1"
        elif "plus2pm" in ssid_lower:
            return "Plus 2PM"
        elif "pro4pm" in ssid_lower:
            return "Pro 4PM"
        elif "pro2pm" in ssid_lower:
            return "Pro 2PM"
        elif "pro1pm" in ssid_lower:
            return "Pro 1PM"
        elif "pro1" in ssid_lower:
            return "Pro 1"
        elif "plugs" in ssid_lower:
            return "Plug S"
        elif "mini1" in ssid_lower:
            return "Mini 1"
        else:
            return "Unknown Model"
    
    @property
    def mac_address(self) -> Optional[str]:
        """Extract MAC address from Shelly SSID"""
        if not self.is_shelly:
            return None
        
        # MAC is usually the last part after the hyphen
        parts = self.ssid.split("-")
        if len(parts) >= 2:
            mac = parts[-1].upper()
            # Validate it looks like a MAC (12 hex chars)
            if len(mac) == 12 and all(c in "0123456789ABCDEF" for c in mac):
                return mac
        return None


class WiFiManagerBase(ABC):
    """Abstract base class for WiFi management"""
    
    def __init__(self):
        self.console = get_console()
        self._original_network: Optional[str] = None
    
    @abstractmethod
    def get_current_network(self) -> Optional[str]:
        """Get currently connected WiFi SSID"""
        pass
    
    @abstractmethod
    def scan_networks(self) -> List[WiFiNetwork]:
        """Scan for available WiFi networks"""
        pass
    
    @abstractmethod
    def connect(self, ssid: str, password: str = "", timeout: int = 30) -> bool:
        """Connect to a WiFi network"""
        pass
    
    @abstractmethod
    def disconnect(self) -> bool:
        """Disconnect from current WiFi network"""
        pass
    
    def save_original_network(self) -> None:
        """Save current network to reconnect later"""
        self._original_network = self.get_current_network()
    
    def restore_original_network(self, password: str = "") -> bool:
        """Reconnect to the original network"""
        if self._original_network:
            return self.connect(self._original_network, password)
        return False
    
    def scan_shelly_networks(self) -> List[WiFiNetwork]:
        """Scan and filter only Shelly AP networks"""
        all_networks = self.scan_networks()
        shelly_networks = [n for n in all_networks if n.is_shelly]
        # Sort by signal strength (strongest first)
        shelly_networks.sort(key=lambda n: n.signal, reverse=True)
        return shelly_networks
    
    def connect_to_shelly(self, ssid: str, timeout: int = 30) -> bool:
        """Connect to Shelly AP (no password required)"""
        return self.connect(ssid, password="", timeout=timeout)


class WindowsWiFiManager(WiFiManagerBase):
    """WiFi manager for Windows using netsh"""
    
    def get_current_network(self) -> Optional[str]:
        try:
            result = subprocess.run(
                ["netsh", "wlan", "show", "interfaces"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            for line in result.stdout.split("\n"):
                if "SSID" in line and "BSSID" not in line:
                    # Extract SSID value
                    parts = line.split(":", 1)
                    if len(parts) == 2:
                        ssid = parts[1].strip()
                        if ssid:
                            return ssid
            return None
        except Exception:
            return None
    
    def scan_networks(self) -> List[WiFiNetwork]:
        networks = []
        
        try:
            result = subprocess.run(
                ["netsh", "wlan", "show", "networks", "mode=bssid"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            current_network: dict = {}
            
            for line in result.stdout.split("\n"):
                line = line.strip()
                
                if line.startswith("SSID") and "BSSID" not in line:
                    # Save previous network if exists
                    if current_network.get("ssid"):
                        networks.append(WiFiNetwork(**current_network))
                    
                    # Start new network
                    parts = line.split(":", 1)
                    ssid = parts[1].strip() if len(parts) > 1 else ""
                    current_network = {"ssid": ssid, "signal": 0, "security": "Open"}
                
                elif "Signal" in line:
                    parts = line.split(":", 1)
                    if len(parts) > 1:
                        signal_str = parts[1].strip().replace("%", "")
                        try:
                            # Convert percentage to approximate dBm
                            signal_pct = int(signal_str)
                            # Rough conversion: -30dBm = 100%, -90dBm = 0%
                            current_network["signal"] = int(-30 - (100 - signal_pct) * 0.6)
                        except ValueError:
                            current_network["signal"] = 0
                
                elif "Authentication" in line:
                    parts = line.split(":", 1)
                    if len(parts) > 1:
                        current_network["security"] = parts[1].strip()
                
                elif "BSSID" in line:
                    parts = line.split(":", 1)
                    if len(parts) > 1:
                        current_network["bssid"] = parts[1].strip()
            
            # Don't forget the last network
            if current_network.get("ssid"):
                networks.append(WiFiNetwork(**current_network))
            
        except Exception:
            pass
        
        return networks
    
    def connect(self, ssid: str, password: str = "", timeout: int = 30) -> bool:
        try:
            # First, try to connect using existing profile
            result = subprocess.run(
                ["netsh", "wlan", "connect", f"name={ssid}"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0 or "is not found" in result.stdout:
                # Need to create a profile first
                if not self._create_profile(ssid, password):
                    return False
                
                # Try connecting again
                result = subprocess.run(
                    ["netsh", "wlan", "connect", f"name={ssid}"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
            
            if result.returncode != 0:
                return False
            
            # Wait for connection
            return self._wait_for_connection(ssid, timeout)
            
        except Exception:
            return False
    
    def _create_profile(self, ssid: str, password: str = "") -> bool:
        """Create a WiFi profile for connection"""
        # Create XML profile
        if password:
            # WPA2 profile
            profile_xml = f'''<?xml version="1.0"?>
<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
    <name>{ssid}</name>
    <SSIDConfig>
        <SSID>
            <name>{ssid}</name>
        </SSID>
    </SSIDConfig>
    <connectionType>ESS</connectionType>
    <connectionMode>auto</connectionMode>
    <MSM>
        <security>
            <authEncryption>
                <authentication>WPA2PSK</authentication>
                <encryption>AES</encryption>
                <useOneX>false</useOneX>
            </authEncryption>
            <sharedKey>
                <keyType>passPhrase</keyType>
                <protected>false</protected>
                <keyMaterial>{password}</keyMaterial>
            </sharedKey>
        </security>
    </MSM>
</WLANProfile>'''
        else:
            # Open network profile
            profile_xml = f'''<?xml version="1.0"?>
<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
    <name>{ssid}</name>
    <SSIDConfig>
        <SSID>
            <name>{ssid}</name>
        </SSID>
    </SSIDConfig>
    <connectionType>ESS</connectionType>
    <connectionMode>auto</connectionMode>
    <MSM>
        <security>
            <authEncryption>
                <authentication>open</authentication>
                <encryption>none</encryption>
                <useOneX>false</useOneX>
            </authEncryption>
        </security>
    </MSM>
</WLANProfile>'''
        
        try:
            # Save profile to temp file
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
                f.write(profile_xml)
                profile_path = f.name
            
            # Add profile
            result = subprocess.run(
                ["netsh", "wlan", "add", "profile", f"filename={profile_path}"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            # Clean up temp file
            import os
            os.unlink(profile_path)
            
            return result.returncode == 0
            
        except Exception:
            return False
    
    def _wait_for_connection(self, ssid: str, timeout: int) -> bool:
        """Wait for WiFi connection to establish"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            current = self.get_current_network()
            if current and current.lower() == ssid.lower():
                # Give it a moment to fully establish
                time.sleep(2)
                return True
            time.sleep(1)
        
        return False
    
    def disconnect(self) -> bool:
        try:
            result = subprocess.run(
                ["netsh", "wlan", "disconnect"],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except Exception:
            return False


class MacOSWiFiManager(WiFiManagerBase):
    """WiFi manager for macOS using networksetup and airport"""
    
    def __init__(self):
        super().__init__()
        self._interface = self._get_wifi_interface()
    
    def _get_wifi_interface(self) -> str:
        """Get the WiFi interface name (usually en0 or en1)"""
        try:
            result = subprocess.run(
                ["networksetup", "-listallhardwareports"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            lines = result.stdout.split("\n")
            for i, line in enumerate(lines):
                if "Wi-Fi" in line or "AirPort" in line:
                    # Next line contains the device
                    if i + 1 < len(lines):
                        device_line = lines[i + 1]
                        if "Device:" in device_line:
                            return device_line.split(":")[1].strip()
            
            return "en0"  # Default fallback
        except Exception:
            return "en0"
    
    def get_current_network(self) -> Optional[str]:
        try:
            result = subprocess.run(
                ["networksetup", "-getairportnetwork", self._interface],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            output = result.stdout.strip()
            if "Current Wi-Fi Network:" in output:
                return output.split(":")[1].strip()
            elif "You are not associated" in output:
                return None
            
            return None
        except Exception:
            return None
    
    def scan_networks(self) -> List[WiFiNetwork]:
        networks = []
        
        try:
            # Use airport utility for scanning
            airport_path = "/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport"
            
            result = subprocess.run(
                [airport_path, "-s"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            lines = result.stdout.strip().split("\n")
            
            # Skip header line
            for line in lines[1:]:
                if not line.strip():
                    continue
                
                # Parse airport output format
                # SSID                            BSSID             RSSI CHANNEL HT CC SECURITY
                parts = line.split()
                if len(parts) >= 4:
                    # SSID might contain spaces, so we need to be careful
                    # RSSI is typically a negative number
                    rssi_idx = None
                    for i, part in enumerate(parts):
                        if part.startswith("-") and part[1:].isdigit():
                            rssi_idx = i
                            break
                    
                    if rssi_idx:
                        ssid = " ".join(parts[:rssi_idx-1]) if rssi_idx > 1 else parts[0]
                        bssid = parts[rssi_idx-1] if rssi_idx > 0 else None
                        signal = int(parts[rssi_idx])
                        security = parts[-1] if len(parts) > rssi_idx + 3 else "Open"
                        
                        networks.append(WiFiNetwork(
                            ssid=ssid,
                            signal=signal,
                            security=security,
                            bssid=bssid
                        ))
            
        except Exception:
            pass
        
        return networks
    
    def connect(self, ssid: str, password: str = "", timeout: int = 30) -> bool:
        try:
            cmd = ["networksetup", "-setairportnetwork", self._interface, ssid]
            if password:
                cmd.append(password)
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            if result.returncode != 0:
                return False
            
            # Wait for connection
            return self._wait_for_connection(ssid, timeout)
            
        except Exception:
            return False
    
    def _wait_for_connection(self, ssid: str, timeout: int) -> bool:
        """Wait for WiFi connection to establish"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            current = self.get_current_network()
            if current and current.lower() == ssid.lower():
                time.sleep(2)  # Give it a moment to fully establish
                return True
            time.sleep(1)
        
        return False
    
    def disconnect(self) -> bool:
        try:
            result = subprocess.run(
                ["networksetup", "-setairportpower", self._interface, "off"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            time.sleep(1)
            
            result = subprocess.run(
                ["networksetup", "-setairportpower", self._interface, "on"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            return True
        except Exception:
            return False


def get_wifi_manager() -> WiFiManagerBase:
    """
    Get the appropriate WiFi manager for the current platform
    
    Returns:
        WiFiManagerBase instance for the current OS
    """
    system = platform.system().lower()
    
    if system == "windows":
        return WindowsWiFiManager()
    elif system == "darwin":
        return MacOSWiFiManager()
    else:
        raise NotImplementedError(f"WiFi management not supported on {system}")
