"""
file: main.py
author: liam274

This is a project which helps people reduce the self-studying cost, aiming to improve the accurency.

"""

import os
import random
import sys
from typing import Callable, Any

from prompt_toolkit import prompt as input
from dataclasses import dataclass
from getch import getche  # type: ignore
import subprocess
import shutil
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.key_binding import KeyBindings

# from rich import print
from ubelt import shrinkuser  # type: ignore

SPECIAL_CHARS: str = "~:"
MAGIC_STRING: str = "35c4p3d"
trues: set[str] = {"y", "yes", "true"}


@dataclass
class answer:
    first: bool
    content: set[str]


@dataclass
class return_value:
    try_again: bool
    exit: bool


bindings = KeyBindings()


@bindings.add("tab")
def _(event: Any):
    event.current_buffer.insert_text("\t")


class parser:
    def __init__(self: parser, path: str):
        with open(path, "r") as file:
            self.iter = (i.rstrip("\n") for i in file.readlines())

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
                    temp.clear()
                else:
                    temp.append(char)
            if temp:
                all.append("".join(temp))
            all[0:0] = special
            result.append(tuple(i for i in all))
        return tuple(result)


def clear() -> None:
    if os.name == "nt":
        subprocess.call(["cls"])
    else:
        subprocess.call(["clear"])


def default(value: str, default_value: int) -> int:
    try:
        return int(value)
    except ValueError:
        return default_value


def get_char(prompt: str = "") -> str:
    print(prompt, end="")
    return getche().decode()  # type: ignore


def parse(path: str) -> tuple[list[tuple[set[str], answer]], str]:
    result: list[tuple[set[str], answer]] = []
    _ = parser(path).exec()
    for line in _[1:]:
        if len(line) < 3:
            print(
                "Error occured when pharsing file, found too few arguments in a line",
                file=sys.stderr,
            )
            return result, ""
        special_char: str = line[0]  # type: ignore
        if special_char == "~":
            result.append(({line[1]}, answer(first=True, content=set(line[2:]))))
        elif special_char == ":":
            result.append(({line[1]}, answer(first=True, content=set(line[2:]))))
            result.append((set(line[2:]), answer(first=False, content={line[1]})))
    return result, _[0][0]


def get_size() -> tuple[int, int]:
    obj: Any = shutil.get_terminal_size()
    return obj.columns, obj.lines


# main function
def unknown(*args: str) -> return_value:
    print("Unknown command:", args[0])
    return return_value(try_again=False, exit=False)


def study(*args: str) -> return_value:
    """Study a file."""
    result: return_value = return_value(try_again=False, exit=False)
    files: list[str] = []
    flags: set[str] = set()
    for i in args[1:]:
        if i.startswith("-"):
            flags.add(i)
        elif os.path.isfile(i):
            files.append(i)
        else:
            print(f"File {i} does not exist, skipping", file=sys.stderr)
    questions: dict[str, answer] = {}
    titles: list[str] = []
    for i in files:
        temp: list[tuple[set[str], answer]]
        title: str
        temp, title = parse(i)
        if not title:
            print(f"File {i} is not valid, skipping", file=sys.stderr)
            continue
        titles.append(title)
        for dic in temp:
            for n in dic[0]:
                questions.update({n: dic[1]})
    if not questions:
        print("No valid file found, exiting", file=sys.stderr)
        return result
    question_list: list[str] = list(questions.keys())
    random.shuffle(question_list)
    wrong_list: set[tuple[str, int]] = set()
    time: int = 0
    title: str = " & ".join(titles)
    for i in question_list:
        clear()
        print(title)
        time += 1
        print(f"{time}.", i)
        trying: int = GLOBALS["chances"]
        ans: str
        while questions[i].content:
            ans = questions[i].content.pop()
            answer: str = input(">> ")
            while answer != ans:
                if answer == MAGIC_STRING:
                    print("Magic string detected, exiting...")
                    return result
                trying -= 1
                print("You're wrong! Please try again.")
                answer = input(">> ")
                if trying == 0:
                    break
            if trying == 0:
                print(
                    "You've ran out of chances! The correct answers are: ",
                    " and ".join(questions[i].content),
                )
            else:
                print("Correct!")
        wrong_list.add((i, trying))
    for i in wrong_list:
        if i[1] < GLOBALS["chances"]:
            print(f"{i[0]}[{i[1]}]")
    return result


def cd(*args: str) -> return_value:
    global working_dir, prompt
    result = return_value(try_again=False, exit=False)
    if len(args) < 2:
        print("No path provided")
        return result
    if not os.path.isdir(args[1]):
        print(f"{args[1]} is not a directory")
        return result
    os.chdir(args[1])
    working_dir = shrinkuser(os.getcwd())
    prompt = (
        f"{BOLD}{GREEN}{username}{RESET}{BOLD}:{BLUE}{working_dir}{YELLOW} $ {RESET}"
    )
    return result


def nano(*args: str) -> return_value:
    result = return_value(try_again=False, exit=False)
    if len(args) < 2:
        print("No path provided")
        return result
    if os.path.isdir(args[1]):
        print(f"{args[1]} is a directory")
        return result
    clear()
    print(args)
    subprocess.call(["nano", args[1]])
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
    if len(args) > 1:
        if args[1] in commands:
            print(f"{args[1]}: {commands[args[1]].__doc__}")
        else:
            print("No such command")
        return result
    print("Available commands:")
    for i in commands:
        print(" " * 17, i)
    print("Magic string(for escaping when you're studying):", MAGIC_STRING)
    return result


def _clear(*args: str) -> return_value:
    result = return_value(try_again=False, exit=False)
    clear()
    return result


def _exec(*args: str) -> return_value:
    result = return_value(try_again=False, exit=False)
    if len(args) < 2:
        print("No command provided")
        return result
    print(eval(" ".join(args[1:])))
    return result


def _set(*args: str) -> return_value:
    result = return_value(try_again=False, exit=False)
    if len(args) < 3:
        print("Not enough arguments provided")
        return result
    if args[1] not in DEFAULTS:
        GLOBALS[args[1]] = int(args[2])
    else:
        GLOBALS[args[1]] = default(args[2], DEFAULTS[args[1]])
    return result


def ls(*args: str) -> return_value:
    result = return_value(try_again=False, exit=False)
    for [_, dirs, files] in os.walk(os.getcwd()):
        for dir in dirs:
            if dir.startswith("."):
                continue
            print(dir + "/")
        for file in files:
            if file.startswith("."):
                continue
            print(file)
        dirs.clear()
    return result


def cat(*args: str) -> return_value:
    result = return_value(try_again=False, exit=False)
    if len(args) < 2:
        print("No path provided")
        return result
    if os.path.isdir(args[1]):
        print(f"{args[1]} is a directory")
        return result
    if not os.path.isfile(args[1]):
        print(f"{args[1]} does not exist")
        return result
    with open(args[1], "r") as file:
        print(file.read())
    return result


def whoami(*args: str) -> return_value:
    result = return_value(try_again=False, exit=False)
    print(f'You are "{username}", who has been studying hard!')
    return result


def echo(*args: str) -> return_value:
    result = return_value(try_again=False, exit=False)
    print(" ".join(args[1:]))
    return result


def restart(*args: str) -> return_value:
    result = return_value(try_again=False, exit=False)
    print("Restarting...")
    os.execv(sys.executable, [sys.executable] + sys.argv)
    sys.exit()
    return result


def rm(*args: str) -> return_value:
    result = return_value(try_again=False, exit=False)
    if len(args) < 2:
        print("No path provided")
        return result
    if os.path.isdir(args[1]):
        print(f"{args[1]} is a directory")
        return result
    if not os.path.isfile(args[1]):
        print(f"{args[1]} does not exist")
        return result
    answer = input(f'Are you sure you want to delete file "{args[1]}"? (y/n) ')
    if answer.lower() in trues:
        os.remove(args[1])
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
    "exec": _exec,
    "set": _set,
    "exit": lambda *args: return_value(try_again=False, exit=True),
    "ls": ls,
    "cat": cat,
    "whoami": whoami,
    "echo": echo,
    "refresh": restart,
    "rm": rm,
}
alias: dict[str, str] = {}
GLOBALS: dict[str, int] = {"chances": 10}
DEFAULTS: dict[str, int] = {"chances": 10}
username: str = os.getenv("USER", "student")
BOLD = "\033[1m"
RESET = "\033[0m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
working_dir: str = shrinkuser(os.getcwd())
prompt = f"{BOLD}{GREEN}{username}{RESET}{BOLD}:{BLUE}{working_dir}{YELLOW} $ {RESET}"


def executor() -> None:
    while 1:
        try:
            pre_command: tuple[str, ...] = tuple(
                input(ANSI(prompt), key_bindings=bindings).split()
            )
            command: str = pre_command[0]
            command = alias.get(command, command)
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
            print()
            continue


if __name__ == "__main__":
    print("Hello from study terminal! Type 'help' for available commands.")
    executor()
