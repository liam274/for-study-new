#!/usr/bin/python
"""
file: main.py
author: liam274

This is a project which helps people reduce the self-studying cost, aiming to improve the accurency.

"""

import os
import random
import sys
from typing import Callable, Any, Iterator
import requests
import itertools
from collections import deque

from prompt_toolkit import prompt as input
from dataclasses import dataclass
from getch import getche  # type: ignore
import subprocess
import shutil
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.completion import (
    Completer,
    Completion,
    PathCompleter,
    CompleteEvent,
)
from prompt_toolkit.document import Document

# from rich import print
from ubelt import shrinkuser  # type: ignore
import time as time_module

SPECIAL_CHARS: str = "~:"
MAGIC_STRING: str = "35c4p3d"
trues: tuple[str, ...] = ("y", "yes", "true")
PATH: str = os.getcwd()


@dataclass
class answer:
    first: bool
    content: set[str]


@dataclass
class return_value:
    try_again: bool
    exit: bool


class StudyCompleter(Completer):
    def __init__(self):
        self.cmd_list = list(commands.keys()) + list(alias.keys())
        # 注意：如果你的库确实不支持 quote_char，请勿传入该参数
        self.path_completer = PathCompleter(expanduser=True)

    def get_completions(self, document: Document, complete_event: CompleteEvent):
        text = document.text_before_cursor
        words = text.split()
        if not words:
            return

        # 命令补全
        if len(words) == 1 and not text.endswith(" "):
            current = words[0]
            for cmd in self.cmd_list:
                if cmd.startswith(current):
                    yield Completion(cmd, start_position=-len(current))
            return

        # 路径补全
        last_space = text.rfind(" ")
        if last_space == -1:
            return
        partial_path = text[last_space + 1 :]  # 用户已输入的路径片段
        path_doc = Document(text=partial_path, cursor_position=len(partial_path))

        for comp in self.path_completer.get_completions(path_doc, complete_event):
            # comp.text 是 PathCompleter 给出的剩余补全部分（不含已输入前缀）
            full_path = partial_path + comp.text  # 拼接出完整路径
            # 如果完整路径含有空格，加双引号包裹
            if " " in full_path:
                full_path = f'"{full_path}"'

            # 替换范围：从 partial_path 开始的部分全部替换为 full_path
            yield Completion(
                full_path, start_position=-len(partial_path), display=comp.display
            )


class ExtendableIterator[T]:
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


basic: Callable[[str], Iterator[str]] = lambda x: (i.strip() for i in x.split(",,"))

modify: dict[str, Callable[[str], Iterator[str]]] = {
    "dismiss": basic,
    "set": basic,
    "mode": basic,
    "define": basic,
}


class meta_data_parser:
    def __init__(self: meta_data_parser):
        self.data: dict[str, list[tuple[str, ...]]] = {
            "dismiss": [],
            "set": [],
            "mode": [],
            "define": [],
        }

    def meta(self: meta_data_parser, data: Iterator[str]):
        macro: dict[str, str] = {}
        data, data2 = itertools.tee(data)
        dataa: ExtendableIterator[str] = ExtendableIterator(data)
        for line_num, line in enumerate(dataa):
            if line[0] != "%":
                continue
            if line[1] == "%":  # comment
                continue
            try:
                if line.startswith("%define"):
                    _, name, value = line.split(maxsplit=2)
                    macro[name] = value.strip('"')
                elif line.startswith("%include"):
                    _, name = line.split(maxsplit=2)
                    if not os.path.exists(name):
                        print(f"Error occurred when trying to open file {name}")
                    s: list[str] = []
                    meta: bool = False
                    with open(name, encoding="utf-8") as file:
                        for i in file.readlines():
                            i = i.strip()
                            if i == "[meta start]":
                                meta = True
                            elif i == "[meta end]":
                                meta = False
                            if meta:
                                s.append(i)
                    data2 = itertools.chain(data2, (i for i in s))
                elif line.startswith("%import"):
                    _, name = line.split(maxsplit=2)
                    if not os.path.exists(name):
                        print(f"Error occurred when trying to open file {name}")
                    meta: bool = False
                    with open(name, encoding="utf-8") as file:
                        for i in file.readlines():
                            i = i.strip()
                            if i == "[meta start]":
                                meta = True
                            elif i == "[meta end]":
                                meta = False
                            if meta:
                                dataa.extend(i)
            except ValueError:
                print(
                    f'Error occurred at line {line_num}, macro "{line.split(" ")[0]}" does not have enough parameter'
                )

        for ln, _ in enumerate(data2):
            if _.startswith("%"):
                continue
            if ":" not in _:
                print(f'Error occurred at line {ln}, separator ":" expected')
                return
            command, argument = _.split(":", maxsplit=1)
            self.data[command] += list(
                tuple(macro.get(i, i).split("^")) for i in modify[command](argument)
            )

    def run_rule(self: meta_data_parser, data: str) -> str:
        for rule in self.data["dismiss"]:
            data = data.replace(rule[0], "")
        for rule in self.data["define"]:
            data = data.replace(rule[0], rule[1])
        return data


class parser:
    def __init__(self: parser, path: str):
        with open(path, "r", encoding="utf-8") as file:
            self.iter = (i.rstrip("\n") for i in file.readlines())

    def exec(
        self,
    ) -> tuple[tuple[tuple[str, ...], ...], dict[str, list[tuple[str, ...]]]]:
        result: list[tuple[str, ...]] = []
        is_meta: bool = False
        metas: list[str] = []
        meta_data: meta_data_parser = meta_data_parser()
        data: list[str] = []
        for i in self.iter:
            if is_meta:
                if i == "[meta end]":
                    is_meta = False
                    meta_data.meta(i for i in metas)
                else:
                    metas.append(i)
                continue
            if i == "[meta start]":
                is_meta = True
                continue
            data.append(i)
        for i in meta_data.run_rule("\n".join(data)).split("\n"):
            all: list[str] = []
            temp: list[str] = []
            special: str = ""
            skip: bool = False
            in_formula: bool = False
            form: str = ""
            t: int = -1
            for char in i:
                t += 1
                if in_formula:
                    form += char
                    if char == ">":
                        in_formula = False
                        special = form
                    continue
                if skip:
                    temp.append(char)
                    skip = False
                    continue
                if char == "\\":
                    skip = True
                    continue
                if char == "-" and len(i) > t + 1 and i[t + 1] in "(>":
                    in_formula = True
                    form = "-"
                    all.append("".join(temp))
                    temp.clear()
                    continue
                if char in SPECIAL_CHARS:
                    all.append("".join(temp))
                    special = char
                    temp.clear()
                else:
                    temp.append(char)
            if temp:
                all.append("".join(temp))
            if special:
                all[0:0] = [special]
            result.append(tuple(i for i in all))
        return tuple(result), meta_data.data


def fetch(url: str, timeout: int = 10) -> list[Any]:
    try:
        resp = requests.get(url, timeout=timeout)
    except Exception as e:
        print("Ouch! The console cannot reach the server...")
        print(e)
        sys.exit(-1)
    return resp.json()


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


def parse(
    path: str,
) -> tuple[tuple[list[tuple[set[str], answer]], str], dict[str, list[tuple[str, ...]]]]:
    result: list[tuple[set[str], answer]] = []
    _, rules = parser(path).exec()
    for line in _[1:]:
        if len(line) < 3:
            print(
                "Error occured when pharsing file, found too few arguments in a line",
                file=sys.stderr,
            )
            return (result, ""), {}
        special_char: str = line[0]  # type: ignore
        if special_char == "~":
            result.append(({line[1]}, answer(first=True, content=set(line[2:]))))
        elif special_char == ":":
            result.append(({line[1]}, answer(first=True, content=set(line[2:]))))
            result.append((set(line[2:]), answer(first=False, content={line[1]})))
        elif special_char.startswith("-("):
            result.append(
                (
                    {line[1] + special_char},
                    answer(
                        first=True, content=set(i.strip() for i in line[2].split("+"))
                    ),
                )
            )
            result.append(
                (
                    {special_char + line[2]},
                    answer(
                        first=False, content=set(i.strip() for i in line[1].split("+"))
                    ),
                )
            )
    return (result, _[0][0]), rules


def get_size() -> tuple[int, int]:
    obj: Any = shutil.get_terminal_size()
    return obj.columns, obj.lines


# main function
def unknown(flags: list[str], *args: str) -> return_value:
    print("Unknown command:", args[0])
    return return_value(try_again=False, exit=False)


def study(_: list[str], *args: str) -> return_value:
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
    rule: dict[str, set[tuple[str, ...]]] = {}
    for i in files:
        _: list[tuple[set[str], answer]]
        title: str
        (_, title), rule_temp = parse(i)
        for name, _rule in rule_temp.items():
            rule.update({name: set(_rule).union(rule.get(name, set()))})
        if not title:
            print(f"File {i} is not valid, skipping", file=sys.stderr)
            continue
        titles.append(title)
        for dic in _:
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
    total: int = len(question_list)
    history = InMemoryHistory()
    if len(set(rule["mode"])) > 1:
        print(
            f"Error occurred when trying to study with {{{", ".join(args)}}}, found multiple mode. You may only study in one mode at a time."
        )
        return result
    for i in question_list:
        clear()
        print(title)
        time += 1
        temp: answer = questions[i]
        sets: set[str] = temp.content
        splitor: str = (
            " ".join(["_"] * len("".join(sets)))
            if ("do-filling",) in rule["set"]
            else ""
        )
        if temp.first:
            i += " " + splitor
        else:
            i = splitor + " " + i
        qer: str = (len(f"{time}{total} ")) * " "
        print(f"({time}/{total})", i)
        trying: int = GLOBALS["chances"]
        while (
            answer := set(
                i.strip() for i in input(qer + ">> ", history=history).split("+")
            )
        ) != sets:
            if MAGIC_STRING in answer:
                print("Magic string detected, exiting...")
                return result
            trying -= 1
            print("You're wrong! Please try again.")
            if trying == 0:
                print(
                    "You've ran out of chances! The correct answers are: ",
                    " and ".join(sets),
                )
                break
        else:
            print("Correct!")
            time_module.sleep(0.1)
            continue
        wrong_list.add((i, trying))
    for i in wrong_list:
        if i[1] < GLOBALS["chances"]:
            print(f"{i[0]}[{i[1]}]")
    if input("try again? ").strip().lower() in trues:
        return return_value(exit=False, try_again=True)
    return result


def cd(flags: list[str], *args: str) -> return_value:
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


def vim(flags: list[str], *args: str) -> return_value:
    result = return_value(try_again=False, exit=False)
    if len(args) < 2:
        print("No path provided")
        return result
    if os.path.isdir(args[1]):
        print(f"{args[1]} is a directory")
        return result
    subprocess.call(["vim", args[1], *flags])
    return result


def set_alias(flags: list[str], *args: str) -> return_value:
    result = return_value(try_again=False, exit=False)
    if len(args) < 3:
        print("Not enough arguments provided")
        return result
    alias[args[1]] = args[2]
    return result


def mkdir(flags: list[str], *args: str) -> return_value:
    result = return_value(try_again=False, exit=False)
    if len(args) < 2:
        print("No path provided")
        return result
    os.mkdir(args[1])
    return result


def cp(flags: list[str], *args: str) -> return_value:
    result = return_value(try_again=False, exit=False)
    if len(args) < 2:
        print("Not enough arguments provided")
        return result
    if len(args) < 3:
        shutil.copy(args[1], args[1])
    else:
        shutil.copy(args[1], args[2])
    return result


def mv(flags: list[str], *args: str) -> return_value:
    result = return_value(try_again=False, exit=False)
    if len(args) < 2:
        print("Not enough arguments provided")
        return result
    if len(args) < 3:
        shutil.move(args[1], args[1])
    else:
        shutil.move(args[1], args[2])
    return result


def _help(flags: list[str], *args: str) -> return_value:
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


def _clear(flags: list[str], *args: str) -> return_value:
    result = return_value(try_again=False, exit=False)
    clear()
    return result


def _exec(flags: list[str], *args: str) -> return_value:
    result = return_value(try_again=False, exit=False)
    if len(args) < 2:
        print("No command provided")
        return result
    print(eval(" ".join(args[1:])))
    return result


def _set(flags: list[str], *args: str) -> return_value:
    result = return_value(try_again=False, exit=False)
    if len(args) < 3:
        print("Not enough arguments provided")
        return result
    if args[1] not in DEFAULTS:
        GLOBALS[args[1]] = int(args[2])
    else:
        GLOBALS[args[1]] = default(args[2], DEFAULTS[args[1]])
    return result


def ls(flags: list[str], *args: str) -> return_value:
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


def cat(flags: list[str], *args: str) -> return_value:
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
    with open(args[1], "r", encoding="utf-8") as file:
        print(file.read())
    return result


def whoami(flags: list[str], *args: str) -> return_value:
    result = return_value(try_again=False, exit=False)
    print(f'You are "{username}", who has been studying hard!')
    return result


def echo(flags: list[str], *args: str) -> return_value:
    result = return_value(try_again=False, exit=False)
    print(" ".join(args[1:]))
    return result


def restart(flags: list[str], *args: str) -> return_value:
    result = return_value(try_again=False, exit=False)
    print("Restarting...")
    os.execv(sys.executable, [sys.executable, os.path.join(PATH, sys.argv[0])])
    sys.exit()
    return result


def rm(flags: list[str], *args: str) -> return_value:
    result = return_value(try_again=False, exit=False)
    if len(args) < 2:
        print("No path provided")
        return result
    for path in args[1:]:
        if os.path.isdir(path):
            print(f"{path} is a directory")
            return result
        if not os.path.isfile(path):
            print(f"{path} does not exist")
            return result
        answer = (
            input(f'Are you sure you want to delete file "{path}"? (y/n) ')
            if "-f" not in flags and "--force" not in flags
            else trues[0]
        )
        if answer.lower() in trues:
            os.remove(args[1])
    return result


DEFAULT_URL: str = "https://api.dictionaryapi.dev/api/v2/entries/en/"


def look_up(flags: list[str], *args: str) -> return_value:
    result = return_value(try_again=False, exit=False)
    if not os.path.exists(args[1]) or ("-w" in flags or "--word" in flags):
        for word in args[1:]:
            defs = fetch(DEFAULT_URL + word)[0]["meanings"]
            if len(defs) == 0:
                print(f'word "{word}" not found')
            for i, entry in enumerate(defs):
                print(
                    f"{i+1}. ({entry["partOfSpeech"]}) {entry["definitions"][0]["definition"]}"
                )
        return result
    res: dict[str, str] = {}
    if not os.path.exists(args[1]):
        print(f"Error occurred when trying to read file {args[1]}, not found.")
        return result
    with open(args[1], encoding="utf-8") as file:
        for word in file.readlines()[1:]:
            print(word)
            result_ = fetch(DEFAULT_URL + word.strip())
            if len(result_) == 0:
                continue
            defs = result_[0]["meanings"]
            ins: int = 0
            while 1:
                defs = fetch(DEFAULT_URL + word.strip())[0]["meanings"]
                ins: int = 0
                if len(defs) > 1:
                    for i, entry in enumerate(defs):
                        print(
                            f"{i+1}. ({entry["partOfSpeech"]}) {entry["definitions"][0]["definition"]}"
                        )
                    if not ("-a" in flags or "--auto" in flags):
                        while (
                            (ins := (int(input("Choose one >>")) - 1))
                            and ins < 0
                            and ins >= len(defs)
                        ):
                            pass
                elif len(defs):
                    print("Found one definition only, picking the first one...")
                else:
                    print(f'Word "{word}" not found.')
                    word = input("do you mean >> ")
                    if word == MAGIC_STRING:
                        break
                    continue
                break
            res[word] = defs[ins]["definitions"][0]["definition"]
    if os.path.exists(args[1] + ".dtb") and not ("-f" in flags or "--force" in flags):
        print(
            f"Error occurred when trying to write to file {args[1]}.dtb, please use -f or --force to force overwrite, or "
            "change the name of the existed file"
        )
    if "-f" in flags or "--force" in flags:
        with open(args[1] + ".dtb", "w", encoding="utf-8") as file:
            pass
    with open(args[1] + ".dtb", "a", encoding="utf-8") as file:
        file.write(input("title? ") + "\n")
        if input("write meta data?") in trues:
            file.write("[meta start]")
            inp: str
            while (inp := input("meta data >> ")) != "END META":
                file.write(inp + "\n")
            file.write("[meta end]")
        for word, definition in res.items():
            file.write(f"{definition}~{word.strip()}\n")
    print(f"Ouput was written in file {args[1]}.dtb")
    return result


def meta(flags: list[str], *args: str) -> return_value:
    result: return_value = return_value(exit=False, try_again=False)
    if not os.path.exists(args[1]):
        print(f"Error occurred when trying to open file {args[1]}, not found.")
    if "-c" in flags or "--check" in flags:
        checker: meta_data_parser = meta_data_parser()
        r: list[str] = []
        meta: bool = False
        with open(args[1], encoding="utf-8") as file:
            for i in file.readlines():
                i = i.strip()
                if i == "[meta start]":
                    meta = True
                elif i == "[meta end]":
                    meta = False
                if meta:
                    r.append(i)
        checker.meta(i for i in r)
        return result
    pin: int = 0
    with open(args[1], "a+", encoding="utf-8") as file:
        while i := file.readline():
            if i.strip() == "[meta start]":
                pin += file.tell()
                break
        file.seek(pin)
        while (inp := input("meta data >> ")) != "META_END":
            file.write(inp + "\n")
    return result


def merge(flags: list[str], *args: str) -> return_value:
    """merge multiple study dtbs"""
    result: return_value = return_value(exit=False, try_again=False)
    it: Iterator[str] = None  # type: ignore
    for file_name in args[1:]:
        if not os.path.exists(file_name):
            print(f"file {file_name} not found, skipping...")
        with open(file_name, encoding="utf-8") as file:
            if it is None:  # type: ignore
                it = (i for i in file.readlines()[1:])
            else:
                it = itertools.chain(it, (i for i in file.readlines()[1:]))
    path: str = input("output file >> ")
    if os.path.exists(path):
        if (
            input("File overlapped. Clear? ").strip().lower() in trues
            or "-f" in flags
            or "--force" in flags
        ):
            with open(path, "w"):
                pass
    with open(path, "a+", encoding="utf-8") as file:
        file.write(input("title? ").strip() + "\n")
        for line in it:
            file.write(line)
    return result


commands: dict[str, Callable[..., return_value]] = {
    "study": study,
    "cd": cd,
    "vim": vim,
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
    "lookup": look_up,
    "meta": meta,
    "merge": merge,
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


def compile(data: str) -> tuple[str, ...]:
    result: list[str] = []
    skip: bool = False
    temp: list[str] = []
    in_str: bool = False
    for char in data:
        if skip:
            skip = False
            temp.append(char)
            continue
        if char == '"':
            in_str = not in_str
            continue
        if in_str:
            temp.append(char)
            continue
        if char == " ":
            result.append("".join(temp))
            temp.clear()
            continue
        temp.append(char)
    if temp:
        result.append("".join(temp))
    return tuple(result)


def executor() -> None:
    history = InMemoryHistory()
    completer = StudyCompleter()
    while 1:
        try:
            pre_command: tuple[str, ...] = compile(
                input(
                    ANSI(prompt),
                    history=history,
                    completer=completer,
                    complete_while_typing=True,
                )
            )
            command: str = pre_command[0]
            command = alias.get(command, command)
            flags: list[str] = []
            arguments: list[str] = []
            for i in pre_command:
                if i[0] == "-":
                    flags.append(i)
                else:
                    arguments.append(i)
            value: return_value = commands.get(command, unknown)(flags, *arguments)
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
