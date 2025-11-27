"""
Enhanced crawler using Crawl4AI for high-fidelity extraction and Playwright management.
"""
import asyncio
import uuid
import json
import random
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

# Try importing Crawl4AI
try:
    from crawl4ai import AsyncWebCrawler
    CRAWL4AI_AVAILABLE = True
except ImportError:
    CRAWL4AI_AVAILABLE = False

import aiosqlite
from tenacity import retry, stop_after_attempt, wait_exponential

from .database import get_pending_domains, update_domain_status, DB_PATH
from .dns_checker import DNSChecker
from .enhanced_extractor import EnhancedExtractor
from .legal_extractor import LegalExtractor
from .link_discoverer import LinkDiscoverer
from .llm_extractor import LLMExtractor
from .utils import logger, load_settings

class EnhancedCrawler:
    def __init__(self, concurrency: int = 5, use_playwright: bool = True, limit: int = 0,
                 use_llm: bool = False, llm_provider: str = "ollama/deepseek-r1:7b",
                 llm_api_base: str = "http://localhost:11434"):
        if not CRAWL4AI_AVAILABLE:
            raise ImportError("Crawl4AI is not installed. Please run: pip install crawl4ai")

        self.concurrency = concurrency
        self.limit = limit  # 0 = unlimited
        self.use_llm = use_llm
        self.run_id = str(uuid.uuid4())  # Unique ID for this crawl session
        logger.info(f"Initialized EnhancedCrawler with Run ID: {self.run_id}")
        if limit > 0:
            logger.info(f"Crawl limit: {limit} domains")

        self.dns_checker = DNSChecker()
        self.extractor = EnhancedExtractor()
        self.legal_extractor = LegalExtractor()
        self.link_discoverer = LinkDiscoverer()
        self.settings = load_settings()
        
        # Initialize LLM extractor if enabled
        self.llm_extractor = None
        if use_llm:
            self.llm_extractor = LLMExtractor(provider=llm_provider, api_base=llm_api_base)
            if self.llm_extractor.is_available():
                logger.info(f"LLM extraction ENABLED: {llm_provider}")
            else:
                logger.warning("LLM extraction requested but not available. Falling back to regex.")
                self.use_llm = False
        
        # Load blacklist
        self.blacklist = set()
        blacklist_path = Path("config/blacklist.txt")
        if blacklist_path.exists():
            with open(blacklist_path, 'r') as f:
                self.blacklist = {line.strip() for line in f if line.strip()}
                
        # Settings
        self.delay_min = float(self.settings.get("delay_min", 1))
        self.delay_max = float(self.settings.get("delay_max", 3))
        self.max_pages_per_domain = int(self.settings.get("max_pages_per_domain", 5))

    async def process_domain(self, domain_row, crawler: AsyncWebCrawler):
        """Process a single domain using the provided crawler instance."""
        domain_id, domain = domain_row['id'], domain_row['domain']
        
        # 1. Blacklist check
        if any(b in domain for b in self.blacklist):
            logger.info(f"Skipping blacklisted: {domain}")
            await update_domain_status(domain_id, "BLACKLISTED")
            return
            
        await update_domain_status(domain_id, "PROCESSING")
        
        # 2. DNS check
        if not await self.dns_checker.check_domain(domain):
            logger.warning(f"DNS failed: {domain}")
            await update_domain_status(domain_id, "FAILED_DNS")
            return
            
        base_url = f"https://{domain}"
        try:
            # 3. Crawl Main Page with timeout
            logger.info(f"Crawling: {base_url}")
            try:
                result = await asyncio.wait_for(
                    crawler.arun(url=base_url, bypass_cache=True),
                    timeout=30.0
                )
            except asyncio.TimeoutError:
                logger.warning(f"Timeout on HTTPS for {domain}, trying HTTP...")
                result = None
            
            if not result or not result.success:
                # Try HTTP
                base_url = f"http://{domain}"
                try:
                    result = await asyncio.wait_for(
                        crawler.arun(url=base_url, bypass_cache=True),
                        timeout=30.0
                    )
                except asyncio.TimeoutError:
                    logger.warning(f"Timeout on HTTP for {domain}")
                    await update_domain_status(domain_id, "FAILED_TIMEOUT")
                    return
                
            if not result or not result.success:
                error_msg = result.error_message if result else "No response"
                # Check for HTTP error codes
                if "ERR_HTTP_RESPONSE_CODE_FAILURE" in str(error_msg):
                    await update_domain_status(domain_id, "FAILED_HTTP")
                else:
                    logger.warning(f"Failed to fetch {domain}: {error_msg}")
                    await update_domain_status(domain_id, "FAILED_FETCH")
                return

            html = result.html
            if not html:
                logger.warning(f"Empty HTML response for {domain}")
                await update_domain_status(domain_id, "FAILED_FETCH")
                return
            
            # 4. Extract data
            data = self.extractor.extract(html, domain, base_url)
            
            if data.get('status') == 'PARKED':
                await update_domain_status(domain_id, "PARKED")
                return
            
            # 4.5 Discover critical pages (smart discovery + links found)
            legal_links = self.link_discoverer.extract_legal_links_smart(html, base_url)
            if legal_links:
                data['critical_pages'] = data.get('critical_pages', []) + legal_links
                
            # 5. Crawl Critical Pages
            enriched_data = await self.crawl_critical_pages(base_url, data, crawler)
            
            # Extract legal info if found
            legal_info = enriched_data.pop('legal_info', None)
            
            # Merge address components into string for compatibility
            if enriched_data.get('address'):
                addr_obj = enriched_data['address']
                if isinstance(addr_obj, dict):
                    parts = [p for p in [addr_obj.get('street'), addr_obj.get('zip'), addr_obj.get('city'), addr_obj.get('country')] if p]
                    enriched_data['address'] = ", ".join(parts)
            
            # 6. Save to database with RUN_ID
            await self.save_results(domain, enriched_data, legal_info)
            
            await update_domain_status(domain_id, "COMPLETED")
            
        except Exception as e:
            logger.error(f"Error processing {domain}: {e}")
            await update_domain_status(domain_id, "FAILED_UNKNOWN")

    async def crawl_critical_pages(self, base_url: str, initial_data: Dict, crawler: AsyncWebCrawler) -> Dict:
        """Crawl critical pages like /contact, /about, /impressum."""
        critical_pages = initial_data.get('critical_pages', [])
        
        # Ensure legal paths are prioritized
        legal_paths = ['/impressum', '/imprint', '/legal-notice', '/legal', 
                      '/contact', '/about', '/company']
        
        # De-duplicate and filter
        pages_to_crawl = []
        seen = {base_url}
        
        # Add discovered pages first
        for url in critical_pages:
            if url not in seen:
                pages_to_crawl.append(url)
                seen.add(url)
                
        # Add defaults if missing
        for path in legal_paths:
            url = urljoin(base_url, path)
            if url not in seen:
                # Only add if it wasn't discovered but might exist
                # We'll try a few speculative ones
                pages_to_crawl.append(url)
                seen.add(url)

        # Limit
        pages_to_crawl = pages_to_crawl[:self.max_pages_per_domain]
        
        merged_data = initial_data.copy()
        
        for page_url in pages_to_crawl:
            await asyncio.sleep(random.uniform(self.delay_min, self.delay_max))
            
            # Crawl page with timeout
            try:
                res = await asyncio.wait_for(
                    crawler.arun(url=page_url),
                    timeout=20.0
                )
            except asyncio.TimeoutError:
                logger.warning(f"Timeout crawling {page_url}")
                continue
            except Exception as e:
                logger.debug(f"Error crawling {page_url}: {e}")
                continue
                
            if not res or not res.success:
                continue
                
            html = res.html
            if not html:
                continue
            
            # Extract general data
            page_data = self.extractor.extract(html, initial_data['domain'], page_url)
            
            # Extract legal data (specialized)
            legal_data = self.legal_extractor.extract(html, page_url)
            
            # Use LLM for legal pages if enabled and this looks like a legal page
            if self.use_llm and self.llm_extractor and legal_data.get('status') == 'SUCCESS':
                is_legal_url = any(kw in page_url.lower() for kw in ['impressum', 'legal', 'imprint'])
                if is_legal_url:
                    logger.info(f"Using LLM extraction for: {page_url}")
                    llm_data = await self.llm_extractor.extract(crawler, page_url)
                    if llm_data:
                        # Merge LLM data with regex data (LLM takes priority)
                        legal_data = self.llm_extractor.merge_with_regex(llm_data, legal_data)
                        legal_data['extraction_method'] = 'LLM+Regex'
                        logger.info(f"LLM extraction successful for {page_url}")
            
            if legal_data.get('status') == 'SUCCESS':
                # We found specific legal info!
                merged_data['legal_info'] = legal_data
                
            # Merge generic data
            for key, value in page_data.items():
                if key in ['critical_pages', 'status', 'domain']: continue
                if not value: continue
                
                if isinstance(value, list):
                    current = merged_data.get(key, [])
                    merged_data[key] = list(set(current + value))
                elif isinstance(value, dict):
                    current = merged_data.get(key, {})
                    current.update(value)
                    merged_data[key] = current
                elif not merged_data.get(key):
                    merged_data[key] = value

        # Recalculate confidence
        merged_data['confidence_score'] = self.extractor.calculate_confidence_score(merged_data)
        return merged_data

    async def save_results(self, domain, data, legal_info):
        """Save results to DB with run_id."""
        async with aiosqlite.connect(DB_PATH) as db:
            # Save Enhanced Results
            emails_str = ','.join(data.get('emails', []))
            phones_str = ','.join(data.get('phones', []))
            social = data.get('social_profiles', {})
            
            # We use INSERT OR REPLACE. run_id will be updated to current run.
            # This effectively "tags" the domain as being part of this run.
            await db.execute("""
                INSERT OR REPLACE INTO results_enhanced 
                (domain, company_name, description, emails, phones, address, 
                 industry, vat_id, social_linkedin, social_facebook, social_twitter,
                 language, confidence_score, run_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                domain,
                data.get('company_name', ''),
                data.get('description', ''),
                emails_str,
                phones_str,
                data.get('address', ''),
                data.get('industry', ''),
                data.get('vat_id', ''),
                social.get('linkedin', ''),
                social.get('facebook', ''),
                social.get('twitter', ''),
                data.get('language', ''),
                data.get('confidence_score', 0),
                self.run_id
            ))
            
            # Save Legal Entities if available
            if legal_info and legal_info.get('status') == 'SUCCESS':
                directors_json = json.dumps(legal_info.get('directors', []))
                auth_reps_json = json.dumps(legal_info.get('authorized_reps', []))
                
                # Bug Fix #1 & #4: Use consistent key mapping for CEO name
                ceo_name = legal_info.get('ceo_name') or legal_info.get('ceo', '')
                
                # Bug Fix #2: Fallback to enhanced data for phone/email if legal-specific ones missing
                legal_phone = legal_info.get('legal_phone', '')
                legal_email = legal_info.get('legal_email', '')
                primary_phone = legal_phone or (data.get('phones', [''])[0] if data.get('phones') else '')
                primary_email = legal_email or (data.get('emails', [''])[0] if data.get('emails') else '')
                
                await db.execute("""
                    INSERT OR REPLACE INTO legal_entities
                    (domain, legal_name, legal_form, trading_name,
                     register_type, register_court, registration_number,
                     vat_id, tax_id, siret, siren,
                     ceo_name, directors, authorized_reps,
                     registered_street, registered_zip, registered_city, 
                     registered_state, registered_country,
                     postal_street, postal_zip, postal_city,
                     postal_state, postal_country,
                     legal_email, legal_phone, fax_number,
                     dpo_name, dpo_email,
                     phone, email,
                     legal_notice_url, extraction_confidence, run_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    domain,
                    legal_info.get('legal_name', ''),
                    legal_info.get('legal_form', ''),
                    legal_info.get('trading_name', ''),
                    legal_info.get('register_type', ''),
                    legal_info.get('register_court', ''),
                    legal_info.get('registration_number', ''),
                    legal_info.get('vat_id', ''),
                    legal_info.get('tax_id', ''),
                    legal_info.get('siret', ''),
                    legal_info.get('siren', ''),
                    ceo_name,
                    directors_json,
                    auth_reps_json,
                    legal_info.get('registered_street', ''),
                    legal_info.get('registered_zip', ''),
                    legal_info.get('registered_city', ''),
                    legal_info.get('registered_state', ''),
                    legal_info.get('registered_country', ''),
                    legal_info.get('postal_street', ''),
                    legal_info.get('postal_zip', ''),
                    legal_info.get('postal_city', ''),
                    legal_info.get('postal_state', ''),
                    legal_info.get('postal_country', ''),
                    legal_email,
                    legal_phone,
                    legal_info.get('fax', ''),
                    legal_info.get('dpo_name', ''),
                    legal_info.get('dpo_email', ''),
                    primary_phone,
                    primary_email,
                    legal_info.get('legal_notice_url', ''),
                    legal_info.get('confidence', 0),
                    self.run_id
                ))
                
            await db.commit()

    async def worker(self, queue):
        """Worker process with timeout protection."""
        # Initialize Crawler context per worker (efficient reuse)
        async with AsyncWebCrawler(verbose=False) as crawler:
            while True:
                domain_row = await queue.get()
                try:
                    # Overall timeout per domain: 2 minutes max
                    await asyncio.wait_for(
                        self.process_domain(domain_row, crawler),
                        timeout=120.0
                    )
                except asyncio.TimeoutError:
                    logger.error(f"Domain timeout (2min): {domain_row['domain']}")
                    await update_domain_status(domain_row['id'], "FAILED_TIMEOUT")
                except Exception as e:
                    logger.exception(f"Worker Error: {e}")
                finally:
                    queue.task_done()

    async def run(self):
        logger.info(f"Starting Crawl Run {self.run_id} with {self.concurrency} workers.")
        logger.info(f"Press Ctrl+C or create STOP file to stop and export results.")
        
        # Get total pending count for progress tracking
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM queue WHERE status = 'PENDING'")
            total_pending = (await cursor.fetchone())[0]
        
        # Apply limit if set
        target_count = self.limit if self.limit > 0 else total_pending
        target_count = min(target_count, total_pending)
        
        self.stats = {
            'total': target_count,
            'completed': 0,
            'failed': 0,
            'processed': 0,
            'start_time': asyncio.get_event_loop().time()
        }
        
        logger.info(f"")
        logger.info(f"=" * 60)
        if self.limit > 0:
            logger.info(f"  CRAWL TARGET: {target_count} domains (limit set)")
        else:
            logger.info(f"  CRAWL TARGET: {target_count} domains (all pending)")
        logger.info(f"=" * 60)
        
        queue = asyncio.Queue()
        workers = [asyncio.create_task(self.worker(queue)) for _ in range(self.concurrency)]
        
        # Start progress reporter
        progress_task = asyncio.create_task(self._progress_reporter())
        
        domains_queued = 0
        try:
            while True:
                if Path("STOP").exists():
                    logger.info("STOP file detected. Finishing current batch...")
                    break
                
                # Check if we've reached the limit
                if self.limit > 0 and domains_queued >= self.limit:
                    logger.info(f"Reached limit of {self.limit} domains. Finishing...")
                    break
                
                # Calculate how many more to fetch
                remaining = (self.limit - domains_queued) if self.limit > 0 else 50
                batch_size = min(50, remaining) if self.limit > 0 else 50
                
                batch = await get_pending_domains(limit=batch_size)
                if not batch:
                    break
                
                for row in batch:
                    await queue.put(row)
                    domains_queued += 1
                
                await queue.join()
        except KeyboardInterrupt:
            logger.info("Ctrl+C pressed. Stopping gracefully...")
        finally:
            progress_task.cancel()
            for w in workers: w.cancel()
            
            # Final stats
            elapsed = asyncio.get_event_loop().time() - self.stats['start_time']
            total_processed = self.stats['completed'] + self.stats['failed']
            
            logger.info(f"")
            logger.info(f"=" * 60)
            logger.info(f"  CRAWL FINISHED")
            logger.info(f"=" * 60)
            logger.info(f"  Run ID:    {self.run_id}")
            logger.info(f"  Completed: {self.stats['completed']}")
            logger.info(f"  Failed:    {self.stats['failed']}")
            logger.info(f"  Time:      {elapsed/60:.1f} minutes")
            logger.info(f"=" * 60)
            logger.info(f"")
            logger.info(f"  To export results, run:")
            logger.info(f"  python main.py export --legal-only")
            logger.info(f"")

    async def _progress_reporter(self):
        """Report progress every 30 seconds."""
        while True:
            await asyncio.sleep(30)
            await self._print_progress()
    
    async def _print_progress(self):
        """Print current progress stats."""
        async with aiosqlite.connect(DB_PATH) as db:
            # Get current counts
            cursor = await db.execute("""
                SELECT status, COUNT(*) FROM queue 
                WHERE status IN ('COMPLETED', 'PENDING', 'PROCESSING', 
                                 'FAILED_DNS', 'FAILED_FETCH', 'FAILED_HTTP', 
                                 'FAILED_TIMEOUT', 'FAILED_UNKNOWN', 'PARKED', 'BLACKLISTED')
                GROUP BY status
            """)
            counts = dict(await cursor.fetchall())
        
        completed = counts.get('COMPLETED', 0)
        pending = counts.get('PENDING', 0)
        processing = counts.get('PROCESSING', 0)
        failed = sum(v for k, v in counts.items() if k.startswith('FAILED_') or k in ('PARKED', 'BLACKLISTED'))
        
        total = completed + pending + processing + failed
        if total == 0:
            return
            
        pct = (completed + failed) / total * 100
        elapsed = asyncio.get_event_loop().time() - self.stats['start_time']
        rate = (completed + failed) / elapsed * 60 if elapsed > 0 else 0
        
        # Update stats
        self.stats['completed'] = completed
        self.stats['failed'] = failed
        
        logger.info(f"")
        logger.info(f"  PROGRESS: {completed + failed}/{total} ({pct:.1f}%) | "
                   f"OK: {completed} | FAIL: {failed} | "
                   f"Rate: {rate:.1f}/min | "
                   f"Pending: {pending}")
