#!/usr/bin/env python3
"""
Local Monitor - Quick local monitoring server for testing.
Run this to start monitor locally, then run streamers.
"""

import subprocess
import sys
import os
import time
import webbrowser
from pathlib import Path


def main():
    print("=" * 60)
    print("Test Lab Monitor - Local Mode")
    print("=" * 60)

    # Install dependencies
    print("\nInstalling dependencies...")
    subprocess.run([sys.executable, "-m", "pip", "install", "-q",
                    "fastapi", "uvicorn[standard]", "websockets", "Pillow"], check=True)

    # Start server
    print("\nStarting monitor server on http://localhost:8765")
    server_proc = subprocess.Popen(
        [sys.executable, str(Path(__file__).parent / "server.py")],
        env={**os.environ, "MONITOR_PORT": "8765"}
    )

    time.sleep(2)

    # Try to open browser
    try:
        webbrowser.open("http://localhost:8765")
    except:
        pass

    print("\nDashboard: http://localhost:8765")
    print("\nTo stream a device, run:")
    print(f"  python monitor/streamer.py --server http://localhost:8765 --device auto --device-name 'My Device' --api-level 34 --screen-size 1080x2400")
    print("\nPress Ctrl+C to stop")
    print("=" * 60)

    try:
        server_proc.wait()
    except KeyboardInterrupt:
        print("\nStopping...")
        server_proc.terminate()
        server_proc.wait()


if __name__ == "__main__":
    main()
