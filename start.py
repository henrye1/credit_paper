"""Single-command launcher for the Credit Paper Assessment application.

Usage: python start.py
"""

import subprocess
import sys
import webbrowser
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
FRONTEND_DIST = FRONTEND_DIR / "dist"
PORT = 8000


def check_node():
    """Check if Node.js is available."""
    try:
        result = subprocess.run(["node", "--version"], capture_output=True, text=True, shell=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False


def install_frontend():
    """Install frontend dependencies if needed."""
    node_modules = FRONTEND_DIR / "node_modules"
    if not node_modules.exists():
        print("Installing frontend dependencies...")
        subprocess.run(
            ["npm", "install"],
            cwd=str(FRONTEND_DIR),
            check=True,
            shell=True,
        )


def build_frontend():
    """Build the React frontend if dist/ is missing or stale."""
    if FRONTEND_DIST.exists():
        src_dir = FRONTEND_DIR / "src"
        if src_dir.exists():
            latest_src = max(f.stat().st_mtime for f in src_dir.rglob("*") if f.is_file())
            index_html = FRONTEND_DIST / "index.html"
            if index_html.exists() and index_html.stat().st_mtime > latest_src:
                print("Frontend build is up to date.")
                return

    print("Building frontend...")
    subprocess.run(
        ["npm", "run", "build"],
        cwd=str(FRONTEND_DIR),
        check=True,
        shell=True,
    )


def start_server():
    """Start the FastAPI server with uvicorn."""
    print(f"\nStarting server on http://localhost:{PORT}")
    print("Press Ctrl+C to stop.\n")

    import threading
    def open_browser():
        time.sleep(1.5)
        webbrowser.open(f"http://localhost:{PORT}")

    threading.Thread(target=open_browser, daemon=True).start()

    subprocess.run(
        [
            sys.executable, "-m", "uvicorn",
            "backend.main:app",
            "--host", "0.0.0.0",
            "--port", str(PORT),
            "--reload",
        ],
        cwd=str(PROJECT_ROOT),
    )


def main():
    print("Credit Paper Assessment - Starting...")
    print(f"Project root: {PROJECT_ROOT}\n")

    if check_node():
        try:
            install_frontend()
            build_frontend()
        except subprocess.CalledProcessError as e:
            print(f"Frontend build failed: {e}")
            print("Continuing without frontend build (use dev mode instead).")
    else:
        print("Node.js not found. Skipping frontend build.")
        print("Use 'npm run dev' in frontend/ for development mode.")

    start_server()


if __name__ == "__main__":
    main()
