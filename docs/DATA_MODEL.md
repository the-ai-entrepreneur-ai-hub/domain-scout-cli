# Data Model & Architecture Guide

> **For Non-Technical Users:** This document explains how the Web Crawler works 
> "under the hood" using simple diagrams and explanations.

---

## Table of Contents

1. [Overview - The Big Picture](#overview---the-big-picture)
2. [How Data Flows Through the System](#how-data-flows-through-the-system)
3. [Database Tables Explained](#database-tables-explained)
4. [Legal Entity Extraction](#legal-entity-extraction)
5. [Domain Discovery Sources](#domain-discovery-sources)
6. [The Crawling Process](#the-crawling-process)

---

## Overview - The Big Picture

The Web Crawler is like a robot assistant that:
1. **Finds** websites (Discovery)
2. **Visits** those websites (Crawling)
3. **Collects** business + legal information (Extraction)
4. **Saves** everything to a timestamped CSV file (Export)

```
+==============================================================================+
|                         SYSTEM OVERVIEW                                      |
+==============================================================================+

   Step 1: DISCOVER          Step 2: CRAWL           Step 3: EXPORT
   =================         ==============          ===============

   +---------------+        +----------------+       +----------------+
   | 8 Internet    |        | Visit Each     |       | Filter & Save  |
   | Sources:      |        | Website:       |       | to CSV:        |
   |               |        |                |       |                |
   | - Tranco      |  ===>  | - Check DNS    | ===>  | Only entries   |
   | - Majestic    |        | - Read HTML    |       | with COMPLETE  |
   | - Umbrella    |        | - Find /legal  |       | metadata are   |
   | - CommonCrawl |        | - Extract all  |       | exported       |
   | - crt.sh      |        |   legal data   |       |                |
   | - Wayback     |        |                |       | Timestamped    |
   | - DuckDuckGo  |        +----------------+       | filename       |
   | - Bing        |               |                 +----------------+
   +---------------+               v                        |
          |                +----------------+               v
          v                | Legal Pages:   |        +----------------+
   +---------------+       | /impressum     |        | legal_entities_|
   | SQLite Queue  |       | /legal-notice  |        | 20241126_      |
   | (pending)     |       | /imprint       |        | 143022.csv     |
   +---------------+       +----------------+        +----------------+
```

---

## How Data Flows Through the System

```
+==============================================================================+
|                        COMPLETE DATA FLOW                                    |
+==============================================================================+

  DISCOVERY SOURCES                    CRAWLING PIPELINE
  =================                    =================

  +-------------+
  | Tranco 1M   |----+
  +-------------+    |
  +-------------+    |
  | Majestic 1M |----+
  +-------------+    |     +------------+     +-------------+
  +-------------+    |     |            |     |             |
  | Umbrella 1M |----+---->|  SQLite    |---->| DNS Check   |
  +-------------+    |     |  Queue     |     | (exists?)   |
  +-------------+    |     |            |     |             |
  | CommonCrawl |----+     +------------+     +------+------+
  +-------------+    |                               |
  +-------------+    |                    NO         |        YES
  | crt.sh      |----+              +--------+       +--------+
  +-------------+    |              | FAILED |       |        |
  +-------------+    |              | _DNS   |       v        |
  | Wayback     |----+              +--------+  +---------+   |
  +-------------+    |                          | robots  |   |
  +-------------+    |                          | .txt?   |   |
  | DuckDuckGo  |----+                          +----+----+   |
  +-------------+    |                               |        |
  +-------------+    |                    BLOCKED    |  OK    |
  | Bing Search |----+                  +--------+   +--------+
  +-------------+                       | BLOCKED|        |
                                        | ROBOTS |        v
                                        +--------+   +----------+
                                                     | Fetch    |
                                                     | Homepage |
                                                     +----+-----+
                                                          |
                      +-----------------------------------+
                      |
                      v
  +==============================================================================+
  |                        EXTRACTION PIPELINE                                   |
  +==============================================================================+

  +-------------------+     +-------------------+     +-------------------+
  | 1. Structured     |     | 2. Legal Page     |     | 3. Pattern        |
  |    Data Extract   |     |    Detection      |     |    Matching       |
  |                   |     |                   |     |                   |
  | - JSON-LD         |---->| - /impressum      |---->| - Company names   |
  | - Schema.org      |     | - /legal-notice   |     | - Phone numbers   |
  | - OpenGraph       |     | - /imprint        |     | - Email addresses |
  | - Microdata       |     | - /contact        |     | - Addresses       |
  +-------------------+     +-------------------+     +-------------------+
                                                              |
                                                              v
                                                     +-------------------+
                                                     | 4. Validation     |
                                                     |                   |
                                                     | - Phone format    |
                                                     | - Email verify    |
                                                     | - VAT check       |
                                                     +--------+----------+
                                                              |
                      +---------------------------------------+
                      |
                      v
  +==============================================================================+
  |                           STORAGE & EXPORT                                   |
  +==============================================================================+

  +-------------------+     +-------------------+     +-------------------+
  | results_enhanced  |     | legal_entities    |     | CSV Export        |
  | (SQLite table)    |     | (SQLite table)    |     |                   |
  |                   |     |                   |     | Only COMPLETE     |
  | - company_name    |     | - legal_name      |     | entries with:     |
  | - emails          |     | - legal_form      |     |                   |
  | - phones          |     | - street_address  |     | [x] Legal name    |
  | - address         |     | - postal_code     |     | [x] Legal form    |
  | - industry        |     | - city, country   |     | [x] Full address  |
  | - confidence      |     | - register_type   |     | [x] Contact info  |
  | - run_id          |     | - register_court  |     | [x] Register info |
  +-------------------+     | - registration_no |     | [x] Representatives|
                            | - ceo_name        |     +-------------------+
                            | - directors       |
                            | - phone, email    |
                            | - run_id          |
                            +-------------------+
```

---

## Database Tables Explained

The crawler stores everything in a **SQLite database** (`data/crawler_data.db`).

### Table 1: Queue (The To-Do List)

```
+==============================================================================+
|                              QUEUE TABLE                                     |
+==============================================================================+
| Column      | Type     | Description                      | Example         |
+-------------+----------+----------------------------------+-----------------+
| id          | INTEGER  | Unique ID (auto)                 | 1, 2, 3...      |
| domain      | TEXT     | Website address (unique)         | example.de      |
| source      | TEXT     | Discovery source                 | TRANCO, MAJESTIC|
| status      | TEXT     | Current processing state         | PENDING, etc.   |
| created_at  | DATETIME | When added to queue              | 2024-01-15 10:30|
| updated_at  | DATETIME | Last status change               | 2024-01-15 11:45|
+-------------+----------+----------------------------------+-----------------+

STATUS VALUES:
+-------------------+------------------------------------------+
| Status            | Meaning                                  |
+-------------------+------------------------------------------+
| PENDING           | Waiting to be crawled                    |
| PROCESSING        | Currently being crawled                  |
| COMPLETED         | Successfully crawled and extracted       |
| FAILED_DNS        | Domain does not exist                    |
| BLOCKED_ROBOTS    | robots.txt disallows crawling            |
| PARKED            | Domain for sale / parking page           |
| BLACKLISTED       | On our skip list                         |
| FAILED_HTTP_4XX   | HTTP client error (403, 404, etc.)       |
| FAILED_HTTP_5XX   | HTTP server error (500, 502, etc.)       |
| FAILED_CONNECTION | Could not connect                        |
| FAILED_EXTRACTION | Page loaded but extraction failed        |
+-------------------+------------------------------------------+
```

### Table 2: Legal Entities (Company Disclosures)

```
+==============================================================================+
|                          LEGAL_ENTITIES TABLE                                |
+==============================================================================+
| Column              | Type  | Description                    | Required     |
+---------------------+-------+--------------------------------+--------------+
| domain              | TEXT  | Website (unique key)           | YES          |
| legal_name          | TEXT  | Official company name          | YES          |
| legal_form          | TEXT  | GmbH, AG, Ltd, LLC, etc.       | YES          |
| street_address      | TEXT  | Street + house number          | YES          |
| postal_code         | TEXT  | ZIP/Postal code                | YES          |
| city                | TEXT  | City name                      | YES          |
| country             | TEXT  | Country name/code              | YES          |
| register_type       | TEXT  | Handelsregister B, etc.        | YES          |
| register_court      | TEXT  | Amtsgericht Berlin, etc.       | YES          |
| registration_number | TEXT  | HRB 12345, etc.                | YES          |
| vat_id              | TEXT  | DE123456789, etc.              | Optional     |
| ceo_name            | TEXT  | Managing director              | Recommended  |
| directors           | TEXT  | Board members (JSON/CSV)       | Optional     |
| authorized_reps     | TEXT  | Legal representatives          | Optional     |
| phone               | TEXT  | Contact phone (intl format)    | Recommended  |
| email               | TEXT  | Contact email                  | Recommended  |
| fax                 | TEXT  | Fax number                     | Optional     |
| legal_notice_url    | TEXT  | URL of impressum page          | Auto         |
| extraction_conf     | REAL  | Confidence score (0-100)       | Auto         |
| run_id              | TEXT  | UUID of crawl session          | Auto         |
+---------------------+-------+--------------------------------+--------------+

NOTE: CSV export only includes entries where ALL "YES" fields are populated.
```

---

## Legal Entity Extraction

The crawler extracts comprehensive legal information from websites:

```
+==============================================================================+
|                    LEGAL ENTITY EXTRACTION PROCESS                           |
+==============================================================================+

  STEP 1: FIND LEGAL PAGES          STEP 2: EXTRACT DATA
  =====================             ===================

  Check for these URLs:             For each legal page found:
  
  +-------------------+             +----------------------------------+
  | /impressum        |             | 1. STRUCTURED DATA (Priority)   |
  | /imprint          |             |    - JSON-LD schemas            |
  | /legal-notice     |             |    - Schema.org Organization    |
  | /legal            |             |    - Microdata                  |
  | /mentions-legales |             +----------------------------------+
  | /aviso-legal      |                          |
  | /note-legali      |                          v
  | /datenschutz      |             +----------------------------------+
  | /contact          |             | 2. PATTERN MATCHING             |
  | /about            |             |    - Company name patterns      |
  +-------------------+             |    - Legal form detection       |
          |                         |    - Registration numbers       |
          v                         |    - Address extraction         |
  +-------------------+             +----------------------------------+
  | Smart Link        |                          |
  | Discovery         |                          v
  | (finds legal      |             +----------------------------------+
  |  links in HTML)   |             | 3. VALIDATION                   |
  +-------------------+             |    - Phone: International fmt   |
                                    |    - Email: Format + MX check   |
                                    |    - VAT: Country-specific      |
                                    +----------------------------------+

  SUPPORTED LEGAL FORMS BY COUNTRY:
  +--------+---------------------------------------------------------------+
  | DE/AT  | GmbH, AG, KG, OHG, GbR, e.K., UG, KGaA, PartG, eG, e.U.       |
  | CH     | AG, GmbH, Sarl, SA, Sagl                                       |
  | UK     | Ltd, Limited, PLC, LLP, CIC                                    |
  | FR     | SARL, SA, SAS, EURL, SNC, SCS                                  |
  | IT     | S.r.l., S.p.A., S.a.s., S.n.c.                                 |
  | ES     | S.L., S.A., S.L.L., S.C.                                       |
  | NL     | B.V., N.V., V.O.F., C.V.                                       |
  | BE     | BVBA, NV, CVBA, VOF                                            |
  | US     | Inc., LLC, Corp., Corporation, Ltd., LLP, LP, PC               |
  +--------+---------------------------------------------------------------+

  REGISTRATION PATTERNS DETECTED:
  +-------------------+--------------------------------------------------+
  | Pattern           | Example                                          |
  +-------------------+--------------------------------------------------+
  | HRB/HRA           | HRB 12345, HRA 98765                             |
  | Amtsgericht       | Amtsgericht Munchen, Amtsgericht Berlin          |
  | Companies House   | Company Number: 12345678                         |
  | RCS (France)      | RCS Paris 123456789                              |
  | SIRET/SIREN       | SIRET 12345678901234                             |
  | VAT/USt-IdNr      | DE123456789, FR12345678901                       |
  +-------------------+--------------------------------------------------+
```

---

## Domain Discovery Sources

```
+==============================================================================+
|                        8 DISCOVERY SOURCES                                   |
+==============================================================================+

  PRIMARY SOURCES (Bulk CSV Downloads - Highest Yield)
  ====================================================
  
  +------------------+------------------+------------------+
  | TRANCO LIST      | MAJESTIC MILLION | CISCO UMBRELLA   |
  | Top 1M sites     | Top 1M by        | Top 1M by        |
  | by traffic       | referring sites  | DNS popularity   |
  +------------------+------------------+------------------+
          |                  |                  |
          +------------------+------------------+
                             |
                             v
  SECONDARY SOURCES (API-Based - Medium Yield)
  ============================================
  
  +------------------+------------------+------------------+
  | COMMON CRAWL     | CRT.SH           | WAYBACK MACHINE  |
  | Web archive      | Certificate      | Historical       |
  | index (CDX API)  | transparency     | web archive      |
  +------------------+------------------+------------------+
          |                  |                  |
          +------------------+------------------+
                             |
                             v
  TERTIARY SOURCES (Search Engines - Lower Yield)
  ===============================================
  
  +------------------+------------------+
  | DUCKDUCKGO       | BING SEARCH      |
  | Privacy-focused  | Microsoft        |
  | search engine    | search engine    |
  +------------------+------------------+
          |                  |
          +------------------+
                   |
                   v
          +------------------+
          |   SQLite Queue   |
          |   (Deduplicated) |
          +------------------+

  SOURCE COMPARISON:
  +-------------+---------------+-------------+------------------------+
  | Source      | Type          | Yield       | Best For               |
  +-------------+---------------+-------------+------------------------+
  | Tranco      | CSV Download  | Very High   | Popular sites          |
  | Majestic    | CSV Download  | Very High   | Sites with backlinks   |
  | Umbrella    | CSV Download  | High        | DNS-popular sites      |
  | CommonCrawl | API           | Medium      | Recently crawled       |
  | crt.sh      | API           | High        | New domains (SSL)      |
  | Wayback     | API           | Medium      | Historical sites       |
  | DuckDuckGo  | Web Scrape    | Low-Medium  | Fresh results          |
  | Bing        | Web Scrape    | Low-Medium  | Alternative results    |
  +-------------+---------------+-------------+------------------------+
```

---

## The Crawling Process

```
+==============================================================================+
|                         CRAWLING PROCESS FLOW                                |
+==============================================================================+

  For each domain in queue:

  +-------------+     +----------------+     +----------------+
  | 1. Get next |     | 2. Check       |     | 3. DNS         |
  |    PENDING  |---->|    Blacklist   |---->|    Resolution  |
  |    domain   |     |                |     |                |
  +-------------+     +-------+--------+     +-------+--------+
                              |                      |
                      Blacklisted?           Exists?
                              |                      |
                      +-------+-------+      +-------+-------+
                      | YES           | NO   | NO            | YES
                      v               v      v               v
               +------------+   Continue   +------------+   Continue
               | BLACKLISTED|              | FAILED_DNS |
               +------------+              +------------+
                                                   
  +----------------+     +----------------+     +----------------+
  | 4. Check       |     | 5. Fetch       |     | 6. Check if   |
  |    robots.txt  |---->|    Homepage    |---->|    Parked      |
  |                |     |    + Legal     |     |                |
  +-------+--------+     +-------+--------+     +-------+--------+
          |                      |                      |
   Allowed?               Success?              Parked?
          |                      |                      |
  +-------+-------+      +-------+-------+      +-------+-------+
  | NO            | YES  | NO            | YES  | YES           | NO
  v               v      v               v      v               v
  +-----------+  Cont.  +-------------+ Cont.  +--------+  Continue
  | BLOCKED_  |         | FAILED_     |        | PARKED |
  | ROBOTS    |         | CONNECTION  |        +--------+
  +-----------+         +-------------+

  +----------------+     +----------------+     +----------------+
  | 7. Extract     |     | 8. Validate    |     | 9. Save to DB  |
  |    All Data    |---->|    All Fields  |---->|    + Mark      |
  |                |     |                |     |    COMPLETED   |
  +----------------+     +----------------+     +----------------+
```

---

## Quick Reference Commands

```
+==============================================================================+
|                          CLI COMMAND REFERENCE                               |
+==============================================================================+

  DISCOVERY:
  ----------
  python main.py discover --tld de --limit 500     # Find German domains
  python main.py discover --tld ch --limit 1000    # Find Swiss domains
  python main.py discover --tld all --limit 2000   # Any TLD

  CRAWLING:
  ---------
  python main.py crawl --concurrency 10            # Basic crawl
  python main.py crawl --enhanced --concurrency 5  # Enhanced with legal extraction

  EXPORT:
  -------
  python main.py export --legal-only               # Legal entities (strict filter)
  python main.py export --legal-only --include-incomplete  # All entries
  python main.py export --enhanced --tld de        # Enhanced results for .de
  python main.py export --enhanced --json          # JSON format

  UTILITIES:
  ----------
  python main.py stats                             # Show statistics
  python main.py reset                             # Reset failed domains
```

---

*Document generated for Web Crawler v4.0 - Legal Entity Extraction*
