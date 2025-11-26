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

Now, the bot visits the websites found in Step 1 to extract legal entity information.

```bash
python main.py crawl --enhanced --concurrency 5
```

**What this does:**
- Checks if each domain exists (DNS check)
- Respects `robots.txt` rules
- Visits homepage + legal pages (/impressum, /legal-notice, /contact)
- Extracts ALL 6 required fields (name, form, address, reps, contact, register)
- Validates phone numbers, emails, and registration data
- Skips "parked" domains (domain for sale pages)

**Example output:**
```
02:15:00 - INFO - Starting Crawl Run abc123 with 5 workers
02:15:02 - INFO - Crawling: https://example.de
02:15:04 - INFO - Found legal page: https://example.de/impressum
02:15:06 - INFO - Extracted: example.de | Example GmbH | HRB 12345
02:15:08 - WARNING - DNS Failed: deadsite.de
```

### Step 3: Save Results (Export)

Once finished, save the data to a timestamped CSV file.

```bash
python main.py export --legal-only
```

**What this does:**
- Exports ONLY entries with complete metadata (all 6 required fields)
- Automatically adds timestamp to filename
- Creates CSV in the `data/` folder

**Your file will be at:** `data/legal_entities_20241126_143022_abc123.csv`

**To export ALL entries (including incomplete):**
```bash
python main.py export --legal-only --include-incomplete
```

---

## Testing the Crawler

Want to make sure everything works? Follow this quick test:

### Quick Test (5 minutes)

```bash
# Step 1: Discover just 20 Swiss (.ch) domains
python main.py discover --tld ch --limit 20

# Step 2: Crawl them with enhanced legal extraction
python main.py crawl --enhanced --concurrency 3

# Step 3: Export legal entities (only complete records)
python main.py export --legal-only

# Step 4: Check statistics
python main.py stats
```

### What to Check

1. **After Discovery**: You should see messages like:
   - `Inserted/Processed X domains into DB`
   - `=== Discovery complete ===`

2. **After Crawling**: Look for:
   - `Crawling: https://domain.ch` 
   - `Found legal page: https://domain.ch/impressum`
   - `Extracted: domain.ch | Company Name | HRB 12345`

3. **After Export**: 
   - Check `data/` folder for `legal_entities_TIMESTAMP.csv`
   - Open in Excel - should have columns: legal_name, legal_form, address, etc.

4. **After Stats**: Shows completion rate and field coverage

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
