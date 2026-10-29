"""Start the local store from its project root and open it when ready."""

import argparse
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
URL = "http://127.0.0.1:8000"


def site_ready():
    try:
        with urllib.request.urlopen(URL, timeout=1) as response:
            return b"/static/app.js" in response.read()
    except (OSError, urllib.error.URLError):
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    os.chdir(ROOT)
    if not (ROOT / ".env").is_file():
        raise SystemExit("Missing .env. Follow README.md: first installation.")
    if site_ready():
        print(f"Site is already running: {URL}")
        if not args.no_browser:
            webbrowser.open(URL)
        return
    with socket.socket() as probe:
        if probe.connect_ex(("127.0.0.1", 8000)) == 0:
            raise SystemExit("Port 8000 is used by another application. See README.md.")
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=ROOT,
    )
    try:
        for _ in range(60):
            if process.poll() is not None:
                raise SystemExit("Server could not start. Read the error above.")
            if site_ready():
                break
            time.sleep(0.25)
        else:
            raise SystemExit("Server did not become ready. Read the error above.")
        print(f"Site: {URL} | Stop: Ctrl+C", flush=True)
        if not args.no_browser:
            webbrowser.open(URL)
        process.wait()
    except KeyboardInterrupt:
        pass
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


if __name__ == "__main__":
    main()
