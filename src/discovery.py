import httpx
import pandas as pd
import zipfile
import io
import asyncio
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote
from bs4 import BeautifulSoup
from .utils import logger
from .database import insert_domains

TRANCO_URL = "https://tranco-list.eu/top-1m.csv.zip"
DATA_DIR = Path("data")
TRANCO_FILE = DATA_DIR / "top-1m.csv"

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
                        if domain and domain not in processed:
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
                if not domain or domain in seen:
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

async def run_discovery(tld: str, limit: int = 100):
    """Main discovery task."""
    # 1. Tranco (always)
    await ingest_tranco_domains(tld, limit)
    
    # 2. Common Crawl (skip for ANY to avoid unbounded results)
    await ingest_common_crawl_domains(tld, limit // 2) # Fetch 50% limit from CC

    # 3. Search engine fallback (top ~50)
    await ingest_search_engine_domains(tld, min(50, max(10, limit // 2)))
