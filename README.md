# Intelligent Web Crawler with Legal Entity Extraction (AI-Enhanced)

**Welcome!** This is a custom-built tool designed to automatically find and extract comprehensive business and legal information from websites. It now features a **Hybrid AI Engine** (GLiNER + Regex) to provide highly accurate data extraction for difficult fields like Company Names and Addresses.

**Key Features:**
- **AI-Powered Extraction**: Uses GLiNER (Generalist Lightweight NER) to semantically understand legal pages.
- **High Accuracy**: Extracts clean company names (e.g., "TechCorp GmbH") without junk prefixes.
- **Smart Discovery**: Finds legal pages (/impressum, /imprint) automatically.
- **Multi-Source**: Discovers domains from 8+ sources (Tranco, CommonCrawl, etc.).
- **Resilient**: Handles DNS issues, timeouts, and robots.txt blocks intelligently.
- **Hybrid Truth (WHOIS)**: Combines website data (Imprint) with official domain registration data (WHOIS) for 100% coverage.

---

## Table of Contents

- [Quick Start Guide](#quick-start-guide)
- [New AI Features](#new-ai-features)
- [Hybrid Truth (WHOIS Integration)](#hybrid-truth-whois-integration)
- [End-to-End Testing](#end-to-end-testing)
- [Step-by-Step Usage](#step-by-step-usage)
- [Legal Data Extraction](#legal-data-extraction)
- [Command Reference](#command-reference)
- [Project Structure](#project-structure)
- [Troubleshooting](#troubleshooting)

---

## Quick Start Guide

### 1. Installation
```bash
pip install -r requirements.txt
playwright install chromium
```
*(Note: First run will download the AI model ~500MB)*

### 2. Basic Workflow
```bash
# 1. Discover & Crawl Automatically (Recommended)
python main.py discover --tld .de --crawl --concurrency 10

# 2. Manual Workflow
# Step A: Discover domains
python main.py discover --tld .de --limit 500

# Step B: Crawl with AI
python main.py crawl --enhanced --limit 100 --ignore-robots

# 3. Export Data (Includes WHOIS + Website Data)
python main.py export --legal-only --include-incomplete
```

---

## New AI Features

The crawler now uses a hybrid approach to solve common extraction problems:

| Feature | Old Method (Regex) | **New Method (AI + GLiNER)** |
| :--- | :--- | :--- |
| **Company Name** | Often captured junk ("Adresse: ...") | **Accurate semantic extraction** |
| **Address** | Confused by multi-line text | **Structured extraction** (Street, City, ZIP) |
| **Context** | Blind pattern matching | **Understands "Managing Director" vs "Contact"** |
| **DNS Handling** | Failed on root domains | **Smart Fallback** (tries `www.` automatically) |

---

## Hybrid Truth (WHOIS Integration)

The system now implements a **"Hybrid Truth"** strategy. It captures data from two independent sources to ensure you get the full picture:

1.  **Website Operator** (from `/impressum`): The company *operating* the site.
2.  **Domain Registrant** (from WHOIS): The company *owning* the domain name.

**Why is this important?**
Often, a brand website (e.g., `peek-cloppenburg.at`) is operated by a local subsidiary (`Fashion ID GmbH`) but owned by a holding company (`JC New Retail AG`). Our export now shows **BOTH** side-by-side.

**How it works:**
- **Website Data**: Extracted via AI/Regex from the legal page.
- **Registrant Data**: Fetched via the `whois` protocol directly from the registry.
- **Smart Fill**: If the website is down or missing legal info, we fallback to WHOIS data to ensure *something* is always captured.

---

## End-to-End Testing

To verify the system is working correctly on your machine:

### 1. Unit Test (Verify WHOIS Module)
Check if the WHOIS enrichment is working standalone:
```bash
python test_whois.py
```
*Expected Output*: JSON data showing registrant info for `peek-cloppenburg.at`.

### 2. Integration Test (Single Domain)
Run a full crawl on a known tricky domain to prove DB storage works:
```bash
python main.py crawl --enhanced --limit 1 --tld .at
```
*(Note: This picks the next available .at domain. For a specific target, clear the queue first.)*

### 3. Batch Test (10 Domains)
Run a small batch to verify stability and export format:
```bash
# 1. Reset queue (optional)
python main.py reset

# 2. Run batch crawl
python main.py crawl --enhanced --limit 10 --concurrency 5 --tld .at

# 3. Export and check results
python main.py export --legal-only --include-incomplete
```
*Check the generated CSV file in the `data/` folder. It should have columns for `legal_name` AND `registrant_name`.*

---

## Step-by-Step Usage

### Step 1: Automated Discovery & Crawling (New)
The easiest way to start. Discovers domains and immediately starts crawling them.
```bash
python main.py discover --tld .de --crawl --concurrency 5
```

### Step 2: Manual Discovery (Optional)
If you want to just populate the queue first.
```bash
python main.py discover --tld .de --limit 1000
```

### Step 3: Manual Crawling (Optional)
Run the enhanced crawler on existing queued items.
```bash
python main.py crawl --enhanced --concurrency 10 --ignore-robots
```
* `--enhanced`: Activates Crawl4AI + GLiNER
* `--ignore-robots`: Optional, bypasses blocking (use responsibly)

### Step 3: Export Results
Get your data in CSV format.
```bash
python main.py export --legal-only --include-incomplete
```
* `--legal-only`: Exports the structured legal entity table.
* `--include-incomplete`: **Important!** Exports all found data, even if some fields (like Fax) are missing.

---

## Legal Data Extraction

The crawler targets these specific fields:

| Field | Description | Example |
| :--- | :--- | :--- |
| **Legal Name** | Official company name | `TechSolutions GmbH` |
| **Legal Form** | Entity type | `GmbH`, `AG`, `Ltd` |
| **Register** | Commercial register ID | `HRB 12345` |
| **Court** | Register court | `Amtsgericht Berlin` |
| **Address** | Structured location | `Musterstr 1, 10115 Berlin` |
| **Management** | CEO / Directors | `Dr. Max Mustermann` |
| **Contact** | Email & Phone | `info@tech.de`, `+49 30...` |

---

## Command Reference

### Reset Queue
Retry failed domains (useful after fixing network issues).
```bash
python main.py reset
```

### Wipe Database (New)
Start fresh by deleting all discovered domains and results. **Warning: Irreversible.**
```bash
python main.py reset-db
```

### Statistics
View progress and success rates.
```bash
python main.py stats
```

### Verification
Run a test on sample data to verify the AI model.
```bash
python test_legal_extraction.py
```

---

## Configuration

### Blacklist
You can exclude specific domains or keywords by adding them to `config/blacklist.txt`. The crawler supports live reloading of this file, so you can add domains while the crawler is running.
- **Exact Match**: Blocks exact domain names.
- **Keyword Match**: Blocks any domain containing the keyword.

Example `config/blacklist.txt`:
```text
google.com
amazon.de
example.com
```

---

## Troubleshooting

**"DNS Failed" errors?**
- We fixed a bug where domains without root A-records failed.
- Run `python main.py reset` then crawl again.

**"Blocked by robots.txt"?**
- Use the `--ignore-robots` flag to bypass.

**Export file is empty or has few rows?**
- Use `--include-incomplete` flag. By default, the exporter is very strict (requires ALL 6 fields).

---

*Developed by George*
