# User Story: How the Web Crawler Works

## Meet John - A Business Researcher

John needs to find company information for 500 German businesses. Instead of 
manually visiting each website, he uses this crawler to automate the process.

---

## Step 1: John Discovers Domains

```
John runs: python main.py discover --tld de --limit 500

+============================================================================+
|                    WHAT HAPPENS BEHIND THE SCENES                          |
+============================================================================+

    John's Computer                         Internet Sources
    ================                        ================

    +---------------+                       +------------------+
    |               |    "Find .de sites"   |  Tranco List     |
    |   Terminal    | --------------------> |  (Top 1M sites)  |
    |               |                       +------------------+
    |  $ python     |                              |
    |    main.py    |                              | 127 domains
    |    discover   |                              v
    |    --tld de   |                       +------------------+
    |    --limit    |                       |  Majestic List   |
    |    500        |                       |  (Backlinks)     |
    +---------------+                       +------------------+
           |                                       |
           |                                       | 98 domains
           |                                       v
           |                                +------------------+
           |                                |  Cisco Umbrella  |
           |                                |  (DNS popular)   |
           |                                +------------------+
           |                                       |
           |                                       | 45 domains
           v                                       v
    +----------------------------------------------------------+
    |                    SQLite Database                        |
    |                    (data/crawler_data.db)                 |
    |                                                           |
    |   +--------------------------------------------------+   |
    |   |  QUEUE TABLE                                     |   |
    |   +--------------------------------------------------+   |
    |   | domain          | source    | status   | created |   |
    |   +-----------------+-----------+----------+---------+   |
    |   | siemens.de      | TRANCO    | PENDING  | 10:30   |   |
    |   | bmw.de          | TRANCO    | PENDING  | 10:30   |   |
    |   | bosch.de        | MAJESTIC  | PENDING  | 10:31   |   |
    |   | mercedes.de     | UMBRELLA  | PENDING  | 10:32   |   |
    |   | ... 496 more    | ...       | PENDING  | ...     |   |
    |   +--------------------------------------------------+   |
    +----------------------------------------------------------+

    OUTPUT: "Discovered 500 domains for .de"
```

**What John sees:**
```
10:30:00 - INFO - Starting discovery for TLD: .de
10:30:02 - INFO - Tranco: ingested 127 domains
10:30:15 - INFO - Majestic: ingested 98 domains
10:30:28 - INFO - Umbrella: ingested 45 domains
10:30:45 - INFO - crt.sh: ingested 230 domains
10:31:00 - INFO - Discovery complete. 500 domains in queue.
```

---

## Step 2: John Crawls the Websites

```
John runs: python main.py crawl --enhanced --concurrency 5

+============================================================================+
|                         CRAWLING PROCESS                                   |
+============================================================================+

                           5 Workers Running in Parallel
    
    Worker 1              Worker 2              Worker 3              Worker 4              Worker 5
    ========              ========              ========              ========              ========
       |                     |                     |                     |                     |
       v                     v                     v                     v                     v
  +---------+           +---------+           +---------+           +---------+           +---------+
  |siemens  |           |bmw.de   |           |bosch.de |           |mercedes |           |sap.de   |
  |.de      |           |         |           |         |           |.de      |           |         |
  +---------+           +---------+           +---------+           +---------+           +---------+
       |                     |                     |                     |                     |
       v                     v                     v                     v                     v


    FOR EACH DOMAIN, THE CRAWLER DOES:

    +------------------------------------------------------------------------+
    |  STEP 1: DNS CHECK - Does the website exist?                           |
    +------------------------------------------------------------------------+
    |                                                                        |
    |    siemens.de  ------>  DNS Server  ------>  93.184.216.34  [EXISTS]  |
    |    fakeco.de   ------>  DNS Server  ------>  NXDOMAIN       [FAILED]  |
    |                                                                        |
    +------------------------------------------------------------------------+
                                    |
                                    v
    +------------------------------------------------------------------------+
    |  STEP 2: ROBOTS.TXT - Are we allowed to crawl?                         |
    +------------------------------------------------------------------------+
    |                                                                        |
    |    GET https://siemens.de/robots.txt                                   |
    |                                                                        |
    |    User-agent: *                                                       |
    |    Allow: /                    <---- We can crawl!                     |
    |    Disallow: /admin/                                                   |
    |                                                                        |
    +------------------------------------------------------------------------+
                                    |
                                    v
    +------------------------------------------------------------------------+
    |  STEP 3: FETCH HOMEPAGE + LEGAL PAGES                                  |
    +------------------------------------------------------------------------+
    |                                                                        |
    |    1. GET https://siemens.de/           (Homepage)                     |
    |    2. GET https://siemens.de/impressum  (Legal Notice - German)        |
    |    3. GET https://siemens.de/contact    (Contact Page)                 |
    |                                                                        |
    +------------------------------------------------------------------------+
                                    |
                                    v
    +------------------------------------------------------------------------+
    |  STEP 4: EXTRACT DATA FROM HTML                                        |
    +------------------------------------------------------------------------+
    |                                                                        |
    |    Raw HTML:                                                           |
    |    <html>                                                              |
    |      <title>Siemens AG - Technology Company</title>                    |
    |      <div class="impressum">                                           |
    |        Siemens Aktiengesellschaft                                      |
    |        Werner-von-Siemens-Str. 1                                       |
    |        80333 Munchen                                                   |
    |        Germany                                                         |
    |        Handelsregister: Amtsgericht Munchen, HRB 6684                  |
    |        Vorstand: Roland Busch (CEO)                                    |
    |        Tel: +49 89 636-00                                              |
    |        Email: contact@siemens.com                                      |
    |      </div>                                                            |
    |    </html>                                                             |
    |                                                                        |
    |                           EXTRACTED:                                   |
    |                           ==========                                   |
    |                                                                        |
    |    +------------------------+-------------------------------+          |
    |    | Field                  | Value                         |          |
    |    +------------------------+-------------------------------+          |
    |    | legal_name             | Siemens Aktiengesellschaft    |          |
    |    | legal_form             | AG                            |          |
    |    | street_address         | Werner-von-Siemens-Str. 1     |          |
    |    | postal_code            | 80333                         |          |
    |    | city                   | Munchen                       |          |
    |    | country                | Germany                       |          |
    |    | register_type          | Handelsregister B             |          |
    |    | register_court         | Amtsgericht Munchen           |          |
    |    | registration_number    | HRB 6684                      |          |
    |    | ceo_name               | Roland Busch                  |          |
    |    | phone                  | +49 89 636-00                 |          |
    |    | email                  | contact@siemens.com           |          |
    |    +------------------------+-------------------------------+          |
    |                                                                        |
    +------------------------------------------------------------------------+
                                    |
                                    v
    +------------------------------------------------------------------------+
    |  STEP 5: SAVE TO DATABASE                                              |
    +------------------------------------------------------------------------+
    |                                                                        |
    |    INSERT INTO legal_entities (domain, legal_name, legal_form, ...)    |
    |    VALUES ('siemens.de', 'Siemens Aktiengesellschaft', 'AG', ...)      |
    |                                                                        |
    |    UPDATE queue SET status = 'COMPLETED' WHERE domain = 'siemens.de'   |
    |                                                                        |
    +------------------------------------------------------------------------+
```

**What John sees during crawling:**
```
10:35:00 - INFO - Starting Crawl Run abc123 with 5 workers
10:35:02 - INFO - Crawling: https://siemens.de
10:35:04 - INFO - Crawling: https://bmw.de
10:35:05 - WARNING - DNS Failed: fakeco.de
10:35:08 - INFO - Crawling: https://bosch.de
10:35:15 - INFO - Found legal page: https://siemens.de/impressum
10:35:20 - INFO - Extracted: siemens.de | Siemens AG | HRB 6684
...
11:45:00 - INFO - Crawl Finished. 487 completed, 13 failed.
```

---

## Step 3: John Exports the Results

```
John runs: python main.py export --legal-only

+============================================================================+
|                         EXPORT PROCESS                                     |
+============================================================================+

    +----------------------------------------------------------+
    |                    SQLite Database                        |
    |                                                           |
    |   LEGAL_ENTITIES TABLE (487 rows)                        |
    |   +--------------------------------------------------+   |
    |   | domain     | legal_name          | legal_form    |   |
    |   +------------+---------------------+---------------+   |
    |   | siemens.de | Siemens AG          | AG            |   |
    |   | bmw.de     | BMW AG              | AG            |   |
    |   | bosch.de   | Robert Bosch GmbH   | GmbH          |   |
    |   | ...        | ...                 | ...           |   |
    |   +--------------------------------------------------+   |
    +----------------------------------------------------------+
                              |
                              v
    +----------------------------------------------------------+
    |              STRICT QUALITY FILTER                        |
    |                                                           |
    |   Only export if ALL these fields are present:           |
    |                                                           |
    |   [x] legal_name         - Company name                  |
    |   [x] legal_form         - GmbH, AG, Ltd, etc.           |
    |   [x] street_address     - Street + number               |
    |   [x] postal_code        - ZIP code                      |
    |   [x] city               - City name                     |
    |   [x] country            - Country                       |
    |   [x] register_type      - Handelsregister, etc.         |
    |   [x] register_court     - Amtsgericht, etc.             |
    |   [x] registration_number- HRB 12345, etc.               |
    |   [x] phone OR email     - Contact info                  |
    |                                                           |
    |   487 rows --> FILTER --> 312 complete rows              |
    |                                                           |
    +----------------------------------------------------------+
                              |
                              v
    +----------------------------------------------------------+
    |              CSV FILE WITH TIMESTAMP                      |
    |                                                           |
    |   Filename: legal_entities_20241126_114500_abc123.csv    |
    |                                                           |
    |   +--------------------------------------------------+   |
    |   | domain     | legal_name    | legal_form | street |   |
    |   +------------+---------------+------------+--------+   |
    |   | siemens.de | Siemens AG    | AG         | Werner.|   |
    |   | bmw.de     | BMW AG        | AG         | Petuel.|   |
    |   | bosch.de   | Bosch GmbH    | GmbH       | Robert.|   |
    |   +------------+---------------+------------+--------+   |
    |                                                           |
    +----------------------------------------------------------+
```

**What John sees:**
```
11:45:00 - INFO - Database initialized.
11:45:01 - INFO - Exported 312 legal entities with full metadata to 
                  data/legal_entities_20241126_114500_abc123.csv
```

---

## The Complete Journey (Summary)

```
+============================================================================+
|                    JOHN'S COMPLETE WORKFLOW                                |
+============================================================================+

    STEP 1                    STEP 2                    STEP 3
    DISCOVER                  CRAWL                     EXPORT
    ========                  =====                     ======

    +----------+              +----------+              +----------+
    |          |              |          |              |          |
    |  Find    |    500       |  Visit   |    487       |  Save    |    312
    |  German  | --------->   |  Each    | --------->   |  Clean   | --------->
    |  Domains |   domains    |  Website |   success    |  Data    |   complete
    |          |              |          |              |          |   records
    +----------+              +----------+              +----------+
         |                         |                         |
         v                         v                         v
    8 Sources:               For each site:            Quality filter:
    - Tranco                 - DNS check               - All 6 fields
    - Majestic               - Robots.txt              - Validated
    - Umbrella               - Fetch HTML              - Timestamped
    - CommonCrawl            - Find /impressum         
    - crt.sh                 - Extract data            
    - Wayback                - Validate                
    - DuckDuckGo             - Save to DB              
    - Bing                                             


    TIME: ~5 minutes          TIME: ~70 minutes         TIME: ~5 seconds
          (one-time)                (depends on          (instant)
                                     concurrency)
```

---

## What Data Does John Get?

```
+============================================================================+
|                    FINAL CSV FILE CONTENTS                                 |
+============================================================================+

  John opens the CSV in Excel and sees:

  +----------+------------------+------+-------------------+-------+--------+
  | domain   | legal_name       | form | street            | zip   | city   |
  +----------+------------------+------+-------------------+-------+--------+
  | siemens  | Siemens AG       | AG   | Werner-von-       | 80333 | Munich |
  | .de      |                  |      | Siemens-Str. 1    |       |        |
  +----------+------------------+------+-------------------+-------+--------+
  | bmw.de   | BMW AG           | AG   | Petuelring 130    | 80809 | Munich |
  +----------+------------------+------+-------------------+-------+--------+
  | bosch.de | Robert Bosch     | GmbH | Robert-Bosch-     | 70469 | Stutt- |
  |          | GmbH             |      | Platz 1           |       | gart   |
  +----------+------------------+------+-------------------+-------+--------+

  Continued columns:

  +----------+-----------------+-------------------+----------+-------------+
  | domain   | register_court  | registration_num  | ceo_name | phone       |
  +----------+-----------------+-------------------+----------+-------------+
  | siemens  | Amtsgericht     | HRB 6684          | Roland   | +49 89      |
  | .de      | Munich          |                   | Busch    | 636-00      |
  +----------+-----------------+-------------------+----------+-------------+
  | bmw.de   | Amtsgericht     | HRB 42243         | Oliver   | +49 89      |
  |          | Munich          |                   | Zipse    | 382-0       |
  +----------+-----------------+-------------------+----------+-------------+
  | bosch.de | Amtsgericht     | HRB 14000         | Stefan   | +49 711     |
  |          | Stuttgart       |                   | Hartung  | 811-0       |
  +----------+-----------------+-------------------+----------+-------------+

  Total: 312 rows of COMPLETE company data!
```

---

## Quick Command Reference for John

```
+============================================================================+
|                         COMMANDS JOHN USES                                 |
+============================================================================+

  TASK                              COMMAND
  ----                              -------

  Find 500 German companies         python main.py discover --tld de --limit 500

  Find 1000 Swiss companies         python main.py discover --tld ch --limit 1000

  Find companies from any country   python main.py discover --tld all --limit 2000

  Start crawling (enhanced mode)    python main.py crawl --enhanced --concurrency 5

  Export complete records only      python main.py export --legal-only

  Export ALL records (incomplete    python main.py export --legal-only --include-incomplete
  ones too)

  Check statistics                  python main.py stats

  Retry failed domains              python main.py reset
```

---

## Why Only 312 Out of 487?

```
+============================================================================+
|                    WHY SOME RECORDS ARE FILTERED OUT                       |
+============================================================================+

  487 websites crawled successfully, but only 312 have COMPLETE data.

  The other 175 are missing required fields:

  +---------------------+--------------------------------------------------+
  | Missing Field       | Why It Happens                                   |
  +---------------------+--------------------------------------------------+
  | legal_name          | Website has no clear company name                |
  | legal_form          | Not a registered company (e.g., freelancer)      |
  | street_address      | Only has P.O. Box, no street                     |
  | postal_code         | Address not in standard format                   |
  | city                | Could not parse from address                     |
  | country             | Not specified on website                         |
  | register_type       | Not a registered company                         |
  | register_court      | Foreign company, different system                |
  | registration_number | Not publicly disclosed                           |
  | phone/email         | Uses contact form only, no direct contact        |
  +---------------------+--------------------------------------------------+

  John can export incomplete records too with:
  
  python main.py export --legal-only --include-incomplete
  
  This gives him all 487 rows, but some fields will be empty.
```

---

*This is how John uses the Web Crawler to collect business information!*
