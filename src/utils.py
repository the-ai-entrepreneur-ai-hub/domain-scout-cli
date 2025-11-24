import logging
import sys
from pathlib import Path
from colorama import init, Fore, Style

# Init colorama for Windows support
init()

class ColoredFormatter(logging.Formatter):
    """
    Custom formatter to add colors to log levels.
    """
    COLORS = {
        logging.DEBUG: Fore.CYAN,
        logging.INFO: Fore.GREEN,
        logging.WARNING: Fore.YELLOW,
        logging.ERROR: Fore.RED,
        logging.CRITICAL: Fore.RED + Style.BRIGHT,
    }

    def format(self, record):
        color = self.COLORS.get(record.levelno, Fore.WHITE)
        message = super().format(record)
        return f"{color}{message}{Style.RESET_ALL}"

def setup_logger(name: str = "crawler", log_level: int = logging.INFO) -> logging.Logger:
    """
    Sets up a logger with colored console and file handlers.
    """
    logger = logging.getLogger(name)
    logger.setLevel(log_level)
    
    if logger.handlers:
        return logger

    # File Handler (No Colors)
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler = logging.FileHandler(log_dir / "crawler.log", encoding="utf-8")
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # Console Handler (Colored)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(ColoredFormatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%H:%M:%S'))
    logger.addHandler(console_handler)

    return logger

logger = setup_logger()
