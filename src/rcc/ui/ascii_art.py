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

# Stylized banner with box characters (matching user's image style)
RCC_BANNER_STYLED = r"""
[primary]┌──────┐ ┌──────┐ ┌──────┐[/primary]
[primary]│[/primary][secondary]██████ [/secondary][primary]│ │[/primary][secondary]██████[/secondary][primary]│ │[/primary][secondary]██████[/secondary][primary]│[/primary]
[primary]│[/primary][secondary]██  ███[/secondary][primary]│ │[/primary][secondary]██[/secondary][primary]    │ │[/primary][secondary]██[/secondary][primary]    │[/primary]
[primary]│[/primary][secondary]██████ [/secondary][primary]│ │[/primary][secondary]██[/secondary][primary]    │ │[/primary][secondary]██[/secondary][primary]    │[/primary]
[primary]│[/primary][secondary]██   ██[/secondary][primary]│ │[/primary][secondary]██[/secondary][primary]    │ │[/primary][secondary]██[/secondary][primary]    │[/primary]
[primary]│[/primary][secondary]██   ██[/secondary][primary]│ │[/primary][secondary]██████[/secondary][primary]│ │[/primary][secondary]██████[/secondary][primary]│[/primary]
[primary]└──────┘ └──────┘ └──────┘[/primary]
"""

# Simple block banner
RCC_BANNER_BLOCKS = """
[primary]██████╗   ██████╗   ██████╗[/primary]
[primary]██[/primary][dim]╔══[/dim][primary]██╗  ██[/primary][dim]╔════╝[/dim]  [primary]██[/primary][dim]╔════╝[/dim]
[primary]██████[/primary][dim]╔╝[/dim]  [primary]██[/primary][dim]║[/dim]       [primary]██[/primary][dim]║[/dim]     
[primary]██[/primary][dim]╔══[/dim][primary]██╗  ██[/primary][dim]║[/dim]       [primary]██[/primary][dim]║[/dim]     
[primary]██[/primary][dim]║[/dim]  [primary]██[/primary][dim]║[/dim]  [dim]╚[/dim][primary]██████╗  [/primary][dim]╚[/dim][primary]██████╗[/primary]
[dim]╚═╝  ╚═╝   ╚═════╝   ╚═════╝[/dim]
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
