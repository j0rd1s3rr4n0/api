import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk


APP_TITLE = "Proxy Security Toolkit"


def resource_path(name: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / name


def launcher_dir() -> Path:
    return Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve().parent


def repo_root() -> Path:
    here = launcher_dir()
    if (here.parent / "opendir_downloader_pro").exists():
        return here.parent
    if (here / "tools").exists():
        return here
    return here


def candidate_paths(*parts: str) -> list[Path]:
    root = repo_root()
    here = launcher_dir()
    return [
        here.joinpath(*parts),
        here / "tools" / Path(*parts).name,
        root.joinpath(*parts),
    ]


def first_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def python_command() -> list[str]:
    return [sys.executable] if not getattr(sys, "frozen", False) else ["python3" if os.name != "nt" else "python"]


class Tool:
    def __init__(self, name: str, description: str, exe_parts: tuple[str, ...], script_parts: tuple[str, ...], console: bool) -> None:
        self.name = name
        self.description = description
        self.exe_parts = exe_parts
        self.script_parts = script_parts
        self.console = console


TOOLS = [
    Tool(
        "OpenDir Downloader Pro",
        "GUI principal para open directories, Tor, proxies, filtros y descarga selectiva.",
        ("opendir_downloader_pro", "dist", "opendir_downloader_pro.exe" if os.name == "nt" else "opendir_downloader_pro"),
        ("opendir_downloader_pro", "opendir_downloader_pro.py"),
        False,
    ),
    Tool(
        "OpenDir Downloader Classic",
        "GUI clasica, mantenida como variante estable.",
        ("opendir_downloader", "dist", "opendir_downloader_gui.exe" if os.name == "nt" else "opendir_downloader_gui"),
        ("opendir_downloader", "opendir_downloader_gui.py"),
        False,
    ),
    Tool(
        "OpenDir CLI",
        "Version de consola para automatizar mirrors de directorios.",
        ("opendir_downloader", "dist", "opendir_downloader.exe" if os.name == "nt" else "opendir_downloader"),
        ("opendir_downloader", "opendir_downloader.py"),
        True,
    ),
    Tool(
        "Google Dork Auditor",
        "Buscador/categorizador de dorks y resultados.",
        ("google_dork_auditor", "dist", "google_dork_auditor.exe" if os.name == "nt" else "google_dork_auditor"),
        ("google_dork_auditor", "google_dork_auditor.py"),
        False,
    ),
    Tool(
        "Ultimate Multi Proxy",
        "Scraper/validador multiproceso de proxies HTTP/HTTPS/SOCKS.",
        ("dist", "ultimater_multi.exe" if os.name == "nt" else "ultimater_multi"),
        ("ultimater_multi.py",),
        True,
    ),
]


class ToolkitApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("900x560")
        self.minsize(780, 480)
        self.configure(bg="#eef2f6")
        icon = resource_path("toolkit.ico")
        if icon.exists() and os.name == "nt":
            self.iconbitmap(default=str(icon))
        self.configure_theme()
        self.build_ui()

    def configure_theme(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        self.option_add("*Font", "{Segoe UI} 9")
        style.configure(".", background="#eef2f6", foreground="#111827", font=("Segoe UI", 9))
        style.configure("TFrame", background="#eef2f6")
        style.configure("Panel.TFrame", background="#ffffff")
        style.configure("Title.TLabel", background="#eef2f6", foreground="#111827", font=("Segoe UI", 18, "bold"))
        style.configure("Sub.TLabel", background="#eef2f6", foreground="#4b5563")
        style.configure("Tool.TLabelframe", background="#ffffff", bordercolor="#d8dee8", relief="solid")
        style.configure("Tool.TLabelframe.Label", background="#eef2f6", foreground="#374151", font=("Segoe UI", 10, "bold"))
        style.configure("Accent.TButton", background="#2563eb", foreground="#ffffff", padding=(12, 7))
        style.map("Accent.TButton", background=[("active", "#1d4ed8")])
        style.configure("TButton", padding=(10, 6))

    def build_ui(self) -> None:
        header = ttk.Frame(self, padding=(18, 16, 18, 8))
        header.pack(fill=tk.X)
        ttk.Label(header, text=APP_TITLE, style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text="Launcher unico para OpenDir, Google Dorks y validacion de proxies.",
            style="Sub.TLabel",
        ).pack(anchor="w", pady=(4, 0))

        body = ttk.Frame(self, padding=(18, 8, 18, 12))
        body.pack(fill=tk.BOTH, expand=True)
        body.columnconfigure(0, weight=1)
        for index, tool in enumerate(TOOLS):
            self.add_tool_row(body, index, tool)

        footer = ttk.Frame(self, padding=(18, 0, 18, 14))
        footer.pack(fill=tk.X)
        self.status = tk.StringVar(value=f"Base: {repo_root()}")
        ttk.Label(footer, textvariable=self.status, style="Sub.TLabel").pack(side=tk.LEFT)
        ttk.Button(footer, text="Abrir carpeta", command=self.open_folder).pack(side=tk.RIGHT)

    def add_tool_row(self, parent: ttk.Frame, row: int, tool: Tool) -> None:
        frame = ttk.LabelFrame(parent, text=tool.name, style="Tool.TLabelframe", padding=10)
        frame.grid(row=row, column=0, sticky="ew", pady=6)
        frame.columnconfigure(0, weight=1)
        ttk.Label(frame, text=tool.description, wraplength=620).grid(row=0, column=0, sticky="w")
        ttk.Button(frame, text="Abrir", style="Accent.TButton", command=lambda: self.launch_tool(tool)).grid(
            row=0, column=1, padx=(12, 0)
        )
        ttk.Button(frame, text="Ubicar", command=lambda: self.locate_tool(tool)).grid(row=0, column=2, padx=(8, 0))

    def resolve_tool(self, tool: Tool) -> tuple[list[str], Path] | None:
        exe = first_existing(candidate_paths(*tool.exe_parts))
        if exe:
            return [str(exe)], exe.parent
        script = first_existing(candidate_paths(*tool.script_parts))
        if script:
            return [*python_command(), str(script)], script.parent
        return None

    def launch_tool(self, tool: Tool) -> None:
        resolved = self.resolve_tool(tool)
        if not resolved:
            messagebox.showerror("No encontrado", f"No encuentro binario ni script para {tool.name}.")
            return
        command, cwd = resolved
        try:
            if os.name == "nt" and tool.console:
                subprocess.Popen(["cmd", "/c", "start", "", *command], cwd=str(cwd))
            else:
                subprocess.Popen(command, cwd=str(cwd))
            self.status.set(f"Lanzado: {tool.name}")
        except Exception as exc:
            messagebox.showerror("Error al abrir", str(exc))

    def locate_tool(self, tool: Tool) -> None:
        resolved = self.resolve_tool(tool)
        if not resolved:
            messagebox.showerror("No encontrado", f"No encuentro {tool.name}.")
            return
        _, cwd = resolved
        self.open_path(cwd)

    def open_folder(self) -> None:
        self.open_path(repo_root())

    @staticmethod
    def open_path(path: Path) -> None:
        try:
            if os.name == "nt":
                os.startfile(str(path))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except Exception as exc:
            messagebox.showerror("Abrir carpeta", str(exc))


if __name__ == "__main__":
    ToolkitApp().mainloop()
