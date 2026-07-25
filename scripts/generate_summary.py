#!/usr/bin/env python3
"""
Summary Generator - Generate cross-device comparison report.
"""

import argparse
import json
import os
import shutil
from datetime import datetime
from pathlib import Path


class SummaryGenerator:
    """Generates cross-device comparison summary."""
    
    def __init__(self, results_dir: str, output_dir: str):
        self.results_dir = Path(results_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def collect_results(self) -> list:
        """Collect results from all test runs."""
        results = []
        
        for artifact_dir in self.results_dir.iterdir():
            if artifact_dir.is_dir() and artifact_dir.name.startswith("test-results"):
                # Parse directory name: test-results-api{level}-{device}
                parts = artifact_dir.name.replace("test-results-", "").split("-")
                
                summary_file = artifact_dir / "exploration_summary.json"
                report_file = artifact_dir / "reports" / "report.json"
                
                result = {
                    "dir_name": artifact_dir.name,
                    "api_level": parts[0].replace("api", "") if parts else "unknown",
                    "device": "-".join(parts[1:]) if len(parts) > 1 else "unknown",
                    "screens": [],
                    "total_steps": 0,
                    "elements_visited": 0
                }
                
                if summary_file.exists():
                    with open(summary_file) as f:
                        summary = json.load(f)
                        result["total_steps"] = summary.get("total_steps", 0)
                        result["elements_visited"] = summary.get("elements_visited", 0)
                        result["screens"] = summary.get("screens", [])
                
                results.append(result)
        
        return results
    
    def generate_html(self, results: list) -> str:
        """Generate cross-device comparison HTML."""
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Collect all unique screen activities
        all_activities = set()
        for result in results:
            for screen in result.get("screens", []):
                activity = screen.get("activity", "unknown")
                all_activities.add(activity)
        
        # Build comparison table rows
        comparison_rows = ""
        for activity in sorted(all_activities):
            row = f"<tr><td>{activity.split('.')[-1] if '.' in activity else activity}</td>"
            
            for result in results:
                found = any(
                    s.get("activity") == activity 
                    for s in result.get("screens", [])
                )
                status = "✅" if found else "❌"
                row += f"<td>{status}</td>"
            
            row += "</tr>"
            comparison_rows += row
        
        # Build device columns header
        device_headers = ""
        for result in results:
            device_name = result.get("device", "unknown")
            api_level = result.get("api_level", "unknown")
            device_headers += f"<th>{device_name}<br>API {api_level}</th>"
        
        # Build stats cards
        stats_cards = ""
        for result in results:
            device_name = result.get("device", "unknown")
            api_level = result.get("api_level", "unknown")
            screens_count = len(result.get("screens", []))
            steps = result.get("total_steps", 0)
            elements = result.get("elements_visited", 0)
            
            stats_cards += f"""
            <div class="device-card">
                <h3>{device_name}</h3>
                <p class="api-level">API {api_level}</p>
                <div class="device-stats">
                    <div class="stat">
                        <span class="stat-number">{screens_count}</span>
                        <span class="stat-label">Screens</span>
                    </div>
                    <div class="stat">
                        <span class="stat-number">{steps}</span>
                        <span class="stat-label">Steps</span>
                    </div>
                    <div class="stat">
                        <span class="stat-number">{elements}</span>
                        <span class="stat-label">Elements</span>
                    </div>
                </div>
            </div>"""
        
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cross-Device Test Summary</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0f0f0f;
            color: #e0e0e0;
            padding: 30px;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        
        header {{
            text-align: center;
            margin-bottom: 40px;
        }}
        
        h1 {{
            font-size: 2.5rem;
            background: linear-gradient(90deg, #00d4ff, #7c3aed);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
        }}
        
        .timestamp {{
            color: #888;
        }}
        
        .devices-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}
        
        .device-card {{
            background: linear-gradient(135deg, #1a1a2e 0%, #2a2a4a 100%);
            padding: 25px;
            border-radius: 12px;
            border: 1px solid #3a3a5a;
            text-align: center;
        }}
        
        .device-card h3 {{
            font-size: 1.3rem;
            margin-bottom: 5px;
        }}
        
        .api-level {{
            color: #a78bfa;
            font-size: 0.9rem;
            margin-bottom: 20px;
        }}
        
        .device-stats {{
            display: flex;
            justify-content: space-around;
        }}
        
        .stat {{
            text-align: center;
        }}
        
        .stat-number {{
            display: block;
            font-size: 1.8rem;
            font-weight: bold;
            color: #00d4ff;
        }}
        
        .stat-label {{
            font-size: 0.8rem;
            color: #888;
        }}
        
        .comparison-section {{
            background: #1a1a2e;
            border-radius: 12px;
            padding: 30px;
            border: 1px solid #2a2a4a;
        }}
        
        .section-title {{
            font-size: 1.5rem;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #3a3a5a;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        
        th, td {{
            padding: 12px 15px;
            text-align: center;
            border-bottom: 1px solid #2a2a4a;
        }}
        
        th {{
            background: rgba(124, 58, 237, 0.1);
            color: #a78bfa;
        }}
        
        td:first-child {{
            text-align: left;
            font-weight: 500;
        }}
        
        tr:hover {{
            background: rgba(255,255,255,0.02);
        }}
        
        .summary-stats {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
            margin-top: 30px;
        }}
        
        .summary-stat {{
            background: #16213e;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }}
        
        .summary-stat .number {{
            font-size: 2rem;
            font-weight: bold;
            color: #00d4ff;
        }}
        
        .summary-stat .label {{
            color: #888;
            margin-top: 5px;
        }}
        
        footer {{
            text-align: center;
            margin-top: 40px;
            color: #666;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Cross-Device Test Summary</h1>
            <p class="timestamp">Generated: {timestamp}</p>
        </header>
        
        <div class="devices-grid">
            {stats_cards}
        </div>
        
        <div class="comparison-section">
            <h2 class="section-title">Screen Coverage Comparison</h2>
            <table>
                <thead>
                    <tr>
                        <th>Activity</th>
                        {device_headers}
                    </tr>
                </thead>
                <tbody>
                    {comparison_rows}
                </tbody>
            </table>
        </div>
        
        <div class="summary-stats">
            <div class="summary-stat">
                <div class="number">{len(results)}</div>
                <div class="label">Devices Tested</div>
            </div>
            <div class="summary-stat">
                <div class="number">{len(all_activities)}</div>
                <div class="label">Unique Screens</div>
            </div>
            <div class="summary-stat">
                <div class="number">{sum(r.get('elements_visited', 0) for r in results)}</div>
                <div class="label">Total Elements Tested</div>
            </div>
        </div>
        
        <footer>
            <p>App Testing Lab | Cross-Device Comparison Report</p>
        </footer>
    </div>
</body>
</html>"""
        
        return html
    
    def generate(self):
        """Generate the summary report."""
        print("Generating cross-device summary...")
        
        results = self.collect_results()
        
        if not results:
            print("No test results found!")
            return
        
        print(f"Found {len(results)} test runs")
        
        # Generate HTML
        html = self.generate_html(results)
        
        # Save report
        report_file = self.output_dir / "summary.html"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(html)
        
        print(f"Summary report: {report_file}")
        
        # Save JSON
        json_file = self.output_dir / "summary.json"
        with open(json_file, "w") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "device_count": len(results),
                "results": results
            }, f, indent=2)
        
        print(f"JSON summary: {json_file}")


def main():
    parser = argparse.ArgumentParser(description="Generate cross-device summary")
    parser.add_argument("--results-dir", "-r", required=True, help="Directory containing all test results")
    parser.add_argument("--output-dir", "-o", required=True, help="Output directory for summary")
    
    args = parser.parse_args()
    
    generator = SummaryGenerator(
        results_dir=args.results_dir,
        output_dir=args.output_dir
    )
    
    generator.generate()


if __name__ == "__main__":
    main()
