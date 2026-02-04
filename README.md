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

## System Requirements

| Platform | Version |
|----------|---------|
| Windows | 10 or 11 |
| macOS | 12 (Monterey) or later |
| Python | 3.11+ (if building from source) |

## Installation & Building

### Option 1: Build from Source (Windows)

**Prerequisites:**
- Python 3.11 or newer installed.
- Git installed.

**Build Steps:**
1.  **Clone the repository:**
    ```powershell
    git clone <your-repo-url>
    cd rcc
    ```
2.  **Add your Logo (Optional):**
    - Place your `RCC-logo.png` in `src/rcc/assets/`.
    - The build script will automatically convert it to an icon.
3.  **Run the Build Script:**
    Double-click `build_windows.bat` or run it from PowerShell:
    ```powershell
    .\build_windows.bat
    ```
    *This script will automatically:*
    - Create a Python virtual environment (`venv`).
    - Install all dependencies (including `Pillow` for icon processing).
    - Generate `.ico` files from your logo.
    - Compile the application into a single executable.
4.  **Locate the Executable:**
    The finished app is located at:
    ```
    dist\RCC.exe
    ```

### Option 2: Build from Source (macOS)

**Prerequisites:**
- Python 3 installed (recommended via Homebrew: `brew install python`).
- Git installed.

**Build Steps:**
1.  **Clone the repository:**
    ```bash
    git clone <your-repo-url>
    cd rcc
    ```
2.  **Add your Logo (Optional):**
    - Place your `RCC-logo.png` in `src/rcc/assets/`.
3.  **Run the Build Script:**
    Make the script executable and run it:
    ```bash
    chmod +x build_macos.sh
    ./build_macos.sh
    ```
    *This script will automatically:*
    - Create a virtual environment.
    - Install dependencies.
    - Generate `.icns` files from your logo.
    - Compile the application.
4.  **Locate the Executable:**
    The finished app is located at:
    ```
    dist/RCC
    ```

## Usage Instructions

### ⚠️ Admin Privileges Required
**Crucial:** This tool requires Administrator (Windows) or Sudo (macOS) privileges to manage WiFi adapters and scan for networks.

### Running on Windows
1.  Navigate to the `dist` folder.
2.  Right-click `RCC.exe` and select **Run as administrator**.
    - *Alternatively, open a Command Prompt as Admin and run `dist\RCC.exe` to see any potential startup errors.*

### Running on macOS
1.  Open Terminal.
2.  Navigate to the `dist` folder.
3.  Run with sudo:
    ```bash
    sudo ./RCC
    ```

### First Run Configuration
On the first run, the tool will ask for your environment details. These are saved for future use (except passwords).

1.  **MQTT Broker**: Enter the IP of your Raspberry Pi (or press Enter to try auto-discovery).
2.  **Credentials**: Enter the MQTT username/password and your Target WiFi SSID/Password.
3.  **Device Naming**: Set a prefix (e.g., `LivingRoom-Shade`) for auto-naming devices.

### Main Menu Guide

```
[1] 🔍 Discover MQTT Broker    - Find Raspberry Pi on network
[2] 📡 Scan Shelly Devices     - List available Shelly APs
[3] ⚡ Provision Devices        - Configure MQTT + WiFi
[4] ✅ Verify Connections       - Check broker connection
[Q] 🚪 Quit
```

- **Scan**: Finds unconfigured Shelly devices broadcasting their own WiFi AP.
- **Provision**: Connects to the Shelly, uploads your WiFi/MQTT settings, reboots the device, and verifies it joins your network.

## Project Structure

```
rcc/
├── src/
│   └── rcc/
│       ├── assets/           # Application Icons/Logos
│       ├── main.py           # Entry point
│       ├── config.py         # Config management
│       ├── wifi_manager.py   # WiFi logic
│       └── ...
├── tools/
│   └── convert_icon.py       # Icon generation script
├── dist/                     # Compiled executables (Output)
├── build_windows.bat         # One-click build for Windows
├── build_macos.sh            # One-click build for macOS
├── requirements.txt          # Python dependencies
└── RCC.spec                  # PyInstaller configuration
```

## Troubleshooting

### Icon not showing updated?
Windows caches icons aggressively. If you updated `RCC-logo.png` but `RCC.exe` shows the old icon:
1.  Rename `RCC.exe` to something else (e.g., `RCC_v2.exe`).
2.  Or copy it to a different folder.
3.  Restart Windows to clear the cache.

### "No Shelly devices found"
- Ensure the device is in **AP Mode** (hold the reset button for 10s if it's already connected to WiFi).
- Ensure your PC has a working WiFi adapter.

### License
Proprietary - All rights reserved
