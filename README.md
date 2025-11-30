# SMB Web Crawler v2 (AI-Enhanced)

**Welcome!** This is a custom-built tool designed to automatically find and extract comprehensive business and legal information from websites. It is optimized for finding Small & Medium Businesses (SMBs) that are often missed by standard crawlers.

**Key Features:**
*   **SMB Discovery**: Uses targeted search dorks (e.g., `site:.de "Impressum" "GmbH"`) to find smaller companies.
*   **AI-Powered Extraction**: Uses GLiNER (Generalist Lightweight NER) and strict heuristics to semantically understand legal pages.
*   **High Data Quality**: New **DataValidator** ensures 100% schema compliance, filtering out navigation garbage and invalid names.
*   **Unified Export**: Produces a clean, single-file CSV with 23 standard columns (Legal Name, CEO, Address, Robots Status, etc.).
*   **Resilient**: Handles DNS issues, timeouts, and search engine blocking (via Common Crawl fallback).
*   **Hybrid Truth (WHOIS)**: Combines website data (Imprint) with official domain registration data (WHOIS).

---

## Table of Contents

- [Quick Start Guide](#quick-start-guide)
- [SMB Discovery & Workflow](#smb-discovery--workflow)
- [Data Quality & Validation](#data-quality--validation)
- [Command Reference](#command-reference)
- [Troubleshooting](#troubleshooting)

---

## Quick Start Guide

### 1. Installation
```bash
pip install -r requirements.txt
playwright install chromium
python -m spacy download de_core_news_sm
```

### 2. Standard SMB Workflow (Recommended)
This workflow is optimized for finding valid German/DACH companies.

```bash
# Step 1: Discover SMBs (Targeted Search)
# Filters out "Top 1M" giants to focus on smaller entities
python main.py discover --company-size smb --limit 100 --tld de

# Step 2: Crawl with Enhanced Validation
# Extracts data, checks robots.txt, and validates legal forms
python main.py crawl --enhanced --concurrency 10

# Step 3: Export Unified Report
# Generates a single, clean CSV matching the client schema
python main.py export --unified
```

---

## SMB Discovery & Workflow

### Discovery Modes
The crawler supports different strategies for finding domains:

*   **SMB Mode** (`--company-size smb`):
    *   Uses specific search dorks (`"Impressum" "GmbH"`, `"Handwerk"`, etc.) to find relevant legal pages directly.
    *   **Automatic Fallback**: If search engines block requests, it automatically queries the Common Crawl index for the TLD.
    *   *Best for: Finding local businesses, craftsmen, startups.*

*   **Enterprise Mode** (`--company-size enterprise`):
    *   Uses Tranco, Majestic, and Umbrella Top 1M lists.
    *   *Best for: Analyzing popular/high-traffic sites.*

### Unified Export Schema
The `export --unified` command produces a strictly validated CSV with the following 23 columns:
*   `company_name`, `legal_form`, `registration_number`
*   `ceo_names`, `owner_organization`
*   `industry`, `company_size`
*   `emails`, `phone_numbers`, `fax_numbers`
*   `street`, `postal_code`, `city`, `country`
*   `service_product_description`
*   `social_links`, `website_created_at`, `website_last_updated_at`
*   `domain`, `crawled_at`, `run_id`
*   `robots_allowed`, `robots_reason`

---

## Architecture & Execution Flow

The system is designed as a modular pipeline. Here is how data flows from the CLI to the final CSV export:

```mermaid
graph TD
    CLI[CLI (main.py)] -->|1. Discover| Discovery[Discovery Module]
    CLI -->|2. Crawl| Crawler{EnhancedCrawler}
    CLI -->|3. Export| Exporter[UnifiedExporter]

    subgraph "Phase 1: Discovery"
        Discovery -->|Fetch| Dorks[Search Dorks / CommonCrawl]
        Dorks -->|Store| Queue[(Database Queue)]
    end

    subgraph "Phase 2: Crawling & Extraction"
        Crawler -->|Read| Queue
        Crawler -->|Render| Playwright[Playwright / Crawl4AI]
        Playwright -->|HTML| Extractor[EnhancedExtractor / LegalExtractor]
        Extractor -->|Raw Data| Validator[DataValidator]
        Validator -->|Valid Data| DB[(Database Results)]
    end

    subgraph "Phase 3: Export"
        Exporter -->|Query| DB
        Exporter -->|Format| CSV[Unified CSV]
    end
```

### Core Components

*   **`main.py`**: The entry point handling CLI arguments and orchestration.
*   **`src/discovery.py`**: Manages domain finding strategies (Targeted Search, Common Crawl, etc.).
*   **`src/enhanced_crawler.py`**: The main engine that manages concurrent workers, Playwright instances, and robots.txt compliance.
*   **`src/enhanced_extractor.py`**: Extracts structured data (emails, phones, addresses) using regex and heuristics.
*   **`src/legal_extractor.py`**: Specialized logic for parsing German Impressum/Legal pages.
*   **`src/validator.py`**: Enforces strict data quality rules (garbage filtering, address validation).
*   **`src/enhanced_storage.py`**: Handles data persistence and generating the Unified Export.

---

## Data Quality & Validation

We have implemented a strict **DataValidator** to ensure production-grade quality:

1.  **Garbage Rejection**:
    *   Blocks navigation terms ("Home | About", "Warenkorb (0)", "Search...") from being saved as Company Names.
    *   Rejects invalid addresses (e.g., missing City or Zip).
2.  **Strict Heuristics**:
    *   **CEO Names**: Must be a person entity, not a company or address. Filters out titles like "Geschäftsführer".
    *   **Addresses**: Enforces German address formats (5-digit Zip).
3.  **Robots Compliance**:
    *   Explicitly checks `robots.txt` for every domain.
    *   Records status (`True`/`False`) and reason in the export.

---

## Command Reference

### Discovery
```bash
# Find 500 SMBs in Switzerland
python main.py discover --company-size smb --limit 500 --tld ch

# Find generic domains (mixed sources)
python main.py discover --limit 1000 --tld de
```

### Crawling
```bash
# Run the enhanced crawler (Playwright + AI)
python main.py crawl --enhanced --concurrency 10

# Options:
# --limit N          : Stop after N domains
# --ignore-robots    : Bypass robots.txt (Use with caution)
```

### Export
```bash
# Recommended: Unified Format
python main.py export --unified

# Legacy Formats (if needed):
python main.py export --legal-only    # Just legal entities table
python main.py export --enhanced      # Raw enhanced results
```

### Maintenance
```bash
# Reset FAILED domains to PENDING (for retrying)
python main.py reset

# Wipe database completely (start fresh)
python main.py reset-db

# View statistics
python main.py stats
```

---

## Troubleshooting

**"Discovery found 0 domains?"**
- Search engines might be rate-limiting your IP.
- **Fix**: The system now auto-falls back to Common Crawl. Just let it run.

**"Missing Legal Info?"**
- Some sites use images for text or complex JS.
- The `enhanced` crawler tries to render this, but it's not 100%.
- Check `robots_allowed` column - we might be respecting a block.

**"Installation Error (SpaCy)?"**
- Run `python -m spacy download de_core_news_sm` manually.

---

*Developed by George*
