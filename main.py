"""Interface principal do CopyWrite."""
from __future__ import annotations

import ctypes
import os
import queue
import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox, scrolledtext, ttk
from typing import Any

from config import SPEED_LABELS, load_config, save_config
from countdown import Countdown
from typer import Typer

try:
    import keyboard  # hotkey global
except ImportError:  # pragma: no cover
    keyboard = None

BASE_SIZE = (640, 480)
MIN_TEXT_LINES = 5
PAD = 10


def enable_dpi_awareness() -> None:
    """Evita interface borrada em telas com escala de 125% ou 150%."""
    if os.name != "nt":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.config: dict[str, Any] = load_config()
        self.events: queue.Queue[tuple[Any, ...]] = queue.Queue()
        self.countdown: Countdown | None = None
        self.hotkey_handle: Any = None
        self.last_error: str | None = None
        self._flow_items: list[tk.Widget] = []
        self._flow_signature: tuple[int, ...] = ()

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
        root = self.root
        root.title("CopyWrite")
        root.columnconfigure(0, weight=1)
        for row, weight in enumerate((0, 1, 0, 0, 0)):  # cabeçalho, texto, controles, progresso, status
            root.rowconfigure(row, weight=weight)

        self.header = ttk.Frame(root, padding=(PAD, PAD, PAD, 0))
        self.header.grid(row=0, column=0, sticky="ew")
        self.header.columnconfigure(0, weight=1)
        ttk.Label(self.header, text="Cole o texto abaixo:").grid(row=0, column=0, sticky="w")
        self.count_var = tk.StringVar(value="0 caracteres")
        ttk.Label(self.header, textvariable=self.count_var).grid(row=0, column=1, sticky="e")

        text_font = ("Segoe UI", 11)
        self.text = scrolledtext.ScrolledText(root, wrap="word", undo=True, font=text_font, width=20, height=MIN_TEXT_LINES)
        self.text.grid(row=1, column=0, sticky="nsew", padx=PAD, pady=8)
        self.text.bind("<<Modified>>", self._on_text_modified)

        self.controls = ttk.Frame(root, padding=(PAD, 0, PAD, 8))
        self.controls.grid(row=2, column=0, sticky="ew")
        self.controls.columnconfigure(99, weight=1)  # coluna elástica: botão fica à direita
        self._build_controls()

        self.progress = ttk.Progressbar(root, mode="determinate")
        self.progress.grid(row=3, column=0, sticky="ew")
        self.status_var = tk.StringVar(value=self._idle_message())
        self.status_label = ttk.Label(root, textvariable=self.status_var, relief="sunken", anchor="w", padding=4)
        self.status_label.grid(row=4, column=0, sticky="ew")

        self._apply_geometry(tkfont.Font(font=text_font).metrics("linespace"))

    def _build_controls(self) -> None:
        speed_frame = ttk.Frame(self.controls)
        ttk.Label(speed_frame, text="Velocidade:").pack(side="left")
        self.label_to_key = {label: key for key, label in SPEED_LABELS.items()}
        speed = self.config["speed"] if self.config["speed"] in SPEED_LABELS else "normal"
        self.speed_var = tk.StringVar(value=SPEED_LABELS[speed])
        speed_box = ttk.Combobox(
            speed_frame, textvariable=self.speed_var, values=list(SPEED_LABELS.values()),
            state="readonly", width=12,
        )
        speed_box.pack(side="left", padx=(4, 0))
        speed_box.bind("<<ComboboxSelected>>", lambda _e: self._save_options())

        self.shift_var = tk.BooleanVar(value=bool(self.config["shift_enter"]))
        shift_check = ttk.Checkbutton(
            self.controls, text="Quebra de linha com Shift+Enter",
            variable=self.shift_var, command=self._save_options,
        )
        self.auto_list_var = tk.BooleanVar(value=bool(self.config["auto_list"]))
        auto_check = ttk.Checkbutton(
            self.controls, text="O destino cria listas sozinho (Word, Docs, Notion)",
            variable=self.auto_list_var, command=self._save_options,
        )
        self.start_button = ttk.Button(self.controls, text="Escreva agora", command=self.start)

        self._flow_items = [speed_frame, shift_check, auto_check, self.start_button]
        self.controls.bind("<Configure>", self._reflow_controls)

    def _reflow_controls(self, _event: Any = None) -> None:
        """Quebra os controles para a linha de baixo quando a janela fica estreita."""
        available = self.controls.winfo_width() - 2 * PAD
        rows: list[int] = []
        row, used = 0, 0
        for widget in self._flow_items:
            need = widget.winfo_reqwidth() + PAD
            if used and used + need > available:
                row, used = row + 1, 0
            rows.append(row)
            used += need
        signature = tuple(rows)
        if signature == self._flow_signature:
            return
        self._flow_signature = signature
        last = len(self._flow_items) - 1
        column = 0
        for index, (widget, widget_row) in enumerate(zip(self._flow_items, rows)):
            if index and rows[index - 1] != widget_row:
                column = 0
            widget.grid_forget()
            if index == last:  # botão sempre à direita e visível
                widget.grid(row=widget_row, column=99, sticky="e", pady=2)
            else:
                widget.grid(row=widget_row, column=column, sticky="w", padx=(0, PAD), pady=2)
                column += 1

    def _apply_geometry(self, line_height: int) -> None:
        """Tamanho inicial e mínimo calculados a partir do que os widgets pedem."""
        root = self.root
        root.update_idletasks()
        screen_w, screen_h = root.winfo_screenwidth(), root.winfo_screenheight()
        scale = root.winfo_fpixels("1i") / 96.0

        # Pior caso dos controles: todos empilhados, um por linha
        items = self._flow_items
        controls_w = max(w.winfo_reqwidth() for w in items) + 2 * PAD
        controls_h = sum(w.winfo_reqheight() + 4 for w in items) + 8
        header_w = self.header.winfo_reqwidth() + 2 * PAD
        text_h = line_height * MIN_TEXT_LINES + 2 * PAD + 16  # linhas, bordas e margens
        fixed_h = (
            self.header.winfo_reqheight() + self.progress.winfo_reqheight()
            + self.status_label.winfo_reqheight()
        )
        min_w = min(max(controls_w, header_w), screen_w)
        min_h = min(fixed_h + text_h + controls_h, screen_h)
        root.minsize(min_w, min_h)

        width = max(min_w, min(int(BASE_SIZE[0] * scale), int(screen_w * 0.85)))
        height = max(min_h, min(int(BASE_SIZE[1] * scale), int(screen_h * 0.85)))
        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 3)
        root.geometry(f"{width}x{height}+{x}+{y}")

    def _idle_message(self) -> str:
        key = str(self.config["stop_key"]).upper()
        return f"Pronto. Tecla de parada: {key}"

    def _on_text_modified(self, _event: Any) -> None:
        if self.text.edit_modified():
            chars = len(self.text.get("1.0", "end-1c"))
            self.count_var.set(f"{chars} caracteres")
            self.text.edit_modified(False)

    def _save_options(self) -> None:
        self.config["speed"] = self.label_to_key.get(self.speed_var.get(), "normal")
        self.config["shift_enter"] = self.shift_var.get()
        self.config["auto_list"] = self.auto_list_var.get()
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
        self.last_error = None
        self.start_button.state(["disabled"])
        self.progress.configure(value=0)
        self.status_var.set("Clique no campo de destino...")
        # O overlay é criado antes do iconify para continuar visível com a janela minimizada
        self.countdown = Countdown(
            self.root, int(self.config["countdown_seconds"]),
            lambda: self._begin_typing(content), str(self.config["stop_key"]),
        )
        self.root.iconify()
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
            self.last_error = event[1]
            self._restore(event[1])
            messagebox.showerror("CopyWrite", event[1])
        elif kind == "finish":
            if self.last_error:  # não sobrescreve a mensagem de erro
                self._restore(self.last_error)
            else:
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
    enable_dpi_awareness()  # antes de criar o Tk
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
