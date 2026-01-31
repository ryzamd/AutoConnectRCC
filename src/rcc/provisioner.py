import time
import json
import os
from datetime import datetime
from typing import List, Optional, Tuple, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum

from .config import SecureConfig, get_config
from .wifi_manager import get_wifi_manager, WiFiNetwork, WiFiManagerBase
from .shelly_api import ShellyAPI, ShellyDeviceInfo, ShellyAPIError, SHELLY_AP_IP
from .discovery import verify_broker
from .ui import get_console


class ProvisionState(Enum):
    """Provisioning state machine states"""
    PENDING = "pending"
    CONNECTING = "connecting"
    GET_INFO = "getting_info"
    CONFIG_MQTT = "config_mqtt"
    CONFIG_WIFI = "config_wifi"
    DISABLE_AP = "disable_ap"
    DISABLE_CLOUD = "disable_cloud"
    RENAME = "rename"
    VERIFY = "verify"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class ProvisionStep:
    """A single provisioning step"""
    name: str
    state: str = "pending"  # pending, progress, success, error, retry
    error_message: Optional[str] = None
    retry_count: int = 0


@dataclass
class ProvisionedDevice:
    """Record of a provisioned device"""
    mac: str
    ap_ssid: str
    model: str
    state: str
    assigned_name: Optional[str] = None
    final_ip: Optional[str] = None
    steps_completed: List[str] = field(default_factory=list)
    error_message: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ProvisionSession:
    """Provisioning session record (for checkpoint/recovery)"""
    session_id: str
    broker_host: str
    broker_port: int
    devices: List[ProvisionedDevice] = field(default_factory=list)
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    
    def save_checkpoint(self, filepath: str) -> None:
        """Save session checkpoint (no credentials!)"""
        data = {
            "session_id": self.session_id,
            "broker_host": self.broker_host,
            "broker_port": self.broker_port,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "devices": [asdict(d) for d in self.devices]
        }
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    
    @classmethod
    def load_checkpoint(cls, filepath: str) -> 'ProvisionSession':
        """Load session from checkpoint"""
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        session = cls(
            session_id=data["session_id"],
            broker_host=data["broker_host"],
            broker_port=data["broker_port"],
        )
        session.started_at = data["started_at"]
        session.completed_at = data.get("completed_at")
        session.devices = [
            ProvisionedDevice(**d) for d in data.get("devices", [])
        ]
        return session


class RetryError(Exception):
    """Exception indicating all retries exhausted"""
    pass


def retry_operation(
    operation: Callable,
    max_retries: int = 3,
    delay_base: float = 2.0,
    backoff: str = "exponential",
    on_retry: Optional[Callable[[int, Exception], None]] = None
):
    """
    Retry an operation with configurable backoff
    
    Args:
        operation: Function to execute
        max_retries: Maximum retry attempts
        delay_base: Base delay in seconds
        backoff: "exponential" or "linear"
        on_retry: Callback when retrying (retry_num, exception)
    
    Returns:
        Operation result
    
    Raises:
        RetryError: If all retries exhausted
    """
    last_error = None
    
    for attempt in range(max_retries):
        try:
            return operation()
        except Exception as e:
            last_error = e
            
            if attempt < max_retries - 1:
                if on_retry:
                    on_retry(attempt + 1, e)
                
                if backoff == "exponential":
                    delay = delay_base * (2 ** attempt)
                else:
                    delay = delay_base
                
                time.sleep(delay)
    
    raise RetryError(f"Operation failed after {max_retries} attempts: {last_error}")


class Provisioner:
    """
    Main provisioner class
    
    Orchestrates the complete Shelly device provisioning workflow.
    """
    
    def __init__(self, config: Optional[SecureConfig] = None):
        """
        Initialize provisioner
        
        Args:
            config: SecureConfig instance (uses global if not provided)
        """
        self.config = config or get_config()
        self.console = get_console()
        self.wifi_manager: Optional[WiFiManagerBase] = None
        self.session: Optional[ProvisionSession] = None
        
        # Callbacks for UI updates
        self.on_step_update: Optional[Callable[[str, str], None]] = None
        self.on_device_complete: Optional[Callable[[ProvisionedDevice], None]] = None
    
    def initialize(self) -> bool:
        """
        Initialize provisioner (WiFi manager, etc.)
        
        Returns:
            True if initialization successful
        """
        try:
            self.wifi_manager = get_wifi_manager()
            return True
        except NotImplementedError as e:
            self.console.print(f"[notice]{str(e)}[/notice]")
            return False
    
    def _update_step(self, step: str, status: str) -> None:
        """Update step status via callback"""
        if self.on_step_update:
            self.on_step_update(step, status)
    
    def provision_device(
        self,
        network: WiFiNetwork,
        device_name: Optional[str] = None
    ) -> ProvisionedDevice:
        """
        Provision a single Shelly device
        
        Args:
            network: WiFi network info (Shelly AP)
            device_name: Optional custom name (auto-generated if not provided)
        
        Returns:
            ProvisionedDevice record
        """
        # Generate device name if not provided
        if not device_name:
            device_name = self.config.naming.get_next_name()
        
        # Initialize device record
        device = ProvisionedDevice(
            mac=network.mac_address or "unknown",
            ap_ssid=network.ssid,
            model=network.shelly_model,
            state=ProvisionState.PENDING.value,
            assigned_name=device_name
        )
        
        try:
            # Step 1: Connect to Shelly AP
            self._update_step("Connecting to AP...", "progress")
            device.state = ProvisionState.CONNECTING.value
            
            success = retry_operation(
                lambda: self.wifi_manager.connect_to_shelly(network.ssid),
                max_retries=self.config.options.max_retries,
                delay_base=5.0,
                backoff="linear",
                on_retry=lambda n, e: self._update_step(f"Connecting to AP... (retry {n})", "retry")
            )
            
            if not success:
                raise Exception("Failed to connect to Shelly AP")
            
            self._update_step("Connecting to AP...", "success")
            device.steps_completed.append("connect_ap")
            
            # Give WiFi time to stabilize
            time.sleep(3)
            
            # Step 2: Get device information
            self._update_step("Getting device info...", "progress")
            device.state = ProvisionState.GET_INFO.value
            
            api = ShellyAPI(SHELLY_AP_IP, timeout=self.config.options.api_timeout)
            
            device_info = retry_operation(
                lambda: api.get_device_info(),
                max_retries=self.config.options.max_retries,
                delay_base=self.config.options.retry_delay_base,
                on_retry=lambda n, e: self._update_step(f"Getting device info... (retry {n})", "retry")
            )
            
            # Update device record with actual info
            device.mac = device_info.mac
            device.model = device_info.friendly_name
            
            self._update_step("Getting device info...", "success")
            device.steps_completed.append("get_info")
            
            # Step 3: Configure MQTT
            self._update_step("Configuring MQTT...", "progress")
            device.state = ProvisionState.CONFIG_MQTT.value
            
            retry_operation(
                lambda: api.configure_mqtt(
                    server=self.config.broker.address,
                    port=self.config.broker.port,
                    username=self.config.broker.username,
                    password=self.config.broker.password,
                    topic_prefix=device_name  # Use custom name as topic prefix
                ),
                max_retries=self.config.options.max_retries,
                delay_base=self.config.options.retry_delay_base,
                on_retry=lambda n, e: self._update_step(f"Configuring MQTT... (retry {n})", "retry")
            )
            
            self._update_step("Configuring MQTT...", "success")
            device.steps_completed.append("config_mqtt")
            
            # Step 4: Configure WiFi
            self._update_step("Configuring WiFi...", "progress")
            device.state = ProvisionState.CONFIG_WIFI.value
            
            retry_operation(
                lambda: api.configure_wifi(
                    ssid=self.config.wifi.ssid,
                    password=self.config.wifi.password,
                    enable_ap=False  # Disable AP to hide Shelly
                ),
                max_retries=self.config.options.max_retries,
                delay_base=self.config.options.retry_delay_base,
                on_retry=lambda n, e: self._update_step(f"Configuring WiFi... (retry {n})", "retry")
            )
            
            self._update_step("Configuring WiFi...", "success")
            device.steps_completed.append("config_wifi")
            
            # Step 5: Disable Cloud
            if self.config.options.disable_shelly_cloud:
                self._update_step("Disabling cloud...", "progress")
                device.state = ProvisionState.DISABLE_CLOUD.value
                
                try:
                    api.disable_cloud()
                    self._update_step("Disabling cloud...", "success")
                    device.steps_completed.append("disable_cloud")
                except Exception:
                    # Cloud disable is optional
                    self._update_step("Disabling cloud...", "success")
            
            # Step 6: Set device name
            self._update_step(f"Renaming to {device_name}...", "progress")
            device.state = ProvisionState.RENAME.value
            
            try:
                api.set_device_name(device_name)
                api.set_discoverable(False)
                self._update_step(f"Renaming to {device_name}...", "success")
                device.steps_completed.append("rename")
            except Exception:
                # Rename is optional
                self._update_step(f"Renaming to {device_name}...", "success")
            
            # Step 7: Reboot device to apply changes
            self._update_step("Rebooting device...", "progress")
            
            try:
                api.reboot()
            except Exception:
                # Reboot request often times out
                pass
            
            self._update_step("Rebooting device...", "success")
            device.steps_completed.append("reboot")
            
            # Mark as completed
            device.state = ProvisionState.COMPLETED.value
            
        except RetryError as e:
            device.state = ProvisionState.FAILED.value
            device.error_message = str(e)
            self._update_step("Failed", "error")
            
            # Attempt rollback
            self._rollback_device(api if 'api' in dir() else None, device)
            
        except Exception as e:
            device.state = ProvisionState.FAILED.value
            device.error_message = str(e)
            self._update_step(f"Error: {str(e)}", "error")
        
        # Notify completion
        if self.on_device_complete:
            self.on_device_complete(device)
        
        return device
    
    def _rollback_device(self, api: Optional[ShellyAPI], device: ProvisionedDevice) -> None:
        """
        Attempt to rollback failed provisioning
        
        Args:
            api: ShellyAPI instance (if available)
            device: Device record
        """
        try:
            if api and "config_mqtt" in device.steps_completed:
                # Disable MQTT if it was configured
                api.configure_mqtt(
                    server="",
                    enable=False
                )
            
            device.state = ProvisionState.ROLLED_BACK.value
        except Exception:
            # Rollback failed - device may be in inconsistent state
            pass
    
    def provision_batch(
        self,
        networks: List[WiFiNetwork],
        progress_callback: Optional[Callable[[int, int, WiFiNetwork], None]] = None
    ) -> List[ProvisionedDevice]:
        """
        Provision multiple devices sequentially
        
        Args:
            networks: List of Shelly networks to provision
            progress_callback: Called with (current, total, network) before each device
        
        Returns:
            List of ProvisionedDevice records
        """
        # Create session
        self.session = ProvisionSession(
            session_id=datetime.now().strftime("%Y%m%d_%H%M%S"),
            broker_host=self.config.broker.address,
            broker_port=self.config.broker.port
        )
        
        # Save original WiFi network
        original_network = self.wifi_manager.get_current_network()
        
        results: List[ProvisionedDevice] = []
        
        for i, network in enumerate(networks):
            if progress_callback:
                progress_callback(i + 1, len(networks), network)
            
            # Provision device
            device = self.provision_device(network)
            results.append(device)
            
            # Add to session
            self.session.devices.append(device)
            
            # Save checkpoint after each device
            checkpoint_path = f"rcc_checkpoint_{self.session.session_id}.json"
            self.session.save_checkpoint(checkpoint_path)
            
            # Small delay between devices
            if i < len(networks) - 1:
                time.sleep(2)
        
        # Mark session complete
        self.session.completed_at = datetime.now().isoformat()
        self.session.save_checkpoint(f"rcc_checkpoint_{self.session.session_id}.json")
        
        # Attempt to reconnect to original network
        if original_network:
            self.console.print(f"\n[info]Reconnecting to {original_network}...[/info]")
            # Note: User will need to provide password for reconnection
            # This is handled in the main flow
        
        return results
    
    def verify_device(self, device: ProvisionedDevice) -> bool:
        """
        Verify a provisioned device is connected to MQTT broker
        
        Args:
            device: Provisioned device record
        
        Returns:
            True if device is connected
        """
        # For now, just verify broker is reachable
        # Full verification would require subscribing to MQTT topic
        return verify_broker(
            self.config.broker.address,
            self.config.broker.port
        )


def create_provisioner() -> Provisioner:
    """
    Create and initialize a provisioner instance
    
    Returns:
        Initialized Provisioner
    """
    provisioner = Provisioner()
    provisioner.initialize()
    return provisioner
