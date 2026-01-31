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


def get_console() -> Console:
    """Get the global console instance with RCC theme"""
    global _console
    if _console is None:
        _console = Console(theme=RCC_THEME)
    return _console


def print_styled(text: str, style: str = "text") -> None:
    """Print text with specified style"""
    get_console().print(text, style=style)


def print_primary(text: str) -> None:
    """Print text in primary color"""
    print_styled(text, "primary")


def print_success(text: str) -> None:
    """Print success message"""
    print_styled(f"✓ {text}", "success")


def print_error(text: str) -> None:
    """Print error message"""
    print_styled(f"✗ {text}", "notice")


def print_info(text: str) -> None:
    """Print info message"""
    print_styled(f"ℹ {text}", "info")


def print_warning(text: str) -> None:
    """Print warning message"""
    print_styled(f"⚠ {text}", "notice")


def print_dim(text: str) -> None:
    """Print dimmed/hint text"""
    print_styled(text, "dim")
