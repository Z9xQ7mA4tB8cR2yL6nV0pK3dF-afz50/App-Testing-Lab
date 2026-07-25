#!/usr/bin/env python3
"""
Auto Explore - ADB-based Android App Auto-Explorer
Discovers screens, captures screenshots, and builds navigation graph.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Element:
    """UI Element found on screen."""
    resource_id: str = ""
    text: str = ""
    content_desc: str = ""
    class_name: str = ""
    package: str = ""
    clickable: bool = False
    scrollable: bool = False
    bounds: str = ""
    index: int = 0
    
    @property
    def bounds_tuple(self):
        """Parse bounds string 'x1,y1 x2,y2' into tuple."""
        try:
            parts = self.bounds.replace("][", ",").strip("[]").split(",")
            if len(parts) == 4:
                return tuple(map(int, parts))
        except:
            pass
        return (0, 0, 0, 0)
    
    @property
    def center(self):
        """Get center point of element."""
        x1, y1, x2, y2 = self.bounds_tuple
        return ((x1 + x2) // 2, (y1 + y2) // 2)


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


class ADBController:
    """Controls Android device via ADB."""
    
    def __init__(self, device_id: Optional[str] = None):
        self.device_id = device_id
        self.adb_cmd = ["adb"]
        if device_id:
            self.adb_cmd.extend(["-s", device_id])
    
    def run(self, command: str, timeout: int = 30) -> str:
        """Run ADB command and return output."""
        full_cmd = self.adb_cmd + ["shell"] + command.split()
        try:
            result = subprocess.run(
                full_cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            return ""
        except Exception as e:
            print(f"ADB error: {e}")
            return ""
    
    def screencap(self, output_path: str) -> bool:
        """Capture screenshot."""
        try:
            full_cmd = self.adb_cmd + ["exec-out", "screencap", "-p"]
            with open(output_path, "wb") as f:
                result = subprocess.run(full_cmd, capture_output=True, timeout=15)
                f.write(result.stdout)
            return os.path.exists(output_path) and os.path.getsize(output_path) > 0
        except Exception as e:
            print(f"Screencap error: {e}")
            return False
    
    def tap(self, x: int, y: int) -> bool:
        """Tap at coordinates."""
        self.run(f"input tap {x} {y}")
        time.sleep(0.5)
        return True
    
    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: int = 300) -> bool:
        """Swipe from (x1,y1) to (x2,y2)."""
        self.run(f"input swipe {x1} {y1} {x2} {y2} {duration}")
        time.sleep(0.5)
        return True
    
    def press_back(self) -> bool:
        """Press back button."""
        self.run("input keyevent 4")
        time.sleep(0.5)
        return True
    
    def press_home(self) -> bool:
        """Press home button."""
        self.run("input keyevent 3")
        time.sleep(0.5)
        return True
    
    def get_current_activity(self) -> str:
        """Get current foreground activity."""
        output = self.run("dumpsys window windows | grep -E mCurrentFocus")
        if "mCurrentFocus" in output:
            try:
                return output.split("}")[-1].strip()
            except:
                pass
        return "unknown"
    
    def get_ui_hierarchy(self) -> Optional[ET.Element]:
        """Dump and parse UI hierarchy."""
        try:
            # Try to dump UI hierarchy
            self.run("uiautomator dump /sdcard/window_dump.xml")
            time.sleep(1)
            
            # Pull the dump
            full_cmd = self.adb_cmd + ["shell", "cat", "/sdcard/window_dump.xml"]
            result = subprocess.run(full_cmd, capture_output=True, text=True, timeout=10)
            
            if result.stdout.strip():
                return ET.fromstring(result.stdout)
        except ET.ParseError as e:
            print(f"XML parse error: {e}")
        except Exception as e:
            print(f"UI dump error: {e}")
        
        return None
    
    def get_screen_size(self) -> tuple:
        """Get screen size."""
        output = self.run("wm size")
        try:
            # "Physical size: 1080x2400"
            size_str = output.split(":")[-1].strip()
            w, h = size_str.split("x")
            return (int(w), int(h))
        except:
            return (1080, 1920)
    
    def is_screen_on(self) -> bool:
        """Check if screen is on."""
        output = self.run("dumpsys power | grep 'Display Power'")
        return "ON" in output.upper()


class AutoExplorer:
    """Automatically explores Android app screens."""
    
    def __init__(self, adb: ADBController, package: str, output_dir: str, max_steps: int = 50):
        self.adb = adb
        self.package = package
        self.output_dir = Path(output_dir)
        self.max_steps = max_steps
        self.screenshots_dir = self.output_dir / "screenshots"
        self.logs_dir = self.output_dir / "logs"
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        
        self.screens: dict[str, Screen] = {}
        self.visited_elements: set = set()
        self.step_count = 0
        self.navigation_graph: dict = {}
        
    def get_screen_hash(self, elements: list[Element]) -> str:
        """Generate unique hash for current screen state."""
        # Use element combination to identify screen
        sig_parts = []
        for e in elements[:10]:  # Top 10 elements
            sig_parts.append(f"{e.class_name}:{e.text}:{e.resource_id}")
        sig = "|".join(sig_parts)
        return hashlib.md5(sig.encode()).hexdigest()[:12]
    
    def parse_elements(self, root: ET.Element) -> list[Element]:
        """Parse UI hierarchy XML into Element objects."""
        elements = []
        
        for node in root.iter("node"):
            try:
                elem = Element(
                    resource_id=node.get("resource-id", ""),
                    text=node.get("text", ""),
                    content_desc=node.get("content-desc", ""),
                    class_name=node.get("class", ""),
                    package=node.get("package", ""),
                    clickable=node.get("clickable", "false") == "true",
                    scrollable=node.get("scrollable", "false") == "true",
                    bounds=node.get("bounds", ""),
                    index=int(node.get("index", "0"))
                )
                
                # Filter: only relevant package and clickable elements
                if elem.package == self.package and (elem.clickable or elem.text or elem.content_desc):
                    elements.append(elem)
            except Exception:
                continue
        
        return elements
    
    def find_interactable_elements(self, elements: list[Element]) -> list[Element]:
        """Find elements worth interacting with."""
        interactable = []
        
        for elem in elements:
            # Skip system elements
            if any(skip in elem.class_name.lower() for skip in [
                "statusbar", "navigationbar", "systemui"
            ]):
                continue
            
            # Prioritize: buttons, inputs, clickable items
            if elem.clickable:
                interactable.append(elem)
            elif elem.text and not elem.scrollable:
                interactable.append(elem)
        
        return interactable
    
    def capture_screen(self, label: str = "") -> str:
        """Capture and save screenshot."""
        timestamp = int(time.time())
        filename = f"step_{self.step_count:03d}_{label}_{timestamp}.png"
        filepath = self.screenshots_dir / filename
        
        if self.adb.screencap(str(filepath)):
            return str(filepath)
        return ""
    
    def explore_step(self) -> bool:
        """Perform one exploration step."""
        if self.step_count >= self.max_steps:
            print(f"Max steps ({self.max_steps}) reached")
            return False
        
        self.step_count += 1
        print(f"\n--- Step {self.step_count}/{self.max_steps} ---")
        
        # Get current activity
        activity = self.adb.get_current_activity()
        print(f"Current activity: {activity}")
        
        # Dump UI hierarchy
        root = self.adb.get_ui_hierarchy()
        if root is None:
            print("Failed to get UI hierarchy")
            return True
        
        # Parse elements
        elements = self.parse_elements(root)
        print(f"Found {len(elements)} interactable elements")
        
        # Get screen signature
        screen_hash = self.get_screen_hash(elements)
        
        # Check if new screen
        is_new_screen = screen_hash not in self.screens
        if is_new_screen:
            print(f"NEW SCREEN discovered: {screen_hash}")
            
            # Capture screenshot
            screenshot = self.capture_screen(screen_hash)
            
            # Record screen
            screen = Screen(
                screen_id=screen_hash,
                activity=activity,
                package=self.package,
                screenshot_path=screenshot,
                elements=elements,
                visited=True,
                timestamp=time.time()
            )
            self.screens[screen_hash] = screen
            
            # Log screen info
            self._log_screen(screen)
        
        # Find interactable elements
        interactable = self.find_interactable_elements(elements)
        print(f"Interactable elements: {len(interactable)}")
        
        if not interactable:
            print("No interactable elements found, going back")
            self.adb.press_back()
            time.sleep(0.5)
            return True
        
        # Try to tap on unvisited elements
        tapped = False
        for elem in interactable:
            elem_key = f"{screen_hash}:{elem.resource_id}:{elem.text}:{elem.bounds}"
            
            if elem_key not in self.visited_elements and elem.center != (0, 0):
                self.visited_elements.add(elem_key)
                
                x, y = elem.center
                label = elem.text or elem.content_desc or elem.resource_id.split("/")[-1] if "/" in elem.resource_id else f"elem_{elem.index}"
                print(f"Tapping: {label} at ({x}, {y})")
                
                self.adb.tap(x, y)
                time.sleep(1)
                
                tapped = True
                break
        
        if not tapped:
            # Try scrolling
            print("No new elements to tap, trying scroll")
            w, h = self.adb.get_screen_size()
            self.adb.swipe(w // 2, h * 3 // 4, w // 2, h // 4, 500)
            time.sleep(0.5)
        
        return True
    
    def _log_screen(self, screen: Screen):
        """Log screen information."""
        log_file = self.logs_dir / "screens.jsonl"
        
        screen_data = {
            "screen_id": screen.screen_id,
            "activity": screen.activity,
            "screenshot": screen.screenshot_path,
            "element_count": len(screen.elements),
            "timestamp": screen.timestamp,
            "elements": [
                {
                    "text": e.text,
                    "resource_id": e.resource_id,
                    "class": e.class_name,
                    "clickable": e.clickable,
                    "bounds": e.bounds
                }
                for e in screen.elements[:20]  # Limit logged elements
            ]
        }
        
        with open(log_file, "a") as f:
            f.write(json.dumps(screen_data) + "\n")
    
    def explore(self):
        """Main exploration loop."""
        print(f"\n{'='*60}")
        print(f"Starting Auto-Explore")
        print(f"Package: {self.package}")
        print(f"Max Steps: {self.max_steps}")
        print(f"Output: {self.output_dir}")
        print(f"{'='*60}\n")
        
        # Ensure screen is on
        if not self.adb.is_screen_on():
            self.adb.run("input keyevent 26")  # Power button
            time.sleep(1)
        
        # Start exploration
        try:
            while self.step_count < self.max_steps:
                if not self.explore_step():
                    break
                
                # Small delay between steps
                time.sleep(0.3)
        
        except KeyboardInterrupt:
            print("\nExploration interrupted")
        
        # Generate summary
        self._generate_summary()
        
        print(f"\n{'='*60}")
        print(f"Exploration Complete!")
        print(f"Screens discovered: {len(self.screens)}")
        print(f"Total steps: {self.step_count}")
        print(f"Elements visited: {len(self.visited_elements)}")
        print(f"{'='*60}")
    
    def _generate_summary(self):
        """Generate exploration summary."""
        summary = {
            "package": self.package,
            "total_screens": len(self.screens),
            "total_steps": self.step_count,
            "elements_visited": len(self.visited_elements),
            "screens": [
                {
                    "id": s.screen_id,
                    "activity": s.activity,
                    "screenshot": s.screenshot_path,
                    "elements": len(s.elements)
                }
                for s in self.screens.values()
            ]
        }
        
        summary_file = self.output_dir / "exploration_summary.json"
        with open(summary_file, "w") as f:
            json.dump(summary, f, indent=2)
        
        print(f"Summary saved to: {summary_file}")


def main():
    parser = argparse.ArgumentParser(description="Auto-explore Android app")
    parser.add_argument("--device", "-d", help="Device ID (default: first available)")
    parser.add_argument("--package", "-p", required=True, help="App package name")
    parser.add_argument("--max-steps", "-m", type=int, default=50, help="Max exploration steps")
    parser.add_argument("--output-dir", "-o", default="artifacts", help="Output directory")
    
    args = parser.parse_args()
    
    # Get device ID if not specified
    device_id = args.device
    if not device_id:
        try:
            result = subprocess.run(["adb", "devices"], capture_output=True, text=True)
            lines = result.stdout.strip().split("\n")[1:]  # Skip header
            for line in lines:
                if "device" in line and "offline" not in line:
                    device_id = line.split("\t")[0]
                    break
        except:
            pass
    
    if not device_id:
        print("No device found. Make sure emulator is running.")
        sys.exit(1)
    
    print(f"Using device: {device_id}")
    
    # Create ADB controller
    adb = ADBController(device_id)
    
    # Create and run explorer
    explorer = AutoExplorer(
        adb=adb,
        package=args.package,
        output_dir=args.output_dir,
        max_steps=args.max_steps
    )
    
    explorer.explore()


if __name__ == "__main__":
    main()
