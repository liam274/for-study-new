from typing import TextIO
import sys

BOLD: str = "\033[1m"
RESET: str = "\033[0m"
GREEN: str = "\033[32m"
YELLOW: str = "\033[33m"
BLUE: str = "\033[34m"
RED: str = "\033[31m"
PURPLE: str = "\033[35m"
ORANGE: str = "\033[38;5;208m"
SYS_NAME: str = "studyish"
STDERR: TextIO = sys.stderr
META_VERSION: int = 1
MACRO_VERSION: int = 1
SPECIAL_CHARS: str = "~:"
MAGIC_STRINGS: dict[str, str] = {
    "exit": "35c4p3d",
    "pause": "p4u53",
    "skip": "5k1p",
    "manual": "m4nu41",
}
trues: tuple[str, ...] = ("y", "yes", "true")
DIR: dict[str, str] = {".py": YELLOW, ".cpp": YELLOW}
