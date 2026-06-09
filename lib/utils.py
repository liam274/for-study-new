from collections import deque
from dataclasses import dataclass, field
from prompt_toolkit.completion import (
    Completer,
    Completion,
    PathCompleter,
    CompleteEvent,
)
from prompt_toolkit.document import Document
from typing import Iterator, Callable, Any
import datetime
import pulsectl  # type: ignore
import requests
import os
import subprocess
from .constants import *
from getch import getche  # type: ignore
import shutil
import pathlib


@dataclass
class answer:
    first: bool
    content: set[str]
    rules: dict[str, set[tuple[str, ...]]]


@dataclass
class return_value:
    try_again: bool
    exit: bool
    flag: set[str] = field(default_factory=lambda: set())


class StudyCompleter(Completer):  # deepseek's job
    def __init__(self, cmd_list: Callable[[], set[str]]):
        self.path_completer = PathCompleter(expanduser=True)
        self.cmd_list = cmd_list

    def get_completions(self, document: Document, complete_event: CompleteEvent):
        text = document.text_before_cursor
        words = text.split()
        if not words:
            return
        if len(words) == 1 and not text.endswith(" "):
            current = words[0]
            for cmd in self.cmd_list():
                if cmd.startswith(current):
                    yield Completion(cmd, start_position=-len(current))
            return
        last_space = text.rfind(" ")
        if last_space == -1:
            return
        partial_path = text[last_space + 1 :]
        path_doc = Document(text=partial_path, cursor_position=len(partial_path))

        for comp in self.path_completer.get_completions(path_doc, complete_event):
            full_path = partial_path + comp.text
            if " " in full_path:
                full_path = f'"{full_path}"'
            yield Completion(
                full_path, start_position=-len(partial_path), display=comp.display
            )


class ExtendableIterator[T]:  # deepseek's job
    def __init__(self, initial_iterator: Iterator[T]):
        self._source = initial_iterator  # original iterator
        self._buffer: deque[T] = deque()  # items added dynamically
        self._exhausted = False

    def __iter__(self):
        return self

    def __next__(self):
        # First, try to yield from the buffer
        if self._buffer:
            return self._buffer.popleft()
        # Buffer empty – try the original source
        try:
            return next(self._source)
        except StopIteration:
            self._exhausted = True
            raise

    def extend(self, items: T):
        """Add more items to be yielded later."""
        self._buffer.extend((items,))

    def is_exhausted(self):
        """Return True if both source and buffer are empty."""
        return self._exhausted and not self._buffer


def fetch(url: str, timeout: int = 10) -> list[Any]:
    """fetch url and return"""
    try:
        resp = requests.get(url, timeout=timeout)
    except Exception as e:
        print("Ouch! The console cannot reach the server...")
        log(f'Fetch for url "{url}" failed: {e}', "ERROR")
        return []
    return resp.json()


def clear() -> None:
    """clear screen"""
    if os.name == "nt":
        subprocess.call(["cls"])
    else:
        subprocess.call(["clear"])


def default(value: str, default_value: int = 0) -> int:
    """return default if not int"""
    try:
        return int(value)
    except ValueError:
        return default_value


def getchar(prompt: str = "") -> str:
    """Get char"""
    print(prompt, end="", flush=True)
    g = getche()  # type: ignore
    print()
    return g  # type: ignore


def log(content: str, level: str):
    """log file"""
    if not os.path.isdir("logs/"):
        os.mkdir("logs/")
    with open(f"logs/{datetime.datetime.today()}.log", "a+", encoding="utf-8") as file:
        file.write(f"{datetime.datetime.now()} {level} {content}")


def is_volume_on():
    """check if the computer's volume is not muted (on)"""
    try:
        with pulsectl.Pulse("volume-check") as pulse:
            sink = pulse.get_sink_by_name(pulse.server_info().default_sink_name)  # type: ignore
            return not sink.mute  # type: ignore
    except Exception as e:
        log(f"is_volume_on failed: {e}", "WARN")
        return True


def get_size() -> tuple[int, int]:
    """get size of terminal"""
    obj: Any = shutil.get_terminal_size()
    return obj.columns, obj.lines


def conflict(data: str) -> str:  # mvp
    """return conflict"""
    if data == "do-filling":
        return "no-filling"
    if data == "no-filling":
        return "do-filling"
    return ""


def safe_int(data: str) -> int:
    """int data safely"""
    try:
        return int(data)
    except:
        return 0


def confirm_input(prompt: str, no_strip: bool = False) -> str:
    """Return the confirmed input"""
    result: str
    ans: str
    while result := input(prompt):
        if (ans := input("Are you sure?").strip()) in trues:
            break
        if ans == MAGIC_STRINGS["exit"]:
            print("Action Canceled")
            return ""
    return result if no_strip else result.strip()


def get_clr(file: str) -> str:
    """get the color of the suitable"""
    path: pathlib.Path = pathlib.Path(file)
    if os.access(path, os.X_OK):
        return BOLD + GREEN
    return BOLD + DIR.get(path.suffix, RESET)


def safe_float(data: str) -> float:
    """convert to float safely"""
    try:
        return float(data)
    except:
        return 0
