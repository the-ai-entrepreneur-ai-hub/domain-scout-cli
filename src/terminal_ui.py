"""
Green Terminal UI - Hacker aesthetic for the crawler.
Provides colored output, banners, progress indicators.
"""
import sys
from datetime import datetime
from typing import Optional

# ANSI color codes (work on Windows 10+ with ANSI support)
class Colors:
    GREEN = '\033[92m'
    BRIGHT_GREEN = '\033[1;92m'
    DARK_GREEN = '\033[32m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    DIM = '\033[2m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

# Enable ANSI on Windows
def _enable_ansi():
    if sys.platform == 'win32':
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)

try:
    _enable_ansi()
except:
    pass


class TerminalUI:
    """Green-themed terminal output for crawler."""
    
    def __init__(self, quiet: bool = False):
        self.quiet = quiet
        self.start_time = datetime.now()
    
    def banner(self):
        """Print startup banner."""
        if self.quiet:
            return
        b = f"""{Colors.BRIGHT_GREEN}
+==============================================================+
|   ____  ___  _    ___    ____ ___ ____  _____                |
|  / ___|/ _ \\| |  |  _ \\  |  _ \\_ _|  _ \\| ____|              |
| | |  _| | | | |  | | | | | |_) | || |_) |  _|                |
| | |_| | |_| | |__| |_| | |  __/| ||  __/| |___               |
|  \\____|\\___/|____|____/  |_|  |___|_|   |_____|              |
|                                                              |
|  Legal Entity Extraction Pipeline v2.0                       |
|  JSON-LD First - Country-Specific Patterns - RDAP Enrichment |
+==============================================================+{Colors.RESET}
"""
        print(b)
    
    def log(self, msg: str, level: str = "info"):
        """Print timestamped log message."""
        if self.quiet and level == "debug":
            return
        
        ts = datetime.now().strftime("%H:%M:%S")
        
        if level == "success":
            prefix = f"{Colors.BRIGHT_GREEN}[+]{Colors.RESET}"
        elif level == "error":
            prefix = f"{Colors.RED}[x]{Colors.RESET}"
        elif level == "warn":
            prefix = f"{Colors.YELLOW}[!]{Colors.RESET}"
        elif level == "info":
            prefix = f"{Colors.GREEN}[>]{Colors.RESET}"
        elif level == "debug":
            prefix = f"{Colors.DIM}[.]{Colors.RESET}"
        else:
            prefix = f"{Colors.GREEN}[*]{Colors.RESET}"
        
        print(f"{Colors.DIM}{ts}{Colors.RESET} {prefix} {msg}")
    
    def domain_start(self, domain: str, index: int, total: int):
        """Log domain processing start."""
        pct = (index / total * 100) if total > 0 else 0
        self.log(f"{Colors.CYAN}{domain}{Colors.RESET} [{index}/{total}] {Colors.DIM}({pct:.0f}%){Colors.RESET}", "info")
    
    def domain_success(self, domain: str, legal_name: str = "", method: str = ""):
        """Log successful extraction."""
        extra = ""
        if legal_name:
            extra = f" -> {Colors.WHITE}{legal_name[:40]}{Colors.RESET}"
        if method:
            extra += f" {Colors.DIM}({method}){Colors.RESET}"
        self.log(f"{Colors.GREEN}{domain}{Colors.RESET}{extra}", "success")
    
    def domain_fail(self, domain: str, reason: str = ""):
        """Log failed extraction."""
        extra = f" {Colors.DIM}({reason}){Colors.RESET}" if reason else ""
        self.log(f"{Colors.RED}{domain}{Colors.RESET}{extra}", "error")
    
    def stats(self, processed: int, success: int, failed: int, legal_found: int):
        """Print current stats."""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        rate = processed / elapsed if elapsed > 0 else 0
        
        print(f"\n{Colors.GREEN}{'-' * 50}{Colors.RESET}")
        print(f"{Colors.BRIGHT_GREEN}  Processed: {processed:>5}  |  Success: {success:>5}  |  Failed: {failed:>5}{Colors.RESET}")
        print(f"{Colors.GREEN}  Legal Found: {legal_found:>4}  |  Rate: {rate:.1f}/sec  |  Time: {elapsed:.0f}s{Colors.RESET}")
        print(f"{Colors.GREEN}{'-' * 50}{Colors.RESET}\n")
    
    def final_report(self, stats: dict):
        """Print final summary."""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        
        print(f"\n{Colors.BRIGHT_GREEN}{'=' * 60}{Colors.RESET}")
        print(f"{Colors.BRIGHT_GREEN}  EXTRACTION COMPLETE{Colors.RESET}")
        print(f"{Colors.GREEN}{'-' * 60}{Colors.RESET}")
        print(f"  {Colors.WHITE}Domains Processed:{Colors.RESET}  {stats.get('processed', 0)}")
        print(f"  {Colors.GREEN}Successful:{Colors.RESET}         {stats.get('success', 0)}")
        print(f"  {Colors.RED}Failed:{Colors.RESET}             {stats.get('failed', 0)}")
        print(f"  {Colors.CYAN}Legal Entities:{Colors.RESET}     {stats.get('legal_found', 0)}")
        print(f"  {Colors.DIM}Duration:{Colors.RESET}           {elapsed:.1f}s")
        print(f"{Colors.BRIGHT_GREEN}{'=' * 60}{Colors.RESET}\n")


# Global instance for easy access
_ui: Optional[TerminalUI] = None

def get_ui(quiet: bool = False) -> TerminalUI:
    global _ui
    if _ui is None:
        _ui = TerminalUI(quiet=quiet)
    return _ui
