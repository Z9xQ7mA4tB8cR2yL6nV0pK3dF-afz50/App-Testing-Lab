#!/usr/bin/env python3
"""
Screenshot Streamer - Streams low-quality screenshots to monitor server.
Runs alongside each test job to provide real-time monitoring.
"""

import base64
import io
import json
import os
import subprocess
import sys
import time
from urllib.request import Request, urlopen
from urllib.error import URLError

try:
    from PIL import Image
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "Pillow"], check=True)
    from PIL import Image


class ScreenshotStreamer:
    """Streams low-quality screenshots to monitor server."""

    def __init__(self, server_url: str, device_id: str, device_name: str, api_level: str, screen_size: str):
        self.server_url = server_url.rstrip("/")
        self.device_id = device_id
        self.device_name = device_name
        self.api_level = api_level
        self.screen_size = screen_size

        if not self.device_id or self.device_id == "auto":
            try:
                result = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=5)
                for line in result.stdout.strip().split("\n")[1:]:
                    if "emulator" in line or "device" in line:
                        self.device_id = line.split("\t")[0]
                        break
            except:
                pass

        self.adb_cmd = ["adb"]
        if self.device_id and self.device_id != "auto":
            self.adb_cmd.extend(["-s", self.device_id])

    def register(self):
        """Register device with monitor server."""
        data = {
            "device_id": self.device_id,
            "device_name": self.device_name,
            "api_level": self.api_level,
            "screen_size": self.screen_size
        }
        self._post("/api/device/register", data)

    def capture_screenshot_base64(self) -> str:
        try:
            import tempfile
            cmd = self.adb_cmd + ["exec-out", "screencap", "-p"]
            result = subprocess.run(cmd, capture_output=True, timeout=10)

            if result.returncode != 0 or len(result.stdout) < 100:
                tmp_local = os.path.join(tempfile.gettempdir(), "streamer_cap.png")
                subprocess.run(self.adb_cmd + ["shell", "screencap", "-p", "/sdcard/streamer_cap.png"], capture_output=True, timeout=10)
                time.sleep(0.5)
                r = subprocess.run(self.adb_cmd + ["pull", "/sdcard/streamer_cap.png", tmp_local], capture_output=True, timeout=10)
                if r.returncode != 0 or not os.path.exists(tmp_local) or os.path.getsize(tmp_local) < 100:
                    return ""
                with open(tmp_local, "rb") as f:
                    img_data = f.read()
                subprocess.run(self.adb_cmd + ["shell", "rm", "/sdcard/streamer_cap.png"], capture_output=True)
            else:
                img_data = result.stdout

            img = Image.open(io.BytesIO(img_data))
            max_height = 360
            if img.height > max_height:
                ratio = max_height / img.height
                new_width = int(img.width * ratio)
                img = img.resize((new_width, max_height), Image.LANCZOS)
            buffer = io.BytesIO()
            img.convert("RGB").save(buffer, format="JPEG", quality=50, optimize=True)
            return base64.b64encode(buffer.getvalue()).decode("utf-8")
        except Exception as e:
            print(f"Screenshot error: {e}")
            return ""

    def send_screenshot(self, image_b64: str, step: int, screens_found: int):
        """Send screenshot to monitor server."""
        data = {
            "image": image_b64,
            "step": step,
            "screens_found": screens_found
        }
        self._post(f"/api/device/{self.device_id}/screenshot", data)

    def send_status(self, status: str, step: int, screens_found: int):
        """Send status update to monitor server."""
        data = {
            "status": status,
            "step": step,
            "screens_found": screens_found
        }
        self._post(f"/api/device/{self.device_id}/status", data)

    def _post(self, path: str, data: dict):
        """POST JSON to server."""
        try:
            url = f"{self.server_url}{path}"
            body = json.dumps(data).encode("utf-8")
            req = Request(url, data=body, headers={"Content-Type": "application/json"})
            urlopen(req, timeout=5)
        except URLError:
            pass
        except Exception:
            pass


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Screenshot streamer for monitor")
    parser.add_argument("--server", required=True, help="Monitor server URL")
    parser.add_argument("--device", required=True, help="Device ID")
    parser.add_argument("--device-name", default="Unknown", help="Device name")
    parser.add_argument("--api-level", default="?", help="API level")
    parser.add_argument("--screen-size", default="?", help="Screen size")
    parser.add_argument("--interval", type=float, default=2.0, help="Screenshot interval (seconds)")
    parser.add_argument("--output-dir", default="artifacts", help="Output directory for logs")
    args = parser.parse_args()

    streamer = ScreenshotStreamer(
        server_url=args.server,
        device_id=args.device,
        device_name=args.device_name,
        api_level=args.api_level,
        screen_size=args.screen_size
    )

    print(f"Streamer: {args.device_name} (API {args.api_level}) -> {args.server}")

    # Register
    streamer.register()

    # Stream loop
    step = 0
    screens_found = 0
    while True:
        try:
            # Read step count from file if exists
            step_file = os.path.join(args.output_dir, "stream_step.txt")
            if os.path.exists(step_file):
                with open(step_file) as f:
                    parts = f.read().strip().split(",")
                    step = int(parts[0]) if parts else 0
                    screens_found = int(parts[1]) if len(parts) > 1 else 0

            # Capture and send
            img_b64 = streamer.capture_screenshot_base64()
            if img_b64:
                streamer.send_screenshot(img_b64, step, screens_found)

            time.sleep(args.interval)
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Streamer error: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()
