import gc
from dataclasses import dataclass, field
from typing import Optional
import atexit


@dataclass
class BrokerConfig:
    hostname: str = "RCCServer.local"
    ip: Optional[str] = None
    port: int = 1883
    username: str = "DeviceRCC"
    password: str = "DeviceRCC@#!"
    
    @property
    def address(self) -> str:
        return self.ip or self.hostname
    
    @property
    def connection_string(self) -> str:
        return f"{self.address}:{self.port}"
    
    def is_configured(self) -> bool:
        return bool(self.address and self.username and self.password)


@dataclass
class WiFiConfig:
    ssid: str = ""
    password: str = ""
    
    def is_configured(self) -> bool:
        return bool(self.ssid and self.password)


@dataclass
class DeviceNamingConfig:
    prefix: str = "RCC-Device"
    start_number: int = 1
    current_number: int = field(default=1, init=False)
    
    def get_next_name(self) -> str:
        name = f"{self.prefix}-{self.current_number:03d}"
        self.current_number += 1
        return name
    
    def reset(self) -> None:
        self.current_number = self.start_number


@dataclass
class ProvisioningOptions:
    disable_shelly_ap: bool = True
    disable_shelly_cloud: bool = True
    verify_after_provision: bool = True
    
    max_retries: int = 3
    retry_delay_base: float = 2.0
    api_timeout: float = 10.0
    wifi_connect_timeout: float = 30.0


class SecureConfig:
    _instance: Optional['SecureConfig'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._broker = BrokerConfig()
        self._wifi = WiFiConfig()
        self._naming = DeviceNamingConfig()
        self._options = ProvisioningOptions()
        
        atexit.register(self.clear_credentials)
        
        self._initialized = True
    
    @property
    def broker(self) -> BrokerConfig:
        return self._broker
    
    @property
    def wifi(self) -> WiFiConfig:
        return self._wifi
    
    @property
    def naming(self) -> DeviceNamingConfig:
        return self._naming
    
    @property
    def options(self) -> ProvisioningOptions:
        return self._options
    
    def is_ready(self) -> bool:
        return self._broker.is_configured() and self._wifi.is_configured()
    
    def clear_credentials(self) -> None:
        self._broker.password = ""
        self._broker.username = ""
        self._wifi.ssid = ""
        self._wifi.password = ""
        gc.collect()
    
    def get_status_string(self) -> str:
        if not self._broker.ip and not self._broker.hostname:
            return "[notice]Not configured[/notice]"
        
        if self._broker.is_configured():
            return f"[success]{self._broker.connection_string}[/success] [dim]● Connected[/dim]"
        else:
            return f"[input]{self._broker.address}[/input] [dim](credentials needed)[/dim]"


def get_config() -> SecureConfig:
    return SecureConfig()