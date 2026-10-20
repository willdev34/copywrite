"""Digitação por eventos reais de teclado usando SendInput (user32.dll)."""
from __future__ import annotations

import ctypes
import os
import random
import threading
from ctypes import wintypes
from typing import Any, Callable

IS_WINDOWS: bool = os.name == "nt"

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
VK_RETURN = 0x0D
VK_SHIFT = 0x10
VK_TAB = 0x09

ULONG_PTR = ctypes.c_size_t


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class _INPUTUNION(ctypes.Union):
    # A união completa é necessária para o tamanho correto da struct
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("union", _INPUTUNION)]


class TypingError(Exception):
    """Falha ao enviar teclas ao sistema."""


def _user32() -> Any:
    if not IS_WINDOWS:
        raise TypingError("A digitação só funciona no Windows.")
    return ctypes.WinDLL("user32", use_last_error=True)


def _send(inputs: list[INPUT]) -> None:
    """Envia os eventos e valida o retorno do SendInput."""
    array = (INPUT * len(inputs))(*inputs)
    sent = _user32().SendInput(len(inputs), array, ctypes.sizeof(INPUT))
    if sent != len(inputs):
        code = ctypes.get_last_error()
        raise TypingError(
            f"Falha no SendInput (código {code}). "
            "O app de destino pode estar rodando como administrador."
        )


def _key_input(vk: int = 0, scan: int = 0, flags: int = 0) -> INPUT:
    item = INPUT(type=INPUT_KEYBOARD)
    item.union.ki = KEYBDINPUT(vk, scan, flags, 0, 0)
    return item


def press_vk(vk: int) -> None:
    """Keydown e keyup de uma tecla virtual."""
    _send([_key_input(vk=vk), _key_input(vk=vk, flags=KEYEVENTF_KEYUP)])


def press_unicode(char: str) -> None:
    """Keydown e keyup de um caractere Unicode (emojis viram dois code units UTF-16)."""
    data = char.encode("utf-16-le")
    units = [int.from_bytes(data[i : i + 2], "little") for i in range(0, len(data), 2)]
    events: list[INPUT] = []
    for unit in units:
        events.append(_key_input(scan=unit, flags=KEYEVENTF_UNICODE))
        events.append(_key_input(scan=unit, flags=KEYEVENTF_UNICODE | KEYEVENTF_KEYUP))
    _send(events)


def press_enter(use_shift: bool) -> None:
    """Quebra de linha com Enter ou Shift+Enter."""
    if not use_shift:
        press_vk(VK_RETURN)
        return
    _send(
        [
            _key_input(vk=VK_SHIFT),
            _key_input(vk=VK_RETURN),
            _key_input(vk=VK_RETURN, flags=KEYEVENTF_KEYUP),
            _key_input(vk=VK_SHIFT, flags=KEYEVENTF_KEYUP),
        ]
    )


def get_foreground_window() -> int:
    """Handle da janela ativa (0 fora do Windows)."""
    if not IS_WINDOWS:
        return 0
    return int(_user32().GetForegroundWindow() or 0)


def window_belongs_to_self(hwnd: int) -> bool:
    """Indica se a janela pertence a este processo."""
    if not IS_WINDOWS or not hwnd:
        return False
    pid = wintypes.DWORD(0)
    _user32().GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value == os.getpid()


class Typer:
    """Digita um texto em thread separada, com ritmo humano."""

    def __init__(
        self,
        config: dict[str, Any],
        on_progress: Callable[[int, int], None],
        on_finish: Callable[[bool], None],
        on_window_changed: Callable[[], None],
        on_error: Callable[[str], None],
    ) -> None:
        self.config = config
        self.on_progress = on_progress
        self.on_finish = on_finish  # recebe True se terminou, False se foi interrompido
        self.on_window_changed = on_window_changed
        self.on_error = on_error
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, text: str) -> None:
        """Valida e inicia a digitação na janela que estiver ativa."""
        if self.running:
            return
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        if not text.strip():
            self.on_error("O texto está vazio.")
            return
        if not IS_WINDOWS:
            self.on_error("A digitação só funciona no Windows.")
            return
        target = get_foreground_window()
        if not target or window_belongs_to_self(target):
            self.on_error("Nenhum app de destino ativo. Clique no campo onde o texto deve ser digitado.")
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, args=(text, target), daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Parada segura: a thread encerra na próxima checagem."""
        self._stop.set()

    def _base_ms(self) -> float:
        profiles = self.config.get("profiles", {})
        speed = self.config.get("speed", "normal")
        return float(profiles.get(speed, {"base_ms": 200})["base_ms"])

    def _delay(self, char: str, base_ms: float) -> float:
        """Intervalo em segundos após digitar o caractere."""
        delay = max(15.0, random.gauss(base_ms, base_ms * 0.3))
        if char == " ":
            delay += base_ms * random.uniform(0.5, 1.2)
        elif char in ",;:":
            delay += base_ms * random.uniform(1.5, 3.0)
        elif char in ".?!":
            delay += base_ms * random.uniform(2.5, 5.0)
        elif char == "\n":
            delay += base_ms * random.uniform(3.0, 6.0)
        if random.random() < float(self.config.get("long_pause_probability", 0.02)):
            delay += random.uniform(1200.0, 3000.0)  # pausa para "pensar"
        return delay / 1000.0

    def _wait_for_window(self, target: int) -> bool:
        """Espera a janela de destino voltar ao foco. Retorna False se o usuário parar."""
        self.on_window_changed()
        while not self._stop.is_set():
            if get_foreground_window() == target:
                return True
            self._stop.wait(0.2)
        return False

    def _type_char(self, char: str, shift_enter: bool) -> None:
        if char == "\n":
            press_enter(shift_enter)
        elif char == "\t":
            press_vk(VK_TAB)
        else:
            press_unicode(char)

    def _run(self, text: str, target: int) -> None:
        total = len(text)
        base_ms = self._base_ms()
        check_every = max(1, int(self.config.get("window_check_every", 5)))
        shift_enter = bool(self.config.get("shift_enter", False))
        completed = False
        try:
            for index, char in enumerate(text):
                if self._stop.is_set():
                    break
                if index % check_every == 0 and get_foreground_window() != target:
                    if not self._wait_for_window(target):
                        break
                self._type_char(char, shift_enter)
                self.on_progress(index + 1, total)
                if self._stop.wait(self._delay(char, base_ms)):
                    break
            else:
                completed = True
        except TypingError as exc:
            self.on_error(str(exc))
        finally:
            self.on_finish(completed)
