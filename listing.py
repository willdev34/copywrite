"""Detecção de listas e plano de teclas. Lógica pura, testável sem Windows."""
from __future__ import annotations

import re
from dataclasses import dataclass

# Marcadores do Word que chegam como caracteres de uso privado (fonte Symbol/Wingdings)
PRIVATE_MARKERS: dict[str, str] = {"": "•", "": "▪"}

BULLETS = "•-*–—▪○◦·■□●‣"

_LIST_RE = re.compile(
    r"^(?P<indent>[ \t]*)"
    r"(?P<marker>[" + re.escape(BULLETS) + r"]|\d{1,3}[.)]|[A-Za-z][.)])"
    r"(?P<spacing>[ \t]+)"
    r"(?P<text>.*)$"
)

TAB_WIDTH = 4

# Uma ação é (tipo, caractere). Tipos: char, enter, enter_plain, tab, shift_tab.
# "enter" respeita a opção Shift+Enter; "enter_plain" é sempre Enter puro (listas).
Action = tuple[str, str]


@dataclass(frozen=True)
class ListLine:
    indent: str
    marker: str
    spacing: str
    text: str

    @property
    def indent_width(self) -> int:
        return sum(TAB_WIDTH if c == "\t" else 1 for c in self.indent)


def normalize_text(text: str) -> str:
    """Troca quebras CRLF/CR por LF e mapeia marcadores privados do Word."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    for private, plain in PRIVATE_MARKERS.items():
        text = text.replace(private, plain)
    return text


def parse_list_line(line: str) -> ListLine | None:
    """Retorna os componentes se a linha for item de lista; senão None. Não altera a linha."""
    match = _LIST_RE.match(line)
    if match is None:
        return None
    return ListLine(match["indent"], match["marker"], match["spacing"], match["text"])


def _literal(text: str) -> list[Action]:
    return [("tab", "") if c == "\t" else ("char", c) for c in text]


def _level_for(stack: list[int], width: int) -> int:
    """Atualiza a pilha de recuos e devolve o nível do item."""
    if not stack:
        stack.append(width)
        return 0
    if width > stack[-1]:
        stack.append(width)
    else:
        while stack and stack[-1] > width:
            stack.pop()
        if not stack or stack[-1] < width:
            stack.append(width)
    return len(stack) - 1


def build_actions(text: str, auto_list: bool = False) -> list[Action]:
    """Converte o texto em ações de teclado.

    Sem auto_list, tudo é digitado literalmente. Com auto_list, blocos de itens
    consecutivos têm o marcador digitado só no primeiro item, subníveis viram
    Tab/Shift+Tab e o bloco termina com um Enter extra (Enter em item vazio).
    """
    lines = normalize_text(text).split("\n")
    actions: list[Action] = []
    stack: list[int] = []
    level = 0
    prev_item = False

    for index, line in enumerate(lines):
        item = parse_list_line(line) if auto_list else None

        if index > 0:
            if prev_item and item is not None:
                actions.append(("enter_plain", "\n"))
            elif prev_item:
                actions.extend([("enter_plain", "\n"), ("enter_plain", "\n")])  # segundo sai da lista
            else:
                actions.append(("enter", "\n"))

        if item is None:
            stack = []
            actions.extend(_literal(line))
        elif not prev_item:
            stack = []
            level = _level_for(stack, item.indent_width)
            actions.extend(_literal(f"{item.marker} {item.text}"))
        else:
            new_level = _level_for(stack, item.indent_width)
            diff = new_level - level
            actions.extend([("tab", "")] * diff if diff > 0 else [("shift_tab", "")] * -diff)
            level = new_level
            actions.extend(_literal(item.text))
        prev_item = item is not None

    return actions
