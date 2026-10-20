"""Interface principal do CopyWrite."""
from __future__ import annotations

import queue
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk
from typing import Any

from config import load_config, save_config
from countdown import Countdown
from typer import Typer

try:
    import keyboard  # hotkey global
except ImportError:  # pragma: no cover
    keyboard = None

SPEEDS: list[str] = ["lenta", "normal", "rapida"]


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.config: dict[str, Any] = load_config()
        self.events: queue.Queue[tuple[Any, ...]] = queue.Queue()
        self.countdown: Countdown | None = None
        self.hotkey_handle: Any = None

        self.typer = Typer(
            self.config,
            on_progress=lambda done, total: self.events.put(("progress", done, total)),
            on_finish=lambda ok: self.events.put(("finish", ok)),
            on_window_changed=lambda: self.events.put(("window",)),
            on_error=lambda msg: self.events.put(("error", msg)),
        )

        self._build_ui()
        self._register_hotkey()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(50, self._poll_events)

    # Interface

    def _build_ui(self) -> None:
        self.root.title("CopyWrite")
        self.root.geometry("640x480")
        self.root.minsize(480, 360)

        top = ttk.Frame(self.root, padding=(10, 10, 10, 0))
        top.pack(fill="x")
        ttk.Label(top, text="Cole o texto abaixo:").pack(side="left")
        self.count_var = tk.StringVar(value="0 caracteres")
        ttk.Label(top, textvariable=self.count_var).pack(side="right")

        self.text = scrolledtext.ScrolledText(self.root, wrap="word", undo=True, font=("Segoe UI", 11))
        self.text.pack(fill="both", expand=True, padx=10, pady=8)
        self.text.bind("<<Modified>>", self._on_text_modified)

        controls = ttk.Frame(self.root, padding=(10, 0, 10, 8))
        controls.pack(fill="x")

        ttk.Label(controls, text="Velocidade:").pack(side="left")
        self.speed_var = tk.StringVar(value=self.config["speed"])
        speed_box = ttk.Combobox(
            controls, textvariable=self.speed_var, values=SPEEDS, state="readonly", width=8
        )
        speed_box.pack(side="left", padx=(4, 12))
        speed_box.bind("<<ComboboxSelected>>", lambda _e: self._save_options())

        self.shift_var = tk.BooleanVar(value=bool(self.config["shift_enter"]))
        ttk.Checkbutton(
            controls,
            text="Quebra de linha com Shift+Enter",
            variable=self.shift_var,
            command=self._save_options,
        ).pack(side="left")

        self.start_button = ttk.Button(controls, text="Escreva agora", command=self.start)
        self.start_button.pack(side="right")

        self.status_var = tk.StringVar(value=self._idle_message())
        ttk.Label(self.root, textvariable=self.status_var, relief="sunken", anchor="w", padding=4).pack(
            fill="x", side="bottom"
        )
        self.progress = ttk.Progressbar(self.root, mode="determinate")
        self.progress.pack(fill="x", side="bottom")

    def _idle_message(self) -> str:
        key = str(self.config["stop_key"]).upper()
        return f"Pronto. Tecla de parada: {key}"

    def _on_text_modified(self, _event: Any) -> None:
        if self.text.edit_modified():
            chars = len(self.text.get("1.0", "end-1c"))
            self.count_var.set(f"{chars} caracteres")
            self.text.edit_modified(False)

    def _save_options(self) -> None:
        self.config["speed"] = self.speed_var.get()
        self.config["shift_enter"] = self.shift_var.get()
        try:
            save_config(self.config)
        except OSError as exc:
            self.status_var.set(f"Não foi possível salvar o config.json: {exc}")

    # Hotkey global

    def _register_hotkey(self) -> None:
        if keyboard is None:
            self.status_var.set("Biblioteca keyboard ausente. Tecla de parada global desativada.")
            return
        try:
            self.hotkey_handle = keyboard.add_hotkey(
                str(self.config["stop_key"]), self.stop, suppress=False
            )
        except Exception as exc:  # falta de permissão, tecla inválida etc.
            self.status_var.set(f"Tecla de parada global indisponível: {exc}")

    def _unregister_hotkey(self) -> None:
        if keyboard is not None and self.hotkey_handle is not None:
            try:
                keyboard.remove_hotkey(self.hotkey_handle)
            except Exception:
                pass

    # Fluxo de digitação

    def start(self) -> None:
        if self.typer.running or self.countdown is not None:
            return
        content = self.text.get("1.0", "end-1c")
        if not content.strip():
            messagebox.showwarning("CopyWrite", "O texto está vazio. Cole algo antes de continuar.")
            return
        self._save_options()
        self.start_button.state(["disabled"])
        self.progress.configure(value=0)
        self.status_var.set("Clique no campo de destino...")
        self.root.iconify()
        self.countdown = Countdown(
            self.root, int(self.config["countdown_seconds"]), lambda: self._begin_typing(content)
        )
        self.countdown.start()

    def _begin_typing(self, content: str) -> None:
        self.countdown = None
        self.status_var.set("Digitando...")
        self.typer.start(content)

    def stop(self) -> None:
        """Chamado pelo hotkey (outra thread) ou pela interface."""
        self.typer.stop()
        self.events.put(("stop",))

    # Eventos vindos de outras threads

    def _poll_events(self) -> None:
        try:
            while True:
                self._handle_event(self.events.get_nowait())
        except queue.Empty:
            pass
        self.root.after(50, self._poll_events)

    def _handle_event(self, event: tuple[Any, ...]) -> None:
        kind = event[0]
        if kind == "progress":
            done, total = event[1], event[2]
            self.progress.configure(maximum=total, value=done)
            self.status_var.set(f"Digitando... {done}/{total} ({done * 100 // total}%)")
        elif kind == "window":
            self.status_var.set("Janela mudou. Pausado. Volte ao campo de destino ou pare com a tecla de parada.")
        elif kind == "stop":
            if self.countdown is not None:
                self.countdown.cancel()
                self.countdown = None
                self._restore("Contagem cancelada.")
        elif kind == "error":
            self._restore(event[1])
            messagebox.showerror("CopyWrite", event[1])
        elif kind == "finish":
            self._restore("Texto digitado com sucesso." if event[1] else "Digitação interrompida.")

    def _restore(self, message: str) -> None:
        """Volta a janela principal e libera o botão."""
        self.start_button.state(["!disabled"])
        self.root.deiconify()
        self.root.lift()
        self.status_var.set(message)

    def _on_close(self) -> None:
        self.typer.stop()
        self._unregister_hotkey()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
