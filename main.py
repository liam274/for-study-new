"""
file: main.py
author: liam274

This is a project which helps people reduce the self-studying cost, aiming to improve the accurency.

"""

import os
import random
import sys
from typing import TextIO
from prompt_toolkit import prompt as input
from dataclasses import dataclass

SPECIAL_CHARS: str = "~:"


@dataclass
class answer:
    first: bool
    content: set[str]


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


def print(
    *values: object,
    sep: str = " ",
    end: str = "\n",
    file: TextIO = sys.stdout,
    flush: bool = True
):
    old_print(*values, sep=sep, end=end, file=file, flush=flush)


def parse(path: str) -> dict[set[str], answer]:
    result: dict[set[str], answer] = {}
    for line in parser(path).exec():
        if len(line) < 3:
            print(
                "Error occured when pharsing file, found too few arguments in a line",
                file=sys.stderr,
            )
        special_char: str = line[0]  # type: ignore
        if special_char == "~":
            result.update({{line[1]}: answer(first=True, content=set(line[2:]))})  # type: ignore
        elif special_char == ":":
            result.update({{line[1]}: answer(first=True, content=set(line[2:]))})  # type: ignore
            result.update({set(line[2:]): answer(first=False, content={line[1]})})  # type: ignore
    return result
