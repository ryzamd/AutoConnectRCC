import requests
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass


# Shelly AP mode default IP
SHELLY_AP_IP = "192.168.33.1"
SHELLY_AP_GATEWAY = "192.168.33.1"


@dataclass
class ShellyDeviceInfo:
    """Information about a Shelly device"""
    id: str              # Device ID (e.g., "shellyplus1-a8032abe54dc")
    mac: str             # MAC address
    model: str           # Model code (e.g., "SNSW-001X16EU")
    gen: int             # Generation (2 for Gen2+)
    fw_id: str           # Firmware ID
    ver: str             # Firmware version
    app: str             # Application name (e.g., "Plus1")
    
    @property
    def friendly_name(self) -> str:
        """Get a friendly name for the device"""
        app_map = {
            "Plus1": "Shelly Plus 1",
            "Plus1PM": "Shelly Plus 1PM",
            "Plus2PM": "Shelly Plus 2PM",
            "Pro1": "Shelly Pro 1",
            "Pro1PM": "Shelly Pro 1PM",
            "Pro2": "Shelly Pro 2",
            "Pro2PM": "Shelly Pro 2PM",
            "Pro4PM": "Shelly Pro 4PM",
            "PlugS": "Shelly Plug S",
            "Mini1": "Shelly Mini 1",
        }
        return app_map.get(self.app, self.app)


class ShellyAPIError(Exception):
    """Exception raised for Shelly API errors"""
    def __init__(self, message: str, code: Optional[int] = None):
        self.message = message
        self.code = code
        super().__init__(f"Shelly API Error: {message}" + (f" (code: {code})" if code else ""))


class ShellyAPI:
    """
    Shelly Gen2 HTTP RPC API Client
    
    Communicates with Shelly devices using the JSON-RPC 2.0 protocol
    over HTTP at the device's IP address (192.168.33.1 in AP mode).
    """
    
    def __init__(self, ip: str = SHELLY_AP_IP, timeout: float = 10.0):
        """
        Initialize Shelly API client
        
        Args:
            ip: Device IP address (default: AP mode IP)
            timeout: Request timeout in seconds
        """
        self.ip = ip
        self.base_url = f"http://{ip}"
        self.timeout = timeout
        self._request_id = 0
    
    def _get_request_id(self) -> int:
        """Generate unique request ID"""
        self._request_id += 1
        return self._request_id
    
    def _rpc_call(self, method: str, params: Optional[Dict] = None) -> Any:
        """
        Make an RPC call to the device
        
        Args:
            method: RPC method name (e.g., "Shelly.GetDeviceInfo")
            params: Method parameters
        
        Returns:
            Response result data
        
        Raises:
            ShellyAPIError: If the request fails or returns an error
        """
        url = f"{self.base_url}/rpc/{method}"
        
        try:
            if params:
                response = requests.post(url, json=params, timeout=self.timeout)
            else:
                response = requests.get(url, timeout=self.timeout)
            
            response.raise_for_status()
            data = response.json()
            
            # Check for RPC error
            if "error" in data:
                error = data["error"]
                raise ShellyAPIError(
                    message=error.get("message", "Unknown error"),
                    code=error.get("code")
                )
            
            return data
            
        except requests.exceptions.Timeout:
            raise ShellyAPIError("Request timeout")
        except requests.exceptions.ConnectionError:
            raise ShellyAPIError("Connection failed - device not reachable")
        except requests.exceptions.RequestException as e:
            raise ShellyAPIError(f"Request failed: {str(e)}")
    
    def get_device_info(self) -> ShellyDeviceInfo:
        """
        Get device information
        
        Returns:
            ShellyDeviceInfo with device details
        """
        # Use the simple /shelly endpoint for basic info
        try:
            response = requests.get(f"{self.base_url}/shelly", timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            
            return ShellyDeviceInfo(
                id=data.get("id", "unknown"),
                mac=data.get("mac", "unknown"),
                model=data.get("model", "unknown"),
                gen=data.get("gen", 2),
                fw_id=data.get("fw_id", "unknown"),
                ver=data.get("ver", "unknown"),
                app=data.get("app", "unknown"),
            )
        except Exception as e:
            raise ShellyAPIError(f"Failed to get device info: {str(e)}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get full device status"""
        return self._rpc_call("Shelly.GetStatus")
    
    def get_config(self) -> Dict[str, Any]:
        """Get full device configuration"""
        return self._rpc_call("Shelly.GetConfig")
    
    # ═══════════════════════════════════════════════════════════════
    # WiFi Configuration
    # ═══════════════════════════════════════════════════════════════
    
    def configure_wifi(
        self,
        ssid: str,
        password: str,
        enable_ap: bool = False
    ) -> bool:
        """
        Configure WiFi station (client) settings
        
        Args:
            ssid: WiFi network SSID to connect to
            password: WiFi password
            enable_ap: Whether to keep AP mode enabled (default: False to hide Shelly)
        
        Returns:
            True if configuration was successful
        """
        config = {
            "config": {
                "sta": {
                    "ssid": ssid,
                    "pass": password,
                    "enable": True,
                    "ipv4mode": "dhcp"
                },
                "ap": {
                    "enable": enable_ap
                }
            }
        }
        
        result = self._rpc_call("WiFi.SetConfig", config)
        return result.get("restart_required", False) or True
    
    def disable_ap(self) -> bool:
        """Disable AP mode to hide Shelly network"""
        config = {
            "config": {
                "ap": {
                    "enable": False
                }
            }
        }
        
        result = self._rpc_call("WiFi.SetConfig", config)
        return True
    
    def get_wifi_status(self) -> Dict[str, Any]:
        """Get WiFi status including current connection"""
        return self._rpc_call("WiFi.GetStatus")
    
    # ═══════════════════════════════════════════════════════════════
    # MQTT Configuration
    # ═══════════════════════════════════════════════════════════════
    
    def configure_mqtt(
        self,
        server: str,
        port: int = 1883,
        username: str = "",
        password: str = "",
        client_id: Optional[str] = None,
        topic_prefix: Optional[str] = None,
        enable: bool = True
    ) -> bool:
        """
        Configure MQTT settings
        
        Args:
            server: MQTT broker hostname or IP
            port: MQTT broker port (default: 1883)
            username: MQTT username
            password: MQTT password
            client_id: Client ID (default: device ID)
            topic_prefix: Topic prefix (default: device ID)
            enable: Enable MQTT (default: True)
        
        Returns:
            True if configuration was successful
        """
        config = {
            "config": {
                "enable": enable,
                "server": f"{server}:{port}",
                "user": username,
                "pass": password,
            }
        }
        
        if client_id:
            config["config"]["client_id"] = client_id
        
        if topic_prefix:
            config["config"]["topic_prefix"] = topic_prefix
        
        result = self._rpc_call("MQTT.SetConfig", config)
        return result.get("restart_required", False) or True
    
    def get_mqtt_status(self) -> Dict[str, Any]:
        """Get MQTT connection status"""
        return self._rpc_call("MQTT.GetStatus")
    
    # ═══════════════════════════════════════════════════════════════
    # Cloud Configuration
    # ═══════════════════════════════════════════════════════════════
    
    def disable_cloud(self) -> bool:
        """Disable Shelly Cloud connection"""
        config = {
            "config": {
                "enable": False
            }
        }
        
        try:
            self._rpc_call("Cloud.SetConfig", config)
            return True
        except ShellyAPIError:
            # Cloud might not be available on all devices
            return True
    
    # ═══════════════════════════════════════════════════════════════
    # Device Configuration
    # ═══════════════════════════════════════════════════════════════
    
    def set_device_name(self, name: str) -> bool:
        """
        Set device friendly name
        
        Args:
            name: New device name (will hide "Shelly" branding)
        
        Returns:
            True if successful
        """
        config = {
            "config": {
                "device": {
                    "name": name
                }
            }
        }
        
        result = self._rpc_call("Sys.SetConfig", config)
        return True
    
    def set_discoverable(self, discoverable: bool = False) -> bool:
        """
        Set device discoverable status
        
        Args:
            discoverable: Whether device should be discoverable (default: False)
        
        Returns:
            True if successful
        """
        config = {
            "config": {
                "device": {
                    "discoverable": discoverable
                }
            }
        }
        
        result = self._rpc_call("Sys.SetConfig", config)
        return True
    
    def reboot(self) -> bool:
        """Reboot the device"""
        try:
            self._rpc_call("Shelly.Reboot")
            return True
        except ShellyAPIError:
            # Request might timeout during reboot
            return True
    
    # ═══════════════════════════════════════════════════════════════
    # Switch Control (for testing)
    # ═══════════════════════════════════════════════════════════════
    
    def get_switch_status(self, switch_id: int = 0) -> Dict[str, Any]:
        """Get switch status"""
        return self._rpc_call("Switch.GetStatus", {"id": switch_id})
    
    def set_switch(self, on: bool, switch_id: int = 0) -> bool:
        """Set switch state"""
        params = {
            "id": switch_id,
            "on": on
        }
        result = self._rpc_call("Switch.Set", params)
        return True


def get_shelly_api(ip: str = SHELLY_AP_IP, timeout: float = 10.0) -> ShellyAPI:
    """
    Create a Shelly API client
    
    Args:
        ip: Device IP address
        timeout: Request timeout
    
    Returns:
        ShellyAPI instance
    """
    return ShellyAPI(ip, timeout)


def check_shelly_ap_mode() -> bool:
    """
    Check if we can reach a Shelly device in AP mode
    
    Returns:
        True if Shelly AP is accessible
    """
    try:
        api = ShellyAPI(SHELLY_AP_IP, timeout=5.0)
        api.get_device_info()
        return True
    except Exception:
        return False
