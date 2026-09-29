"""Clickable Windows launcher for the local Study Transcribe web app."""
from __future__ import annotations
import subprocess, sys, time, webbrowser
from pathlib import Path


def repo_root() -> Path:
    location = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve()
    candidates = [location.parent, location.parent.parent] if getattr(sys, "frozen", False) else [location.parent]
    for candidate in candidates:
        if (candidate / ".venv" / "Scripts" / "python.exe").is_file() and (candidate / "webapp" / "app.py").is_file():
            return candidate
    return location.parent


def main() -> None:
    root = repo_root(); python = root / ".venv" / "Scripts" / "python.exe"; app = root / "webapp" / "app.py"
    if not python.is_file() or not app.is_file():
        import tkinter.messagebox as messagebox
        messagebox.showerror("Study Transcribe", "Could not find .venv\\Scripts\\python.exe or webapp\\app.py beside the launcher.")
        return
    subprocess.Popen([str(python), str(app)], cwd=str(root), creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    time.sleep(1.5); webbrowser.open("http://127.0.0.1:5000")


if __name__ == "__main__":
    main()
