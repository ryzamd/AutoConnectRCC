import requests
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass

SHELLY_AP_IP = "192.168.33.1"
SHELLY_AP_GATEWAY = "192.168.33.1"


@dataclass
class ShellyDeviceInfo:
    id: str
    mac: str
    model: str
    gen: int
    fw_id: str
    ver: str
    app: str
    
    @property
    def friendly_name(self) -> str:
        return f"Device {self.mac}"


class ShellyAPIError(Exception):
    def __init__(self, message: str, code: Optional[int] = None):
        self.message = message
        self.code = code
        super().__init__(f"API Error: {message}" + (f" (code: {code})" if code else ""))


class ShellyAPI:
    def __init__(self, ip: str = SHELLY_AP_IP, timeout: float = 10.0):
        self.ip = ip
        self.base_url = f"http://{ip}"
        self.timeout = timeout
        self._request_id = 0
    
    def _get_request_id(self) -> int:
        self._request_id += 1
        return self._request_id
    
    def _rpc_call(self, method: str, params: Optional[Dict] = None) -> Any:
        url = f"{self.base_url}/rpc/{method}"
        
        try:
            if params:
                response = requests.post(url, json=params, timeout=self.timeout)
            else:
                response = requests.get(url, timeout=self.timeout)
            
            response.raise_for_status()
            data = response.json()
            
            if data and "error" in data:
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
        return self._rpc_call("Shelly.GetStatus")
    
    def get_config(self) -> Dict[str, Any]:
        return self._rpc_call("Shelly.GetConfig")
    
    # ═══════════════════════════════════════════════════════════════
    # WiFi Configuration
    # ═══════════════════════════════════════════════════════════════
    
    def configure_wifi(self, ssid: str, password: str, enable_ap: bool = False) -> bool:
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
        return self._rpc_call("WiFi.GetStatus")
    
    # ═══════════════════════════════════════════════════════════════
    # MQTT Configuration
    # ═══════════════════════════════════════════════════════════════
    
    def configure_mqtt(self, server: str, port: int = 1883, username: str = "", password: str = "",
        client_id: Optional[str] = None,
        topic_prefix: Optional[str] = None,
        enable: bool = True
    ) -> bool:
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
        return self._rpc_call("MQTT.GetStatus")
    
    # ═══════════════════════════════════════════════════════════════
    # Cloud Configuration
    # ═══════════════════════════════════════════════════════════════
    
    def disable_cloud(self) -> bool:
        config = {
            "config": {
                "enable": False
            }
        }
        
        try:
            self._rpc_call("Cloud.SetConfig", config)
            return True
        except ShellyAPIError:
            return True
    
    # ═══════════════════════════════════════════════════════════════
    # Device Configuration
    # ═══════════════════════════════════════════════════════════════
    
    def set_device_name(self, name: str) -> bool:
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
        config = {
            "config": {
                "device": {
                    "discoverable": discoverable
                }
            }
        }
        
        result = self._rpc_call("Sys.SetConfig", config)
        return True
    
    def reboot(self) -> None:
        self._rpc_call("Shelly.Reboot")
    
    def factory_reset(self) -> bool:
        try:
            self._rpc_call("Shelly.FactoryReset")
            return True
        except ShellyAPIError:
            return False
    
    # ═══════════════════════════════════════════════════════════════
    # Switch Control (for testing)
    # ═══════════════════════════════════════════════════════════════
    
    def get_switch_status(self, switch_id: int = 0) -> Dict[str, Any]:
        return self._rpc_call("Switch.GetStatus", {"id": switch_id})
    
    def set_switch(self, on: bool, switch_id: int = 0) -> bool:
        params = {
            "id": switch_id,
            "on": on
        }
        result = self._rpc_call("Switch.Set", params)
        return True


def get_shelly_api(ip: str = SHELLY_AP_IP, timeout: float = 10.0) -> ShellyAPI:
    return ShellyAPI(ip, timeout)


def check_shelly_ap_mode() -> bool:
    try:
        api = ShellyAPI(SHELLY_AP_IP, timeout=5.0)
        api.get_device_info()
        return True
    except Exception:
        return False
