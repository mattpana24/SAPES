import os
import sys
import time
import socket
import threading
import webbrowser

from streamlit.web import bootstrap


def resource_path(relative_path: str) -> str:
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


def wait_for_port(host="127.0.0.1", port=8501, timeout=30):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            time.sleep(0.5)
    return False


def open_browser():
    if wait_for_port():
        webbrowser.open("http://localhost:8501")


def main():
    app_path = resource_path("app.py")

    if not os.path.exists(app_path):
        print(f"ERROR: app.py not found at {app_path}")
        input("Press Enter to exit...")
        return

    threading.Thread(target=open_browser, daemon=True).start()

    bootstrap.run(
        app_path,
        False,
        [],
        {
            "server.headless": True,
            "browser.gatherUsageStats": False,
            "server.port": 8501,
        },
    )


if __name__ == "__main__":
    main()