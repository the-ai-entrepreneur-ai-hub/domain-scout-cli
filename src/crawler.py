import asyncio
import httpx
import time
from pathlib import Path
from fake_useragent import UserAgent
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .database import get_pending_domains, update_domain_status, DB_PATH
from .dns_checker import DNSChecker
from .extractor import Extractor
from .utils import logger
from .models import CrawlResult
import aiosqlite

class Crawler:
    def __init__(self, concurrency: int = 10):
        self.concurrency = concurrency
        self.ua = UserAgent()
        self.dns_checker = DNSChecker()
        self.extractor = Extractor()
        
        # Load blacklist
        self.blacklist = set()
        blacklist_path = Path("config/blacklist.txt")
        if blacklist_path.exists():
            with open(blacklist_path, 'r') as f:
                self.blacklist = {line.strip() for line in f if line.strip()}
    
    def get_headers(self):
        return {
            "User-Agent": self.ua.random,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        }

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=10),
           retry=retry_if_exception_type((httpx.RequestError, httpx.TimeoutException)))
    async def fetch_page(self, client: httpx.AsyncClient, url: str) -> httpx.Response:
        return await client.get(url)

    async def process_domain(self, domain_row):
        domain_id, domain = domain_row['id'], domain_row['domain']
        
        # 0. Check Stop File
        if Path("STOP").exists():
            logger.warning("STOP file detected. Halting worker.")
            return False

        # 1. Blacklist Check
        if any(b in domain for b in self.blacklist):
            logger.info(f"Skipping blacklisted: {domain}")
            await update_domain_status(domain_id, "BLACKLISTED")
            return

        await update_domain_status(domain_id, "PROCESSING")
        
        # 2. DNS Check
        if not await self.dns_checker.check_domain(domain):
            logger.warning(f"DNS Failed: {domain}")
            await update_domain_status(domain_id, "FAILED_DNS")
            return

        url = f"https://{domain}"
        
        try:
            async with httpx.AsyncClient(timeout=15, http2=True, follow_redirects=True, verify=False) as client:
                # 3. Fetch
                try:
                    resp = await self.fetch_page(client, url)
                except Exception as e:
                    # Try http if https failed? For PoC, we assume https first.
                    # Actually, follow_redirects might handle it if we started with http, but we force https.
                    # Let's fallback to http if generic error.
                    try:
                        url_http = f"http://{domain}"
                        resp = await self.fetch_page(client, url_http)
                    except Exception as e2:
                        await update_domain_status(domain_id, "FAILED_CONNECTION")
                        return

                if resp.status_code >= 400:
                    await update_domain_status(domain_id, f"FAILED_HTTP_{resp.status_code}")
                    return

                # 4. Extract
                data = self.extractor.extract(resp.text, domain)
                
                if data.get("status") == "PARKED":
                    await update_domain_status(domain_id, "PARKED")
                    return
                
                if data.get("status") == "EXTRACTION_FAILED":
                    await update_domain_status(domain_id, "FAILED_EXTRACTION")
                    return

                # 5. Validate & Save
                try:
                    result = CrawlResult(
                        domain=domain,
                        company_name=data.get("company_name"),
                        description=data.get("description"),
                        email=data.get("email"),
                        phone=data.get("phone"),
                        address=data.get("address")
                    )
                except Exception as e:
                    logger.error(f"Validation Failed for {domain}: {e}")
                    await update_domain_status(domain_id, "FAILED_VALIDATION")
                    return
                
                async with aiosqlite.connect(DB_PATH) as db:
                    await db.execute("""
                        INSERT OR REPLACE INTO results 
                        (domain, company_name, description, email, phone, address) 
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        result.domain, result.company_name, result.description, 
                        result.email, result.phone, result.address
                    ))
                    await db.commit()
                
                await update_domain_status(domain_id, "COMPLETED")
                logger.info(f"Crawled: {domain} | {result.company_name or 'Unknown'}")
                
        except Exception as e:
            logger.error(f"Worker Error on {domain}: {e}")
            await update_domain_status(domain_id, "FAILED_UNKNOWN")

    async def worker(self, queue):
        while True:
            domain_row = await queue.get()
            try:
                await self.process_domain(domain_row)
            except Exception as e:
                logger.exception(f"Critical Worker Failure: {e}")
            finally:
                queue.task_done()

    async def run(self):
        logger.info(f"Starting Crawler with {self.concurrency} workers...")
        
        queue = asyncio.Queue()
        
        # Start workers
        workers = [asyncio.create_task(self.worker(queue)) for _ in range(self.concurrency)]
        
        while True:
            # Fetch batch from DB
            # We only fetch domains that are PENDING.
            # In a real distributed system, we would 'lock' them. 
            # Here, we rely on the fact that we are the only consumer.
            batch = await get_pending_domains(limit=100)
            
            if not batch:
                logger.info("No pending domains found. Sleeping...")
                # Check if we are done-done or just waiting for slow discovery?
                # For PoC, we just exit if empty.
                break
                
            for row in batch:
                await queue.put(row)
            
            # Wait for queue to drain before fetching next batch
            await queue.join()
            
        # Cancel workers
        for w in workers:
            w.cancel()
        
        logger.info("Crawler finished queue.")
