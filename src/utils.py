import os

# ANSI escape codes for basic colors
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_box(title: str, content: str, tags: str = ""):
    """Prints a visually appealing box in the terminal."""
    width = 60
    border = Colors.CYAN + "╭" + "─" * (width - 2) + "╮" + Colors.ENDC
    bottom_border = Colors.CYAN + "╰" + "─" * (width - 2) + "╯" + Colors.ENDC
    
    print()
    print(border)
    print(Colors.CYAN + "│" + Colors.ENDC + f" {Colors.BOLD}{title.center(width - 4)}{Colors.ENDC} " + Colors.CYAN + "│" + Colors.ENDC)
    print(Colors.CYAN + "├" + "─" * (width - 2) + "┤" + Colors.ENDC)
    
    # Simple word wrap for content
    words = content.split()
    lines = []
    current_line = ""
    for word in words:
        if len(current_line) + len(word) + 1 > width - 4:
            lines.append(current_line)
            current_line = word
        else:
            current_line += f" {word}" if current_line else word
    if current_line:
        lines.append(current_line)
        
    for line in lines:
        padded_line = line.ljust(width - 4)
        print(Colors.CYAN + "│" + Colors.ENDC + f" {padded_line} " + Colors.CYAN + "│" + Colors.ENDC)
        
    if tags:
        print(Colors.CYAN + "│" + " " * (width - 2) + "│" + Colors.ENDC)
        tags_str = f"🏷️  {tags}".ljust(width - 4)
        print(Colors.CYAN + "│" + Colors.ENDC + f" {Colors.YELLOW}{tags_str}{Colors.ENDC} " + Colors.CYAN + "│" + Colors.ENDC)
        
    print(bottom_border)
    print()

def print_header(title: str):
    print(f"\n{Colors.BOLD}{Colors.PURPLE}✦ {title} ✦{Colors.ENDC}\n")
    
# Fallback mapping
Colors.PURPLE = Colors.HEADER
