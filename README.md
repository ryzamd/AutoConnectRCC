# RCC - RemoteControlContactor

**Shelly Device Provisioning Tool**

A cross-platform CLI tool for configuring Shelly Gen2 devices with MQTT broker settings and WiFi credentials.

```
 ██████╗   ██████╗   ██████╗
 ██╔══██╗ ██╔════╝  ██╔════╝
 ██████╔╝ ██║       ██║
 ██╔══██╗ ██║       ██║
 ██║  ██║ ╚██████╗  ╚██████╗
 ╚═╝  ╚═╝  ╚═════╝   ╚═════╝
 P R O V I S I O N E R   v1.0.0
```

## Features

- **Discover MQTT Broker**: Automatically find Raspberry Pi broker on LAN via mDNS
- **Scan Devices**: Detect all Shelly devices in AP mode
- **Provision Single/Batch**: Configure MQTT + WiFi for one or multiple devices
- **Verify Connections**: Check devices are connected to broker
- **Secure**: All credentials stored in memory only, cleared on exit
- **Cross-Platform**: Windows 10/11 and macOS 12+

## Security

⚠️ **No configuration files are created.** All credentials (WiFi password, MQTT password) are:
- Entered via CLI with password masking
- Stored in memory only during the session
- Automatically cleared when the tool exits

Log files do NOT contain any credentials.

## Requirements

### System Requirements

| Platform | Version |
|----------|---------|
| Windows | 10 or 11 |
| macOS | 12 (Monterey) or later |
| Python | 3.11+ (bundled in executable) |

### Network Requirements

- PC and Raspberry Pi on the same LAN subnet
- Raspberry Pi running Mosquitto MQTT broker
- Shelly devices in AP mode (unconfigured)
- WiFi adapter enabled on PC

### Before You Start

1. **Raspberry Pi Setup**
   - Mosquitto broker running
   - Firewall allows port 1883
   - MQTT user account created for devices

2. **Shelly Devices**
   - Powered on
   - Not yet configured (broadcasting AP)
   - Within WiFi range

3. **PC/Mac**
   - VPN disabled
   - WiFi adapter enabled
   - Run as Administrator (Windows) or with sudo (macOS)

## Installation

### Option 1: Download Executable (Recommended)

Download the pre-built executable for your platform:
- `RCC.exe` for Windows
- `RCC` for macOS

### Option 2: Build from Source

**Windows:**
```batch
git clone <repo>
cd rcc
build_windows.bat
```

**macOS:**
```bash
git clone <repo>
cd rcc
chmod +x build_macos.sh
./build_macos.sh
```

## Usage

### Run the Tool

**Windows:**
```batch
RCC.exe
```

**macOS:**
```bash
sudo ./RCC
```

> Note: Admin/sudo required for WiFi management

### First Run - Configuration

On first run, you'll be prompted for:

```
MQTT Broker Configuration:
─────────────────────────
  Broker hostname [raspi-RCC.local]:
  Broker IP (or Enter to auto-discover):
  Broker port [1883]:
  MQTT username for devices: DeviceRCC
  MQTT password for devices: ******** (hidden)

Target WiFi Configuration:
──────────────────────────
  WiFi SSID: MyHomeNetwork
  WiFi Password: ******** (hidden)

Device Naming:
──────────────
  Device name prefix [RCC-Device]:
  Start number [1]:
```

### Main Menu

```
[1] 🔍 Discover MQTT Broker    - Find Raspberry Pi on network
[2] 📡 Scan Shelly Devices     - List available Shelly APs
[3] ⚡ Provision Devices        - Configure MQTT + WiFi
[4] ✅ Verify Connections       - Check broker connection
[Q] 🚪 Quit
```

### Provisioning Workflow

1. Tool connects to Shelly AP (e.g., `ShellyPlus1-A8032ABE54DC`)
2. Gets device information
3. Configures MQTT broker settings
4. Configures WiFi credentials
5. Disables Shelly AP and Cloud
6. Renames device (hides Shelly branding)
7. Reboots device

After provisioning:
- Shelly connects to your WiFi
- Shelly connects to MQTT broker
- Shelly AP is hidden (no more `ShellyPlus1-XXXX` network)
- Device appears as `RCC-Device-001` in MQTT topics

## Project Structure

```
rcc/
├── src/
│   └── rcc/
│       ├── __init__.py
│       ├── main.py           # Entry point
│       ├── config.py         # Secure config management
│       ├── discovery.py      # Broker discovery
│       ├── wifi_manager.py   # Cross-platform WiFi
│       ├── shelly_api.py     # Shelly HTTP API
│       ├── provisioner.py    # Main logic
│       └── ui/
│           ├── theme.py      # Color theme
│           ├── console.py    # CLI interface
│           └── ascii_art.py  # Banner
├── requirements.txt
├── pyproject.toml
├── build_windows.bat
├── build_macos.sh
└── README.md
```

## Troubleshooting

### "No Shelly devices found"

- Ensure Shelly is powered on
- Ensure Shelly is in AP mode (factory reset if needed)
- Move closer to the device
- Check WiFi adapter is enabled

### "Cannot connect to broker"

- Verify Raspberry Pi IP address
- Check Mosquitto is running: `sudo systemctl status mosquitto`
- Check firewall: `sudo ufw status`
- Test connection: `mosquitto_pub -h <IP> -t test -m hello -u <user> -P <pass>`

### "WiFi connection failed"

- Run tool as Administrator/sudo
- Disable VPN
- Check WiFi adapter is working

### macOS: "Operation not permitted"

Run with sudo:
```bash
sudo ./RCC
```

## Color Theme

| Element | Color | Hex |
|---------|-------|-----|
| Primary | 🟧 | `#da7757` |
| Secondary | 🟧 | `#d47151` |
| Text | 🟩 | `#96c077` |
| Notice | 🟥 | `#cf6e6e` |
| Info | 🔵 | `#5f9ea0` |
| Success | 🟩 | `#98c379` |
| Input | 🟨 | `#e5c07b` |
| Dim | ⬜ | `#6b7280` |

## License

Proprietary - All rights reserved

## Support

For issues and feature requests, contact the development team.
