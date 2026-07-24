from __future__ import annotations

import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Callable

from .config import Config, is_valid_exe_name, normalize_exe_name, save_config
from .controller import ShadowController
from .hotkeys import capture_hotkey_blocking, format_hotkey_display, to_keyboard_hotkey


class ShadowApp(tk.Tk):
    def __init__(self, controller: ShadowController, on_hide: Callable[[], None]) -> None:
        super().__init__()
        self.controller = controller
        self.on_hide = on_hide
        self.title("Shadow")
        self.geometry("540x340")
        self.minsize(500, 300)
        self.configure(bg="#1e1e1e")

        cfg = controller.config
        self._process_var = tk.StringVar(value=cfg.process_name)
        self._pending_var = tk.StringVar(value=cfg.pending_dir)
        self._disable_raw = to_keyboard_hotkey(cfg.disable_hotkey) or "f8"
        self._enable_raw = to_keyboard_hotkey(cfg.enable_hotkey) or "f9"
        self._disable_var = tk.StringVar(value=format_hotkey_display(self._disable_raw))
        self._enable_var = tk.StringVar(value=format_hotkey_display(self._enable_raw))
        self._status_var = tk.StringVar(value="Ready. Shadow is OFF.")
        self._capturing: str | None = None
        self._save_after_id: str | None = None

        self._build()
        self.protocol("WM_DELETE_WINDOW", self._hide_to_tray)
        self.bind("<Unmap>", self._on_unmap)

        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TLabel", background="#1e1e1e", foreground="#e8e8e8")
        style.configure("TFrame", background="#1e1e1e")
        style.configure("TButton", padding=6)
        style.configure("Header.TLabel", font=("Segoe UI", 16, "bold"), foreground="#f2f2f2")
        style.configure("Hint.TLabel", background="#1e1e1e", foreground="#888888")
        style.configure("Status.TLabel", foreground="#b0b0b0", wraplength=500)
        style.configure("Error.TLabel", background="#1e1e1e", foreground="#e07070")
        style.configure("Hotkey.TButton", padding=6)

        self._process_var.trace_add("write", self._on_process_changed)
        self._pending_var.trace_add("write", self._schedule_autosave)

    def _build(self) -> None:
        root = ttk.Frame(self, padding=16)
        root.pack(fill=tk.BOTH, expand=True)

        ttk.Label(root, text="Shadow", style="Header.TLabel").pack(anchor="w")
        ttk.Label(
            root,
            text="Freeze observer captures and block one process network.",
        ).pack(anchor="w", pady=(4, 14))

        form = ttk.Frame(root)
        form.pack(fill=tk.X)
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="Process name").grid(row=0, column=0, sticky="w", pady=6)
        process_entry = ttk.Entry(form, textvariable=self._process_var, width=36)
        process_entry.grid(row=0, column=1, sticky="ew", padx=(10, 0), pady=6)
        process_entry.bind("<FocusOut>", self._validate_process_focus)
        ttk.Label(form, text="must end with .exe", style="Hint.TLabel").grid(
            row=0, column=2, sticky="w", padx=(8, 0)
        )
        self._process_hint = ttk.Label(form, text="", style="Error.TLabel")
        self._process_hint.grid(row=1, column=1, sticky="w", padx=(10, 0))

        ttk.Label(form, text="Pending directory").grid(row=2, column=0, sticky="w", pady=6)
        ttk.Entry(form, textvariable=self._pending_var, width=36).grid(
            row=2, column=1, sticky="ew", padx=(10, 0), pady=6
        )
        ttk.Button(form, text="…", width=3, command=self._browse_pending).grid(
            row=2, column=2, padx=(6, 0)
        )

        ttk.Label(form, text="Disable hotkey").grid(row=3, column=0, sticky="w", pady=6)
        self._disable_btn = ttk.Button(
            form,
            textvariable=self._disable_var,
            style="Hotkey.TButton",
            command=lambda: self._start_hotkey_capture("disable"),
        )
        self._disable_btn.grid(row=3, column=1, sticky="ew", padx=(10, 0), pady=6)
        ttk.Label(form, text="click, then press key", style="Hint.TLabel").grid(
            row=3, column=2, sticky="w", padx=(8, 0)
        )

        ttk.Label(form, text="Enable hotkey").grid(row=4, column=0, sticky="w", pady=6)
        self._enable_btn = ttk.Button(
            form,
            textvariable=self._enable_var,
            style="Hotkey.TButton",
            command=lambda: self._start_hotkey_capture("enable"),
        )
        self._enable_btn.grid(row=4, column=1, sticky="ew", padx=(10, 0), pady=6)
        ttk.Label(form, text="click, then press key", style="Hint.TLabel").grid(
            row=4, column=2, sticky="w", padx=(8, 0)
        )

        btns = ttk.Frame(root)
        btns.pack(fill=tk.X, pady=(16, 8))
        ttk.Button(btns, text="Shadow ON", command=self.controller.activate_shadow).pack(
            side=tk.LEFT
        )
        ttk.Button(btns, text="Shadow OFF", command=self.controller.deactivate_shadow).pack(
            side=tk.LEFT, padx=(8, 0)
        )
        ttk.Button(btns, text="Hide to tray", command=self._hide_to_tray).pack(side=tk.RIGHT)

        ttk.Label(root, textvariable=self._status_var, style="Status.TLabel").pack(
            anchor="w", pady=(10, 0), fill=tk.X
        )

    def _browse_pending(self) -> None:
        path = filedialog.askdirectory(initialdir=self._pending_var.get() or None)
        if path:
            if not path.endswith("\\") and not path.endswith("/"):
                path += "\\"
            self._pending_var.set(path)

    def _on_process_changed(self, *_args: object) -> None:
        value = self._process_var.get().strip()
        if not value:
            self._process_hint.configure(text="")
            return
        if is_valid_exe_name(value):
            self._process_hint.configure(text="")
            self._schedule_autosave()
        else:
            self._process_hint.configure(text="Invalid — use a name like wordpress.exe")

    def _validate_process_focus(self, _event: tk.Event | None = None) -> None:
        value = self._process_var.get().strip()
        if value and is_valid_exe_name(value):
            return
        self._process_var.set(self.controller.config.process_name)
        self._process_hint.configure(text="")
        if value:
            self.set_status("Process name must be an .exe filename.")

    def _schedule_autosave(self, *_args: object) -> None:
        if self._save_after_id is not None:
            try:
                self.after_cancel(self._save_after_id)
            except Exception:
                pass
        self._save_after_id = self.after(250, self._autosave)

    def _autosave(self) -> None:
        self._save_after_id = None
        if self._capturing:
            return
        process = normalize_exe_name(self._process_var.get())
        if process is None:
            return
        pending = self._pending_var.get().strip()
        if not pending:
            return
        disable = to_keyboard_hotkey(self._disable_raw) or "f8"
        enable = to_keyboard_hotkey(self._enable_raw) or "f9"
        if disable == enable:
            self.set_status("Disable and enable hotkeys must be different.")
            return

        cfg = Config(
            process_name=process,
            pending_dir=pending,
            disable_hotkey=disable,
            enable_hotkey=enable,
        )
        if (
            cfg.process_name == self.controller.config.process_name
            and cfg.pending_dir == self.controller.config.pending_dir
            and to_keyboard_hotkey(cfg.disable_hotkey)
            == to_keyboard_hotkey(self.controller.config.disable_hotkey)
            and to_keyboard_hotkey(cfg.enable_hotkey)
            == to_keyboard_hotkey(self.controller.config.enable_hotkey)
        ):
            return

        save_config(cfg)
        self.controller.update_config(cfg)
        self.set_status("Settings saved.")

    def _start_hotkey_capture(self, which: str) -> None:
        if self._capturing:
            return
        self._capturing = which
        btn = self._disable_btn if which == "disable" else self._enable_btn
        var = self._disable_var if which == "disable" else self._enable_var
        previous = var.get()
        var.set("Press a key…")
        btn.state(["disabled"])
        self._disable_btn.state(["disabled"])
        self._enable_btn.state(["disabled"])
        self.controller.pause_hotkeys()
        self.set_status(f"Listening for {which} hotkey…")

        def worker() -> None:
            try:
                captured = capture_hotkey_blocking()
            except Exception:
                captured = ""
            self.after(0, lambda: self._finish_hotkey_capture(which, captured, previous))

        threading.Thread(target=worker, name="shadow-hotkey-capture", daemon=True).start()

    def _finish_hotkey_capture(self, which: str, captured: str, previous: str) -> None:
        self._disable_btn.state(["!disabled"])
        self._enable_btn.state(["!disabled"])
        var = self._disable_var if which == "disable" else self._enable_var
        self._capturing = None
        self.controller.resume_hotkeys()

        if not captured:
            var.set(previous)
            self.set_status("Hotkey capture cancelled.")
            return

        other = self._enable_raw if which == "disable" else self._disable_raw
        if to_keyboard_hotkey(captured) == to_keyboard_hotkey(other):
            var.set(previous)
            messagebox.showerror("Shadow", "Disable and enable hotkeys must be different.")
            self.set_status("Hotkeys must be different.")
            return

        if which == "disable":
            self._disable_raw = captured
        else:
            self._enable_raw = captured
        var.set(format_hotkey_display(captured))
        self._autosave()
        self.set_status(f"{which.capitalize()} hotkey set to {format_hotkey_display(captured)}.")

    def set_status(self, message: str) -> None:
        self._status_var.set(message)

    def _hide_to_tray(self) -> None:
        self.withdraw()
        try:
            self.on_hide()
        except Exception:
            pass

    def _on_unmap(self, _event: tk.Event) -> None:
        if self.state() == "iconic":
            self.after(10, self._hide_to_tray)

    def show_window(self) -> None:
        self.deiconify()
        self.lift()
        self.focus_force()
