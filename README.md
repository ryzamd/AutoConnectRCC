# RCC - RemoteControlContactor

**Shelly Device Provisioning Tool**

A cross-platform CLI tool for configuring Shelly Gen2 devices with MQTT broker settings and WiFi credentials.

```
████████████████████████████████████████████████████
█▌                                                ▐█
█▌                                                ▐█
█▌     ██╗  ██╗███████╗██████╗ ███╗   ███╗██╗     ▐█
█▌     ██║  ██║██╔════╝██╔══██╗████╗ ████║██║     ▐█
█▌     ███████║█████╗  ██████╔╝██╔████╔██║██║     ▐█
█▌     ██╔══██║██╔══╝  ██╔══██╗██║╚██╔╝██║██║     ▐█
█▌     ██║  ██║███████╗██║  ██║██║ ╚═╝ ██║██║     ▐█
█▌     ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝╚═╝     ▐█
█▌                                                ▐█
█▌                                                ▐█
████████████████████████████████████████████████████

RCC tool - Auto config v1.0.0
```

## Features

- **Discover MQTT Broker**: Automatically find `RCCServer.local` on LAN via mDNS or fallback to manual IP.
- **Scan Devices**: Detect all Shelly devices in AP mode (e.g., `ShellyPlus1-AABBCC`).
- **Provision Devices**:
  - Auto-configure Target WiFi (SSID/Password).
  - Auto-configure MQTT Broker (Host, Port, User `DeviceRCC`, Pass `DeviceRCC@#!`).
  - Auto-name devices with prefix (Default: `RCC-Device-001`).
  - Disable Shelly Cloud & AP mode after provisioning.
- **Reset Devices**: Remote factory reset for provisioned devices.
- **Cross-Platform**: Windows 10/11 and macOS 12+.

## System Requirements

| Platform | Version |
|----------|---------|
| Windows | 10 or 11 |
| macOS | 12 (Monterey) or later |
| Python | 3.11+ (if building from source) |

## Installation & Building

### Prerequisites
1.  **Python 3.11+** installed.
2.  **Git** (optional).
3.  **Internet Access** for dependencies.

### Build on Windows
1.  Run `build_windows.bat`.
2.  Executable created at `dist\RCC.exe`.

### Build on macOS
1.  Run `chmod +x build_macos.sh`.
2.  Run `./build_macos.sh`.
3.  Executable created at `dist/RCC`.

## Usage Instructions

### ⚠️ Admin/Root Privileges Required
You must run this tool as **Administrator** (Windows) or with `sudo` (macOS) to manage WiFi adapters.

### First Run Configuration
When you run the tool for the first time, it will guide you through a simplified setup:
1.  **Target WiFi**: Enter the SSID and Password for the network Shelly devices should join.
2.  **Broker Port**: Default is `1883`.
3.  **Connection Test**: The tool will attempt to connect to the WiFi and auto-discover the broker.

*Note: MQTT Credentials are currently hardcoded to User: `DeviceRCC` / Pass: `DeviceRCC@#!`.*

### Main Menu

```
[1] Discover MQTT Broker    - Find Raspberry Pi on network
[2] Scan Shelly Devices     - List available Shelly APs
[3] Provision Devices        - Configure MQTT + WiFi
[4] Reset Device             - Factory reset provisioned devices
[Q] Quit
```

- **[1] Discover**: Re-runs mDNS discovery for `RCCServer`.
- **[3] Provision**: The main workhorse. Scans for Shelly APs, connects to them one-by-one, uploads config, and verifies.
- **[4] Reset**: Finds devices already connected to the broker (must have `RCC-Device` prefix) and factory resets them.

## Troubleshooting

### "No devices found"
- Ensure device is in **AP Mode** (Hold reset button for 10s).
- Ensure your PC has a working WiFi adapter and is not manually connected to the Shelly AP.

### Icon issues (Windows)
- If the icon doesn't update, rename the `.exe` or move it to a new folder to clear Windows icon cache.