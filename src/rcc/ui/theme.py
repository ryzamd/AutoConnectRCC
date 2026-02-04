import platform
import ctypes
import os
from rich.console import Console
from rich.theme import Theme

COLORS = {
    "primary": "#da7757",      # Titles, highlights, ASCII art
    "secondary": "#d47151",    # Borders, accents, dividers
    "text": "#96c077",         # Normal text, menu items
    "notice": "#cf6e6e",       # Errors, warnings
    "info": "#5f9ea0",         # Information messages
    "dim": "#6b7280",          # Hints, disabled, version text
    "input": "#e5c07b",        # User input prompts, cursor
    "success": "#98c379",      # Completed, checkmarks
}

RCC_THEME = Theme({
    # Primary colors
    "primary": COLORS["primary"],
    "secondary": COLORS["secondary"],
    "text": COLORS["text"],
    "notice": COLORS["notice"],
    
    # Supplementary colors
    "info": COLORS["info"],
    "dim": COLORS["dim"],
    "input": COLORS["input"],
    "success": COLORS["success"],
    
    # Semantic aliases
    "title": COLORS["primary"],
    "border": COLORS["secondary"],
    "menu": COLORS["text"],
    "menu.key": f"bold {COLORS['primary']}",
    "menu.item": COLORS["text"],
    
    # Status colors
    "status.ok": COLORS["success"],
    "status.error": COLORS["notice"],
    "status.warning": COLORS["notice"],
    "status.pending": COLORS["dim"],
    "status.progress": COLORS["input"],
    
    # Progress bar
    "bar.complete": COLORS["primary"],
    "bar.finished": COLORS["success"],
    "bar.pulse": COLORS["secondary"],
    
    # Input styling
    "prompt": COLORS["input"],
    "prompt.default": COLORS["dim"],
    
    # Log levels
    "log.info": COLORS["info"],
    "log.success": COLORS["success"],
    "log.warning": COLORS["notice"],
    "log.error": COLORS["notice"],
    
    # Table styling
    "table.header": f"bold {COLORS['primary']}",
    "table.border": COLORS["secondary"],
    "table.row": COLORS["text"],
    "table.row.dim": COLORS["dim"],
})

# Global console instance
_console: Console | None = None

def _enable_windows_virtual_terminal():
    if platform.system() == "Windows":
        try:
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.GetStdHandle(-11)
            if handle:
                mode = ctypes.c_ulong()
                if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                    mode.value |= 0x0004
                    kernel32.SetConsoleMode(handle, mode)
        except Exception:
            pass

def get_console() -> Console:
    global _console
    if _console is None:
        _enable_windows_virtual_terminal()
        
        _console = Console(
            theme=RCC_THEME,
            force_terminal=True,
            color_system="truecolor" if platform.system() == "Windows" else "auto"
        )
    return _console


def print_styled(text: str, style: str = "text") -> None:
    get_console().print(text, style=style)


def print_primary(text: str) -> None:
    print_styled(text, "primary")


def print_success(text: str) -> None:
    print_styled(f"✓ {text}", "success")


def print_error(text: str) -> None:
    print_styled(f"✗ {text}", "notice")


def print_info(text: str) -> None:
    print_styled(f"ℹ {text}", "info")


def print_warning(text: str) -> None:
    print_styled(f"⚠ {text}", "notice")


def print_dim(text: str) -> None:
    print_styled(text, "dim")