from meta_parser import meta_data_parser
from constants import SPECIAL_CHARS


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
