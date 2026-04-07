"""Hot-reload dev runner for the Discord bot.

Watches all .py files in the project. On any change, kills the current
bot process and restarts it automatically.

Usage:
    uv run python dev.py discord [--provider gemini] [--model ...]
    uv run python dev.py telegram [--provider gemini]
    uv run python dev.py run "your requirement"  # CLI pipeline

Pass any extra flags after the command — they are forwarded to main.py.

Example:
    uv run python dev.py discord --provider gemini --log-level DEBUG
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from watchfiles import watch


# ------------------------------------------------------------------
# Config
# ------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent
WATCH_DIRS = [PROJECT_ROOT]
IGNORE_PATTERNS = {
    "__pycache__", ".venv", ".git", ".mypy_cache",
    "*.pyc", "*.pyo", "output.md", "*.log",
}


def _should_ignore(path: str) -> bool:
    p = Path(path)
    for part in p.parts:
        if part in IGNORE_PATTERNS:
            return True
    return p.suffix in {".pyc", ".pyo", ".log"}


# ------------------------------------------------------------------
# Process management
# ------------------------------------------------------------------

def start_process(args: list[str]) -> subprocess.Popen:
    cmd = [sys.executable, str(PROJECT_ROOT / "main.py")] + args
    print(f"\n🚀 Starting: {' '.join(cmd)}\n{'─' * 60}")
    return subprocess.Popen(cmd, cwd=PROJECT_ROOT)


def stop_process(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return  # already dead
    print("\n🔄 File change detected — restarting bot...")
    try:
        if sys.platform == "win32":
            proc.terminate()
        else:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        proc.wait(timeout=5)
    except Exception:
        proc.kill()


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    # Forward all args after dev.py to main.py
    forward_args = sys.argv[1:]

    proc = start_process(forward_args)

    try:
        for changes in watch(
            *WATCH_DIRS,
            watch_filter=lambda _, path: not _should_ignore(path),
            poll_delay_ms=300,
        ):
            changed_files = [Path(p).relative_to(PROJECT_ROOT) for _, p in changes]
            print(f"📝 Changed: {', '.join(str(f) for f in changed_files)}")

            stop_process(proc)
            time.sleep(0.3)  # brief pause so files finish writing
            proc = start_process(forward_args)

    except KeyboardInterrupt:
        print("\n⏹️  Stopping...")
        stop_process(proc)
        sys.exit(0)


if __name__ == "__main__":
    main()
