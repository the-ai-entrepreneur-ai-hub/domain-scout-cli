import httpx
import pandas as pd
import zipfile
import io
import asyncio
import json
import re
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote
from bs4 import BeautifulSoup
from .utils import logger
from .database import insert_domains

TRANCO_URL = "https://tranco-list.eu/top-1m.csv.zip"
MAJESTIC_URL = "https://downloads.majestic.com/majestic_million.csv"
UMBRELLA_URL = "http://s3-us-west-1.amazonaws.com/umbrella-static/top-1m.csv.zip"
DATA_DIR = Path("data")
TRANCO_FILE = DATA_DIR / "top-1m.csv"
MAJESTIC_FILE = DATA_DIR / "majestic_million.csv"
UMBRELLA_FILE = DATA_DIR / "umbrella-top-1m.csv"

# Subdomains that almost always lead to DNS/timeouts and non-HTML targets
SKIP_SUBDOMAIN_PREFIXES = {
    "mail", "smtp", "imap", "pop", "pop3", "mx", "dns", "ns", "ns1", "ns2",
    "p", "api", "cdn", "static", "assets", "open", "rss", "ftp", "webmail"
}

# Non-commercial domain patterns (universities, government, etc.)
NON_COMMERCIAL_PATTERNS = [
    '.ac.at',      # Austrian universities
    '.ac.uk',      # UK universities  
    '.edu',        # US education
    '.gv.at',      # Austrian government
    '.gov.',       # Government sites
    'uni-',        # German universities
    'university',  # University sites
    'hochschule',  # German higher education
]

def should_skip_domain(domain: str) -> bool:
    """
    Filters out noisy/non-HTML domains and non-commercial entities.
    Drops service subdomains, universities, government sites.
    """
    if not domain:
        return True
    d = str(domain).strip().lower()
    # Disallow obvious path/port noise
    if "/" in d or ":" in d:
        return True
    parts = d.split(".")
    if len(parts) >= 3:
        sub = parts[0]
        if sub in SKIP_SUBDOMAIN_PREFIXES:
            return True
    
    # Skip non-commercial domains (universities, government, etc.)
    for pattern in NON_COMMERCIAL_PATTERNS:
        if pattern in d:
            return True
            
    return False

def setup_data_dir():
    DATA_DIR.mkdir(exist_ok=True)

def download_tranco_list():
    if TRANCO_FILE.exists():
        logger.info("Tranco list already exists.")
        return

    logger.info("Downloading Tranco list...")
    try:
        with httpx.Client(timeout=60, follow_redirects=True) as client:
            response = client.get(TRANCO_URL)
            response.raise_for_status()
            with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                z.extractall(DATA_DIR)
        logger.info("Tranco list downloaded.")
    except Exception as e:
        logger.error(f"Failed to download Tranco list: {e}")
        raise

async def ingest_tranco_domains(tld: str, limit: int = 1000):
    """Reads Tranco list and pushes matching TLDs to DB."""
    setup_data_dir()
    if not TRANCO_FILE.exists():
        download_tranco_list()

    logger.info(f"Ingesting Tranco domains for TLD: {tld or 'ANY'}")
    
    batch = []
    count = 0
    chunk_size = 100000
    
    use_filter = tld not in (None, "", "*", "all", "any")
    suffix = None
    if use_filter:
        suffix = tld if tld.startswith('.') else f".{tld}"
    
    try:
        # Using pandas for fast CSV reading
        for chunk in pd.read_csv(TRANCO_FILE, header=None, names=['rank', 'domain'], chunksize=chunk_size):
            if use_filter:
                domain_iter = chunk[chunk['domain'].str.endswith(suffix, na=False)]['domain']
            else:
                domain_iter = chunk['domain']

            for domain in domain_iter:
                if should_skip_domain(domain):
                    continue
                batch.append((domain, "TRANCO"))
                count += 1
                
                if len(batch) >= 1000:
                    await insert_domains(batch)
                    batch = []
                    
            if count >= limit:
                break
        
        if batch:
            await insert_domains(batch)
            
    except Exception as e:
        logger.error(f"Error processing Tranco list: {e}")

def download_majestic_list():
    """Download Majestic Million CSV (no zip)."""
    if MAJESTIC_FILE.exists():
        logger.info("Majestic Million list already exists.")
        return

    logger.info("Downloading Majestic Million list...")
    try:
        with httpx.Client(timeout=120, follow_redirects=True) as client:
            response = client.get(MAJESTIC_URL)
            response.raise_for_status()
            MAJESTIC_FILE.write_bytes(response.content)
        logger.info("Majestic Million list downloaded.")
    except Exception as e:
        logger.error(f"Failed to download Majestic Million: {e}")


def download_umbrella_list():
    """Download Cisco Umbrella top 1M (zipped)."""
    if UMBRELLA_FILE.exists():
        logger.info("Umbrella list already exists.")
        return

    logger.info("Downloading Cisco Umbrella list...")
    try:
        with httpx.Client(timeout=120, follow_redirects=True) as client:
            response = client.get(UMBRELLA_URL)
            response.raise_for_status()
            with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                for name in z.namelist():
                    if name.endswith('.csv'):
                        with z.open(name) as src:
                            UMBRELLA_FILE.write_bytes(src.read())
                        break
        logger.info("Umbrella list downloaded.")
    except Exception as e:
        logger.error(f"Failed to download Umbrella list: {e}")


async def ingest_majestic_domains(tld: str, limit: int = 1000):
    """Reads Majestic Million and pushes matching TLDs to DB."""
    setup_data_dir()
    try:
        download_majestic_list()
    except:
        logger.warning("Skipping Majestic source (download failed)")
        return

    if not MAJESTIC_FILE.exists():
        return

    logger.info(f"Ingesting Majestic domains for TLD: {tld or 'ANY'}")

    batch = []
    count = 0
    chunk_size = 100000

    use_filter = tld not in (None, "", "*", "all", "any")
    suffix = None
    if use_filter:
        suffix = tld if tld.startswith('.') else f".{tld}"

    try:
        for chunk in pd.read_csv(MAJESTIC_FILE, chunksize=chunk_size):
            col = 'Domain' if 'Domain' in chunk.columns else chunk.columns[-1]
            if use_filter:
                domain_iter = chunk[chunk[col].astype(str).str.endswith(suffix, na=False)][col]
            else:
                domain_iter = chunk[col]

            for domain in domain_iter:
                domain = str(domain).strip().lower()
                if domain and not should_skip_domain(domain):
                    batch.append((domain, "MAJESTIC"))
                    count += 1

                    if len(batch) >= 1000:
                        await insert_domains(batch)
                        batch = []

            if count >= limit:
                break

        if batch:
            await insert_domains(batch)
        logger.info(f"Majestic: ingested {count} domains")

    except Exception as e:
        logger.error(f"Error processing Majestic list: {e}")


async def ingest_umbrella_domains(tld: str, limit: int = 1000):
    """Reads Cisco Umbrella list and pushes matching TLDs to DB."""
    setup_data_dir()
    try:
        download_umbrella_list()
    except:
        logger.warning("Skipping Umbrella source (download failed)")
        return

    if not UMBRELLA_FILE.exists():
        return

    logger.info(f"Ingesting Umbrella domains for TLD: {tld or 'ANY'}")

    batch = []
    count = 0
    chunk_size = 100000

    use_filter = tld not in (None, "", "*", "all", "any")
    suffix = None
    if use_filter:
        suffix = tld if tld.startswith('.') else f".{tld}"

    try:
        for chunk in pd.read_csv(UMBRELLA_FILE, header=None, names=['rank', 'domain'], chunksize=chunk_size):
            if use_filter:
                domain_iter = chunk[chunk['domain'].astype(str).str.endswith(suffix, na=False)]['domain']
            else:
                domain_iter = chunk['domain']

            for domain in domain_iter:
                domain = str(domain).strip().lower()
                if domain and not should_skip_domain(domain):
                    batch.append((domain, "UMBRELLA"))
                    count += 1

                    if len(batch) >= 1000:
                        await insert_domains(batch)
                        batch = []

            if count >= limit:
                break

        if batch:
            await insert_domains(batch)
        logger.info(f"Umbrella: ingested {count} domains")

    except Exception as e:
        logger.error(f"Error processing Umbrella list: {e}")


async def ingest_common_crawl_domains(tld: str, limit: int = 100):
    """Queries Common Crawl and pushes to DB."""
    logger.info(f"Searching Common Crawl for TLD: {tld}")

    if tld in (None, "", "*", "all", "any"):
        logger.info("Skipping Common Crawl for ANY-TLD mode to avoid huge responses.")
        return
    
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            # 1. Get latest index
            idx_resp = await client.get("https://index.commoncrawl.org/collinfo.json")
            if idx_resp.status_code == 200:
                indexes = idx_resp.json()
                latest_index = sorted(indexes, key=lambda x: x['id'], reverse=True)[0]['id']
            else:
                latest_index = "CC-MAIN-2024-42"
            
            logger.info(f"Using Common Crawl Index: {latest_index}")
            
            cdx_url = f"https://index.commoncrawl.org/{latest_index}-index"
            params = {
                'url': f"*.{tld.lstrip('.')}",
                'output': 'json',
                'fl': 'url',
                'limit': limit * 3, 
                'filter': 'status:200'
            }
            
            resp = await client.get(cdx_url, params=params)
            
            batch = []
            processed = set()
            
            for line in resp.text.splitlines():
                try:
                    import json
                    data = json.loads(line)
                    url = data.get('url')
                    if url:
                        parsed = urlparse(url)
                        domain = parsed.netloc
                        if domain and domain not in processed and not should_skip_domain(domain):
                            processed.add(domain)
                            batch.append((domain, "COMMON_CRAWL"))
                            
                    if len(batch) >= 100:
                        await insert_domains(batch)
                        batch = []
                        
                    if len(processed) >= limit:
                        break
                except:
                    continue
            
            if batch:
                await insert_domains(batch)

    except Exception as e:
        logger.error(f"Error querying Common Crawl: {e}")

async def ingest_search_engine_domains(tld: str, limit: int = 50):
    """
    Lightweight search-engine fallback (DuckDuckGo HTML) to grab fresh domains.
    """
    suffix = None
    if tld not in (None, "", "*", "all", "any"):
        suffix = tld.lstrip(".")
        query = f"site:{suffix} contact"
    else:
        query = "company site contact"
    logger.info(f"Search engine fallback for {tld or 'ANY'} (limit={limit})")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119 Safari/537.36"
    }

    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get("https://duckduckgo.com/html/", params={"q": query, "kl": "us-en"}, headers=headers)
            if resp.status_code >= 400:
                logger.warning(f"Search fallback returned HTTP {resp.status_code}")
                return

            soup = BeautifulSoup(resp.text, "lxml")
            batch = []
            seen = set()

            for anchor in soup.select("a.result__a"):
                href = anchor.get("href")
                if not href:
                    continue

                parsed = urlparse(href)
                if parsed.netloc == "duckduckgo.com" and parsed.path == "/l/":
                    params = parse_qs(parsed.query)
                    target = params.get("uddg", [None])[0]
                    if target:
                        href = unquote(target)
                        parsed = urlparse(href)

                domain = parsed.netloc.split(":")[0]
                if not domain or domain in seen or should_skip_domain(domain):
                    continue
                if suffix and not domain.endswith(f".{suffix}"):
                    continue

                seen.add(domain)
                batch.append((domain, "SEARCH"))

                if len(batch) >= 50 or len(seen) >= limit:
                    await insert_domains(batch)
                    batch = []

                if len(seen) >= limit:
                    break

            if batch:
                await insert_domains(batch)

    except Exception as e:
        logger.error(f"Search fallback error: {e}")

async def ingest_crtsh_domains(tld: str, limit: int = 100):
    """Query Certificate Transparency logs via crt.sh for domains."""
    if tld in (None, "", "*", "all", "any"):
        logger.info("Skipping crt.sh for ANY-TLD mode.")
        return

    suffix = tld.lstrip(".")
    logger.info(f"Querying crt.sh for TLD: {suffix}")

    try:
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            resp = await client.get(
                "https://crt.sh/",
                params={"q": f"%.{suffix}", "output": "json"},
                headers={"User-Agent": "Mozilla/5.0"}
            )
            if resp.status_code != 200:
                logger.warning(f"crt.sh returned HTTP {resp.status_code}")
                return

            try:
                certs = resp.json()
            except:
                logger.warning("crt.sh returned non-JSON response")
                return

            batch = []
            seen = set()

            for cert in certs:
                name = cert.get("common_name") or cert.get("name_value", "")
                for part in name.replace("\n", " ").split():
                    part = part.strip().lower().lstrip("*.")
                    if not part or part in seen or should_skip_domain(part):
                        continue
                    if not part.endswith(f".{suffix}"):
                        continue
                    seen.add(part)
                    batch.append((part, "CRTSH"))

                    if len(batch) >= 500:
                        await insert_domains(batch)
                        batch = []

                    if len(seen) >= limit:
                        break
                if len(seen) >= limit:
                    break

            if batch:
                await insert_domains(batch)
            logger.info(f"crt.sh: ingested {len(seen)} domains")

    except Exception as e:
        logger.error(f"crt.sh error: {e}")


async def ingest_wayback_domains(tld: str, limit: int = 100):
    """Query Wayback Machine CDX for historical domains."""
    if tld in (None, "", "*", "all", "any"):
        logger.info("Skipping Wayback for ANY-TLD mode.")
        return

    suffix = tld.lstrip(".")
    logger.info(f"Querying Wayback Machine for TLD: {suffix}")

    try:
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            resp = await client.get(
                "https://web.archive.org/cdx/search/cdx",
                params={
                    "url": f"*.{suffix}",
                    "matchType": "domain",
                    "output": "json",
                    "fl": "original",
                    "collapse": "urlkey",
                    "limit": limit * 5,
                    "filter": "statuscode:200"
                }
            )
            if resp.status_code != 200:
                logger.warning(f"Wayback returned HTTP {resp.status_code}")
                return

            try:
                rows = resp.json()
            except:
                logger.warning("Wayback returned non-JSON response")
                return

            batch = []
            seen = set()

            for row in rows[1:]:  # Skip header row
                if not row:
                    continue
                url = row[0] if isinstance(row, list) else row
                parsed = urlparse(url if url.startswith("http") else f"http://{url}")
                domain = parsed.netloc.split(":")[0].lower()
                if not domain or domain in seen or should_skip_domain(domain):
                    continue
                if not domain.endswith(f".{suffix}"):
                    continue

                seen.add(domain)
                batch.append((domain, "WAYBACK"))

                if len(batch) >= 500:
                    await insert_domains(batch)
                    batch = []

                if len(seen) >= limit:
                    break

            if batch:
                await insert_domains(batch)
            logger.info(f"Wayback: ingested {len(seen)} domains")

    except Exception as e:
        logger.error(f"Wayback error: {e}")


async def ingest_bing_search(tld: str, limit: int = 50):
    """Bing search fallback for domain discovery."""
    suffix = None
    if tld not in (None, "", "*", "all", "any"):
        suffix = tld.lstrip(".")
        query = f"site:{suffix} contact OR about"
    else:
        query = "company contact page"
    
    logger.info(f"Bing search fallback for {tld or 'ANY'} (limit={limit})")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5"
    }

    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(
                "https://www.bing.com/search",
                params={"q": query, "count": min(50, limit)},
                headers=headers
            )
            if resp.status_code >= 400:
                logger.warning(f"Bing returned HTTP {resp.status_code}")
                return

            soup = BeautifulSoup(resp.text, "lxml")
            batch = []
            seen = set()

            for anchor in soup.select("li.b_algo h2 a, .b_algo a"):
                href = anchor.get("href")
                if not href or not href.startswith("http"):
                    continue

                parsed = urlparse(href)
                domain = parsed.netloc.split(":")[0].lower()
                if not domain or domain in seen or should_skip_domain(domain):
                    continue
                if "bing.com" in domain or "microsoft.com" in domain:
                    continue
                if suffix and not domain.endswith(f".{suffix}"):
                    continue

                seen.add(domain)
                batch.append((domain, "BING"))

                if len(batch) >= 50:
                    await insert_domains(batch)
                    batch = []

                if len(seen) >= limit:
                    break

            if batch:
                await insert_domains(batch)
            logger.info(f"Bing: ingested {len(seen)} domains")

    except Exception as e:
        logger.error(f"Bing search error: {e}")


async def ingest_targeted_search(tld: str, limit: int = 100):
    """
    Targeted SMB discovery using specific legal page dorks.
    Finds companies that might not be in top lists but have legal requirements.
    Enhanced with diverse SMB-focused dorks (Issue #2 compliance).
    """
    suffix = tld.lstrip(".") if tld and tld not in (None, "", "*", "all", "any") else "de"
    
    # Comprehensive SMB dorks covering different business types
    dorks = [
        # Legal pages with company forms
        f'site:.{suffix} "Impressum" "GmbH" -site:facebook.com -site:youtube.com -site:linkedin.com',
        f'site:.{suffix} "Kontakt" "Geschäftsführer" -site:facebook.com',
        f'site:.{suffix} "Rechtliche Hinweise" "HRB" -site:amazon.{suffix}',
        
        # Small business / sole proprietors
        f'site:.{suffix} "Impressum" "Einzelunternehmen"',
        f'site:.{suffix} "Impressum" "Freiberufler"',
        f'site:.{suffix} "Impressum" "Selbstständig"',
        f'site:.{suffix} "Impressum" "Inhaber"',
        
        # Trades and crafts
        f'site:.{suffix} "Impressum" "Handwerksbetrieb"',
        f'site:.{suffix} "Impressum" "Meisterbetrieb"',
        f'site:.{suffix} "Handwerker" "Kontakt"',
        f'site:.{suffix} "Tischlerei" OR "Schreinerei" "Impressum"',
        f'site:.{suffix} "Elektroinstallation" "Impressum"',
        f'site:.{suffix} "Sanitär" "Heizung" "Impressum"',
        
        # Small retail / local shops
        f'site:.{suffix} "Impressum" "Laden" OR "Geschäft"',
        f'site:.{suffix} "Fachgeschäft" "Impressum"',
        
        # Small professional services
        f'site:.{suffix} "Impressum" "Rechtsanwalt" OR "Steuerberater"',
        f'site:.{suffix} "Impressum" "Architekturbüro" OR "Ingenieurbüro"',
        f'site:.{suffix} "Praxis" "Impressum" -klinik -krankenhaus',
        
        # Small UG companies (startups)
        f'site:.{suffix} "Impressum" "UG (haftungsbeschränkt)"',
        f'site:.{suffix} "Impressum" "UG" "Gründer"',
        
        # Regional / local businesses
        f'site:.{suffix} "Impressum" "regional" OR "lokal"',
        f'site:.{suffix} "Familienbetrieb" "Impressum"',
        
        # GbR partnerships
        f'site:.{suffix} "Impressum" "GbR"',
        f'site:.{suffix} "Gesellschaft bürgerlichen Rechts" "Kontakt"',
    ]
    
    logger.info(f"Running targeted SMB search for TLD: {suffix} (limit={limit})")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
    }

    total_found = 0
    consecutive_failures = 0
    MAX_CONSECUTIVE_FAILURES = 3  # Stop after 3 consecutive failures (rate limited)
    
    # Global Giant Blacklist (Skip these if found in search)
    GIANT_BLACKLIST = {
        "facebook.com", "linkedin.com", "youtube.com", "twitter.com", "instagram.com",
        "amazon.com", "amazon.de", "ebay.com", "ebay.de", "wikipedia.org",
        "yelp.com", "tripadvisor.com", "xing.com", "kununu.com"
    }

    # Only try first 5 dorks to avoid excessive timeouts
    dorks_to_try = dorks[:5]

    async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:  # Reduced timeout
        for dork in dorks_to_try:
            if total_found >= limit:
                break
            
            # Early exit if rate limited
            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                logger.warning(f"Search engine appears rate-limited after {consecutive_failures} failures. Skipping remaining dorks.")
                break
                
            try:
                # Using DuckDuckGo HTML (Lite) version to avoid JS requirements
                resp = await client.get(
                    "https://duckduckgo.com/html/", 
                    params={"q": dork, "kl": f"de-de" if suffix == "de" else "us-en"}, 
                    headers=headers
                )
                
                if resp.status_code >= 400:
                    logger.warning(f"Targeted search status {resp.status_code} for dork: {dork}")
                    continue

                soup = BeautifulSoup(resp.text, "lxml")
                batch = []
                
                for anchor in soup.select("a.result__a"):
                    href = anchor.get("href")
                    if not href:
                        continue

                    # Decode DDG redirect url
                    parsed = urlparse(href)
                    if parsed.netloc == "duckduckgo.com" and parsed.path == "/l/":
                        params = parse_qs(parsed.query)
                        target = params.get("uddg", [None])[0]
                        if target:
                            href = unquote(target)
                            parsed = urlparse(href)

                    domain = parsed.netloc.split(":")[0].lower()
                    if not domain or should_skip_domain(domain):
                        continue
                    
                    # Check giant blacklist
                    root_domain = ".".join(domain.split(".")[-2:])
                    if domain in GIANT_BLACKLIST or root_domain in GIANT_BLACKLIST:
                        continue
                        
                    if suffix and not domain.endswith(f".{suffix}"):
                        continue

                    batch.append((domain, "TARGETED_SEARCH"))
                    total_found += 1
                    
                if batch:
                    await insert_domains(batch)
                    logger.info(f"Found {len(batch)} domains with dork: {dork}")
                    consecutive_failures = 0  # Reset on success
                else:
                    consecutive_failures += 1
                    
                # Be nice to the search engine
                await asyncio.sleep(1)

            except Exception as e:
                consecutive_failures += 1
                logger.warning(f"Targeted search failed ({consecutive_failures}/{MAX_CONSECUTIVE_FAILURES}): {str(e)[:50]}")

async def run_discovery(tld: str, limit: int = 100, company_size: str = "all"):
    """
    Main discovery task - aggregates domains from multiple sources.
    Modes:
    - all: Balanced mix (default)
    - smb: Prioritize search engines and ignore Top 1M lists
    - enterprise: Prioritize Top 1M lists
    """
    logger.info(f"=== Starting discovery for TLD: {tld or 'ANY'}, limit: {limit}, size: {company_size} ===")

    if company_size == "smb":
        # SMB Mode: Focus on finding real small businesses, not top 1M domains
        logger.info("=== SMB Mode: Prioritizing small business discovery ===")
        
        # 1. Certificate Transparency - MOST RELIABLE for finding real SMB domains
        logger.info("Step 1/4: Certificate Transparency (crt.sh)...")
        await ingest_crtsh_domains(tld, limit)
        
        # 2. Common Crawl - RELIABLE archive of real websites
        logger.info("Step 2/4: Common Crawl archive...")
        await ingest_common_crawl_domains(tld, limit=min(limit, 100))
        
        # 3. Wayback Machine (historical domains often include SMBs)
        logger.info("Step 3/4: Wayback Machine...")
        await ingest_wayback_domains(tld, limit // 2)
        
        # 4. Targeted Search (may be rate-limited, try with fewer dorks)
        logger.info("Step 4/4: Targeted search (may be slow if rate-limited)...")
        await ingest_targeted_search(tld, limit // 2)
        
        # Skip Top 1M lists for SMB mode (they're dominated by enterprises)
        logger.info("Skipping Top 1M lists for SMB mode (enterprise-dominated)")
        
    elif company_size == "enterprise":
        # Prioritize lists
        await ingest_tranco_domains(tld, limit)
        await ingest_majestic_domains(tld, limit)
        await ingest_umbrella_domains(tld, limit)
        
    else:
        # Default Balanced Mode
        await ingest_targeted_search(tld, limit // 3)
        await ingest_tranco_domains(tld, limit)
        await ingest_majestic_domains(tld, limit)
        await ingest_common_crawl_domains(tld, limit // 2)
        await ingest_search_engine_domains(tld, 50)

    logger.info("=== Discovery complete ===")
