#!/usr/bin/env python3
"""
Auto Explore - Production-grade Android App Auto-Explorer
Multi-strategy approach for reliable screen discovery.
Works with Flutter, React Native, and native Android apps.
"""

import argparse
import base64
import hashlib
import io
import json
import os
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.request import Request, urlopen
from urllib.error import URLError

try:
    from PIL import Image
except ImportError:
    subprocess.run([sys.executable, "-m", "pip", "install", "Pillow"], check=True, capture_output=True)
    from PIL import Image


@dataclass
class Element:
    """UI Element found on screen."""
    resource_id: str = ""
    text: str = ""
    content_desc: str = ""
    hint_text: str = ""
    class_name: str = ""
    package: str = ""
    clickable: bool = False
    scrollable: bool = False
    bounds: str = ""
    index: int = 0
    source: str = "uiautomator"

    @property
    def bounds_tuple(self):
        try:
            clean = self.bounds.replace("][", ",").strip("[]")
            parts = clean.split(",")
            if len(parts) == 4:
                return tuple(map(int, parts))
        except:
            pass
        return (0, 0, 0, 0)

    @property
    def center(self):
        x1, y1, x2, y2 = self.bounds_tuple
        return ((x1 + x2) // 2, (y1 + y2) // 2)

    @property
    def area(self):
        x1, y1, x2, y2 = self.bounds_tuple
        return (x2 - x1) * (y2 - y1)

    @property
    def label(self):
        return self.text or self.content_desc or self.hint_text or self.resource_id.split("/")[-1] if "/" in self.resource_id else f"elem_{self.index}"


@dataclass
class Screen:
    """Represents a discovered screen."""
    screen_id: str = ""
    activity: str = ""
    package: str = ""
    screenshot_path: str = ""
    elements: list = field(default_factory=list)
    visited: bool = False
    timestamp: float = 0.0
    strategy_used: str = ""


class ADBController:
    """Controls Android device via ADB with retry logic."""

    def __init__(self, device_id: Optional[str] = None):
        self.device_id = device_id
        self.adb_cmd = ["adb"]
        if device_id:
            self.adb_cmd.extend(["-s", device_id])

    def run(self, command: str, timeout: int = 30, retries: int = 2) -> str:
        for attempt in range(retries):
            try:
                full_cmd = self.adb_cmd + ["shell"] + command.split()
                result = subprocess.run(
                    full_cmd, capture_output=True, text=True, timeout=timeout
                )
                if result.returncode == 0:
                    return result.stdout.strip()
            except subprocess.TimeoutExpired:
                if attempt < retries - 1:
                    time.sleep(1)
                    continue
            except Exception as e:
                print(f"  ADB error: {e}")
                if attempt < retries - 1:
                    time.sleep(1)
                    continue
        return ""

    def run_raw(self, args: list, timeout: int = 30) -> str:
        try:
            full_cmd = self.adb_cmd + args
            result = subprocess.run(
                full_cmd, capture_output=True, text=True, timeout=timeout
            )
            return result.stdout.strip()
        except:
            return ""

    def screencap(self, output_path: str) -> bool:
        try:
            full_cmd = self.adb_cmd + ["exec-out", "screencap", "-p"]
            with open(output_path, "wb") as f:
                result = subprocess.run(full_cmd, capture_output=True, timeout=15)
                if result.returncode == 0 and len(result.stdout) > 100:
                    f.write(result.stdout)
                    return True
            # Fallback: file-based capture
            self.run("screencap -p /sdcard/screencap_tmp.png")
            time.sleep(0.5)
            pull_cmd = self.adb_cmd + ["pull", "/sdcard/screencap_tmp.png", output_path]
            subprocess.run(pull_cmd, capture_output=True, timeout=15)
            self.run("rm /sdcard/screencap_tmp.png")
            return os.path.exists(output_path) and os.path.getsize(output_path) > 0
        except Exception as e:
            print(f"  Screencap error: {e}")
            return False

    def tap(self, x: int, y: int) -> bool:
        self.run(f"input tap {x} {y}")
        time.sleep(0.8)
        return True

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: int = 300) -> bool:
        self.run(f"input swipe {x1} {y1} {x2} {y2} {duration}")
        time.sleep(0.8)
        return True

    def press_back(self) -> bool:
        self.run("input keyevent 4")
        time.sleep(0.8)
        return True

    def press_home(self) -> bool:
        self.run("input keyevent 3")
        time.sleep(0.5)
        return True

    def get_current_activity(self) -> str:
        output = self.run("dumpsys activity activities | grep mResumedActivity")
        if not output:
            output = self.run("dumpsys activity activities | grep -E 'mCurrentFocus|mFocusedApp'")
        return output

    def get_screen_size(self) -> tuple:
        output = self.run("wm size")
        try:
            size_str = output.split(":")[-1].strip()
            w, h = size_str.split("x")
            return (int(w), int(h))
        except:
            return (1080, 1920)

    def get_ui_hierarchy_uiautomator(self) -> Optional[ET.Element]:
        """Strategy 1: Standard uiautomator dump."""
        try:
            self.run("rm /sdcard/window_dump.xml")
            output = self.run("uiautomator dump /sdcard/window_dump.xml", timeout=15)
            if "dumped" in output.lower() or "hierarchy" in output.lower():
                time.sleep(0.5)
                xml_content = self.run("cat /sdcard/window_dump.xml")
                if xml_content and "<hierarchy" in xml_content:
                    return ET.fromstring(xml_content)
        except ET.ParseError as e:
            print(f"  XML parse error: {e}")
        except Exception as e:
            print(f"  uiautomator dump failed: {e}")
        return None

    def get_ui_hierarchy_dumpsys(self, package: str) -> list:
        """Strategy 2: Use dumpsys to find clickable regions."""
        elements = []
        try:
            output = self.run("dumpsys activity top | grep -A 5 'View Hierarchy'", timeout=10)
            # Parse view hierarchy from dumpsys
        except:
            pass
        return elements

    def is_screen_on(self) -> bool:
        output = self.run("dumpsys power | grep 'Display Power'")
        return "ON" in output.upper()

    def wake_screen(self):
        if not self.is_screen_on():
            self.run("input keyevent 26")
            time.sleep(1)


class ScreenComparator:
    """Compare screenshots to detect screen changes."""

    @staticmethod
    def compute_hash(image_path: str, region: str = "header") -> str:
        try:
            with open(image_path, "rb") as f:
                data = f.read()
            return hashlib.md5(data).hexdigest()[:16]
        except:
            return ""

    @staticmethod
    def compare_files(path1: str, path2: str) -> float:
        try:
            from PIL import Image
            import numpy as np

            img1 = Image.open(path1).convert("RGB").resize((180, 320))
            img2 = Image.open(path2).convert("RGB").resize((180, 320))

            arr1 = np.array(img1, dtype=np.float32)
            arr2 = np.array(img2, dtype=np.float32)

            diff = np.abs(arr1 - arr2)
            mean_diff = diff.mean()

            if mean_diff < 2.0:
                return 1.0
            elif mean_diff < 10.0:
                return 0.95
            elif mean_diff < 30.0:
                return 0.7
            else:
                return 0.3
        except ImportError:
            try:
                with open(path1, "rb") as f1, open(path2, "rb") as f2:
                    data1 = f1.read()
                    data2 = f2.read()
                if data1 == data2:
                    return 1.0
                size_ratio = min(len(data1), len(data2)) / max(len(data1), len(data2))
                return size_ratio
            except:
                return 0.0
        except:
            return 0.0


class AutoExplorer:
    """Production-grade Android app auto-explorer with multi-strategy approach."""

    def __init__(self, adb: ADBController, package: str, output_dir: str, max_steps: int = 50, server_url: str = "", device_label: str = ""):
        self.adb = adb
        self.package = package
        self.output_dir = Path(output_dir)
        self.max_steps = max_steps
        self.server_url = server_url.rstrip("/") if server_url else ""
        self.device_label = device_label or ("emulator" if not adb.device_id else adb.device_id)
        self.screenshots_dir = self.output_dir / "screenshots"
        self.logs_dir = self.output_dir / "logs"
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        self.screens: dict[str, Screen] = {}
        self.visited_elements: set = set()
        self.step_count = 0
        self.consecutive_same_screen = 0
        self.consecutive_out_of_app = 0
        self.last_screen_hash = ""
        self.last_screenshot_path = ""
        self.grid_offset = 0

    def get_screen_signature(self, elements: list[Element]) -> str:
        sig_parts = []
        sorted_elems = sorted(elements, key=lambda e: (e.class_name, e.bounds, e.text[:6]))
        for e in sorted_elems[:15]:
            sig_parts.append(f"{e.class_name}:{e.bounds}")
        return hashlib.md5("|".join(sig_parts).encode()).hexdigest()[:12]

    def parse_elements_from_xml(self, root: ET.Element) -> list[Element]:
        elements = []
        for node in root.iter("node"):
            try:
                elem = Element(
                    resource_id=node.get("resource-id", ""),
                    text=node.get("text", ""),
                    content_desc=node.get("content-desc", ""),
                    hint_text=node.get("hint", ""),
                    class_name=node.get("class", ""),
                    package=node.get("package", ""),
                    clickable=node.get("clickable", "false") == "true",
                    scrollable=node.get("scrollable", "false") == "true",
                    bounds=node.get("bounds", ""),
                    index=int(node.get("index", "0")),
                    source="uiautomator"
                )
                if elem.package == self.package and (elem.clickable or elem.text or elem.content_desc or elem.hint_text):
                    elements.append(elem)
            except:
                continue
        return elements

    def generate_grid_elements(self, screen_width: int, screen_height: int) -> list[Element]:
        """Strategy: Generate grid-based tap points with randomized order."""
        import random
        elements = []
        top_margin = int(screen_height * 0.10)
        bottom_margin = int(screen_height * 0.85)

        grid_cols = 3
        grid_rows = 5
        cell_w = screen_width // grid_cols
        cell_h = (bottom_margin - top_margin) // grid_rows

        all_points = []
        for row in range(grid_rows):
            for col in range(grid_cols):
                x = col * cell_w + cell_w // 2
                y = top_margin + row * cell_h + cell_h // 2
                all_points.append((x, y))

        random.shuffle(all_points)

        for idx, (x, y) in enumerate(all_points):
            elem = Element(
                bounds=f"[{x-15},{y-15}][{x+15},{y+15}]",
                clickable=True,
                index=idx,
                source="grid",
                text=f"grid_{idx}"
            )
            elements.append(elem)
        return elements

    def capture_screen(self, label: str = "") -> str:
        timestamp = int(time.time())
        filename = f"step_{self.step_count:03d}_{label}_{timestamp}.png"
        filepath = self.screenshots_dir / filename
        if self.adb.screencap(str(filepath)):
            self._send_screenshot(filepath)
            return str(filepath)
        return ""

    def _send_screenshot(self, filepath: str):
        if not self.server_url:
            return
        import threading
        t = threading.Thread(target=self._do_send_screenshot, args=(filepath,), daemon=True)
        t.start()

    def _do_send_screenshot(self, filepath: str):
        data_bytes = None
        try:
            with open(filepath, "rb") as f:
                img_data = f.read()
            img = Image.open(io.BytesIO(img_data))
            max_height = 720
            if img.height > max_height:
                ratio = max_height / img.height
                new_width = int(img.width * ratio)
                img = img.resize((new_width, max_height), Image.LANCZOS)
            buffer = io.BytesIO()
            img.convert("RGB").save(buffer, format="JPEG", quality=85, optimize=True)
            b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
            data_bytes = json.dumps({"image": b64, "step": self.step_count, "device_id": self.device_label}).encode()
        except Exception as e:
            print(f"  [stream] Encode error: {e}")
            return

        for attempt in range(3):
            try:
                req = Request(f"{self.server_url}/api/screenshot", data=data_bytes, headers={"Content-Type": "application/json"})
                urlopen(req, timeout=5)
                return
            except Exception as e:
                if attempt < 2:
                    time.sleep(2)
                if attempt == 2:
                    print(f"  [stream] Failed after 3 attempts: {e}")

    def strategy_ui_hierarchy(self) -> list[Element]:
        """Strategy 1: Standard uiautomator dump."""
        root = self.adb.get_ui_hierarchy_uiautomator()
        if root is not None:
            elements = self.parse_elements_from_xml(root)
            if elements:
                print(f"  [uiautomator] Found {len(elements)} elements")
                return elements
        print("  [uiautomator] No elements found, trying fallback")
        return []

    def strategy_dumpsys(self) -> list[Element]:
        """Strategy 2: Use dumpsys to find current activity and UI state."""
        activity = self.adb.get_current_activity()
        print(f"  [dumpsys] Activity: {activity[:80]}")
        # Return empty - this is for logging, not element discovery
        return []

    def strategy_grid(self) -> list[Element]:
        """Strategy 3: Grid-based exploration."""
        w, h = self.adb.get_screen_size()
        elements = self.generate_grid_elements(w, h)
        print(f"  [grid] Generated {len(elements)} grid points")
        return elements

    def is_in_target_app(self) -> bool:
        activity = self.adb.get_current_activity()
        return self.package in activity

    def relaunch_app(self):
        print(f"  [recovery] Relaunching {self.package}")
        self.adb.press_home()
        time.sleep(0.5)
        self.adb.run(f"monkey -p {self.package} -c android.intent.category.LAUNCHER 1")
        time.sleep(3)
        self.consecutive_same_screen = 0
        self.consecutive_out_of_app = 0
        self.visited_elements.clear()

    def explore_step(self) -> bool:
        if self.step_count >= self.max_steps:
            print(f"Max steps ({self.max_steps}) reached")
            return False

        self.step_count += 1
        print(f"\n--- Step {self.step_count}/{self.max_steps} ---")

        self.adb.wake_screen()

        if not self.is_in_target_app():
            self.consecutive_out_of_app += 1
            print(f"  [out of app] Not in {self.package} (count: {self.consecutive_out_of_app})")
            if self.consecutive_out_of_app >= 2:
                self.relaunch_app()
            else:
                self.adb.press_back()
                time.sleep(1)
            return True
        else:
            self.consecutive_out_of_app = 0

        current_screenshot = self.capture_screen(f"step_{self.step_count}")

        elements = self.strategy_ui_hierarchy()
        self.strategy_dumpsys()

        if not elements:
            for retry in range(3):
                activity = self.adb.get_current_activity()
                if self.package in activity:
                    print(f"  [retry] uiautomator empty, waiting... ({retry+1}/3)")
                    time.sleep(2)
                    elements = self.strategy_ui_hierarchy()
                    if elements:
                        break
                else:
                    break

        if not elements:
            elements = self.strategy_grid()

        if not elements:
            self.adb.press_back()
            time.sleep(1)
            return True

        screen_hash = self.get_screen_signature(elements)

        if screen_hash == self.last_screen_hash:
            self.consecutive_same_screen += 1
            print(f"  Same elements as before (stuck: {self.consecutive_same_screen}/3)")
            if self.consecutive_same_screen >= 3:
                self.adb.press_back()
                time.sleep(1)
                if not self.is_in_target_app():
                    self.relaunch_app()
                else:
                    self.consecutive_same_screen = 0
                return True
        else:
            self.consecutive_same_screen = 0

        self.last_screen_hash = screen_hash

        is_new_screen = screen_hash not in self.screens
        if is_new_screen:
            print(f"  NEW SCREEN: {screen_hash}")
            self.screens[screen_hash] = Screen(
                screen_id=screen_hash,
                activity=self.adb.get_current_activity()[:100],
                package=self.package,
                screenshot_path=current_screenshot,
                elements=elements,
                visited=True,
                timestamp=time.time(),
                strategy_used=elements[0].source if elements else "unknown"
            )

        tapped = False
        for elem in elements:
            elem_key = f"{screen_hash}:{elem.bounds}:{elem.source}"

            if elem_key not in self.visited_elements:
                self.visited_elements.add(elem_key)
                x, y = elem.center

                if x > 0 and y > 0:
                    print(f"  Tapping: {elem.label} at ({x}, {y}) [{elem.source}]")
                    self.adb.tap(x, y)
                    time.sleep(1)
                    tapped = True
                    break

        if not tapped:
            w, h = self.adb.get_screen_size()
            print("  No new elements, scrolling down")
            self.adb.swipe(w // 2, h * 3 // 4, w // 2, h // 4, 500)
            time.sleep(0.5)

        return True

    def _log_screen(self, screen: Screen):
        log_file = self.logs_dir / "screens.jsonl"
        screen_data = {
            "screen_id": screen.screen_id,
            "activity": screen.activity,
            "screenshot": screen.screenshot_path,
            "element_count": len(screen.elements),
            "timestamp": screen.timestamp,
            "strategy": screen.strategy_used,
            "elements": [
                {
                    "text": e.text,
                    "content_desc": e.content_desc,
                    "resource_id": e.resource_id,
                    "class": e.class_name,
                    "clickable": e.clickable,
                    "bounds": e.bounds,
                    "source": e.source
                }
                for e in screen.elements[:20]
            ]
        }
        with open(log_file, "a") as f:
            f.write(json.dumps(screen_data) + "\n")

    def explore(self):
        print(f"\n{'='*60}")
        print(f"Production Auto-Explorer")
        print(f"Package: {self.package}")
        print(f"Max Steps: {self.max_steps}")
        print(f"Output: {self.output_dir}")
        print(f"{'='*60}\n")

        self.adb.wake_screen()

        # Launch app
        self.adb.run(f"monkey -p {self.package} -c android.intent.category.LAUNCHER 1")
        time.sleep(3)

        try:
            while self.step_count < self.max_steps:
                if not self.explore_step():
                    break
                time.sleep(0.3)
        except KeyboardInterrupt:
            print("\nExploration interrupted")

        self._generate_summary()

        print(f"\n{'='*60}")
        print(f"Exploration Complete!")
        print(f"Screens discovered: {len(self.screens)}")
        print(f"Total steps: {self.step_count}")
        print(f"Elements visited: {len(self.visited_elements)}")
        print(f"{'='*60}")

    def _generate_summary(self):
        summary = {
            "package": self.package,
            "total_screens": len(self.screens),
            "total_steps": self.step_count,
            "elements_visited": len(self.visited_elements),
            "strategies_used": list(set(s.strategy_used for s in self.screens.values())),
            "screens": [
                {
                    "id": s.screen_id,
                    "activity": s.activity,
                    "screenshot": s.screenshot_path,
                    "elements": len(s.elements),
                    "strategy": s.strategy_used
                }
                for s in self.screens.values()
            ]
        }
        summary_file = self.output_dir / "exploration_summary.json"
        with open(summary_file, "w") as f:
            json.dump(summary, f, indent=2)
        print(f"Summary saved to: {summary_file}")


def main():
    parser = argparse.ArgumentParser(description="Production-grade auto-explore Android app")
    parser.add_argument("--device", "-d", help="Device ID")
    parser.add_argument("--package", "-p", required=True, help="App package name")
    parser.add_argument("--max-steps", "-m", type=int, default=50, help="Max exploration steps")
    parser.add_argument("--output-dir", "-o", default="artifacts", help="Output directory")
    parser.add_argument("--server", "-s", default="", help="Monitor server URL for screenshot streaming")
    parser.add_argument("--device-label", default="", help="Label for dashboard display")
    args = parser.parse_args()

    device_id = args.device
    if not device_id or device_id == "auto":
        try:
            result = subprocess.run(["adb", "devices"], capture_output=True, text=True)
            lines = result.stdout.strip().split("\n")[1:]
            for line in lines:
                if "device" in line and "offline" not in line:
                    device_id = line.split("\t")[0]
                    break
        except:
            pass

    if not device_id:
        print("No device found.")
        sys.exit(1)

    print(f"Device: {device_id}")

    adb = ADBController(device_id)
    explorer = AutoExplorer(
        adb=adb,
        package=args.package,
        output_dir=args.output_dir,
        max_steps=args.max_steps,
        server_url=args.server,
        device_label=args.device_label
    )
    explorer.explore()


if __name__ == "__main__":
    main()
