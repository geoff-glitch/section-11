# Manual JSON Export

Export Intervals.icu data locally for different time ranges.

## Prerequisites

- Python 3.8+
- `requests` library: `pip install requests`

## First-Time Setup

```bash
python sync.py --setup
```

Enter your Intervals.icu credentials when prompted. Config saves to `.sync_config.json`.

**Finding your credentials:**
- **Athlete ID**: Intervals.icu → Settings → bottom of page (e.g., `i123456`)
- **API Key**: Intervals.icu → Settings → Developer Settings → API Key

## Usage

### Export to local file

```bash
# Last 7 days (default)
python sync.py --output latest.json

# Last 14 days
python sync.py --days 14 --output 14days.json

# Last 90 days
python sync.py --days 90 --output 90days.json
```

### Common time ranges

| Days | Use case |
|------|----------|
| 7 | Weekly review |
| 14 | Two-week block |
| 42 | 6-week training block |
| 90 | Quarterly / build cycle |
| 180 | Season review |

### Push to GitHub (optional)

If you configured GitHub credentials during setup:

```bash
python sync.py --days 14
```

Pushes to your configured GitHub repo.

## Use with AI

**Option 1: Upload file**
Upload the JSON file directly to Claude, ChatGPT, or other AI.

**Option 2: Paste contents**
Copy/paste the JSON contents into your AI chat.

**Option 3: Reference URL (if pushed to GitHub)**
```
Analyze my training data from https://raw.githubusercontent.com/USERNAME/REPO/main/latest.json
```

## Options Reference

| Flag | Description | Default |
|------|-------------|---------|
| `--setup` | Run setup wizard | - |
| `--days N` | Days of data to export | 7 |
| `--output FILE` | Save to local file | - |
| `--debug` | Show API field debug info | off |
| `--anonymize` | Remove identifying info | on |
