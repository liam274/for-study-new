from .constants import SPECIAL_CHARS
from .constants import *
import itertools
from typing import Iterator, Callable
from .utils import ExtendableIterator, safe_int

import os

basic: Callable[[str], Iterator[str]] = lambda x: (i.strip() for i in x.split(",,"))

modify: dict[str, Callable[[str], Iterator[str]]] = {
    "dismiss": basic,
    "set": basic,
    "mode": basic,
    "define": basic,
    "include": basic,
    "version": basic,
    "time-limit": basic,
}


class meta_data_parser:
    def __init__(self: meta_data_parser):
        self.data: dict[str, list[tuple[str, ...]]] = {
            "dismiss": [],
            "set": [],
            "mode": [],
            "define": [],
            "include": [],
            "version": [],
            "time-limit": [],
        }
        self.default: dict[str, tuple[str, ...]] = {"version": (str(META_VERSION),)}

    def meta(
        self: meta_data_parser, data: Iterator[str], flags: set[str] = set()
    ) -> bool:
        macro: dict[str, str] = {}
        data, data2 = itertools.tee(data)
        dataa: ExtendableIterator[str] = ExtendableIterator(data)
        in_if: int = 0
        touch_end: bool = False
        touch: int = 0
        parent_touch_end: bool = False
        included: set[str] = set()
        imported: set[str] = set()
        for line_num, line in enumerate(dataa):
            if line[0] != "%":
                continue
            if line[1] == "%":  # comment
                continue
            testie: list[str] = line.strip().split(" ")
            try:
                if touch_end:  # skipping
                    if testie[0].startswith("%if"):  # count skip higher
                        touch += 1
                    elif testie[0] == "%endif":  # count skip lower
                        touch -= 1
                        if touch == 0:  # get out
                            touch_end = False
                            parent_touch_end = False
                            in_if -= 1
                    elif testie[0] == "%else":
                        if touch < 2:  # check get in else
                            touch = 0
                            touch_end = False
                            in_if += 1
                            if len(testie) < 3:
                                continue
                            if testie[1] == "%ifdef":
                                if testie[2] not in macro:
                                    touch_end = True
                                    parent_touch_end = True
                                    in_if -= 1
                                    touch = 1
                            elif testie[1] == "%ifndef":
                                if testie[2] in macro:
                                    touch_end = True
                                    parent_touch_end = True
                                    in_if -= 1
                                    touch = 1
                elif line.startswith("%define"):
                    _, name, value = line.split(maxsplit=2)
                    macro[name] = value.strip('"')
                elif line.startswith("%include"):
                    _, name = line.split(maxsplit=1)
                    if not os.path.isfile(name):
                        print(
                            f'{RED}Error occurred when trying to open file "{name}"{RESET}'
                        )
                        return False
                    if name in included:
                        print(
                            f'{RED}Error occurred when trying to include file "{name}", recursive including occurrs{RESET}'
                        )
                        return False
                    included.add(name)
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
                    _, name = line.split(maxsplit=1)
                    if not os.path.isfile(name):
                        print(
                            f'{RED}Error occurred when trying to open file "{name}"{RESET}'
                        )
                        return False
                    if name in imported:
                        print(
                            f'{RED}Error occurred when trying to import file "{name}", recursive including occurrs{RESET}'
                        )
                        return False
                    imported.add(name)
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
                    _, content = line.split(maxsplit=1)
                    print(RED + content.strip("\"'") + RESET)
                    return False
                elif line.startswith("%version"):
                    _, version = line.split(maxsplit=1)
                    if safe_int(version) > MACRO_VERSION:
                        if "--omit-macro-version" in flags:
                            print(
                                f"{RED}Error! Provided macro uses a higher version, please either upgrade the application, "
                                f"or uses the flag --omit-macro-version!{RESET}"
                            )
                            return False
                        print(
                            f"{YELLOW}Warning! Provided macro uses a higher version, upgrading the application is suggested.{RESET}"
                        )
                elif testie[0] == "%ifdef":
                    in_if += 1
                    if testie[1] not in macro or parent_touch_end:
                        touch_end = True
                        parent_touch_end = True
                        touch += 1
                elif testie[0] == "%ifndef":
                    in_if += 1
                    if testie[1] in macro or parent_touch_end:
                        touch_end = True
                        parent_touch_end = True
                        touch += 1
                elif testie[0] == "%endif":
                    in_if -= 1
                elif testie[0].startswith("%el"):
                    touch_end = True
                    parent_touch_end = True
            except ValueError:
                print(
                    f'{RED}Error occurred at line {line_num}, macro "{line.split(" ")[0]}" does not have enough parameter{RESET}'
                )
                return False
        if in_if:
            print(
                f"{RED}Error occurred when pharsing macro, found unclosed if, {in_if}.{RESET}"
            )
            return False
        in_if = 0
        touch_end = False
        touch = 0
        parent_touch_end = False
        for ln, _ in enumerate(data2):
            testie: list[str] = _.strip().split(" ")
            if testie[0].startswith("%%"):
                continue
            if touch_end:
                if testie[0].startswith("%if"):
                    touch += 1
                elif testie[0] == "%endif":
                    touch -= 1
                    if touch == 0:
                        touch_end = False
                        parent_touch_end = False
                        in_if -= 1
                elif testie[0] == "%else":
                    if touch < 2:
                        touch = 0
                        touch_end = False
                        in_if += 1
                        if testie[1] == "%ifdef":
                            if testie[1] not in macro:
                                touch_end = True
                                parent_touch_end = True
                                in_if -= 1
                                touch = 1
                        elif testie[1] == "%ifndef":
                            if testie[1] in macro:
                                touch_end = True
                                parent_touch_end = True
                                in_if -= 1
                                touch = 1
                continue
            if _[0] == "%":
                if testie[0] == "%ifdef":
                    in_if += 1
                    if testie[1] not in macro or parent_touch_end:
                        touch_end = True
                        parent_touch_end = True
                        touch += 1
                elif testie[0] == "%ifndef":
                    in_if += 1
                    if testie[1] in macro or parent_touch_end:
                        touch_end = True
                        parent_touch_end = True
                        touch += 1
                elif testie[0] == "%endif":
                    in_if -= 1
                elif testie[0].startswith("%el"):
                    touch_end = True
                    parent_touch_end = True
                continue
            if ":" not in _:
                print(f'{RED}Error occurred at line {ln}, separator ":" expected{RED}')
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
                    f"{RED}Error! Provided meta uses a higher version, please either upgrade the application, "
                    f"or uses the flag --omit-meta-version!{RED}"
                )
                return False
            print(
                f"{YELLOW}Warning! Provided meta uses a higher version, upgrading the application is suggested.{RESET}"
            )
        if in_if:
            print(f"{RED}Error occurred when pharsing macro, found unclosed if.{RESET}")
            return False
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
                        data = "\n".join([(d[0] + " & " + l[0]).strip()] + d[1:])
        return data


class parser:
    def __init__(self: parser, path: str):
        with open(path, "r", encoding="utf-8") as file:
            self.iter = (i.rstrip("\n") for i in file.readlines())

    def exec(self, flags: set[str] = set()) -> tuple[
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
                rule[_[0].lstrip("@")] = {*(tuple(i.split("^")) for i in _[1:])}.union(
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
