# Intelligent Web Crawler with Legal Entity Extraction

**Welcome!** This is a custom-built tool designed to automatically find and extract comprehensive business and legal information from websites for any country/domain (e.g., `.de` for Germany, `.ch` for Switzerland).

**Key Features:**
- Extracts company names, contact info, and full legal disclosures
- Supports 10+ languages (German, English, French, Italian, Spanish, etc.)
- Validates phone numbers, emails, and registration data
- Only exports entries with COMPLETE metadata (strict quality control)

---

## Table of Contents

- [Quick Start Guide](#quick-start-guide)
- [How It Works](#how-it-works)
- [Legal Data Extraction](#legal-data-extraction)
- [Step-by-Step Usage](#step-by-step-usage)
- [Testing the Crawler](#testing-the-crawler)
- [Advanced Controls](#advanced-controls)
- [Output Data](#output-data)
- [Project Structure](#project-structure)
- [Troubleshooting](#troubleshooting)

---

## Quick Start Guide

### 1. Get the Code
```bash
git clone https://github.com/the-ai-entrepreneur-ai-hub/domain-scout-cli.git
cd domain-scout-cli
```

### 2. Prerequisites
- **Python 3.9 or higher** - Download from [python.org](https://www.python.org/downloads/)
- Check version: `python --version`

### 3. Installation
```bash
pip install -r requirements.txt
```

---

## How It Works

```
+============================================================================+
|                         WEB CRAWLER PIPELINE                               |
+============================================================================+

  PHASE 1: DISCOVER        PHASE 2: CRAWL           PHASE 3: EXPORT
  ==================       ===============          ================

  +----------------+       +----------------+       +----------------+
  |  8 Sources:    |       |  For Each URL: |       |  Quality Filter|
  |  - Tranco      |       |                |       |                |
  |  - Majestic    | ====> |  1. DNS Check  | ====> |  Only Complete |
  |  - Umbrella    |       |  2. Robots.txt |       |  Entries With: |
  |  - CommonCrawl |       |  3. Fetch HTML |       |                |
  |  - crt.sh      |       |  4. Extract:   |       |  * Legal Name  |
  |  - Wayback     |       |     - Company  |       |  * Legal Form  |
  |  - DuckDuckGo  |       |     - Legal    |       |  * Address     |
  |  - Bing        |       |     - Contact  |       |  * Contact     |
  +----------------+       +----------------+       |  * Register    |
         |                        |                +----------------+
         v                        v                        |
  +----------------+       +----------------+              v
  |   SQLite DB    |       |  Legal Pages:  |       +----------------+
  |   (queue)      |       |  /impressum    |       | Timestamped    |
  +----------------+       |  /legal-notice |       | CSV Export     |
                           |  /imprint      |       +----------------+
                           +----------------+
```

---

## Legal Data Extraction

The crawler extracts **6 mandatory fields** from every website's legal notice section:

```
+============================================================================+
|                    MANDATORY LEGAL ENTITY FIELDS                           |
+============================================================================+

  +---------------------------+--------------------------------------------+
  | FIELD                     | DESCRIPTION                                |
  +---------------------------+--------------------------------------------+
  | 1. Company/Person Name    | Official legal name or responsible person |
  | 2. Legal Form             | GmbH, AG, LLC, Ltd, SARL, S.r.l., etc.    |
  | 3. Full Postal Address    | Street, ZIP, City, Country (structured)   |
  | 4. Authorized Reps        | CEO, Directors, Managing Partners         |
  | 5. Contact Information    | Email AND Phone (validated format)        |
  | 6. Register Details       | Type, Court, Registration Number          |
  +---------------------------+--------------------------------------------+

  SUPPORTED COUNTRIES & PATTERNS:
  +--------+------------------+---------------------------+
  | Country| Legal Forms      | Register Types            |
  +--------+------------------+---------------------------+
  | DE/AT  | GmbH, AG, KG, UG | HRB/HRA + Amtsgericht     |
  | CH     | AG, GmbH, Sarl   | Commercial Register       |
  | UK     | Ltd, PLC, LLP    | Companies House           |
  | FR     | SARL, SAS, SA    | RCS + SIRET/SIREN         |
  | IT     | S.r.l., S.p.A.   | Registro Imprese          |
  | ES     | S.L., S.A.       | Registro Mercantil        |
  | US     | Inc, LLC, Corp   | State + EIN               |
  +--------+------------------+---------------------------+
```

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

### Enhanced Results CSV (`--enhanced`)
```
+==============================================================================+
|                          ENHANCED RESULTS COLUMNS                            |
+==============================================================================+
| Column           | Description                    | Example                  |
+------------------+--------------------------------+--------------------------+
| domain           | Website address                | example.de               |
| company_name     | Official business name         | Example GmbH             |
| description      | Company description            | Leading provider of...   |
| emails           | Contact emails (comma-sep)     | info@example.de          |
| phones           | Phone numbers (intl format)    | +49 30 123456            |
| address          | Physical address               | Musterstr. 1, Berlin     |
| industry         | Business sector                | Technology               |
| vat_id           | VAT/Tax ID                     | DE123456789              |
| social_linkedin  | LinkedIn company page          | linkedin.com/company/... |
| confidence_score | Data quality (0-100%)          | 85.0                     |
+------------------+--------------------------------+--------------------------+
```

### Legal Entities CSV (`--legal-only`)
```
+==============================================================================+
|                       LEGAL ENTITY EXPORT COLUMNS                            |
+==============================================================================+
| Column              | Description                 | Example                  |
+---------------------+-----------------------------+--------------------------+
| domain              | Website                     | example.de               |
| legal_name          | Official company name       | Example GmbH             |
| legal_form          | Entity type                 | GmbH                     |
| street_address      | Street + number             | Musterstrasse 123        |
| postal_code         | ZIP/Postal code             | 12345                    |
| city                | City name                   | Berlin                   |
| country             | Country                     | Germany                  |
| register_type       | Registration type           | Handelsregister B        |
| register_court      | Court/Authority             | Amtsgericht Berlin       |
| registration_number | Company number              | HRB 12345                |
| vat_id              | VAT identification          | DE123456789              |
| ceo_name            | Managing director           | Max Mustermann           |
| directors           | Board members               | Name1; Name2             |
| phone               | Contact phone               | +49 30 123456            |
| email               | Contact email               | info@example.de          |
| extraction_conf     | Confidence score            | 90.0                     |
+---------------------+-----------------------------+--------------------------+

NOTE: By default, only entries with ALL required fields are exported.
      Use --include-incomplete to export partial data.
```

---

## Project Structure

```
+==============================================================================+
|                           PROJECT FILE STRUCTURE                             |
+==============================================================================+

Web Crawler/
|
|-- main.py                    # CLI entry point
|-- requirements.txt           # Python dependencies
|-- README.md                  # This documentation
|
|-- src/                       # Source code
|   |-- discovery.py           # Domain discovery (8 sources)
|   |-- crawler.py             # Basic HTTP crawler
|   |-- enhanced_crawler.py    # Advanced crawler with Crawl4AI
|   |-- extractor.py           # Basic data extraction
|   |-- enhanced_extractor.py  # Structured data + validation
|   |-- legal_extractor.py     # Legal notice parsing (multi-language)
|   |-- enhanced_storage.py    # CSV/JSON export with filtering
|   |-- link_discoverer.py     # Smart legal page detection
|   |-- dns_checker.py         # DNS resolution
|   |-- database.py            # SQLite operations
|   |-- storage.py             # Basic CSV export
|   |-- models.py              # Pydantic data models
|   |-- utils.py               # Logging and settings
|   +-- reset_tool.py          # Reset failed domains
|
|-- config/                    # Configuration
|   |-- settings.yaml          # Crawler settings
|   +-- blacklist.txt          # Domains to skip
|
|-- data/                      # Output (auto-created)
|   |-- crawler_data.db        # SQLite database
|   |-- legal_entities_*.csv   # Legal entity exports
|   +-- results_*.csv          # Enhanced results
|
+-- logs/
    +-- crawler.log            # Activity log
```

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
