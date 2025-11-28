import asyncio
import httpx
from pathlib import Path
from random import uniform
from urllib.robotparser import RobotFileParser
from typing import Optional, Dict
from fake_useragent import UserAgent
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .database import get_pending_domains, update_domain_status, DB_PATH
from .dns_checker import DNSChecker
from .extractor import Extractor
from .utils import logger, load_settings
from .models import CrawlResult
import aiosqlite

class Crawler:
    def __init__(self, concurrency: int = 10, ignore_robots: bool = False):
        self.concurrency = concurrency
        self.ua = UserAgent()
        self.ignore_robots = ignore_robots
        self.dns_checker = DNSChecker()
        self.extractor = Extractor()
        self.settings = load_settings()
        
        # Load blacklist
        self.blacklist = set()
        blacklist_path = Path("config/blacklist.txt")
        if blacklist_path.exists():
            with open(blacklist_path, 'r') as f:
                self.blacklist = {line.strip() for line in f if line.strip()}

        # Politeness and HTTP controls
        self.delay_min = float(self.settings.get("delay_min", 1))
        self.delay_max = float(self.settings.get("delay_max", 3))
        self.request_timeout = float(self.settings.get("request_timeout", 15))
        self.max_redirects = int(self.settings.get("max_redirects", 5))
        self.respect_robots = bool(self.settings.get("respect_robots", True))
        self.robots_cache: Dict[str, RobotFileParser] = {}
    
    def get_headers(self, user_agent: Optional[str] = None):
        ua_string = user_agent or self.ua.random
        return {
            "User-Agent": ua_string,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        }

    async def fetch_robots(self, client: httpx.AsyncClient, domain: str, headers: dict) -> RobotFileParser:
        """
        Fetch and parse robots.txt for a domain. Cache result to avoid duplicate hits.
        """
        if domain in self.robots_cache:
            return self.robots_cache[domain]

        rp = RobotFileParser()
        for scheme in ("https", "http"):
            robots_url = f"{scheme}://{domain}/robots.txt"
            try:
                resp = await client.get(robots_url, headers=headers, timeout=self.request_timeout)
            except Exception:
                continue

            if resp.status_code in (401, 403):
                rp.parse(["User-agent: *", "Disallow: /"])
                break

            if resp.status_code >= 400:
                rp.parse([])  # Treat missing robots as allow-all
                break

            rp.parse(resp.text.splitlines())
            break

        self.robots_cache[domain] = rp
        return rp

    async def robots_allows(self, client: httpx.AsyncClient, domain: str, headers: dict, path: str = "/") -> bool:
        if self.ignore_robots:
            return True
        if not self.respect_robots:
            return True
        try:
            rp = await self.fetch_robots(client, domain, headers)
            return rp.can_fetch(headers.get("User-Agent", "*"), path)
        except Exception as exc:
            logger.warning(f"Robots check failed for {domain}: {exc}")
            return False

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=10),
           retry=retry_if_exception_type((httpx.RequestError, httpx.TimeoutException)))
    async def fetch_page(self, client: httpx.AsyncClient, url: str, headers: dict) -> httpx.Response:
        return await client.get(url, headers=headers, timeout=self.request_timeout)

    async def process_domain(self, domain_row):
        domain_id, domain = domain_row['id'], domain_row['domain']

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
        user_agent = self.ua.random
        headers = self.get_headers(user_agent)
        
        try:
            async with httpx.AsyncClient(timeout=self.request_timeout, http2=True, follow_redirects=True, verify=False, max_redirects=self.max_redirects) as client:
                # Robots.txt check
                if not await self.robots_allows(client, domain, headers, "/"):
                    logger.info(f"Blocked by robots.txt: {domain}")
                    await update_domain_status(domain_id, "BLOCKED_ROBOTS")
                    return

                # Politeness delay
                await asyncio.sleep(uniform(self.delay_min, self.delay_max))

                # 3. Fetch
                try:
                    resp = await self.fetch_page(client, url, headers)
                except Exception as e:
                    # Try http if https failed? For PoC, we assume https first.
                    # Actually, follow_redirects might handle it if we started with http, but we force https.
                    # Let's fallback to http if generic error.
                    try:
                        url_http = f"http://{domain}"
                        resp = await self.fetch_page(client, url_http, headers)
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
            if Path("STOP").exists():
                logger.warning("STOP file detected. Halting before fetching new batch.")
                break

            # Fetch batch from DB
            # We only fetch domains that are PENDING.
            # In a real distributed system, we would 'lock' them. 
            # Here, we rely on the fact that we are the only consumer.
            batch = await get_pending_domains(limit=100)
            
            if not batch:
                logger.info("No pending domains found. Exiting crawl loop.")
                break
                
            for row in batch:
                await queue.put(row)
            
            # Wait for queue to drain before fetching next batch
            await queue.join()

            if Path("STOP").exists():
                logger.warning("STOP file detected. Stopping after current batch.")
                break
            
        # Cancel workers
        for w in workers:
            w.cancel()
        
        logger.info("Crawler finished queue.")
