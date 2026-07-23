from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Callable

from .config import Config, save_config
from .controller import ShadowController


class ShadowApp(tk.Tk):
    def __init__(self, controller: ShadowController, on_hide: Callable[[], None]) -> None:
        super().__init__()
        self.controller = controller
        self.on_hide = on_hide
        self.title("Shadow")
        self.geometry("520x360")
        self.minsize(480, 320)
        self.configure(bg="#1e1e1e")

        self._process_var = tk.StringVar(value=controller.config.process_name)
        self._pending_var = tk.StringVar(value=controller.config.pending_dir)
        self._disable_var = tk.StringVar(value=controller.config.disable_hotkey)
        self._enable_var = tk.StringVar(value=controller.config.enable_hotkey)
        self._status_var = tk.StringVar(value="Ready. Shadow is OFF.")

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
        style.configure("Status.TLabel", foreground="#b0b0b0", wraplength=470)

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

        self._row(form, 0, "Process name", self._process_var, hint="e.g. wordpress.exe")
        self._row(form, 1, "Pending directory", self._pending_var, browse=True)
        self._row(form, 2, "Disable hotkey", self._disable_var, hint="default F8")
        self._row(form, 3, "Enable hotkey", self._enable_var, hint="default F9")

        btns = ttk.Frame(root)
        btns.pack(fill=tk.X, pady=(16, 8))
        ttk.Button(btns, text="Save config", command=self._save).pack(side=tk.LEFT)
        ttk.Button(btns, text="Shadow ON", command=self.controller.activate_shadow).pack(
            side=tk.LEFT, padx=(8, 0)
        )
        ttk.Button(btns, text="Shadow OFF", command=self.controller.deactivate_shadow).pack(
            side=tk.LEFT, padx=(8, 0)
        )
        ttk.Button(btns, text="Hide to tray", command=self._hide_to_tray).pack(side=tk.RIGHT)

        ttk.Label(root, textvariable=self._status_var, style="Status.TLabel").pack(
            anchor="w", pady=(10, 0), fill=tk.X
        )

    def _row(
        self,
        parent: ttk.Frame,
        row: int,
        label: str,
        variable: tk.StringVar,
        hint: str = "",
        browse: bool = False,
    ) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=6)
        entry = ttk.Entry(parent, textvariable=variable, width=42)
        entry.grid(row=row, column=1, sticky="ew", padx=(10, 0), pady=6)
        if browse:
            ttk.Button(parent, text="…", width=3, command=self._browse_pending).grid(
                row=row, column=2, padx=(6, 0)
            )
        elif hint:
            ttk.Label(parent, text=hint, style="Hint.TLabel").grid(
                row=row, column=2, sticky="w", padx=(8, 0)
            )
        parent.columnconfigure(1, weight=1)

    def _browse_pending(self) -> None:
        path = filedialog.askdirectory(initialdir=self._pending_var.get() or None)
        if path:
            if not path.endswith("\\") and not path.endswith("/"):
                path += "\\"
            self._pending_var.set(path)

    def _save(self) -> None:
        cfg = Config(
            process_name=self._process_var.get().strip() or "wordpress.exe",
            pending_dir=self._pending_var.get().strip(),
            disable_hotkey=self._disable_var.get().strip().upper() or "F8",
            enable_hotkey=self._enable_var.get().strip().upper() or "F9",
        )
        if cfg.disable_hotkey == cfg.enable_hotkey:
            messagebox.showerror("Shadow", "Disable and enable hotkeys must be different.")
            return
        save_config(cfg)
        self.controller.update_config(cfg)
        self.set_status("Config saved.")
        messagebox.showinfo("Shadow", "Configuration saved.")

    def set_status(self, message: str) -> None:
        self._status_var.set(message)

    def _hide_to_tray(self) -> None:
        self.withdraw()
        try:
            self.on_hide()
        except Exception:
            pass

    def _on_unmap(self, _event: tk.Event) -> None:
        # Minimize also goes to tray.
        if self.state() == "iconic":
            self.after(10, self._hide_to_tray)

    def show_window(self) -> None:
        self.deiconify()
        self.lift()
        self.focus_force()
