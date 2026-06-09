#!/usr/bin/python
"""
file: main.py
author: liam274

This is a project which helps people reduce the self-studying cost, aiming to improve the accuracy.

"""

import os
import random
import sys
from typing import Callable, Iterator
import itertools
import pathlib

from lib.constants import *
from lib.utils import *
from lib.parser import meta_data_parser, parse

from prompt_toolkit import prompt as input
import subprocess
import shutil
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit.history import InMemoryHistory
import pyttsx3  # type: ignore

# from rich import print
from ubelt import shrinkuser  # type: ignore
import time as time_module

PATH: str = os.getcwd()


def cmd_list() -> set[str]:
    return {*commands.keys()}.union(alias.keys())


# main function
def unknown(flags: set[str], *args: str) -> return_value:
    print(f"{RED}{BOLD}Unknown command:", args[0], RESET)
    return return_value(try_again=False, exit=False)


def study(flags: set[str], *args: str) -> return_value:
    """Study a file."""
    result: return_value = return_value(try_again=False, exit=False)
    files: list[str] = []
    for i in args[1:]:
        if os.path.isfile(i):
            files.append(i)
        else:
            print(f'{RED}{BOLD}Error: File "{i}" does not exist, skipping{RESET}')
    titles: list[str] = []
    have_title: bool = False
    if "--dtbs" in flags:
        have_title = True
        f: list[str] = []
        for file in files:
            if not os.path.isfile(file):
                print(
                    f'{RED}{BOLD}Error: File "{file}" does not exist, skipping{RESET}'
                )
            with open(file, encoding="utf-8") as FI:
                d: list[str] = FI.readlines()
                f += [i.strip() for i in d[1:]]
                titles.append(d[0])
        files = f
    questions: dict[str, answer] = {}
    rule: dict[str, set[tuple[str, ...]]] = {}
    for i in files:
        _: list[tuple[set[str], answer]]
        title: str
        (_, title), rule_temp = parse(i)
        for name, _rule in rule_temp.items():
            rule.update({name: set(_rule).union(rule.get(name, set()))})
        if not title:
            print(f'{RED}{BOLD}Error: File "{i}" is not valid, skipping{RESET}')
            continue
        if not have_title:
            titles.append(title)
        for dic in _:
            for n in dic[0]:
                questions.update({n: dic[1]})
    if not questions:
        print(f"{RED}{BOLD}Error: No valid file found, exiting{RESET}")
        return result
    question_list: list[str] = list(questions.keys())
    random.shuffle(question_list)
    status_list: set[tuple[str, str, int]] = set()
    time: int = 0
    title: str = " & ".join(titles)
    total: int = len(question_list)
    history = InMemoryHistory()
    if len(rule["mode"]) > 1:
        print(
            f"{RED}{BOLD}Error occurred when trying to study with {{{", ".join(args)}}}, found multiple mode. You may only study in one mode at a time.{RESET}"
        )
        return result
    MODE: str = rule["mode"].pop()[0] if rule["mode"] else ""
    if MODE == "tts":
        while not is_volume_on():
            print("\rPlease turn on the volume", end="")
            time_module.sleep(1)
            print("\r\033[K", end="")
            time_module.sleep(1)
    TIME_LIMIT: float = safe_float(
        rule["time-limit"].pop()[0] if rule["time-limit"] else "inf"
    )
    DO_WRONG: bool = "--do-wrong" in flags
    chances: int = GLOBALS["chances"]
    time_consumed: float = 0
    done_question: int = 0
    most_question: str = ""
    most_time: float = 0
    break_through: bool = False
    timeout_interrupt: int = 0
    skip: int = 0
    t: int = 0
    for t, i in enumerate(question_list):
        if break_through:
            break
        i = i.strip()
        if DO_WRONG and i not in flags:
            continue
        clear()
        print(title)
        time += 1
        temp: answer = questions[i]
        sets: set[str] = temp.content
        specific_rules: dict[str, set[tuple[str, ...]]] = {}
        for name, rl in rule.items():
            tempie: set[tuple[str, ...]] = {*rl}
            res: set[tuple[str, ...]] = temp.rules.get(name, set())
            for r in res:
                for item in {*tempie}:
                    if conflict("^".join(r)) in item:
                        tempie.remove(item)
            specific_rules[name] = res.union(tempie)
        if ("ignore",) in specific_rules.get("set", set()):
            continue
        done_question += 1
        if MODE == "tts":
            getchar("Press any key to listen >>")
            TTS_ENGINE.say(i)
            TTS_ENGINE.runAndWait()
            i = ""
        if ("do-filling",) in specific_rules.get("set", set()):
            splitor: str = " ".join(["_"] * len("".join(sets)))
            if temp.first:
                i += " " + splitor
            else:
                i = splitor + " " + i
        qer: str = (len(f"{time}{total} ")) * " " + ">> "
        print(f"({time}/{total})", i)
        trying: int = (
            safe_int(specific_rules.get("chance", set("0")).pop()[0]) or chances
        )
        ori_trying: int = trying
        start: float = time_module.time()
        while sets:
            answer = set(i.strip() for i in input(qer, history=history).split("+"))
            if not any(answer):
                continue
            if MAGIC_STRINGS["exit"] in answer:
                print("Escape magic string detected, exiting...")
                return result
            if MAGIC_STRINGS["pause"] in answer:
                print("Pause magic string detected, paused...")
                time_consumed += time_module.time() - start
                input("Press enter to resume>> ")
                start = time_module.time()
                continue
            if MAGIC_STRINGS["skip"] in answer:
                print("Skip magic string detected, skipping...")
                time_consumed += time_module.time() - start
                trying = 0
                skip += 1
                break
            if sets - answer != sets and not (answer - sets):
                sets -= answer
            else:
                trying -= 1
                print("You're wrong! Please try again.")
                if trying == 0:
                    print(
                        "You've ran out of chances! The correct answers are: ",
                        " and ".join(sets),
                    )
                    time_consumed += time_module.time() - start
                    getchar("Press to continue >>")
                    break
            if (end := time_module.time() - start) > min(
                safe_int(specific_rules.get("max_time", set(("0",))).pop()[0])
                or GLOBALS["max_time"],
                3600,
            ):
                time_consumed += end
                print(
                    "Are you doing on something else? Go either play, or "
                    f"study! Don't PRETEND to study. You've used too much time ({end:.2f} sec)"
                )
                break_through = True
                timeout_interrupt += 1
                getchar("Press to continue >>")
                break
            if end > TIME_LIMIT:
                print("Time's up!")
                break_through = True
                time_consumed += end
                break
        else:
            print("Correct!")
            end: float = time_module.time() - start
            time_consumed += end
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
                    f"study! Don't PRETEND to study. You've used too much time ({end:.2f} sec)"
                )
                getchar("Press to continue >>")
                timeout_interrupt += 1
                break
            if end > TIME_LIMIT:
                print("Time's up!")
                break
            time_module.sleep(0.2)
            status_list.add((i, "~".join(sets), ori_trying - trying))
            continue
        end: float = time_module.time() - start
        time_consumed += end
        if end > most_time:
            most_question = i
            most_time = end
        if end > TIME_LIMIT:
            print("Time's up!")
            break
        status_list.add((i, "~".join(sets), ori_trying - trying))
    clear()
    print(f"{BOLD}{BLUE}Study stat: ")
    print(f"  Time consumed: {time_consumed:.2f}")
    print(f"  {GREEN}Average time per question: {time_consumed/done_question:.2f}")
    print(
        f"  {YELLOW}Question that used most time: {most_question} in {most_time:.2f} sec"
    )
    if MODE == "timed":
        timeout_interrupt += len(question_list) - t
    print(f"  {PURPLE}Timeout interrupted questions: {timeout_interrupt:.2f}")
    print(f"  {RED}Skipped questions: {skip}")
    wrong_list: set[tuple[str, str, int]] = set()
    print(f"  Wrong Question: {RESET}")
    for question, answer, time in status_list:
        if time > 0:
            print(f"    [{time}] {question} -> {answer.replace("~"," + ")}")
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
            q: set[str] = {
                "--do-wrong",
            }
            for question, __, __ in wrong_list:
                q.add(question)
            result.flag = q
    return result


def cd(flags: set[str], *args: str) -> return_value:
    global working_dir, prompt
    result = return_value(try_again=False, exit=False)
    if len(args) < 2:
        working_dir = "~"
        os.chdir(os.path.expanduser("~"))
        prompt = f"{BOLD}{GREEN}{username}@{SYS_NAME}{RESET}{BOLD}:{BLUE}{working_dir}{YELLOW} $ {RESET}"
        return result
    if not os.path.isdir(args[1]):
        print(f"{BOLD}{RED}{args[1]} is not a directory{RESET}")
        return result
    os.chdir(args[1])
    working_dir = shrinkuser(os.getcwd())
    prompt = f"{BOLD}{GREEN}{username}@{SYS_NAME}{RESET}{BOLD}:{BLUE}{working_dir}{YELLOW} $ {RESET}"
    return result


def vim(flags: set[str], *args: str) -> return_value:
    result = return_value(try_again=False, exit=False)
    if len(args) < 2:
        print(f"{RED}{BOLD}No path provided{RESET}")
        return result
    if os.path.isdir(args[1]):
        print(f"{RED}{BOLD}{args[1]} is a directory{RESET}")
        return result
    subprocess.call(["nvim", args[1], *flags])
    return result


def set_alias(flags: set[str], *args: str) -> return_value:
    result = return_value(try_again=False, exit=False)
    if len(args) < 3:
        print(f"{RED}{BOLD}Not enough arguments provided{RESET}")
        return result
    alias[args[1]] = args[2]
    return result


def mkdir(flags: set[str], *args: str) -> return_value:
    result = return_value(try_again=False, exit=False)
    if len(args) < 2:
        print(f"{RED}{BOLD}No path provided{RESET}")
        return result
    os.mkdir(args[1])
    return result


def cp(flags: set[str], *args: str) -> return_value:
    result = return_value(try_again=False, exit=False)
    if len(args) < 3:
        print(f"{RED}{BOLD}Not enough arguments provided{RESET}")
        return result
    shutil.copy(args[1], args[2])
    return result


def mv(flags: set[str], *args: str) -> return_value:
    result = return_value(try_again=False, exit=False)
    if len(args) < 3:
        print(f"{RED}{BOLD}Not enough arguments provided{RESET}")
        return result
    f_path: str = args[-1]
    IS_DIR: bool = os.path.isdir(f_path)
    if not IS_DIR and len(args) > 3:
        print(f"{RED}{BOLD}Moving files to mono file is not allowed{RESET}")
    for path in args[1:-1]:
        t_f_path = f_path
        if os.path.exists(t_f_path):
            if IS_DIR:
                t_f_path = os.path.join(t_f_path, path)
            os.remove(t_f_path)
        else:
            pathlib.Path(t_f_path).touch()
        shutil.move(path, t_f_path)
    return result


def _help(flags: set[str], *args: str) -> return_value:
    result = return_value(try_again=False, exit=False)
    if len(args) > 1:
        if args[1] in commands:
            print(f"{args[1]}: {commands[args[1]].__doc__}")
        else:
            print(f"{RED}{BOLD}No such command{RESET}")
        return result
    print("Available commands:")
    for i in commands:
        print(" " * 17, i)
    print("Magic strings:", MAGIC_STRINGS)
    return result


def _clear(flags: set[str], *args: str) -> return_value:
    result = return_value(try_again=False, exit=False)
    clear()
    return result


def _exec(flags: set[str], *args: str) -> return_value:
    result = return_value(try_again=False, exit=False)
    if len(args) < 2:
        print(f"{RED}{BOLD}No command provided{RESET}")
        return result
    print(eval(" ".join(args[1:])))
    return result


def _set(flags: set[str], *args: str) -> return_value:
    result = return_value(try_again=False, exit=False)
    if len(args) < 3:
        print(f"{RED}{BOLD}Not enough arguments provided{RESET}")
        return result
    if args[1] not in DEFAULTS:
        GLOBALS[args[1]] = safe_int(args[2])
    else:
        GLOBALS[args[1]] = default(args[2], DEFAULTS[args[1]])
    return result


def ls(flags: set[str], *args: str) -> return_value:
    result = return_value(try_again=False, exit=False)
    hide: bool = "-a" not in flags
    for [_, dirs, files] in os.walk(args[1] if len(args) > 1 else os.getcwd()):
        print(BLUE + BOLD, end="")
        for dir in dirs:
            if dir.startswith(".") and hide:
                continue
            print(dir + "/")
        print(RESET, end="")
        for file in files:
            if file.startswith(".") and hide:
                continue
            print(get_clr(file) + file)
        dirs.clear()
        print(RESET, end="")
    return result


def cat(flags: set[str], *args: str) -> return_value:
    result = return_value(try_again=False, exit=False)
    if len(args) < 2:
        print(f"{RED}{BOLD}No path provided{RESET}")
        return result
    for path in args[1:]:
        if os.path.isdir(path):
            print(f"{RED}{BOLD}{path} is a directory{RESET}")
            return result
        if not os.path.isfile(path):
            print(f"{RED}{BOLD}{path} does not exist{RESET}")
            return result
        with open(path, "r", encoding="utf-8") as file:
            if "--no-flag" not in flags:
                print(path + ":")
            print(file.read())
    return result


def whoami(flags: set[str], *args: str) -> return_value:
    result = return_value(try_again=False, exit=False)
    print(f'You are "{username}", who has been studying hard!')
    return result


def echo(flags: set[str], *args: str) -> return_value:
    result = return_value(try_again=False, exit=False)
    print(" ".join(args[1:]))
    return result


def restart(flags: set[str], *args: str) -> return_value:
    result = return_value(try_again=False, exit=False)
    print("Restarting...")
    os.execv(sys.executable, [sys.executable, os.path.join(PATH, sys.argv[0])])
    sys.exit()
    return result


def rm(flags: set[str], *args: str) -> return_value:
    result = return_value(try_again=False, exit=False)
    if len(args) < 2:
        print(f"{RED}{BOLD}No path provided{RESET}")
        return result
    for path in args[1:]:
        if os.path.isdir(path):
            if "-r" in flags:
                answer = (
                    input(f'Are you sure you want to delete file "{path}"? (y/n) ')
                    if "-f" not in flags and "--force" not in flags
                    else trues[0]
                )
                if answer.lower() in trues:
                    shutil.rmtree(path)
            else:
                print(f'{RED}{BOLD}"{path}" is a directory{RESET}')
            return result
        if not os.path.isfile(path):
            print(f'{RED}{BOLD}"{path}" does not exist{RESET}')
            return result
        answer = (
            input(f'Are you sure you want to delete file "{path}"? (y/n) ')
            if "-f" not in flags and "--force" not in flags
            else trues[0]
        )
        if answer.lower() in trues:
            os.remove(path)
    return result


DEFAULT_URL: str = "https://api.dictionaryapi.dev/api/v2/entries/en/"


def look_up(flags: set[str], *args: str) -> return_value:
    result = return_value(try_again=False, exit=False)
    if len(args) < 2:
        return result
    if not os.path.isfile(args[1]) or ("-w" in flags or "--word" in flags):
        for word in args[1:]:
            defs = fetch(DEFAULT_URL + word)[0]["meanings"]
            if len(defs) == 0:
                print(f'{ORANGE}{BOLD}word "{word}" not found{RESET}')
            for i, entry in enumerate(defs):
                print(
                    f"{i+1}. ({entry["partOfSpeech"]}) {entry["definitions"][0]["definition"]}"
                )
        return result
    res: dict[str, str] = {}
    if not os.path.isfile(args[1]):
        print(
            f'{RED}{BOLD}Error occurred when trying to read file "{args[1]}", not found.{RESET}'
        )
        return result
    title: str = ""
    with open(args[1], encoding="utf-8") as file:
        _: list[str] = file.readlines()
        if len(_) < 2:
            print(
                f'{RED}{BOLD}Error occurred when trying to read a empty file "{args[1]}"{RESET}'
            )
            return result
        title = _[0].strip()
        for word in _[1:]:
            print(word)
            _word: str = ""
            result_ = fetch(DEFAULT_URL + word.strip())
            if "title" in result_:
                _word = input("Word not found, please correct >> ").strip()
                if _word == MAGIC_STRINGS["exit"]:
                    return result
                if _word == MAGIC_STRINGS["manual"]:
                    res[word] = confirm_input("Please enter definition >> ")
                    continue
                while "title" in (result_ := fetch(DEFAULT_URL + _word)):
                    _word = input(
                        f'Word "{_word}" not found, please correct >> '
                    ).strip()
                    if _word == MAGIC_STRINGS["exit"]:
                        return result
                    if _word == MAGIC_STRINGS["manual"]:
                        res[word] = confirm_input("Please enter definition >> ")
                        break
                continue
            defs = result_[0]["meanings"]
            ins: int = 0
            while 1:
                if len(defs) > 1:
                    for i, entry in enumerate(defs):
                        print(
                            f"{i+1}. ({entry["partOfSpeech"]}) {entry["definitions"][0]["definition"]}"
                        )
                    if not ("-a" in flags or "--auto" in flags):
                        t: str
                        while 1:
                            t = input("Choose one >>").strip()
                            if t == MAGIC_STRINGS["exit"]:
                                return result
                            if t == MAGIC_STRINGS["manual"]:
                                res[word] = confirm_input("Please enter definition >> ")
                                if res[word]:
                                    defs.clear()
                                    break
                            ins = safe_int(t) - 1
                            if ins < 0 or ins >= len(defs):
                                print("Given value is not expected!")
                                continue
                            break
                elif len(defs):
                    print("Found one definition only, picking the first one...")
                else:
                    print(f'Word "{word}" not found.')
                    _word = input("Please correct >> ").strip()
                    if _word == MAGIC_STRINGS["exit"]:
                        return result
                    if _word == MAGIC_STRINGS["manual"]:
                        res[word] = confirm_input("Please enter definition >> ")
                        break
                    result_ = fetch(DEFAULT_URL + _word.strip())
                    if "title" in result_:
                        _word = input("Word not found, please correct >> ").strip()
                        if _word == MAGIC_STRINGS["exit"]:
                            return result
                        if _word == MAGIC_STRINGS["manual"]:
                            res[word] = confirm_input("Please enter definition >> ")
                            break
                    defs = result_[0]["meanings"]
                    continue
                break
            if len(defs):
                res[_word or word] = defs[ins]["definitions"][0]["definition"]
    if os.path.isfile(args[1] + ".dtb"):
        if "-f" in flags or "--force" in flags:
            with open(args[1] + ".dtb", "w", encoding="utf-8") as file:
                pass
        else:
            print(
                f'{RED}{BOLD}Error occurred when trying to write to file "{args[1]}.dtb", please use -f or --force to force overwrite, or '
                f"change the name of the existed file{RESET}"
            )
            return result
    if os.path.isdir(args[1] + ".dtb"):
        print(
            f'{RED}{BOLD}Error occurred when trying to write to directory "{args[1]}.dtb"'
        )
        return result
    with open(args[1] + ".dtb", "a", encoding="utf-8") as file:
        if input(f"Use original title ({title})?") in trues:
            file.write(title + "\n")
        else:
            file.write(input("title? ").strip() + "\n")
        if input("write meta data?").strip() in trues:
            file.write("[meta start]\n")
            inp: str
            while (inp := input("meta data >> ").strip()) != "END META":
                file.write(inp + "\n")
            file.write("[meta end]\n")
        for word, definition in res.items():
            file.write(f"{definition}~{word.strip()}\n")
    print(f"Ouput was written in file {args[1]}.dtb")
    return result


def meta(flags: set[str], *args: str) -> return_value:
    result: return_value = return_value(exit=False, try_again=False)
    if not os.path.isfile(args[1]):
        print(
            f"{RED}{BOLD}Error occurred when trying to open file {args[1]}, not found.{RESET}"
        )
        return result
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
        while (inp := input("meta data >> ").strip()) != "META_END":
            file.write(inp + "\n")
    return result


def merge(flags: set[str], *args: str) -> return_value:
    """merge multiple study dtbs"""
    result: return_value = return_value(exit=False, try_again=False)
    if len(args) < 2:
        print(f"{RED}{BOLD}Error: No enough arguments provided{RESET}")
        return result
    it: Iterator[str] = None  # type: ignore
    for file_name in args[1:]:
        if not os.path.isfile(file_name):
            print(f"file {file_name} not found, skipping...")
        with open(file_name, encoding="utf-8") as file:
            if it is None:  # type: ignore
                it = (i for i in file.readlines()[1:])
            else:
                it = itertools.chain(it, (i for i in file.readlines()[1:]))
    path: str = input("output file >> ").strip()
    if os.path.isfile(path):
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


def info(flags: set[str], *args: str) -> return_value:
    result: return_value = return_value(exit=False, try_again=False)
    if len(args) < 2:
        print(f"{RED}{BOLD}Error: No enough arguments provided{RESET}")
        return result
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


def runner(line: str) -> bool:
    pre_command: tuple[str, ...] = compile(line.strip())
    if not pre_command:
        return True
    command: str = pre_command[0]
    command = alias.get(command, command)
    flags: set[str] = set()
    arguments: list[str] = []
    for i in pre_command:
        if i[0] == "-" and len(i) > 1:
            if i[1] == "-":
                flags.add(i)
            else:
                for part in i[1:]:
                    flags.add(f"-{part}")
        else:
            arguments.append(i)
    value: return_value = commands.get(command, unknown)(flags, *arguments)
    if value.exit:
        return False
    while value.try_again:
        value = commands.get(command, unknown)(flags.union(value.flag), *arguments)
        if value.exit:
            return False
    return True


def bash(_: set[str], *args: str) -> return_value:
    result: return_value = return_value(exit=False, try_again=False)
    if len(args) < 2:
        print(f"{RED}{BOLD}Error: No enough arguments provided{RESET}")
        return result
    for file in args[1:]:
        if os.path.isfile(file):
            with open(file, encoding="utf-8") as f:
                for line in f.readlines():
                    try:
                        if not runner(line):
                            break
                    except KeyboardInterrupt:
                        continue
    return result


def unalias(_: set[str], *args: str) -> return_value:
    global alias
    result: return_value = return_value(try_again=False, exit=False)
    if len(args) == 1:
        if input("Are you sure you're gonna to remove all the alias?") in trues:
            alias.clear()
        return result
    for alia in args[1:]:
        if alia in alias:
            alias.pop(alia)
        else:
            print(
                f'{RED}{BOLD}Error occurred when trying to remove alias "{alia}", not found.{RESET}'
            )
            return result
    return result


def grep(_: set[str], *args: str) -> return_value:
    result: return_value = return_value(try_again=False, exit=False)
    if len(args) < 2:
        print(f"{RED}{BOLD}Error: No enough arguments provided{RESET}")
        return result
    subprocess.call(["grep", *args[1:]])
    return result


def touch(_: set[str], *args: str) -> return_value:
    result: return_value = return_value(try_again=False, exit=False)
    if len(args) < 2:
        print(f"{RED}{BOLD}Error: No enough arguments provided{RESET}")
        return result
    for path in args[1:]:
        pathlib.Path(path).touch()
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
    "unalias": unalias,
    "grep": grep,
    "touch": touch,
}
alias: dict[str, str] = {}
GLOBALS: dict[str, int] = {"chances": 10, "max_time": 300}
DEFAULTS: dict[str, int] = {"chances": 10, "max_time": 300}
username: str = os.getenv("USER", "student")
working_dir: str = shrinkuser(os.getcwd())
prompt = f"{BOLD}{GREEN}{username}@{SYS_NAME}{RESET}{BOLD}:{BLUE}{working_dir}{YELLOW} $ {RESET}"

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
    completer = StudyCompleter(cmd_list)
    while 1:
        try:
            if not runner(
                input(
                    ANSI(prompt),
                    history=history,
                    completer=completer,
                    complete_while_typing=True,
                ).strip()
            ):
                break
        except KeyboardInterrupt:
            continue


if __name__ == "__main__":
    print(
        f"Hello from study terminal! Type {GREEN}'help'{RESET} for available commands."
    )
    if os.path.isfile(".studyrc"):
        bash(set(), ".studyrc")
    executor()
