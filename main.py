#!/usr/bin/python
"""
file: main.py
author: liam274

This is a project which helps people reduce the self-studying cost, aiming to improve the accurency.

"""

import os
import random
import sys
from typing import Callable, Any, Iterator, TextIO
import requests
import itertools
from collections import deque
import datetime

from prompt_toolkit import prompt as input
from dataclasses import dataclass, field
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
import pyttsx3  # type: ignore
import pulsectl  # type: ignore

# from rich import print
from ubelt import shrinkuser  # type: ignore
import time as time_module

SPECIAL_CHARS: str = "~:"
MAGIC_STRINGS: dict[str, str] = {"exit": "35c4p3d", "pause": "p4u53", "skip": "5k1p"}
trues: tuple[str, ...] = ("y", "yes", "true")
PATH: str = os.getcwd()
STDERR: TextIO = sys.stderr


@dataclass
class answer:
    first: bool
    content: set[str]
    rules: dict[str, set[tuple[str, ...]]]


@dataclass
class return_value:
    try_again: bool
    exit: bool
    flag: list[str] = field(default_factory=lambda: [])


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
    "include": basic,
    "version": basic,
}

META_VERSION: int = 1
MACRO_VERSION: int = 1


class meta_data_parser:
    def __init__(self: meta_data_parser):
        self.data: dict[str, list[tuple[str, ...]]] = {
            "dismiss": [],
            "set": [],
            "mode": [],
            "define": [],
            "include": [],
            "version": [],
        }
        self.default: dict[str, tuple[str, ...]] = {"version": (str(META_VERSION),)}

    def meta(
        self: meta_data_parser, data: Iterator[str], flags: list[str] = []
    ) -> bool:
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
                        print(
                            ANSI(
                                f"{RED}Error occurred when trying to open file {name}{RESET}"
                            ),
                            file=STDERR,
                        )
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
                        print(
                            ANSI(
                                f"{RED}Error occurred when trying to open file {name}{RESET}"
                            ),
                            file=STDERR,
                        )
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
                elif line.startswith("%error"):
                    _, content = line.split(maxsplit=2)
                    print(ANSI(RED + content.strip("\"'") + RESET), file=STDERR)
                    return False
                elif line.startswith("%version"):
                    _, version = line.split(maxsplit=1)
                    if safe_int(version) > MACRO_VERSION:
                        if "--omit-macro-version" in flags:
                            print(
                                ANSI(
                                    f"{RED}Error! Provided macro uses a higher version, please either upgrade the application, "
                                    f"or uses the flag --omit-macro-version!{RESET}"
                                ),
                                file=STDERR,
                            )
                            return False
                        print(
                            ANSI(
                                f"{YELLOW}Warning! Provided macro uses a higher version, upgrading the application is suggested.{RESET}"
                            )
                        )
            except ValueError:
                print(
                    ANSI(
                        f'{RED}Error occurred at line {line_num}, macro "{line.split(" ")[0]}" does not have enough parameter{RESET}'
                    ),
                    file=STDERR,
                )
        in_if: int = 0
        touch_end: bool = False
        touch: int = 0
        for ln, _ in enumerate(data2):
            testie: list[str] = _.strip().split(" ")
            if touch_end:
                if testie[0].startswith("%if"):
                    touch += 1
                elif testie[0] == "%endif":
                    touch -= 1
                    if touch == 0:
                        touch_end = False
                elif testie[0] == "%else":
                    if touch < 22:
                        touch = 0
                        touch_end = False
                        in_if += 1
                continue
            if _[0] == "%":
                if testie[0] == "%ifdef":
                    if testie[1] in macro:
                        in_if += 1
                    else:
                        touch_end = True
                elif testie[0] == "%ifndef":
                    if testie[1] not in macro:
                        in_if += 1
                    else:
                        touch_end = True
                elif testie[0] == "%endif":
                    in_if -= 1
                elif testie[0] == "%else":
                    touch_end = True
                continue
            if ":" not in _:
                print(
                    ANSI(
                        f'{RED}Error occurred at line {ln}, separator ":" expected{RED}'
                    ),
                    file=STDERR,
                )
                return False
            command, argument = _.strip().split(":", maxsplit=1)
            self.data[command] += list(
                tuple(macro.get(i, i).split("^")) for i in modify[command](argument)
            )
        for name, default_value in self.default.items():
            if len(self.data[name]):
                continue
            self.data[name] = [default_value]
        if safe_int(self.data["version"][0][0]) > META_VERSION:
            if "--omit-meta-version" in flags:
                print(
                    ANSI(
                        f"{RED}Error! Provided meta uses a higher version, please either upgrade the application, "
                        f"or uses the flag --omit-meta-version!{RED}"
                    ),
                    file=STDERR,
                )
                return False
            print(
                ANSI(
                    f"{YELLOW}Warning! Provided meta uses a higher version, upgrading the application is suggested.{RESET}"
                )
            )
        if in_if:
            print(
                ANSI(
                    f"{RED}Error occurred when pharsing macro, found unclosed if.{RESET}"
                ),
                file=STDERR,
            )
        return True

    def run_rule(self: meta_data_parser, data: str) -> str:
        for rule in self.data["dismiss"]:
            data = data.replace(rule[0], "")
        for rule in self.data["define"]:
            data = data.replace(rule[0], rule[1])
        for rule, *_ in self.data["include"]:
            if os.path.isfile(rule):
                with open(rule, encoding="utf-8") as file:
                    l = file.readlines()
                    if len(l) != 0:
                        d = data.split("\n") + list(i.strip() for i in l[1:])
                        data = "\n".join([(d[0][:-1] + " & " + l[0]).strip()] + d[1:])
        return data


class parser:
    def __init__(self: parser, path: str):
        with open(path, "r", encoding="utf-8") as file:
            self.iter = (i.rstrip("\n") for i in file.readlines())

    def exec(self, flags: list[str] = []) -> tuple[
        tuple[tuple[tuple[str, ...], dict[str, set[tuple[str, ...]]]], ...],
        dict[str, list[tuple[str, ...]]],
    ]:
        result: list[tuple[tuple[str, ...], dict[str, set[tuple[str, ...]]]]] = []
        is_meta: bool = False
        metas: list[str] = []
        meta_data: meta_data_parser = meta_data_parser()
        data: list[str] = []
        rule: dict[str, set[tuple[str, ...]]] = {}
        for i in self.iter:
            if is_meta:
                if i == "[meta end]":
                    is_meta = False
                    if not meta_data.meta((i for i in metas), flags):
                        break
                else:
                    metas.append(i)
                continue
            if i == "[meta start]":
                is_meta = True
                continue
            data.append(i)
        for i in meta_data.run_rule("\n".join(data)).split("\n"):
            if i[0] == "@":
                _: list[str] = i.split(" ")
                rule[_[0].lstrip("@")] = set(tuple(i.split("^")) for i in _[1:]).union(
                    rule.get(_[0].lstrip("@"), set())
                )
                continue
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
            if ("ignore",) not in rule.get("set", set()):
                result.append((tuple(i for i in all), rule))
            rule.clear()
        return tuple(result), meta_data.data


def fetch(url: str, timeout: int = 10) -> list[Any]:
    try:
        resp = requests.get(url, timeout=timeout)
    except Exception as e:
        print("Ouch! The console cannot reach the server...")
        log(f'Fetch for url "{url}" failed: {e}', "ERROR")
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


def getchar(prompt: str = "") -> str:
    print(prompt, end="", flush=True)
    g = getche()  # type: ignore
    print()
    return g  # type: ignore


def log(content: str, level: str):
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


def parse(
    path: str,
) -> tuple[tuple[list[tuple[set[str], answer]], str], dict[str, list[tuple[str, ...]]]]:
    result: list[tuple[set[str], answer]] = []
    _, rules = parser(path).exec()
    for line, rl in _[1:]:
        special_char: str = line[0]  # type: ignore
        if special_char == "~":
            result.append(
                ({line[1]}, answer(first=True, content=set(line[2:]), rules=rl))
            )
        elif special_char == ":":
            result.append(
                ({line[1]}, answer(first=True, content=set(line[2:]), rules=rl))
            )
            result.append(
                (set(line[2:]), answer(first=False, content={line[1]}, rules=rl))
            )
        elif special_char.startswith("-("):
            result.append(
                (
                    {line[1] + special_char},
                    answer(
                        first=True,
                        content=set(i.strip() for i in line[2].split("+")),
                        rules=rl,
                    ),
                )
            )
            result.append(
                (
                    {special_char + line[2]},
                    answer(
                        first=False,
                        content=set(i.strip() for i in line[1].split("+")),
                        rules=rl,
                    ),
                )
            )
        else:
            result.append(({line[0]}, answer(first=True, content={line[0]}, rules=rl)))
    return (result, _[0][0][0]), rules


def get_size() -> tuple[int, int]:
    obj: Any = shutil.get_terminal_size()
    return obj.columns, obj.lines


def conflict(data: str) -> str:  # mvp
    if data == "do-filling":
        return "no-filling"
    if data == "no-filling":
        return "do-filling"
    return ""


def safe_int(data: str) -> int:
    if data.isdigit():
        return int(data)
    return 0


# main function
def unknown(flags: list[str], *args: str) -> return_value:
    print("Unknown command:", args[0])
    return return_value(try_again=False, exit=False)


def study(flags: list[str], *args: str) -> return_value:
    """Study a file."""
    result: return_value = return_value(try_again=False, exit=False)
    files: list[str] = []
    for i in args[1:]:
        if os.path.isfile(i):
            files.append(i)
        else:
            print(
                ANSI(f"{RED}Error: File {i} does not exist, skipping{RESET}"),
                file=STDERR,
            )
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
            print(
                ANSI(f"{RED}Error: File {i} is not valid, skipping{RESET}"), file=STDERR
            )
            continue
        titles.append(title)
        for dic in _:
            for n in dic[0]:
                questions.update({n: dic[1]})
    if not questions:
        print(ANSI(f"{RED}Error: No valid file found, exiting{RESET}"), file=STDERR)
        return result
    question_list: list[str] = list(questions.keys())
    random.shuffle(question_list)
    status_list: set[tuple[str, str, int]] = set()
    time: int = 0
    title: str = " & ".join(titles)
    total: int = len(question_list)
    history = InMemoryHistory()
    rule["mode"] = set(rule["mode"])
    if len(rule["mode"]) > 1:
        print(
            ANSI(
                f"{RED}Error occurred when trying to study with {{{", ".join(args)}}}, found multiple mode. You may only study in one mode at a time.{RESET}"
            ),
            file=STDERR,
        )
        return result
    MODE: str = rule["mode"].pop()[0] if rule["mode"] else ""
    if MODE == "tts":
        while not is_volume_on():
            print("\rPlease turn on the volume", end="")
            time_module.sleep(1)
            print("\r\033[K", end="")
            time_module.sleep(1)
    DO_WRONG: bool = "--do-wrong" in flags
    chances: int = GLOBALS["chances"]
    time_consumed: float = 0
    time_start_stamp: float = time_module.time()
    done_question: int = 0
    most_question: str = ""
    most_time: float = 0
    break_through: bool = False
    timeout_interrupt: int = 0
    skip: int = 0
    for i in question_list:
        if break_through:
            break
        if DO_WRONG and i not in flags:
            continue
        clear()
        print(title)
        time += 1
        temp: answer = questions[i]
        sets: set[str] = temp.content
        specific_rules: dict[str, set[tuple[str, ...]]] = {}
        for name, rl in temp.rules.items():
            tempie: set[tuple[str, ...]] = rule.get(name, set())
            for r in rl:
                for item in tempie:
                    if conflict("^".join(r)) in item:
                        tempie.remove(item)
            specific_rules[name] = rl.union(tempie)
        if "ignore" in specific_rules.get("set", tuple()):
            continue
        done_question += 1
        splitor: str = (
            " ".join(["_"] * len("".join(sets)))
            if ("do-filling",) in specific_rules.get("set", set())
            else ""
        )
        if MODE == "tts":
            getche("Press any key to listen >>")
            TTS_ENGINE.say(i)
            TTS_ENGINE.runAndWait()
            i = ""
        if temp.first:
            i += " " + splitor
        else:
            i = splitor + " " + i
        qer: str = (len(f"{time}{total} ")) * " " + ">> "
        print(f"({time}/{total})", i)
        trying: int = (
            safe_int(specific_rules.get("chance", set("0")).pop()[0]) or chances
        )
        start: float = time_module.time()
        while (
            answer := set(i.strip() for i in input(qer, history=history).split("+"))
        ) != sets:
            if break_through:
                break
            if MAGIC_STRINGS["exit"] in answer:
                print("Escape magic string detected, exiting...")
                return result
            if MAGIC_STRINGS["pause"] in answer:
                print("Pause magic string detected, paused...")
                time_consumed = time_module.time() - time_start_stamp
                input("Press enter to resume>> ")
                time_start_stamp = time_module.time()
            if MAGIC_STRINGS["skip"] in answer:
                print("Skip magic string detected, skipping...")
                trying = 0
                skip += 1
                break
            trying -= 1
            print("You're wrong! Please try again.")
            if (end := time_module.time() - start) > min(
                safe_int(specific_rules.get("max_time", set("0")).pop()[0])
                or GLOBALS["max_time"],
                3600,
            ):
                print(
                    "Are you doing on something else? Go either play, or "
                    f"study! Don't PRETEND to study. You've used too much time ({end} sec)"
                )
                break_through = True
                skip += 1
            if trying == 0:
                print(
                    "You've ran out of chances! The correct answers are: ",
                    " and ".join(sets),
                )
                break
        else:
            print("Correct!")
            end: float = time_module.time() - start
            if end > most_time:
                most_question = i
                most_time = end
            if end > (
                min(
                    safe_int(specific_rules.get("max_time", set("0")).pop()[0])
                    or GLOBALS["max_time"],
                    3600,
                )
            ):
                print(
                    "Are you doing on something else? Go either play, or "
                    f"study! Don't PRETEND to study. You've used too much time ({end} sec)"
                )
                break_through = True
                skip += 1
            time_module.sleep(0.1)
            continue
        end: float = time_module.time() - start
        if end > most_time:
            most_question = i
            most_time = end
        status_list.add((i, "~".join(sets), trying))
    clear()
    print("Study stat: ")
    print(f"Time consumed: {time_consumed:.2f}")
    print(f"Average time per question: {time_consumed/done_question:.2f}")
    print(f"Question that used most time: {most_question} in {most_time:.2f} sec")
    print(f"Timeout interrupted questions: {timeout_interrupt}")
    print(f"Skipped questions: {skip}")
    wrong_list: set[tuple[str, str, int]] = set()
    print("Wrong Question: ")
    for question, answer, time in status_list:
        if time < GLOBALS["chances"]:
            print(f"  {question}[{time}]")
            wrong_list.add((question, answer, time))
    if "--export-wrong" in flags:
        for i in args[1:]:
            if os.path.isfile(i):
                continue
            with open(i, "a+", encoding="utf-8") as file:
                file.write(f"Wrong list for {title}\n")
                file.write("[meta start]\n")
                for r, content in rule.items():
                    file.write(f"{r}: {",,".join("^".join(i) for i in content)}\n")
                file.write("[meta end]\n")
                for question, answer, __ in wrong_list:
                    file.write(f"{question}~{answer}\n")
            break
    getchar("Press any key to continue>> ")
    if input("try again? ").strip().lower() in trues:
        result = return_value(exit=False, try_again=True)
        if ("do-wrong-again-only",) in rule["set"]:
            q: list[str] = ["--do-wrong"]
            for question, __, __ in wrong_list:
                q.append(question)
            result.flag = q
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
    print("Magic strings:", MAGIC_STRINGS)
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
    for path in args[1:]:
        if os.path.isdir(path):
            print(f"{path} is a directory")
            return result
        if not os.path.isfile(path):
            print(f"{path} does not exist")
            return result
        with open(path, "r", encoding="utf-8") as file:
            if "--no-flag" not in flags:
                print(path + ":")
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
        print(
            ANSI(
                f"{RED}Error occurred when trying to read file {args[1]}, not found.{RESET}"
            ),
            file=STDERR,
        )
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
                    if word == MAGIC_STRINGS["exit"]:
                        break
                    continue
                break
            res[word] = defs[ins]["definitions"][0]["definition"]
    if os.path.exists(args[1] + ".dtb") and not ("-f" in flags or "--force" in flags):
        print(
            ANSI(
                f"{RED}Error occurred when trying to write to file {args[1]}.dtb, please use -f or --force to force overwrite, or "
                f"change the name of the existed file{RESET}"
            ),
            file=STDERR,
        )
    if "-f" in flags or "--force" in flags:
        with open(args[1] + ".dtb", "w", encoding="utf-8") as file:
            pass
    with open(args[1] + ".dtb", "a", encoding="utf-8") as file:
        file.write(input("title? ") + "\n")
        if input("write meta data?") in trues:
            file.write("[meta start]\n")
            inp: str
            while (inp := input("meta data >> ")) != "END META":
                file.write(inp + "\n")
            file.write("[meta end]\n")
        for word, definition in res.items():
            file.write(f"{definition}~{word.strip()}\n")
    print(f"Ouput was written in file {args[1]}.dtb")
    return result


def meta(flags: list[str], *args: str) -> return_value:
    result: return_value = return_value(exit=False, try_again=False)
    if not os.path.exists(args[1]):
        print(
            ANSI(
                f"{RED}Error occurred when trying to open file {args[1]}, not found.{RESET}"
            ),
            file=STDERR,
        )
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
        checker.meta((i for i in r), flags)
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


def info(flags: list[str], *args: str) -> return_value:
    result: return_value = return_value(exit=False, try_again=False)
    for file in args[1:]:
        if not os.path.isfile(file):
            continue
        (problem, title), rules = parse(file)
        print("-" * shutil.get_terminal_size().columns)
        print(f"File name: {file}")
        print(f"Dtb title: {title}")
        print(f"Question number: {len(problem)}")
        print("Meta data: ")
        for rule, content in rules.items():
            print(f"\t{rule}: {",,".join("^".join(i) for i in content)}")
    return result


def bash(_: list[str], *args: str) -> return_value:
    result: return_value = return_value(exit=False, try_again=False)
    for file in args[1:]:
        if os.path.isfile(file):
            with open(file, encoding="utf-8") as f:
                for line in f.readlines():
                    try:
                        pre_command: tuple[str, ...] = compile(line.strip())
                        command: str = pre_command[0]
                        command = alias.get(command, command)
                        flags: list[str] = []
                        arguments: list[str] = []
                        for i in pre_command:
                            if i[0] == "-":
                                flags.append(i)
                            else:
                                arguments.append(i)
                        value: return_value = commands.get(command, unknown)(
                            flags, *arguments
                        )
                        if value.exit:
                            break
                        while value.try_again:
                            value = commands.get(command, unknown)(
                                flags + value.flag, *arguments
                            )
                            if value.exit:
                                break
                        else:
                            continue
                        break
                    except KeyboardInterrupt:
                        print()
                        continue
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
    "info": info,
    "bash": bash,
}
alias: dict[str, str] = {}
GLOBALS: dict[str, int] = {"chances": 10, "max_time": 300}
DEFAULTS: dict[str, int] = {"chances": 10, "max_time": 300}
username: str = os.getenv("USER", "student")
BOLD = "\033[1m"
RESET = "\033[0m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
RED = "\033[31m"
working_dir: str = shrinkuser(os.getcwd())
prompt = f"{BOLD}{GREEN}{username}{RESET}{BOLD}:{BLUE}{working_dir}{YELLOW} $ {RESET}"

TTS_ENGINE: pyttsx3.Engine = pyttsx3.init()  # type: ignore
TTS_ENGINE.setProperty("rate", 150)  # type: ignore
TTS_ENGINE.setProperty("volume", 0.9)  # type: ignore


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
            if temp:
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
                value = commands.get(command, unknown)(flags + value.flag, *arguments)
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
