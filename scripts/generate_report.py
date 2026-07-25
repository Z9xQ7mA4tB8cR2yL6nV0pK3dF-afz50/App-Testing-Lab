#!/usr/bin/env python3
"""
Report Generator - Generate HTML test report from exploration results.
"""

import argparse
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional


class ReportGenerator:
    """Generates HTML test report from exploration artifacts."""
    
    def __init__(self, input_dir: str, output_dir: str, package: str, device: str, api_level: str, screen: str):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.package = package
        self.device = device
        self.api_level = api_level
        self.screen = screen
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def load_summary(self) -> dict:
        """Load exploration summary."""
        summary_file = self.input_dir / "exploration_summary.json"
        if summary_file.exists():
            with open(summary_file) as f:
                return json.load(f)
        return {}
    
    def load_screen_logs(self) -> list:
        """Load screen logs."""
        screens = []
        log_file = self.input_dir / "logs" / "screens.jsonl"
        if log_file.exists():
            with open(log_file) as f:
                for line in f:
                    if line.strip():
                        try:
                            screens.append(json.loads(line))
                        except:
                            pass
        return screens
    
    def copy_screenshots(self) -> dict:
        """Copy screenshots to report directory."""
        screenshots = {}
        report_screenshots = self.output_dir / "screenshots"
        report_screenshots.mkdir(exist_ok=True)
        
        source_dir = self.input_dir / "screenshots"
        if source_dir.exists():
            for img_file in source_dir.glob("*.png"):
                dest = report_screenshots / img_file.name
                shutil.copy2(img_file, dest)
                screenshots[img_file.stem] = f"screenshots/{img_file.name}"
        
        return screenshots
    
    def generate_html(self, summary: dict, screens: list, screenshots: dict) -> str:
        """Generate HTML report."""
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        total_screens = summary.get("total_screens", len(screens))
        total_steps = summary.get("total_steps", 0)
        elements_visited = summary.get("elements_visited", 0)
        
        # Build screen cards
        screen_cards = ""
        for i, screen in enumerate(screens, 1):
            screen_id = screen.get("screen_id", f"screen_{i}")
            activity = screen.get("activity", "Unknown")
            element_count = screen.get("element_count", 0)
            screenshot_path = screen.get("screenshot", "")
            
            # Find matching screenshot in our copied files
            screenshot_html = ""
            for key, path in screenshots.items():
                if screen_id in key or key in screenshot_path:
                    screenshot_html = f'<img src="{path}" alt="Screen {i}" loading="lazy">'
                    break
            
            if not screenshot_html and screenshot_path:
                # Try to use original path
                screenshot_html = f'<img src="../{screenshot_path}" alt="Screen {i}" loading="lazy">'
            
            # Element details
            elements = screen.get("elements", [])
            element_rows = ""
            for elem in elements[:10]:  # Show max 10 elements
                text = elem.get("text", "") or elem.get("resource_id", "").split("/")[-1] if "/" in elem.get("resource_id", "") else ""
                clickable = "Yes" if elem.get("clickable") else "No"
                element_rows += f"""
                    <tr>
                        <td>{text[:50]}</td>
                        <td>{elem.get('class', '').split('.')[-1]}</td>
                        <td>{clickable}</td>
                    </tr>"""
            
            screen_cards += f"""
            <div class="screen-card">
                <div class="screen-header">
                    <span class="screen-number">#{i}</span>
                    <h3>{activity.split('.')[-1] if '.' in activity else activity}</h3>
                    <span class="element-count">{element_count} elements</span>
                </div>
                <div class="screen-content">
                    <div class="screenshot-container">
                        {screenshot_html}
                    </div>
                    <div class="elements-table">
                        <h4>UI Elements</h4>
                        <table>
                            <thead>
                                <tr>
                                    <th>Text/ID</th>
                                    <th>Type</th>
                                    <th>Clickable</th>
                                </tr>
                            </thead>
                            <tbody>
                                {element_rows}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>"""
        
        # Generate HTML
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>App Testing Report - {self.package}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: #0f0f0f;
            color: #e0e0e0;
            line-height: 1.6;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }}
        
        header {{
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            padding: 30px;
            border-radius: 12px;
            margin-bottom: 30px;
            border: 1px solid #2a2a4a;
        }}
        
        h1 {{
            font-size: 2rem;
            margin-bottom: 10px;
            background: linear-gradient(90deg, #00d4ff, #7c3aed);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        
        .meta-info {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-top: 20px;
        }}
        
        .meta-item {{
            background: rgba(255,255,255,0.05);
            padding: 15px;
            border-radius: 8px;
            border: 1px solid #3a3a5a;
        }}
        
        .meta-item label {{
            display: block;
            font-size: 0.85rem;
            color: #888;
            margin-bottom: 5px;
        }}
        
        .meta-item span {{
            font-size: 1.1rem;
            font-weight: 600;
            color: #fff;
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            margin-bottom: 30px;
        }}
        
        .stat-card {{
            background: linear-gradient(135deg, #1e1e2e 0%, #2a2a4a 100%);
            padding: 25px;
            border-radius: 12px;
            text-align: center;
            border: 1px solid #3a3a5a;
        }}
        
        .stat-card .number {{
            font-size: 2.5rem;
            font-weight: bold;
            background: linear-gradient(90deg, #00d4ff, #7c3aed);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        
        .stat-card .label {{
            font-size: 0.9rem;
            color: #888;
            margin-top: 5px;
        }}
        
        .section-title {{
            font-size: 1.5rem;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #3a3a5a;
        }}
        
        .screen-card {{
            background: #1a1a2e;
            border-radius: 12px;
            margin-bottom: 20px;
            overflow: hidden;
            border: 1px solid #2a2a4a;
        }}
        
        .screen-header {{
            display: flex;
            align-items: center;
            padding: 15px 20px;
            background: rgba(255,255,255,0.03);
            border-bottom: 1px solid #2a2a4a;
        }}
        
        .screen-number {{
            background: linear-gradient(90deg, #00d4ff, #7c3aed);
            color: #fff;
            padding: 5px 12px;
            border-radius: 20px;
            font-weight: bold;
            margin-right: 15px;
            font-size: 0.9rem;
        }}
        
        .screen-header h3 {{
            flex: 1;
            font-size: 1.1rem;
        }}
        
        .element-count {{
            background: rgba(124, 58, 237, 0.2);
            color: #a78bfa;
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 0.85rem;
        }}
        
        .screen-content {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            padding: 20px;
        }}
        
        .screenshot-container {{
            background: #0f0f0f;
            border-radius: 8px;
            padding: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        
        .screenshot-container img {{
            max-width: 100%;
            max-height: 500px;
            border-radius: 8px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.5);
        }}
        
        .elements-table {{
            overflow-x: auto;
        }}
        
        .elements-table h4 {{
            margin-bottom: 10px;
            color: #a78bfa;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        
        th, td {{
            padding: 10px 12px;
            text-align: left;
            border-bottom: 1px solid #2a2a4a;
        }}
        
        th {{
            background: rgba(124, 58, 237, 0.1);
            color: #a78bfa;
            font-weight: 600;
        }}
        
        tr:hover {{
            background: rgba(255,255,255,0.02);
        }}
        
        footer {{
            text-align: center;
            padding: 30px;
            color: #666;
            font-size: 0.9rem;
        }}
        
        @media (max-width: 900px) {{
            .stats-grid {{
                grid-template-columns: repeat(2, 1fr);
            }}
            
            .screen-content {{
                grid-template-columns: 1fr;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>App Testing Report</h1>
            <div class="meta-info">
                <div class="meta-item">
                    <label>Package</label>
                    <span>{self.package}</span>
                </div>
                <div class="meta-item">
                    <label>Device</label>
                    <span>{self.device}</span>
                </div>
                <div class="meta-item">
                    <label>Android Version</label>
                    <span>API {self.api_level}</span>
                </div>
                <div class="meta-item">
                    <label>Screen Size</label>
                    <span>{self.screen}</span>
                </div>
                <div class="meta-item">
                    <label>Generated</label>
                    <span>{timestamp}</span>
                </div>
            </div>
        </header>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="number">{total_screens}</div>
                <div class="label">Screens Discovered</div>
            </div>
            <div class="stat-card">
                <div class="number">{total_steps}</div>
                <div class="label">Exploration Steps</div>
            </div>
            <div class="stat-card">
                <div class="number">{elements_visited}</div>
                <div class="label">Elements Tested</div>
            </div>
            <div class="stat-card">
                <div class="number">{len(screenshots)}</div>
                <div class="label">Screenshots</div>
            </div>
        </div>
        
        <h2 class="section-title">Discovered Screens</h2>
        {screen_cards}
        
        <footer>
            <p>Generated by App Testing Lab | {timestamp}</p>
        </footer>
    </div>
</body>
</html>"""
        
        return html
    
    def generate(self):
        """Generate the complete report."""
        print("Generating test report...")
        
        # Load data
        summary = self.load_summary()
        screens = self.load_screen_logs()
        screenshots = self.copy_screenshots()
        
        # Generate HTML
        html = self.generate_html(summary, screens, screenshots)
        
        # Save report
        report_file = self.output_dir / "report.html"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(html)
        
        print(f"Report generated: {report_file}")
        
        # Also save JSON summary
        json_report = {
            "package": self.package,
            "device": self.device,
            "api_level": self.api_level,
            "screen_size": self.screen,
            "timestamp": datetime.now().isoformat(),
            "summary": summary,
            "screens": screens
        }
        
        json_file = self.output_dir / "report.json"
        with open(json_file, "w") as f:
            json.dump(json_report, f, indent=2)
        
        print(f"JSON report: {json_file}")
        
        return report_file


def main():
    parser = argparse.ArgumentParser(description="Generate HTML test report")
    parser.add_argument("--input-dir", "-i", required=True, help="Input artifacts directory")
    parser.add_argument("--output-dir", "-o", required=True, help="Output report directory")
    parser.add_argument("--package", "-p", required=True, help="App package name")
    parser.add_argument("--device", "-d", required=True, help="Device name")
    parser.add_argument("--api-level", "-a", required=True, help="Android API level")
    parser.add_argument("--screen", "-s", required=True, help="Screen size")
    
    args = parser.parse_args()
    
    generator = ReportGenerator(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        package=args.package,
        device=args.device,
        api_level=args.api_level,
        screen=args.screen
    )
    
    generator.generate()


if __name__ == "__main__":
    main()
