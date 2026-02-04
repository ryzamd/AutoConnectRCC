from .theme import get_console, COLORS

# ASCII Art Banner - Block style similar to user's reference image
RCC_BANNER = r"""
[primary]
 ██████╗   ██████╗   ██████╗
 ██╔══██╗ ██╔════╝  ██╔════╝
 ██████╔╝ ██║       ██║
 ██╔══██╗ ██║       ██║
 ██║  ██║ ╚██████╗  ╚██████╗
 ╚═╝  ╚═╝  ╚═════╝   ╚═════╝
[/primary]
"""

# Alternative compact banner
RCC_BANNER_COMPACT = r"""
[primary]
 ╦═╗ ╔═╗ ╔═╗
 ╠╦╝ ║   ║
 ╩╚═ ╚═╝ ╚═╝
[/primary]
"""

SUBTITLE = "[dim]P R O V I S I O N E R   v1.0.0[/dim]"

DIVIDER = "[secondary]─────────────────────────────────────────[/secondary]"


def print_banner(compact: bool = False) -> None:
    """Print the RCC banner with styling"""
    console = get_console()
    
    # Clear screen
    console.clear()
    
    # Print banner
    if compact:
        console.print(RCC_BANNER_COMPACT)
    else:
        console.print(RCC_BANNER)
    
    # Print subtitle
    console.print(SUBTITLE)
    console.print(DIVIDER)
    console.print()


def print_divider() -> None:
    """Print a styled divider line"""
    get_console().print(DIVIDER)


def print_section(title: str) -> None:
    """Print a section header"""
    console = get_console()
    console.print()
    console.print(f"[primary]{title}[/primary]")
    console.print(DIVIDER)
