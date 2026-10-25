"""Overlay de contagem regressiva, sempre no topo e sem borda."""
from __future__ import annotations

import tkinter as tk
from typing import Callable


class Countdown:
    """Mostra um número grande de N até 1 e chama on_done ao final.

    Crie o overlay antes de minimizar a janela principal; a cada segundo ele
    se reafirma como visível e no topo, mesmo com a janela principal minimizada.
    """

    def __init__(
        self, root: tk.Tk, seconds: int, on_done: Callable[[], None], stop_key: str = ""
    ) -> None:
        self.root = root
        self.remaining = max(1, int(seconds))
        self.on_done = on_done
        self._cancelled = False
        self._after_id: str | None = None

        screen_w = root.winfo_screenwidth()
        screen_h = root.winfo_screenheight()
        number_size = max(48, screen_h // 10)
        hint_size = max(10, screen_h // 60)
        self._margin = max(20, screen_h // 30)
        self._screen = (screen_w, screen_h)

        self.window = tk.Toplevel(root)
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.configure(bg="#1e1e1e")
        self.label = tk.Label(
            self.window, text=str(self.remaining), font=("Segoe UI", -number_size, "bold"),
            fg="#ffffff", bg="#1e1e1e", padx=number_size // 2, pady=number_size // 8,
        )
        self.label.pack()
        hint = "Clique no campo de destino."
        if stop_key:
            hint += f" Parar: {stop_key.upper()}"
        tk.Label(
            self.window, text=hint, font=("Segoe UI", -hint_size), fg="#cccccc", bg="#1e1e1e",
            padx=hint_size, pady=hint_size // 2,
        ).pack()
        self._place_top_right()
        self.window.update()  # garante que o overlay já está desenhado antes do iconify

    def _place_top_right(self) -> None:
        """Canto superior direito, sempre dentro da tela."""
        self.window.update_idletasks()
        screen_w, screen_h = self._screen
        width, height = self.window.winfo_reqwidth(), self.window.winfo_reqheight()
        x = max(0, min(screen_w - width - self._margin, screen_w - width))
        y = max(0, min(self._margin, screen_h - height))
        self.window.geometry(f"+{x}+{y}")

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

    def _keep_visible(self) -> None:
        if self.window.state() != "normal":
            self.window.deiconify()
        self.window.attributes("-topmost", True)
        self.window.lift()

    def _tick(self) -> None:
        if self._cancelled:
            return
        if self.remaining <= 0:
            self._close()
            self.on_done()
            return
        self.label.config(text=str(self.remaining))
        self._keep_visible()
        self.remaining -= 1
        self._after_id = self.root.after(1000, self._tick)
