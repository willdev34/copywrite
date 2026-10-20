"""Overlay de contagem regressiva, sempre no topo e sem borda."""
from __future__ import annotations

import tkinter as tk
from typing import Callable


class Countdown:
    """Mostra um número grande de N até 1 e chama on_done ao final."""

    def __init__(self, root: tk.Tk, seconds: int, on_done: Callable[[], None]) -> None:
        self.root = root
        self.remaining = max(1, int(seconds))
        self.on_done = on_done
        self._cancelled = False
        self._after_id: str | None = None

        self.window = tk.Toplevel(root)
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.configure(bg="#1e1e1e")
        self.label = tk.Label(
            self.window, text="", font=("Segoe UI", 64, "bold"), fg="#ffffff", bg="#1e1e1e", padx=30, pady=10
        )
        self.label.pack()
        self._place_top_right()

    def _place_top_right(self) -> None:
        self.window.update_idletasks()
        width = self.window.winfo_reqwidth()
        x = self.window.winfo_screenwidth() - width - 40
        self.window.geometry(f"+{x}+40")

    def start(self) -> None:
        self._tick()

    def cancel(self) -> None:
        """Cancela a contagem e fecha o overlay sem chamar on_done."""
        self._cancelled = True
        if self._after_id is not None:
            self.root.after_cancel(self._after_id)
            self._after_id = None
        self._close()

    def _close(self) -> None:
        if self.window.winfo_exists():
            self.window.destroy()

    def _tick(self) -> None:
        if self._cancelled:
            return
        if self.remaining <= 0:
            self._close()
            self.on_done()
            return
        self.label.config(text=str(self.remaining))
        self.remaining -= 1
        self._after_id = self.root.after(1000, self._tick)
