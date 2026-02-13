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

### 1. Discover MQTT Broker
- **Function**: Automatically finds the MQTT broker (e.g., Raspberry Pi) on the local network.
- **Method**: Uses mDNS (Multicast DNS) to look for `RCCServer.local`.
- **Fallback**: Allows manual IP entry if auto-discovery fails.
- **Verification**: Verifies connectivity to the broker port (default 1883) before saving.

### 2. Scan Devices
- **Function**: Scans the device's WiFi interface for available Shelly devices.
- **Filter**: Looks for WiFi SSIDs starting with `Shelly` and containing `-` (e.g., `ShellyPlus1-AABBCC`).
- **Output**: Displays a list of found devices with Signal Strength (RSSI) and Model.

### 3. Provision Devices (Core Feature)
- **Function**: Configures selected Shelly devices with:
    - Target WiFi credentials.
    - MQTT Broker settings (Host, Port, User, Password).
    - Device Name (Auto-generated using a prefix).
- **Modes**: Support for Provisioning a single device, specific selection, or ALL found devices.

### 4. Reset Devices
- **Function**: Remote Factory Reset for already provisioned devices.
- **Scope**: Scans for devices already connected to the MQTT broker (with `RCC-Device` ID prefix).
- **Action**: Sends a factory reset command via the Shelly API.

## Operational Flow

### User Journey (Typical)
1.  **Startup**: 
    - Loads configuration. 
    - If first run, prompts for **Target WiFi SSID/Pass**, **MQTT Credentials**, and **Device Naming Prefix**.
2.  **Main Menu**:
    - User selects **[1] Discover** to ensure Broker IP is set.
    - User selects **[3] Provision** to start the main workflow.
3.  **Provisioning Workflow**:
    - **Step 1: Scan**: Finds unprovisioned Shelly APs.
    - **Step 2: Connect**: App disconnects PC from current WiFi and connects to the Shelly AP.
    - **Step 3: Configure**:
        - Fetches Device Info (MAC, Model).
        - Sets MQTT settings (updates `topic_prefix` to the new name).
        - Sets WiFi settings (Target SSID/Pass).
        - Disables Cloud (optional).
        - Renames Device (System Name).
    - **Step 4: Reboot**: Sends reboot command.
    - **Step 5: Disable AP**: (Attempted) Reconnects to AP to disable it (security measure).
    - **Step 6: Completion**: Marks device as Success/Fail.
    - **Step 7: Repeat**: Moves to the next device in the batch.
    - **Step 8: Restore**: PC reconnects to the original WiFi network.
    - **Step 9: Verify**: Attempts to resolve the new hostnames to confirm they joined the network.

## System Requirements

| Platform | Version |
|----------|---------|
| Windows | 10 or 11 |
| macOS | 12 (Monterey) or later |
| Python | 3.11+ (if building from source) |

## Installation & Building

The project includes automated scripts to build standalone executables for Windows (`.exe`) and macOS.

### Prerequisites (Both Platforms)
1.  **Python 3.11 or newer**: Ensure python is installed and added to your system PATH.
2.  **Internet Access**: Required to download dependencies (`pip install`).
3.  **Git**: To clone the repository (optional if you have the files).

### Building on Windows

A batch script is provided to automate the setup and build process.

1.  **Open Setup Directory**: Navigate to the project root folder.
2.  **Run Build Script**: Double-click `build_windows.bat` or run it from PowerShell:
    ```powershell
    .\build_windows.bat
    ```
3.  **Process**:
    - The script automatically creates a `venv` (virtual environment).
    - Installs all dependencies from `requirements.txt` and `pyinstaller`.
    - Compiles `run_rcc.py` into a single file executable.
    - Embeds the icon from `src\rcc\assets\RCC-logo.ico`.
4.  **Output**:
    - Success: `Build successful!`
    - The executable is located at: **`dist\RCC.exe`**

### Building on macOS

A shell script is provided for macOS builds.

1.  **Open Terminal**: Navigate to the project root folder.
2.  **Make Executable (First time only)**:
    ```bash
    chmod +x build_macos.sh
    ```
3.  **Run Build Script**:
    ```bash
    ./build_macos.sh
    ```
4.  **Process**:
    - Checks for `python3`.
    - Creates `venv` and installs dependencies.
    - Compiles `run_rcc.py` (entry point).
    - Embeds the icon from `src/rcc/assets/RCC-logo.icns`.
5.  **Output**:
    - The executable is located at: **`dist/RCC`**

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
- **AP Mode**: Ensure the device is in **AP Mode** (hold the reset button for 10s if it's already connected to WiFi).
- **WiFi Adapter**: Ensure your PC has a working WiFi and is not currently connected to the Shelly AP manually (let the tool handle it).

### License
Proprietary - All rights reserved