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
    ssid: str
    signal: int
    security: str = "Open"
    bssid: Optional[str] = None
    
    @property
    def is_shelly(self) -> bool:
        return self.ssid.lower().startswith("shelly")
    
    @property
    def shelly_model(self) -> str:
        if not self.is_shelly:
            return "Unknown"
        
        if self.mac_address:
            model_part = "Unknown"
            if self.ssid.lower().startswith("shelly"):
                base = self.ssid[6:]
                if "-" in base:
                    model_part = base.split("-")[0]
            
            return f"Device-[{model_part}]"
        
        return "Device (Unknown)"
    
    @property
    def mac_address(self) -> Optional[str]:
        if not self.is_shelly:
            return None
        
        parts = self.ssid.split("-")
        if len(parts) >= 2:
            mac = parts[-1].upper()
            if len(mac) == 12 and all(c in "0123456789ABCDEF" for c in mac):
                return mac
        return None


class WiFiManagerBase(ABC):
    def __init__(self):
        self.console = get_console()
        self._original_network: Optional[str] = None
    
    @abstractmethod
    def get_current_network(self) -> Optional[str]:
        pass
    
    @abstractmethod
    def scan_networks(self) -> List[WiFiNetwork]:
        pass
    
    @abstractmethod
    def connect(self, ssid: str, password: str = "", timeout: int = 30) -> bool:
        pass
    
    @abstractmethod
    def disconnect(self) -> bool:
        pass
    
    def save_original_network(self) -> None:
        self._original_network = self.get_current_network()
    
    def restore_original_network(self, password: str = "") -> bool:
        if self._original_network:
            return self.connect(self._original_network, password)
        return False
    
    def scan_shelly_networks(self) -> List[WiFiNetwork]:
        all_networks = self.scan_networks()
        shelly_networks = [n for n in all_networks if n.is_shelly]
        shelly_networks.sort(key=lambda n: n.signal, reverse=True)
        return shelly_networks
    
    def connect_to_shelly(self, ssid: str, timeout: int = 30) -> bool:
        return self.connect(ssid, password="", timeout=timeout)


class WindowsWiFiManager(WiFiManagerBase):
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
                    if current_network.get("ssid"):
                        networks.append(WiFiNetwork(**current_network))
                    
                    parts = line.split(":", 1)
                    ssid = parts[1].strip() if len(parts) > 1 else ""
                    current_network = {"ssid": ssid, "signal": 0, "security": "Open"}
                
                elif "Signal" in line:
                    parts = line.split(":", 1)
                    if len(parts) > 1:
                        signal_str = parts[1].strip().replace("%", "")
                        try:
                            signal_pct = int(signal_str)
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
            
            if current_network.get("ssid"):
                networks.append(WiFiNetwork(**current_network))
            
        except Exception:
            pass
        
        return networks
    
    def connect(self, ssid: str, password: str = "", timeout: int = 30) -> bool:
        try:
            result = subprocess.run(
                ["netsh", "wlan", "connect", f"name={ssid}"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0 or "is not found" in result.stdout:
                if not self._create_profile(ssid, password):
                    return False
                
                result = subprocess.run(
                    ["netsh", "wlan", "connect", f"name={ssid}"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
            
            if result.returncode != 0:
                return False
            
            return self._wait_for_connection(ssid, timeout)
            
        except Exception:
            return False
    
    def _create_profile(self, ssid: str, password: str = "") -> bool:
        if password:
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
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.xml', delete=False) as f:
                f.write(profile_xml)
                profile_path = f.name
            
            result = subprocess.run(
                ["netsh", "wlan", "add", "profile", f"filename={profile_path}"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            import os
            os.unlink(profile_path)
            
            return result.returncode == 0
            
        except Exception:
            return False
    
    def _wait_for_connection(self, ssid: str, timeout: int) -> bool:
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            current = self.get_current_network()
            if current and current.lower() == ssid.lower():
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
    def __init__(self):
        super().__init__()
        self._interface = self._get_wifi_interface()
    
    def _get_wifi_interface(self) -> str:
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
                    if i + 1 < len(lines):
                        device_line = lines[i + 1]
                        if "Device:" in device_line:
                            return device_line.split(":")[1].strip()
            
            return "en0"
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
            airport_path = "/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport"
            
            result = subprocess.run(
                [airport_path, "-s"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            lines = result.stdout.strip().split("\n")
            
            for line in lines[1:]:
                if not line.strip():
                    continue
                
                parts = line.split()
                if len(parts) >= 4:
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
            
            return self._wait_for_connection(ssid, timeout)
            
        except Exception:
            return False
    
    def _wait_for_connection(self, ssid: str, timeout: int) -> bool:
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            current = self.get_current_network()
            if current and current.lower() == ssid.lower():
                time.sleep(2)
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
    system = platform.system().lower()
    
    if system == "windows":
        return WindowsWiFiManager()
    elif system == "darwin":
        return MacOSWiFiManager()
    else:
        raise NotImplementedError(f"WiFi management not supported on {system}")
