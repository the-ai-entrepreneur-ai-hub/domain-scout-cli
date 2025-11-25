# Simple Web Crawler (PoC)

**Welcome!** This is a custom-built tool designed to automatically find and extract public business information from websites (like email addresses and company names) for a specific country/domain (e.g., `.de` for Germany).

It was built to be robust, efficient, and respectful of website rules.

---

## Table of Contents

- [Quick Start Guide](#quick-start-guide)
- [How It Works](#how-it-works)
- [Step-by-Step Usage](#step-by-step-usage)
- [Testing the Crawler](#testing-the-crawler)
- [Advanced Controls](#advanced-controls)
- [Output Data](#output-data)
- [Project Structure](#project-structure)
- [Documentation](#documentation)
- [Troubleshooting](#troubleshooting)

---

## Quick Start Guide

Follow these simple steps to get the crawler running on your machine.

### 1. Get the Code
First, download the latest version of the code using git:
```bash
git clone https://github.com/the-ai-entrepreneur-ai-hub/domain-scout-cli.git
cd domain-scout-cli
```

### 2. Prerequisites
Make sure you have **Python 3.9 or higher** installed. If not, download it from [python.org](https://www.python.org/downloads/).

To check your Python version:
```bash
python --version
```

### 3. Installation
Run this command to install the necessary tools:

```bash
pip install -r requirements.txt
```

---

## How It Works

The crawler operates in **three simple phases**:

```
 DISCOVER          CRAWL            EXPORT
    |                |                 |
    v                v                 v
+--------+      +--------+       +--------+
| Find   | ---> | Visit  | --->  | Save   |
| Domains|      | Sites  |       | to CSV |
+--------+      +--------+       +--------+
```

1. **Discovery**: Searches 8 different sources to find website addresses
2. **Crawling**: Visits each website and extracts business information
3. **Export**: Saves everything to a CSV file you can open in Excel

> **Want to learn more?** Check out the detailed [Data Model Documentation](docs/DATA_MODEL.md) with diagrams!

---

## Step-by-Step Usage

### Step 1: Find Domains (Discovery)

First, we find a list of active websites. Replace `.de` with any extension you want (e.g., `.ch`, `.fr`, `.at`).

```bash
python main.py discover --tld de --limit 1000
```

**What this does:**
- Searches **8 different sources** (Tranco, Majestic, Umbrella, Common Crawl, crt.sh, Wayback, DuckDuckGo, Bing)
- Finds up to 1000 domains ending in `.de`
- Saves them to the database for crawling

**Example output:**
```
02:11:21 - INFO - === Starting discovery for TLD: .de, limit: 1000 ===
02:11:21 - INFO - Ingesting Tranco domains for TLD: .de
02:11:22 - INFO - Inserted/Processed 290 domains into DB.
02:11:45 - INFO - Majestic: ingested 279 domains
02:12:06 - INFO - Umbrella: ingested 24 domains
02:12:26 - INFO - crt.sh: ingested 10 domains
02:12:46 - INFO - === Discovery complete ===
```

### Step 2: Extract Data (Crawling)

Now, the bot visits the websites found in Step 1 to find emails and company names.

```bash
python main.py crawl --concurrency 10
```

**What this does:**
- Checks if each domain exists (DNS check)
- Respects `robots.txt` rules
- Visits the homepage
- Extracts company name, email, phone, address
- Skips "parked" domains (domain for sale pages)

**Example output:**
```
02:15:00 - INFO - Starting Crawler with 10 workers...
02:15:02 - INFO - Crawled: example.de | Example GmbH
02:15:04 - WARNING - DNS Failed: deadsite.de
02:15:06 - INFO - Crawled: company.de | Company AG
```

### Step 3: Save Results (Export)

Once finished, save the data to a readable Excel/CSV file.

```bash
python main.py export --tld de
```

**What this does:**
- Reads all successful results from the database
- Filters by your chosen TLD (optional)
- Creates a timestamped CSV file in the `data/` folder

**Your file will be at:** `data/results_de_20240115_143022.csv`

---

## Testing the Crawler

Want to make sure everything works? Follow this quick test:

### Quick Test (5 minutes)

```bash
# Step 1: Discover just 20 Swiss (.ch) domains
python main.py discover --tld ch --limit 20

# Step 2: Crawl them (uses 5 workers for a quick test)
python main.py crawl --concurrency 5

# Step 3: Export the results
python main.py export --tld ch
```

### What to Check

1. **After Discovery**: You should see messages like:
   - `Inserted/Processed X domains into DB`
   - `=== Discovery complete ===`

2. **After Crawling**: Look for:
   - `Crawled: domain.ch | Company Name` (successful crawls)
   - Some `DNS Failed` or `PARKED` messages are normal

3. **After Export**: 
   - Check the `data/` folder for a new CSV file
   - Open it in Excel to see your results

### Verify Database Contents

To see what's in your database:

```bash
# Show domain counts by source
python -c "import sqlite3; c=sqlite3.connect('data/crawler_data.db').cursor(); c.execute('SELECT source, COUNT(*) FROM queue GROUP BY source'); print(c.fetchall())"

# Show domain counts by status
python -c "import sqlite3; c=sqlite3.connect('data/crawler_data.db').cursor(); c.execute('SELECT status, COUNT(*) FROM queue GROUP BY status'); print(c.fetchall())"
```

---

## Advanced Controls

### Reset Failed Domains

If the crawler gets stuck or you want to retry failed domains:
```bash
python main.py reset
```
This changes all `FAILED_*` statuses back to `PENDING` so they can be retried.

### Stop the Crawler Safely

To safely stop the crawler while it's running:
- **Option 1**: Press `Ctrl+C` in the terminal
- **Option 2**: Create a file named `STOP` in the project folder

### Adjust Crawler Settings

Edit `config/settings.yaml` to change:
- `delay_min` / `delay_max`: Time between requests (be polite!)
- `request_timeout`: How long to wait for a response
- `respect_robots`: Whether to obey robots.txt (recommended: true)

### Skip Certain Websites

Add domains to `config/blacklist.txt` (one per line):
```
facebook.com
amazon.com
google.com
```

---

## Output Data

Your exported CSV file will contain:

| Column | Description | Example |
|--------|-------------|---------|
| domain | Website address | `example.de` |
| company_name | Official business name | `Example GmbH` |
| description | What the company does | `Leading provider of...` |
| email | Public contact email | `info@example.de` |
| phone | Phone number | `+49 30 123456` |
| address | Physical address | `Musterstr. 1, Berlin` |

---

## Project Structure

```
Web Crawler/
|-- main.py              # Main entry point (start here!)
|-- requirements.txt     # Python dependencies
|-- README.md            # This file
|
|-- src/                 # Source code
|   |-- discovery.py     # Finds domains (8 sources)
|   |-- crawler.py       # Visits websites
|   |-- extractor.py     # Extracts data from HTML
|   |-- dns_checker.py   # Checks if domains exist
|   |-- database.py      # Database operations
|   |-- storage.py       # CSV export
|   |-- models.py        # Data structures
|   |-- utils.py         # Logging and settings
|   +-- reset_tool.py    # Reset failed domains
|
|-- config/              # Configuration files
|   |-- settings.yaml    # Crawler settings
|   +-- blacklist.txt    # Domains to skip
|
|-- data/                # Output data (created automatically)
|   |-- crawler_data.db  # SQLite database
|   +-- results_*.csv    # Exported results
|
|-- logs/                # Log files
|   +-- crawler.log      # Detailed activity log
|
+-- docs/                # Documentation
    +-- DATA_MODEL.md    # Detailed architecture guide
```

---

## Documentation

For a deeper understanding of how the crawler works:

- **[Data Model & Architecture Guide](docs/DATA_MODEL.md)** - Detailed diagrams showing:
  - How data flows through the system
  - Database table structures
  - All 8 discovery sources explained
  - The crawling process step-by-step
  - How data extraction works

---

## Troubleshooting

### "No module named X"
Run the installation again:
```bash
pip install -r requirements.txt
```

### "No pending domains found"
You need to run discovery first:
```bash
python main.py discover --tld de --limit 100
```

### Crawler seems stuck
1. Check `logs/crawler.log` for errors
2. Try resetting: `python main.py reset`
3. Reduce concurrency: `python main.py crawl --concurrency 3`

### Empty CSV file
- Make sure you ran both `discover` and `crawl` commands
- Check if the TLD filter matches: `--tld de` vs `--tld .de` (both work)

### DNS errors for all domains
- Check your internet connection
- Some corporate networks block DNS queries

---

## Important Notes

- This tool is a **Proof of Concept** for demonstration purposes
- It respects `robots.txt` rules automatically
- Includes a blacklist to avoid crawling major sites (Amazon, Facebook, etc.)
- Filters personal emails for GDPR compliance
- Please use responsibly and in accordance with local regulations

---

*Developed by George*
