from getpass import getpass
from typing import Optional, List, Tuple
import sys

from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.live import Live
from rich.layout import Layout

from .theme import get_console, RCC_THEME, COLORS
from .ascii_art import print_banner, print_divider, print_section, DIVIDER


class RCCConsole:
    
    def __init__(self):
        self.console = get_console()
    
    def clear(self) -> None:
        self.console.clear()
    
    def print(self, text: str = "", style: str = "text") -> None:
        self.console.print(text, style=style)
    
    def print_success(self, text: str) -> None:
        self.console.print(f"[success]✓ {text}[/success]")
    
    def print_error(self, text: str) -> None:
        self.console.print(f"[notice]✗ {text}[/notice]")
    
    def print_info(self, text: str) -> None:
        self.console.print(f"[info]ℹ {text}[/info]")
    
    def print_warning(self, text: str) -> None:
        self.console.print(f"[notice]⚠ {text}[/notice]")
    
    def print_step(self, step: str, status: str = "pending") -> None:
        icons = {
            "pending": "[dim]○[/dim]",
            "progress": "[input]⟳[/input]",
            "success": "[success]✓[/success]",
            "error": "[notice]✗[/notice]",
            "retry": "[notice]↻[/notice]",
        }
        icon = icons.get(status, icons["pending"])
        self.console.print(f"    {icon} {step}")
    
    def show_banner(self, compact: bool = False) -> None:
        print_banner(compact)
    
    def show_main_menu(self, broker_status: Optional[str] = None) -> str:
        self.clear()
        self.show_banner()
        self.console.print()
        self.console.print("[menu.key][1][/menu.key] [menu]Discover Server IP[/menu]")
        self.console.print("[menu.key][2][/menu.key] [menu]Scan Devices[/menu]")
        self.console.print("[menu.key][3][/menu.key] [menu]Provision Devices[/menu]")
        self.console.print("[menu.key][4][/menu.key] [menu]Verify Connections[/menu]")
        self.console.print("[menu.key][Q][/menu.key] [menu]Quit[/menu]")
        self.console.print()
        print_divider()
        
        if broker_status:
            self.console.print(f"[dim]Server: {broker_status}[/dim]")
        else:
            self.console.print("[notice]Server: Not configured[/notice]")
        
        self.console.print()
        
        choice = Prompt.ask(
            "[input]Select option[/input]",
            choices=["1", "2", "3", "4", "q", "Q"],
            default="1"
        )
        return choice.upper()
    
    def show_provision_menu(self) -> str:
        self.clear()
        self.show_banner()
        print_section("Provision Options")
        self.console.print()
        self.console.print("[menu.key][1][/menu.key] [menu]Single Device[/menu]")
        self.console.print("[menu.key][2][/menu.key] [menu]All Devices[/menu]")
        self.console.print("[menu.key][B][/menu.key] [menu]← Back[/menu]")
        self.console.print()
        
        choice = Prompt.ask(
            "[input]Select option[/input]",
            choices=["1", "2", "b", "B"],
            default="1"
        )
        return choice.upper()
    
    def prompt_text(self, prompt: str, default: Optional[str] = None, password: bool = False) -> str:
        if password:
            self.console.print(f"[input]{prompt}[/input]", end="")
            if default:
                self.console.print(f" [dim](default: {'*' * len(default)})[/dim]", end="")
            self.console.print(": ", end="")
            value = getpass("")
            return value if value else (default or "")
        else:
            if default:
                prompt_text = f"[input]{prompt}[/input] [dim](default: {default})[/dim]"
            else:
                prompt_text = f"[input]{prompt}[/input]"
            
            value = Prompt.ask(prompt_text, default=default or "")
            return value
    
    def prompt_int(self, prompt: str, default: int, min_val: Optional[int] = None, max_val: Optional[int] = None) -> int:
        while True:
            value_str = self.prompt_text(prompt, str(default))
            try:
                value = int(value_str)
                if min_val is not None and value < min_val:
                    self.print_error(f"Value must be at least {min_val}")
                    continue
                if max_val is not None and value > max_val:
                    self.print_error(f"Value must be at most {max_val}")
                    continue
                return value
            except ValueError:
                self.print_error("Please enter a valid number")
    
    def prompt_confirm(self, prompt: str, default: bool = True) -> bool:
        return Confirm.ask(f"[input]{prompt}[/input]", default=default)
    
    def prompt_selection(self, items: List[Tuple[str, str]], prompt: str = "Select", allow_all: bool = False, allow_back: bool = True) -> List[int]:
        self.console.print()
        for i, (item_id, description) in enumerate(items, 1):
            self.console.print(f"[menu.key][{i}][/menu.key] [menu]{item_id}[/menu] [dim]{description}[/dim]")
        
        if allow_all:
            self.console.print(f"[menu.key][A][/menu.key] [menu]Select All[/menu]")
        if allow_back:
            self.console.print(f"[menu.key][B][/menu.key] [menu]← Back[/menu]")
        
        self.console.print()
        
        # Build valid choices
        valid = [str(i) for i in range(1, len(items) + 1)]
        if allow_all:
            valid.extend(["a", "A"])
        if allow_back:
            valid.extend(["b", "B"])
        
        while True:
            choice = Prompt.ask(f"[input]{prompt}[/input]")
            choice = choice.strip().upper()
            
            if choice == "B" and allow_back:
                return []
            
            if choice == "A" and allow_all:
                return list(range(len(items)))
            
            try:
                if "," in choice:
                    indices = [int(x.strip()) - 1 for x in choice.split(",")]
                else:
                    indices = [int(choice) - 1]
                
                if all(0 <= i < len(items) for i in indices):
                    return indices
                else:
                    self.print_error("Invalid selection")
            except ValueError:
                self.print_error("Invalid input. Enter numbers separated by commas, 'A' for all, or 'B' to go back")
    
    def show_device_table(self, devices: List[dict]) -> None:
        table = Table(
            title="[primary]Discovered Devices[/primary]",
            border_style="secondary",
            header_style="table.header",
        )
        
        table.add_column("#", style="primary", width=3)
        table.add_column("SSID", style="text")
        table.add_column("Signal", style="dim", width=8)
        table.add_column("Model", style="info")
        
        for i, device in enumerate(devices, 1):
            table.add_row(
                str(i),
                device.get("ssid", "Unknown"),
                f"{device.get('signal', 'N/A')} dBm",
                device.get("model", "Unknown")
            )
        
        self.console.print()
        self.console.print(table)
        self.console.print()
    
    def show_progress(self, description: str, total: int = 100):
        return Progress(
            SpinnerColumn(style="input"),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(complete_style="primary", finished_style="success"),
            TaskProgressColumn(),
            console=self.console,
        )
    
    def show_device_progress(self, device_num: int, total_devices: int, device_id: str, steps: List[Tuple[str, str]]) -> None:
        self.console.print()
        self.console.print(f"[primary][{device_num}/{total_devices}][/primary] [text]Provisioning {device_id}[/text]")
        
        for step_name, status in steps:
            self.print_step(step_name, status)
    
    def show_summary(self, success_count: int, fail_count: int, devices: List[dict], ip_col_name: str = "IP") -> None:
        print_section("Provisioning Summary")
        
        self.console.print()
        self.console.print(f"[success]✓ Successful: {success_count}[/success]")
        if fail_count > 0:
            self.console.print(f"[notice]✗ Failed: {fail_count}[/notice]")
        
        if devices:
            self.console.print()
            table = Table(
                border_style="secondary",
                header_style="table.header",
            )
            table.add_column("Device", style="text")
            table.add_column("Name", style="info")
            table.add_column(ip_col_name, style="dim")
            table.add_column("Status", style="text")
            
            for device in devices:
                status_style = "success" if device.get("status") == "OK" else "notice"
                table.add_row(
                    device.get("mac", "Unknown"),
                    device.get("name", "N/A"),
                    device.get("ip", "N/A"),
                    f"[{status_style}]{device.get('status', 'Unknown')}[/{status_style}]"
                )
            
            self.console.print(table)
        
        self.console.print()
        print_divider()
    
    def wait_for_key(self, message: str = "Press Enter to continue...") -> None:
        self.console.print()
        Prompt.ask(f"[dim]{message}[/dim]", default="")
