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

def should_skip_domain(domain: str) -> bool:
    """
    Filters out noisy/non-HTML domains before queueing.
    Drops service subdomains (mail, api, cdn, dns, etc.).
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


async def run_discovery(tld: str, limit: int = 100):
    """Main discovery task - aggregates domains from multiple sources."""
    logger.info(f"=== Starting discovery for TLD: {tld or 'ANY'}, limit: {limit} ===")

    # Primary sources (bulk domain lists)
    await ingest_tranco_domains(tld, limit)
    await ingest_majestic_domains(tld, limit)
    await ingest_umbrella_domains(tld, limit)

    # Secondary sources (APIs)
    await ingest_common_crawl_domains(tld, limit // 2)
    await ingest_crtsh_domains(tld, limit // 2)
    await ingest_wayback_domains(tld, limit // 2)

    # Tertiary sources (search engines)
    search_limit = min(50, max(10, limit // 2))
    await ingest_search_engine_domains(tld, search_limit)
    await ingest_bing_search(tld, search_limit)

    logger.info("=== Discovery complete ===")
