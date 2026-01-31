import gc
from dataclasses import dataclass, field
from typing import Optional
import atexit


@dataclass
class BrokerConfig:
    """MQTT Broker configuration"""
    hostname: str = "raspi-RCC.local"
    ip: Optional[str] = None
    port: int = 1883
    username: str = ""
    password: str = ""  # Stored in memory only
    
    @property
    def address(self) -> str:
        """Get broker address (IP or hostname)"""
        return self.ip or self.hostname
    
    @property
    def connection_string(self) -> str:
        """Get connection string for display (password hidden)"""
        return f"{self.address}:{self.port}"
    
    def is_configured(self) -> bool:
        """Check if broker is properly configured"""
        return bool(self.address and self.username and self.password)


@dataclass
class WiFiConfig:
    """Target WiFi configuration for Shelly devices"""
    ssid: str = ""
    password: str = ""  # Stored in memory only
    
    def is_configured(self) -> bool:
        """Check if WiFi is properly configured"""
        return bool(self.ssid and self.password)


@dataclass
class DeviceNamingConfig:
    """Device naming configuration"""
    prefix: str = "RCC-Device"
    start_number: int = 1
    current_number: int = field(default=1, init=False)
    
    def get_next_name(self) -> str:
        """Get next device name and increment counter"""
        name = f"{self.prefix}-{self.current_number:03d}"
        self.current_number += 1
        return name
    
    def reset(self) -> None:
        """Reset counter to start number"""
        self.current_number = self.start_number


@dataclass
class ProvisioningOptions:
    """Provisioning behavior options"""
    disable_shelly_ap: bool = True
    disable_shelly_cloud: bool = True
    verify_after_provision: bool = True
    
    # Retry settings
    max_retries: int = 3
    retry_delay_base: float = 2.0  # seconds
    api_timeout: float = 10.0  # seconds
    wifi_connect_timeout: float = 30.0  # seconds


class SecureConfig:
    """
    Secure configuration container
    
    All sensitive data is stored in memory only and cleared on exit.
    No configuration files are created or read.
    """
    
    _instance: Optional['SecureConfig'] = None
    
    def __new__(cls):
        """Singleton pattern - only one config instance"""
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
        
        # Register cleanup on exit
        atexit.register(self.clear_credentials)
        
        self._initialized = True
    
    @property
    def broker(self) -> BrokerConfig:
        """Get broker configuration"""
        return self._broker
    
    @property
    def wifi(self) -> WiFiConfig:
        """Get WiFi configuration"""
        return self._wifi
    
    @property
    def naming(self) -> DeviceNamingConfig:
        """Get device naming configuration"""
        return self._naming
    
    @property
    def options(self) -> ProvisioningOptions:
        """Get provisioning options"""
        return self._options
    
    def is_ready(self) -> bool:
        """Check if all required configuration is set"""
        return self._broker.is_configured() and self._wifi.is_configured()
    
    def clear_credentials(self) -> None:
        """
        Securely clear all sensitive credentials from memory
        
        Called automatically on exit via atexit
        """
        # Clear broker credentials
        self._broker.password = ""
        self._broker.username = ""
        
        # Clear WiFi credentials
        self._wifi.ssid = ""
        self._wifi.password = ""
        
        # Force garbage collection to free memory
        gc.collect()
    
    def get_status_string(self) -> str:
        """Get configuration status for display"""
        if not self._broker.ip and not self._broker.hostname:
            return "[notice]Not configured[/notice]"
        
        if self._broker.is_configured():
            return f"[success]{self._broker.connection_string}[/success] [dim]● Connected[/dim]"
        else:
            return f"[input]{self._broker.address}[/input] [dim](credentials needed)[/dim]"


def get_config() -> SecureConfig:
    """Get the global secure configuration instance"""
    return SecureConfig()
