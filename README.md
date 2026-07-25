# App Testing Lab

Fully open-source, self-hosted mobile app testing lab using GitHub Actions. Test any Android APK across multiple devices and API levels without third-party platforms.

## Features

- **No Third-Party Dependencies** - 100% self-hosted on GitHub Actions
- **Auto-Explore** - Automatically discovers and tests all screens
- **Multi-Device** - Test across different screen sizes and Android versions
- **Screenshot Capture** - Visual evidence of every screen
- **HTML Reports** - Beautiful, interactive test reports
- **Flutter Support** - Works with Flutter, React Native, and native apps

## How It Works

1. Upload your APK (or provide URL)
2. GitHub Actions spins up multiple Android emulators
3. Auto-explorer discovers all screens and components
4. Screenshots captured at each step
5. HTML report generated with cross-device comparison

## Quick Start

### 1. Fork/Clone this repository

```bash
git clone https://github.com/your-username/app-testing-lab.git
cd app-testing-lab
```

### 2. Trigger a test run

Go to **Actions** → **App Testing Lab** → **Run workflow**

Fill in:
- **APK URL**: Direct link to your APK file
- **Package Name**: Your app's package (e.g., `com.example.app`)
- **Test Depth**: quick (15 steps), normal (50 steps), or deep (100 steps)

### 3. View results

After the workflow completes:
- Go to **Actions** → Click on the completed run
- Download **complete-test-report** artifact
- Open `summary.html` in your browser

## Repository Structure

```
app-testing-lab/
├── .github/
│   └── workflows/
│       └── test-lab.yml          # GitHub Actions workflow
├── scripts/
│   ├── auto_explore.py           # ADB-based app explorer
│   ├── generate_report.py        # HTML report generator
│   ├── generate_summary.py       # Cross-device summary
│   └── requirements.txt          # Python dependencies
├── configs/
│   └── devices.json              # Device configurations
├── .gitignore
└── README.md
```

## Device Matrix

Default test devices:

| Device | API Level | Screen Size | Description |
|--------|-----------|-------------|-------------|
| Pixel | 28 | 1080x1920 | Budget (Android 9) |
| Pixel 6 | 31 | 1080x2400 | Mid-range (Android 12) |
| Pixel 7 Pro | 34 | 1440x3120 | Flagship (Android 14) |

## Local Testing

### Prerequisites

- Python 3.11+
- Android SDK with ADB
- Running emulator or connected device

### Run locally

```bash
# Install dependencies
pip install -r scripts/requirements.txt

# Start your emulator
emulator -avd Pixel_6_API_31

# Run auto-explore
python scripts/auto_explore.py \
  --package com.example.app \
  --max-steps 50 \
  --output-dir artifacts

# Generate report
python scripts/generate_report.py \
  --input-dir artifacts \
  --output-dir artifacts/reports \
  --package com.example.app \
  --device pixel_6 \
  --api-level 31 \
  --screen 1080x2400
```

## Customization

### Add new devices

Edit `configs/devices.json` and update the matrix in `.github/workflows/test-lab.yml`:

```yaml
strategy:
  matrix:
    include:
      - api-level: 28
        device: 'your_device'
        screen: 'WIDTHxHEIGHT'
        density: DPI
```

### Adjust test depth

- **quick**: 15 steps - Smoke test (~2 minutes)
- **normal**: 50 steps - Standard coverage (~5 minutes)
- **deep**: 100 steps - Deep exploration (~10 minutes)

## Output

### Screenshots
All screenshots saved in `artifacts/screenshots/`

### Reports
- `artifacts/reports/report.html` - Device-specific report
- `summary/summary.html` - Cross-device comparison

### Logs
- `artifacts/logs/logcat_full.txt` - Complete device logs
- `artifacts/logs/screens.jsonl` - Screen discovery log

## License

MIT - Free to use, modify, and distribute.
