from __future__ import annotations

import re

from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich.style import Style


class TokenBuffer:
    def __init__(self) -> None:
        self._lines: list[str] = [""]
        self._partial_word = ""

    def feed(self, token: str) -> None:
        for ch in token:
            if ch == "\n":
                self._lines.append("")
                self._partial_word = ""
            elif ch == " " and self._partial_word:
                self._lines[-1] += self._partial_word + " "
                self._partial_word = ""
            else:
                self._partial_word += ch

    def flush(self) -> None:
        if self._partial_word:
            self._lines[-1] += self._partial_word
            self._partial_word = ""

    @property
    def text(self) -> str:
        self.flush()
        return "\n".join(self._lines)

    def reset(self) -> None:
        self._lines = [""]
        self._partial_word = ""


def _render_code_block(code: str, lang: str = "") -> Text:
    try:
        syntax = Syntax(code, lang or "text", theme="monokai", line_numbers=False)
        text = Text()
        text.append("\n")
        text.append_text(syntax)
        text.append("\n")
        return text
    except Exception:
        lines = code.split("\n")
        t = Text()
        for line in lines:
            t.append(f"  {line}\n", style="bold green")
        return t


def _render_inline(text: Text, s: str, style: Style | str) -> Text:
    text.append(s, style=style)
    return text


def render_markdown(text: str) -> Text | Table:
    if not text.strip():
        return Text("")

    lines = text.split("\n")
    result = Text()
    in_code_block = False
    code_buffer: list[str] = []
    code_lang = ""
    bullet_list: list[str] | None = None

    for line in lines:
        if line.startswith("```"):
            if in_code_block:
                code_buffer.append("")
                block = _render_code_block("\n".join(code_buffer), code_lang)
                result.append_text(block)
                code_buffer = []
                code_lang = ""
                in_code_block = False
            else:
                code_lang = line[3:].strip()
                in_code_block = True
            continue

        if in_code_block:
            code_buffer.append(line)
            continue

        if not line.strip():
            if bullet_list is not None:
                for bl in bullet_list:
                    result.append(f"  • {bl}\n")
                bullet_list = None
            result.append("\n")
            continue

        if re.match(r"^#{1,6}\s", line):
            match = re.match(r"^(#{1,6})\s(.+)", line)
            if match:
                level = len(match.group(1))
                content = match.group(2)
                if level == 1:
                    result.append(f"\n{content}\n", style="bold cyan underline")
                    result.append("─" * len(content) + "\n", style="dim cyan")
                else:
                    result.append(f"{content}\n", style="bold cyan")
            continue

        if line.strip().startswith("- ") or line.strip().startswith("* "):
            item = line.strip()[2:]
            if bullet_list is None:
                bullet_list = []
            bullet_list.append(item)
            continue

        if bullet_list is not None:
            for bl in bullet_list:
                result.append(f"  • {bl}\n")
            bullet_list = None

        i = 0
        while i < len(line):
            if line[i : i + 2] == "**":
                end = line.find("**", i + 2)
                if end != -1:
                    result.append(line[i + 2 : end], style="bold white")
                    i = end + 2
                    continue
            if line[i : i + 1] == "`":
                end = line.find("`", i + 1)
                if end != -1:
                    result.append(line[i + 1 : end], style="yellow")
                    i = end + 1
                    continue
            if line[i : i + 1] == "*":
                end = line.find("*", i + 1)
                if end != -1:
                    result.append(line[i + 1 : end], style="italic")
                    i = end + 1
                    continue
            result.append(line[i])
            i += 1

        result.append("\n")

    if bullet_list is not None:
        for bl in bullet_list:
            result.append(f"  • {bl}\n")

    if in_code_block and code_buffer:
        block = _render_code_block("\n".join(code_buffer), code_lang)
        result.append_text(block)

    return result
