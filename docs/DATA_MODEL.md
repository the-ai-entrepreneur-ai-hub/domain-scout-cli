# Data Model & Architecture Guide

> **For Non-Technical Users:** This document explains how the Web Crawler works "under the hood" using simple diagrams and explanations. Think of it as a map of the system!

---

## Table of Contents

1. [Overview - The Big Picture](#overview---the-big-picture)
2. [How Data Flows Through the System](#how-data-flows-through-the-system)
3. [Database Tables Explained](#database-tables-explained)
4. [Source Files & What They Do](#source-files--what-they-do)
5. [Domain Discovery Sources](#domain-discovery-sources)
6. [The Crawling Process](#the-crawling-process)
7. [Data Extraction](#data-extraction)

---

## Overview - The Big Picture

The Web Crawler is like a robot assistant that:
1. **Finds** websites (Discovery)
2. **Visits** those websites (Crawling)
3. **Collects** business information (Extraction)
4. **Saves** everything to a file you can open in Excel (Export)

```mermaid
flowchart LR
    subgraph "Step 1: Discovery"
        A[Internet Sources] --> B[Domain List]
    end
    
    subgraph "Step 2: Crawling"
        B --> C[Crawler Bot]
        C --> D[Visit Websites]
    end
    
    subgraph "Step 3: Export"
        D --> E[Database]
        E --> F[CSV/Excel File]
    end
    
    style A fill:#e1f5fe
    style F fill:#c8e6c9
```

---

## How Data Flows Through the System

This diagram shows the complete journey of data from start to finish:

```mermaid
flowchart TB
    subgraph DISCOVERY["DISCOVERY PHASE"]
        direction TB
        T[Tranco List<br/>Top 1M Sites] --> Q[(Queue<br/>Database)]
        M[Majestic Million] --> Q
        U[Cisco Umbrella] --> Q
        CC[Common Crawl] --> Q
        CT[Certificate Logs<br/>crt.sh] --> Q
        WB[Wayback Machine] --> Q
        DDG[DuckDuckGo Search] --> Q
        BING[Bing Search] --> Q
    end

    subgraph CRAWLING["CRAWLING PHASE"]
        direction TB
        Q --> DNS{DNS Check<br/>Does site exist?}
        DNS -->|No| FAIL1[Mark as<br/>FAILED_DNS]
        DNS -->|Yes| ROBOT{Robots.txt<br/>Are we allowed?}
        ROBOT -->|No| FAIL2[Mark as<br/>BLOCKED_ROBOTS]
        ROBOT -->|Yes| FETCH[Fetch Page]
        FETCH --> PARK{Is it a<br/>Parked Domain?}
        PARK -->|Yes| FAIL3[Mark as<br/>PARKED]
        PARK -->|No| EXTRACT[Extract Data]
    end

    subgraph EXTRACTION["EXTRACTION PHASE"]
        direction TB
        EXTRACT --> COMP[Company Name]
        EXTRACT --> EMAIL[Email Address]
        EXTRACT --> PHONE[Phone Number]
        EXTRACT --> ADDR[Address]
        EXTRACT --> DESC[Description]
    end

    subgraph STORAGE["STORAGE PHASE"]
        direction TB
        COMP --> R[(Results<br/>Database)]
        EMAIL --> R
        PHONE --> R
        ADDR --> R
        DESC --> R
        R --> CSV[Export to CSV]
    end

    style DISCOVERY fill:#e3f2fd
    style CRAWLING fill:#fff3e0
    style EXTRACTION fill:#f3e5f5
    style STORAGE fill:#e8f5e9
```

---

## Database Tables Explained

The crawler stores everything in a **SQLite database** (a simple file-based database). There are two main "tables" (like spreadsheets):

### Table 1: Queue (The To-Do List)

This table keeps track of all domains we need to visit.

```mermaid
erDiagram
    QUEUE {
        int id PK "Unique ID (auto-generated)"
        string domain UK "Website address (e.g., example.de)"
        string source "Where we found it (TRANCO, MAJESTIC, etc.)"
        string status "Current state (PENDING, COMPLETED, FAILED...)"
        datetime created_at "When it was added"
        datetime updated_at "Last status change"
    }
```

| Column | What It Means | Example |
|--------|---------------|---------|
| `id` | Unique number for each entry | 1, 2, 3... |
| `domain` | The website address | `example.de` |
| `source` | Where we found this domain | `TRANCO`, `MAJESTIC`, `CRTSH` |
| `status` | What's happening with it | See status list below |
| `created_at` | When we added it | `2024-01-15 10:30:00` |
| `updated_at` | Last time we touched it | `2024-01-15 11:45:00` |

#### Possible Status Values

```mermaid
stateDiagram-v2
    [*] --> PENDING: Domain discovered
    PENDING --> PROCESSING: Worker picks it up
    PROCESSING --> COMPLETED: Success!
    PROCESSING --> FAILED_DNS: Site doesnt exist
    PROCESSING --> BLOCKED_ROBOTS: Not allowed to crawl
    PROCESSING --> PARKED: Domain for sale page
    PROCESSING --> BLACKLISTED: On our skip list
    PROCESSING --> FAILED_HTTP: Website error
    PROCESSING --> FAILED_CONNECTION: Could not connect
    PROCESSING --> FAILED_EXTRACTION: Could not read page
    
    COMPLETED --> [*]
    FAILED_DNS --> [*]
    BLOCKED_ROBOTS --> [*]
    PARKED --> [*]
    BLACKLISTED --> [*]
```

### Table 2: Results (The Collected Data)

This table stores the actual business information we found.

```mermaid
erDiagram
    RESULTS {
        int id PK "Unique ID"
        string domain UK "Website address"
        string company_name "Business name"
        string description "What the company does"
        string email "Contact email"
        string phone "Phone number"
        string address "Physical address"
        datetime crawled_at "When we visited"
    }
```

| Column | What It Means | Example |
|--------|---------------|---------|
| `domain` | The website | `acme-corp.de` |
| `company_name` | Business name | `ACME Corporation GmbH` |
| `description` | What they do | `Leading provider of...` |
| `email` | Contact email | `info@acme-corp.de` |
| `phone` | Phone number | `+49 30 123456` |
| `address` | Location | `Musterstrasse 123, Berlin` |

---

## Source Files & What They Do

Think of each file as a worker with a specific job:

```mermaid
flowchart TB
    subgraph ENTRY["Entry Point"]
        MAIN[main.py<br/>The Boss - Runs everything]
    end

    subgraph CORE["Core Workers"]
        DISC[discovery.py<br/>Finds domains from 8 sources]
        CRAWL[crawler.py<br/>Visits websites]
        EXTRACT[extractor.py<br/>Reads page content]
        DNS[dns_checker.py<br/>Checks if sites exist]
    end

    subgraph DATA["Data Handlers"]
        DB[database.py<br/>Manages the database]
        STORE[storage.py<br/>Exports to CSV]
        MODEL[models.py<br/>Defines data structure]
    end

    subgraph HELPERS["Helpers"]
        UTIL[utils.py<br/>Logging and settings]
        RESET[reset_tool.py<br/>Retry failed domains]
    end

    MAIN --> DISC
    MAIN --> CRAWL
    MAIN --> STORE
    MAIN --> RESET
    
    DISC --> DB
    CRAWL --> DNS
    CRAWL --> EXTRACT
    CRAWL --> DB
    EXTRACT --> MODEL
    STORE --> DB

    style ENTRY fill:#ffcdd2
    style CORE fill:#bbdefb
    style DATA fill:#c8e6c9
    style HELPERS fill:#fff9c4
```

### File Details

| File | Purpose | Simple Explanation |
|------|---------|-------------------|
| `main.py` | Entry point | The "start button" - runs the whole show |
| `discovery.py` | Find domains | Searches 8 different sources to find websites |
| `crawler.py` | Visit sites | The robot that opens each website |
| `extractor.py` | Read content | Finds emails, phone numbers, etc. on pages |
| `dns_checker.py` | Check DNS | Makes sure websites actually exist |
| `database.py` | Database ops | Saves and retrieves data |
| `storage.py` | Export data | Creates the final CSV/Excel file |
| `models.py` | Data shapes | Defines what data looks like |
| `utils.py` | Utilities | Logging, colors, settings |
| `reset_tool.py` | Reset tool | Lets you retry failed domains |

---

## Domain Discovery Sources

The crawler searches **8 different sources** to find as many domains as possible:

```mermaid
flowchart TB
    subgraph PRIMARY["Primary Sources - Bulk Lists"]
        direction LR
        P1[Tranco List<br/>Top 1 Million websites<br/>by traffic ranking]
        P2[Majestic Million<br/>Top 1 Million by<br/>referring websites]
        P3[Cisco Umbrella<br/>Top 1 Million by<br/>DNS popularity]
    end

    subgraph SECONDARY["Secondary Sources - APIs"]
        direction LR
        S1[Common Crawl<br/>Web archive index<br/>of crawled pages]
        S2[Certificate Logs<br/>crt.sh database of<br/>SSL certificates]
        S3[Wayback Machine<br/>Historical archive<br/>of websites]
    end

    subgraph TERTIARY["Tertiary Sources - Search Engines"]
        direction LR
        T1[DuckDuckGo<br/>Privacy-focused<br/>search engine]
        T2[Bing Search<br/>Microsoft search<br/>engine]
    end

    PRIMARY --> DB[(Database<br/>Queue)]
    SECONDARY --> DB
    TERTIARY --> DB

    style PRIMARY fill:#fff3e0
    style SECONDARY fill:#e8eaf6
    style TERTIARY fill:#fce4ec
```

### Source Comparison

| Source | Type | Typical Yield | Best For |
|--------|------|---------------|----------|
| Tranco | CSV Download | Very High | Popular sites |
| Majestic | CSV Download | Very High | Sites with backlinks |
| Umbrella | CSV Download | High | DNS-popular sites |
| Common Crawl | API | Medium | Recently crawled sites |
| crt.sh | API | High | New domains (SSL certs) |
| Wayback | API | Medium | Historical/older sites |
| DuckDuckGo | Web Scrape | Low-Medium | Fresh results |
| Bing | Web Scrape | Low-Medium | Alternative results |

---

## The Crawling Process

Here's what happens when the crawler visits each website:

```mermaid
sequenceDiagram
    participant Q as Queue DB
    participant W as Crawler Worker
    participant DNS as DNS Checker
    participant WEB as Website
    participant E as Extractor
    participant R as Results DB

    Q->>W: Get next PENDING domain
    W->>W: Check blacklist
    
    alt Domain is blacklisted
        W->>Q: Mark as BLACKLISTED
    else Domain is OK
        W->>DNS: Does domain exist?
        
        alt DNS fails
            DNS->>W: No - NXDOMAIN
            W->>Q: Mark as FAILED_DNS
        else DNS succeeds
            DNS->>W: Yes - IP found
            W->>WEB: Fetch robots.txt
            
            alt Blocked by robots.txt
                WEB->>W: Disallow
                W->>Q: Mark as BLOCKED_ROBOTS
            else Allowed
                WEB->>W: Allow
                W->>W: Wait - politeness delay
                W->>WEB: GET homepage
                
                alt Connection fails
                    WEB->>W: Error or Timeout
                    W->>Q: Mark as FAILED_CONNECTION
                else Success
                    WEB->>W: HTML content
                    W->>E: Extract data
                    
                    alt Parked domain detected
                        E->>W: PARKED status
                        W->>Q: Mark as PARKED
                    else Valid content
                        E->>W: Company - Email - Phone
                        W->>R: Save results
                        W->>Q: Mark as COMPLETED
                    end
                end
            end
        end
    end
```

---

## Data Extraction

The Extractor looks for specific information on each page:

```mermaid
flowchart TB
    HTML[Raw HTML Page] --> PARSE[Parse with BeautifulSoup]
    
    PARSE --> PARK{Parked Domain<br/>Check}
    PARK -->|Domain for sale<br/>Under construction| SKIP[Skip - Parked]
    PARK -->|Real content| EXTRACT
    
    subgraph EXTRACT["Data Extraction"]
        direction TB
        
        subgraph COMPANY["Company Name Priority"]
            C1["1. og:site_name meta tag"]
            C2["2. application-name meta"]
            C3["3. Page title"]
            C4["4. First H1 heading"]
            C5["5. Domain name - fallback"]
            C1 --> C2 --> C3 --> C4 --> C5
        end
        
        subgraph EMAIL["Email Extraction"]
            E1["Find all emails with regex"]
            E2["Filter out personal emails<br/>gmail, yahoo, etc"]
            E3["Prefer business emails<br/>info@ contact@"]
            E1 --> E2 --> E3
        end
        
        subgraph PHONE["Phone Extraction"]
            P1["Look for Tel or Phone label"]
            P2["Match international formats<br/>+49, 030, etc"]
            P1 --> P2
        end
        
        subgraph DESC["Description"]
            D1["meta description tag"]
            D2["og:description tag"]
            D1 --> D2
        end
    end
    
    EXTRACT --> RESULT[CrawlResult Object]
    
    style PARK fill:#fff3e0
    style EXTRACT fill:#e8f5e9
```

### Email Filtering Rules

The crawler is smart about which emails to keep:

| Email Type | Example | Action |
|------------|---------|--------|
| Business (same domain) | `info@company.de` | KEEP (priority) |
| Generic business | `contact@company.de` | KEEP |
| Personal (free provider) | `john@gmail.com` | SKIP |
| Personal pattern | `john.smith@company.de` | SKIP (GDPR) |

---

## Project File Structure

```
Web Crawler/
|
|-- main.py              # Start here! The main entry point
|-- requirements.txt     # Python packages needed
|-- README.md            # Quick start guide
|
|-- src/                 # Source code
|   |-- discovery.py     # Finds domains (8 sources)
|   |-- crawler.py       # Visits websites
|   |-- extractor.py     # Extracts data from HTML
|   |-- dns_checker.py   # Verifies domains exist
|   |-- database.py      # Database operations
|   |-- storage.py       # CSV export
|   |-- models.py        # Data structures
|   |-- utils.py         # Helpers (logging, settings)
|   +-- reset_tool.py    # Reset failed domains
|
|-- config/              # Configuration
|   |-- settings.yaml    # Crawler settings
|   +-- blacklist.txt    # Sites to skip
|
|-- data/                # Output data
|   |-- crawler_data.db  # SQLite database
|   |-- top-1m.csv       # Downloaded Tranco list
|   |-- majestic_million.csv  # Downloaded Majestic list
|   +-- results_*.csv    # Exported results
|
|-- logs/                # Log files
|   +-- crawler.log      # Detailed activity log
|
+-- docs/                # Documentation
    +-- DATA_MODEL.md    # This file!
```

---

## Quick Reference Commands

| What You Want | Command |
|---------------|---------|
| Find 500 German domains | `python main.py discover --tld de --limit 500` |
| Find 1000 Swiss domains | `python main.py discover --tld ch --limit 1000` |
| Start crawling | `python main.py crawl --concurrency 10` |
| Export results | `python main.py export --tld de` |
| Reset failed domains | `python main.py reset` |

---

*Document generated for Web Crawler v1.0*
