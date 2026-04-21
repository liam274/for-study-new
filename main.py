"""
file: main.py
author: liam274

This is a project which helps people reduce the self-studying cost, aiming to improve the accurency.

"""

import os
import random
import sys
from typing import Callable, TextIO, Any
from prompt_toolkit import prompt as input
from dataclasses import dataclass
from getch import getche  # type: ignore
import subprocess
import shutil
import curses

SPECIAL_CHARS: str = "~:"


@dataclass
class answer:
    first: bool
    content: set[str]


@dataclass
class return_value:
    try_again: bool
    exit: bool


class parser:
    def __init__(self: parser, path: str):
        self.path = path
        with open(path, "r") as file:
            self.iter = (i for i in file.readlines())
        self.exec()

    def exec(self) -> tuple[tuple[str, ...], ...]:
        result: list[tuple[str, ...]] = []
        for i in self.iter:
            all: list[str] = []
            temp: list[str] = []
            special: str = ""
            skip: bool = False
            for char in i:
                if skip:
                    temp.append(char)
                    skip = False
                    continue
                if char == "\\":
                    skip = True
                    continue
                if char in SPECIAL_CHARS:
                    all.append("".join(temp))
                    special = char
                else:
                    temp.append(char)
            if temp:
                all.append("".join(temp))
            all[0:0] = special
            result.append(tuple(i for i in all))
        return tuple(i for i in result)


old_print = print
path_join = os.path.join


def clear() -> None:
    if os.name == "nt":
        subprocess.call(["cls"])
    else:
        subprocess.call(["clear"])


def print(
    *values: object,
    sep: str = " ",
    end: str = "\n",
    file: TextIO = sys.stdout,
    flush: bool = True,
) -> None:
    old_print("[for study]", *values, sep=sep, end=end, file=file, flush=flush)


def default(value: str, default_value: int) -> int:
    try:
        return int(value)
    except ValueError:
        return default_value


def get_char(prompt: str = "") -> str:
    print(prompt, end="")
    return getche().decode()  # type: ignore


def parse(path: str) -> list[tuple[set[str], answer]]:
    result: list[tuple[set[str], answer]] = []
    for line in parser(path).exec():
        if len(line) < 3:
            print(
                "Error occured when pharsing file, found too few arguments in a line",
                file=sys.stderr,
            )
            sys.exit()
        special_char: str = line[0]  # type: ignore
        if special_char == "~":
            result.append(({line[1]}, answer(first=True, content=set(line[2:]))))
        elif special_char == ":":
            result.append(({line[1]}, answer(first=True, content=set(line[2:]))))
            result.append((set(line[2:]), answer(first=False, content={line[1]})))
    return result


def get_size() -> tuple[int, int]:
    obj: Any = shutil.get_terminal_size()
    return obj.columns, obj.lines


# main function
def unknown(*args: str) -> return_value:
    print("Unknown command: ", args[0])
    return return_value(try_again=False, exit=False)


def study(*args: str) -> return_value:
    """Study a file."""
    result: return_value = return_value(try_again=False, exit=False)
    files: list[str] = []
    flags: set[str] = set()
    for i in args:
        if i.startswith("-"):
            flags.add(i)
        elif os.path.isfile(i):
            files.append(i)
        else:
            print(f"File {i} does not exist, skipping", file=sys.stderr)
    questions: dict[str, answer] = {}
    for i in files:
        temp: list[tuple[set[str], answer]] = parse(i)
        for dic in temp:
            for n in dic[0]:
                questions.update({n: dic[1]})
    if not questions:
        print("No valid file found, exiting", file=sys.stderr)
        return_value(try_again=False, exit=True)
    question_list: list[str] = list(questions.keys())
    random.shuffle(question_list)
    wrong_list: set[tuple[str, int]] = set()
    time: int = 0
    for i in question_list:
        time += 1
        print(f"{time}.", i)
        answer: str = input(">> ")
        trying: int = GLOBALS["chances"]
        while answer not in questions[i].content:
            trying -= 1
            answer = input(">> ")
            if trying == 0:
                break
        if trying == 0:
            print(
                "You've ran out of chances! The correct answers are: ",
                " or ".join(questions[i].content),
            )
        else:
            print("Correct!")
        wrong_list.add((i, trying))
    for i in wrong_list:
        if i[1] < GLOBALS["chances"]:
            print(f"{i[0]}[{i[1]}]")
    return result


def cd(*args: str) -> return_value:
    result = return_value(try_again=False, exit=False)
    if len(args) < 2:
        print("No path provided")
        return result
    os.chdir(args[1])
    return result


def real_nano(stdscr: Any, path: str) -> None:
    curses.echo()
    with open(path, "r") as file:
        content: list[str] = file.readlines()
    for i, line in enumerate(content):
        stdscr.addstr(i, 0, line)
    stdscr.refresh()
    while True:
        key: int = stdscr.getch()
        if key == 27:  # ESC
            break
        elif key in (curses.KEY_BACKSPACE, 127):
            y, x = stdscr.getyx()
            if x > 0:
                stdscr.delch(y, x - 1)
                stdscr.move(y, x - 1)
        elif key == curses.KEY_ENTER or key == 10:
            y, x = stdscr.getyx()
            stdscr.insertln()
            stdscr.move(y + 1, 0)
        else:
            stdscr.addch(key)
    with open(path, "w") as file:
        for i in range(get_size()[1]):
            line = stdscr.instr(i, 0).decode().rstrip()
            file.write(line + "\n")


def nano(*args: str) -> return_value:
    result = return_value(try_again=False, exit=False)
    if len(args) < 2:
        print("No path provided")
        return result
    clear()
    curses.wrapper(real_nano, args[1])
    clear()
    return result


def set_alias(*args: str) -> return_value:
    result = return_value(try_again=False, exit=False)
    if len(args) < 3:
        print("Not enough arguments provided")
        return result
    alias[args[1]] = args[2]
    return result


def mkdir(*args: str) -> return_value:
    result = return_value(try_again=False, exit=False)
    if len(args) < 2:
        print("No path provided")
        return result
    os.mkdir(args[1])
    return result


def cp(*args: str) -> return_value:
    result = return_value(try_again=False, exit=False)
    if len(args) < 2:
        print("Not enough arguments provided")
        return result
    if len(args) < 3:
        shutil.copy(args[1], args[1])
    else:
        shutil.copy(args[1], args[2])
    return result


def mv(*args: str) -> return_value:
    result = return_value(try_again=False, exit=False)
    if len(args) < 2:
        print("Not enough arguments provided")
        return result
    if len(args) < 3:
        shutil.move(args[1], args[1])
    else:
        shutil.move(args[1], args[2])
    return result


def _help(*args: str) -> return_value:
    result = return_value(try_again=False, exit=False)
    if len(args):
        if args[1] in commands:
            print(f"{args[1]}: {commands[args[1]].__doc__}")
        else:
            print("No such command")
        return result
    print("Available commands:")
    for i in commands:
        print(i)
    return result


def _clear(*args: str) -> return_value:
    result = return_value(try_again=False, exit=False)
    clear()
    return result


commands: dict[str, Callable[..., return_value]] = {
    "study": study,
    "cd": cd,
    "nano": nano,
    "cp": cp,
    "mv": mv,
    "alias": set_alias,
    "mkdir": mkdir,
    "help": _help,
    "clear": _clear,
}
alias: dict[str, str] = {}
GLOBALS: dict[str, int] = {}


def executor() -> None:
    _: str = input("How many chances would you like to have? ")
    chances: int = default(_, 10)
    GLOBALS.update({"chances": chances})
    while 1:
        try:
            pre_command: tuple[str, ...] = tuple(input("$ ").split())
            command: str = pre_command[0]
            arguments: tuple[str, ...] = pre_command
            value: return_value = commands.get(command, unknown)(*arguments)
            if value.exit:
                break
            while value.try_again:
                value = commands.get(command, unknown)(*arguments)
                if value.exit:
                    break
            else:
                continue
            break
        except KeyboardInterrupt:
            continue


if __name__ == "__main__":
    print("Hello from study terminal! Type 'help' for available commands.")
    executor()
