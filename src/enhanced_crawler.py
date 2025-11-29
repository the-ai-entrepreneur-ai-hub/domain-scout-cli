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
import httpx

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
from .whois_enricher import WhoisEnricher
from .utils import logger, load_settings

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"

class EnhancedCrawler:
    def __init__(self, concurrency: int = 5, use_playwright: bool = True, limit: int = 0,
                 use_llm: bool = False, llm_provider: str = "ollama/deepseek-r1:7b",
                 llm_api_base: str = "http://localhost:11434", ignore_robots: bool = False,
                 tld_filter: Optional[str] = None):
        if not CRAWL4AI_AVAILABLE:
            raise ImportError("Crawl4AI is not installed. Please run: pip install crawl4ai")

        self.concurrency = concurrency
        self.limit = limit  # 0 = unlimited
        self.use_llm = use_llm
        self.ignore_robots = ignore_robots
        self.tld_filter = tld_filter
        self.run_id = str(uuid.uuid4())  # Unique ID for this crawl session
        logger.info(f"Initialized EnhancedCrawler with Run ID: {self.run_id}")
        if limit > 0:
            logger.info(f"Crawl limit: {limit} domains")
        if ignore_robots:
            logger.warning("Ignoring robots.txt rules! This may lead to bans.")

        self.dns_checker = DNSChecker()
        self.extractor = EnhancedExtractor()
        self.legal_extractor = LegalExtractor()
        self.link_discoverer = LinkDiscoverer()
        self.whois_enricher = WhoisEnricher()
        self.settings = load_settings()
        
        # Initialize Session Stats (Not Global)
        self.session_stats = {
            'processed': 0,
            'success': 0,
            'failed': 0,
            'legal_found': 0
        }
        
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
        self.blacklist_path = Path("config/blacklist.txt")
        self.last_blacklist_mtime = 0
        self.blacklist = set()
        self._reload_blacklist()
                
        # Settings
        self.delay_min = float(self.settings.get("delay_min", 1))
        self.delay_max = float(self.settings.get("delay_max", 3))
        self.max_pages_per_domain = int(self.settings.get("max_pages_per_domain", 5))

    def _reload_blacklist(self):
        """Reload blacklist if file has changed."""
        if self.blacklist_path.exists():
            try:
                mtime = self.blacklist_path.stat().st_mtime
                if mtime > self.last_blacklist_mtime:
                    with open(self.blacklist_path, 'r') as f:
                        self.blacklist = {line.strip() for line in f if line.strip()}
                    self.last_blacklist_mtime = mtime
                    logger.info(f"Blacklist loaded/updated ({len(self.blacklist)} domains)")
            except Exception as e:
                logger.error(f"Error reloading blacklist: {e}")

    async def process_domain(self, domain_row, crawler: AsyncWebCrawler):
        """Process a single domain using the provided crawler instance."""
        domain_id, domain = domain_row['id'], domain_row['domain']
        self.session_stats['processed'] += 1
        
        # 0. Live Blacklist Reload
        self._reload_blacklist()
        
        # 1. Blacklist check
        if any(b in domain for b in self.blacklist):
            logger.info(f"Skipping blacklisted: {domain}")
            await update_domain_status(domain_id, "BLACKLISTED")
            self.session_stats['failed'] += 1
            return
            
        await update_domain_status(domain_id, "PROCESSING")
        
        # 2. DNS check (Soft Check)
        if not await self.dns_checker.check_domain(domain):
            logger.warning(f"DNS check failed for {domain}, attempting WHOIS fallback...")
            # Try WHOIS anyway
            await self._handle_failure_with_whois(domain, domain_id, "PARTIAL_DNS")
            return
            
        base_url = f"https://{domain}"
        try:
            # 3. Crawl Main Page with timeout
            logger.info(f"Crawling: {base_url}")
            result = None
            
            try:
                result = await asyncio.wait_for(
                    crawler.arun(url=base_url, bypass_cache=True, headers={'User-Agent': USER_AGENT}),
                    timeout=25.0
                )
            except asyncio.TimeoutError:
                logger.warning(f"Timeout on HTTPS for {domain}, trying HTTP...")
            
            if not result or not result.success:
                # Try HTTP
                base_url = f"http://{domain}"
                try:
                    result = await asyncio.wait_for(
                        crawler.arun(url=base_url, bypass_cache=True, headers={'User-Agent': USER_AGENT}),
                        timeout=25.0
                    )
                except asyncio.TimeoutError:
                    logger.warning(f"Timeout on HTTP for {domain}")
                    
            if not result or not result.success:
                # Try WWW subdomain (common fix if root domain fails)
                base_url = f"https://www.{domain}"
                logger.info(f"Retrying with www: {base_url}")
                try:
                    result = await asyncio.wait_for(
                        crawler.arun(url=base_url, bypass_cache=True, headers={'User-Agent': USER_AGENT}),
                        timeout=20.0
                    )
                except asyncio.TimeoutError:
                    pass
                
            if not result or not result.success:
                # Static fallback with httpx before giving up
                httpx_data = await self._httpx_fallback(base_url, domain)
                if httpx_data:
                    await self.save_results(domain, httpx_data, None)
                    await update_domain_status(domain_id, "COMPLETED")
                    self.session_stats['success'] += 1
                    logger.info(f"Completed via httpx fallback: {domain}")
                    return

                error_msg = result.error_message if result else "No response"
                # Check for HTTP error codes
                if "ERR_HTTP_RESPONSE_CODE_FAILURE" in str(error_msg):
                    logger.warning(f"HTTP failure for {domain}, attempting WHOIS fallback...")
                    await self._handle_failure_with_whois(domain, domain_id, "PARTIAL_HTTP")
                else:
                    logger.warning(f"Failed to fetch {domain}: {error_msg}, attempting WHOIS fallback...")
                    await self._handle_failure_with_whois(domain, domain_id, "PARTIAL_FETCH")
                return

            html = result.html
            if not html:
                # Try static fallback once
                httpx_data = await self._httpx_fallback(base_url, domain)
                if httpx_data:
                    await self.save_results(domain, httpx_data, None)
                    await update_domain_status(domain_id, "COMPLETED")
                    self.session_stats['success'] += 1
                    logger.info(f"Completed via httpx fallback (empty HTML): {domain}")
                    return

                logger.warning(f"Empty HTML response for {domain}, attempting WHOIS fallback...")
                await self._handle_failure_with_whois(domain, domain_id, "PARTIAL_FETCH")
                return
            
            # 4. Extract data
            data = self.extractor.extract(html, domain, base_url)
            
            if data.get('status') == 'PARKED':
                await update_domain_status(domain_id, "PARKED")
                self.session_stats['failed'] += 1 # Count parked as 'failed' for goal purposes
                return
            
            # 4.5 Discover critical pages (smart discovery + links found)
            legal_links = self.link_discoverer.extract_legal_links_smart(html, base_url)
            if legal_links:
                data['critical_pages'] = data.get('critical_pages', []) + legal_links
                
            # 5. Crawl Critical Pages
            enriched_data = await self.crawl_critical_pages(base_url, data, crawler)
            
            # Extract legal info if found
            legal_info = enriched_data.pop('legal_info', {})
            
            # 5.5 WHOIS Enrichment (The "Hybrid Truth" Strategy)
            # Always fetch WHOIS to separate Website Operator vs Domain Registrant
            whois_data = self.whois_enricher.get_whois_data(domain)
            
            # Merge WHOIS data into legal_info for storage
            legal_info.update(whois_data)
            
            # Smart Fill: If website data is missing, fallback to WHOIS
            if not legal_info.get('legal_name') and whois_data.get('registrant_name'):
                legal_info['legal_name'] = whois_data['registrant_name']
                legal_info['extraction_method'] = 'whois_fallback'
                
            if not legal_info.get('registered_street') and whois_data.get('registrant_address'):
                legal_info['registered_street'] = whois_data['registrant_address']
                legal_info['registered_city'] = whois_data.get('registrant_city', '')
                legal_info['registered_zip'] = whois_data.get('registrant_zip', '')
                legal_info['registered_country'] = whois_data.get('registrant_country', '')
            
            # Merge address components into string for compatibility
            if enriched_data.get('address'):
                addr_obj = enriched_data['address']
                if isinstance(addr_obj, dict):
                    parts = [p for p in [addr_obj.get('street'), addr_obj.get('zip'), addr_obj.get('city'), addr_obj.get('country')] if p]
                    enriched_data['address'] = ", ".join(parts)
            
            # 6. Save to database with RUN_ID
            await self.save_results(domain, enriched_data, legal_info)
            
            await update_domain_status(domain_id, "COMPLETED")
            self.session_stats['success'] += 1
            
            if legal_info and legal_info.get('status') == 'SUCCESS':
                self.session_stats['legal_found'] += 1
            
        except asyncio.TimeoutError:
             # Handle timeout gracefully: if we have partial data, save it!
            logger.warning(f"Timeout processing {domain} (partial data might be saved)")
            
            # Emergency WHOIS Fallback on Timeout
            # If we timed out, we likely didn't get to the normal save block.
            # So we try to fetch WHOIS now and save what we have.
            try:
                if 'enriched_data' not in locals(): enriched_data = data if 'data' in locals() else {}
                if 'legal_info' not in locals(): legal_info = {}
                
                whois_data = self.whois_enricher.get_whois_data(domain)
                legal_info.update(whois_data)
                
                if not legal_info.get('legal_name') and whois_data.get('registrant_name'):
                    legal_info['legal_name'] = whois_data['registrant_name']
                    legal_info['extraction_method'] = 'whois_fallback'
                
                await self.save_results(domain, enriched_data, legal_info)
                await update_domain_status(domain_id, "PARTIAL_TIMEOUT")
                self.session_stats['success'] += 1 # Count partials as success for now
            except Exception as e:
                logger.error(f"Failed to save partial results for {domain}: {e}")
                await update_domain_status(domain_id, "FAILED_TIMEOUT")
                self.session_stats['failed'] += 1
            
        except Exception as e:
            logger.error(f"Error processing {domain}: {e}")
            await update_domain_status(domain_id, "FAILED_UNKNOWN")
            self.session_stats['failed'] += 1

    async def _handle_failure_with_whois(self, domain: str, domain_id: int, status_code: str):
        """
        Fallback handler: Fetches WHOIS data when website crawl fails.
        Saves partial result and marks success if WHOIS data found.
        """
        try:
            whois_data = self.whois_enricher.get_whois_data(domain)
            
            # Prepare partial data structure
            legal_info = whois_data.copy()
            
            # Promote registrant name to legal name if missing
            if whois_data.get('registrant_name'):
                legal_info['legal_name'] = whois_data['registrant_name']
                legal_info['extraction_method'] = 'whois_fallback_only'
            
            # Basic enriched data wrapper
            enriched_data = {
                'domain': domain,
                'company_name': legal_info.get('legal_name', ''),
                'address': legal_info.get('registrant_address', '')
            }
            
            await self.save_results(domain, enriched_data, legal_info)
            await update_domain_status(domain_id, status_code)
            self.session_stats['success'] += 1
            logger.info(f"Saved WHOIS fallback for {domain} (Status: {status_code})")
            
        except Exception as e:
            logger.error(f"WHOIS fallback failed for {domain}: {e}")
            # If even WHOIS fails, then it's a true failure
            final_status = status_code.replace("PARTIAL", "FAILED")
            await update_domain_status(domain_id, final_status)
            self.session_stats['failed'] += 1

    async def _httpx_fallback(self, base_url: str, domain: str) -> Optional[Dict]:
        """
        Lightweight fallback when Playwright/Crawl4AI fails.
        Fetches a single page with httpx and runs the enhanced extractor.
        """
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True, verify=False) as client:
                resp = await client.get(base_url, headers={'User-Agent': USER_AGENT})
                if resp.status_code >= 400 or not resp.text:
                    return None
                html = resp.text
        except Exception as e:
            logger.debug(f"httpx fallback failed for {domain}: {e}")
            return None

        data = self.extractor.extract(html, domain, base_url)
        if data.get('status') != 'SUCCESS':
            return None

        # Try to find legal links even in fallback mode
        legal_links = self.link_discoverer.extract_legal_links_smart(html, base_url)
        if legal_links:
            data['critical_pages'] = data.get('critical_pages', []) + legal_links

        # Recalculate confidence in case extractor didn't set it
        data['confidence_score'] = self.extractor.calculate_confidence_score(data)
        return data

    async def crawl_critical_pages(self, base_url: str, initial_data: Dict, crawler: AsyncWebCrawler) -> Dict:
        """Crawl critical pages. Prioritizes discovered links, then falls back to TLD-specific guesses."""
        critical_pages = initial_data.get('critical_pages', [])
        
        # TLD-specific Fallbacks (Smart Discovery)
        # Only use these if we didn't find good links on the homepage
        tld = base_url.split('.')[-1].lower()
        if '/' in tld: tld = tld.split('/')[0] # Handle edge cases
        
        fallbacks = []
        if tld in ['de', 'ch', 'at']:
            fallbacks = ['/impressum', '/kontakt', '/datenschutz']
        elif tld in ['uk', 'com', 'org', 'net', 'io', 'ai']:
            fallbacks = ['/contact', '/about', '/legal', '/privacy', '/terms']
        elif tld in ['fr']:
            fallbacks = ['/mentions-legales', '/contact']
        elif tld in ['it']:
            fallbacks = ['/contatti', '/note-legali']
        elif tld in ['es']:
            fallbacks = ['/contacto', '/aviso-legal']
        else:
            # Generic fallback for others
            fallbacks = ['/contact', '/about', '/legal', '/impressum']

        # De-duplicate and filter
        pages_to_crawl = []
        seen = {base_url, base_url + '/'}
        
        # 1. Add discovered pages FIRST (Highest Priority)
        for url in critical_pages:
            if url not in seen:
                pages_to_crawl.append(url)
                seen.add(url)
                
        # 2. Add fallbacks ONLY if we have few discovered pages (or to be safe)
        # We limit the number of fallbacks to avoid 404 spam
        for path in fallbacks:
            url = urljoin(base_url, path)
            if url not in seen:
                pages_to_crawl.append(url)
                seen.add(url)

        # Limit total pages to crawl per domain
        pages_to_crawl = pages_to_crawl[:self.max_pages_per_domain]
        
        merged_data = initial_data.copy()
        
        for page_url in pages_to_crawl:
            await asyncio.sleep(random.uniform(self.delay_min, self.delay_max))
            
            # Crawl page with timeout
            try:
                res = await asyncio.wait_for(
                    crawler.arun(url=page_url, headers={'User-Agent': USER_AGENT}),
                    timeout=15.0
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
            
            # Use LLM for legal pages if enabled
            is_legal_url = any(kw in page_url.lower() for kw in ['impressum', 'legal', 'imprint'])
            if self.use_llm and self.llm_extractor and is_legal_url:
                logger.info(f"Using LLM extraction for: {page_url}")
                llm_data = await self.llm_extractor.extract(crawler, page_url)
                if llm_data:
                    # Merge LLM data with regex data (LLM takes priority)
                    legal_data = self.llm_extractor.merge_with_regex(llm_data, legal_data)
                    legal_data['extraction_method'] = 'LLM+Regex'
                    legal_data['status'] = 'SUCCESS'  # Mark as success since LLM found data
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
        async with aiosqlite.connect(DB_PATH, timeout=60.0) as db:
            # Save Enhanced Results
            emails_str = ','.join(data.get('emails', []))
            phones_str = ','.join(data.get('phones', []))
            social = data.get('social_profiles', {})
            
            # Safe Address String Conversion
            raw_address = data.get('address', '')
            address_str = ''
            if isinstance(raw_address, dict):
                parts = [p for p in [raw_address.get('street'), raw_address.get('zip'), raw_address.get('city'), raw_address.get('country')] if p]
                address_str = ", ".join(parts)
            elif isinstance(raw_address, str):
                address_str = raw_address
            
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
                address_str,
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
            if legal_info and (legal_info.get('status') == 'SUCCESS' or legal_info.get('extraction_method') == 'whois_fallback'):
                directors_json = json.dumps(legal_info.get('directors', []))
                auth_reps_json = json.dumps(legal_info.get('authorized_reps', []))
                
                # Bug Fix #1 & #4: Use consistent key mapping for CEO name
                ceo_name = legal_info.get('ceo_name') or legal_info.get('ceo', '')
                
                # Bug Fix #2: Fallback to enhanced data for phone/email if legal-specific ones missing
                legal_phone = legal_info.get('legal_phone', '')
                legal_email = legal_info.get('legal_email', '')
                primary_phone = legal_phone or (data.get('phones', [''])[0] if data.get('phones') else '')
                primary_email = legal_email or (data.get('emails', [''])[0] if data.get('emails') else '')
                
                # Map address fields to v4.0 schema (street_address, city, etc.)
                # Prioritize registered address -> postal address -> generic address
                street = legal_info.get('registered_street') or legal_info.get('postal_street') or data.get('address', '')
                if isinstance(street, dict): street = street.get('street', '') # Handle if dict slipped through
                
                city = legal_info.get('registered_city') or legal_info.get('postal_city') or (data.get('address', {}).get('city') if isinstance(data.get('address'), dict) else '')
                zip_code = legal_info.get('registered_zip') or legal_info.get('postal_zip') or (data.get('address', {}).get('zip') if isinstance(data.get('address'), dict) else '')
                country = legal_info.get('registered_country') or legal_info.get('postal_country') or (data.get('address', {}).get('country') if isinstance(data.get('address'), dict) else '')

                # Ensure registrant_address is a string (whois can return list)
                def sanitize_whois_field(val):
                    if isinstance(val, list):
                        return ", ".join([str(x) for x in val if x])
                    return val or ''

                reg_addr = sanitize_whois_field(legal_info.get('registrant_address', ''))
                reg_name = sanitize_whois_field(legal_info.get('registrant_name', ''))
                reg_city = sanitize_whois_field(legal_info.get('registrant_city', ''))
                reg_zip = sanitize_whois_field(legal_info.get('registrant_zip', ''))
                reg_country = sanitize_whois_field(legal_info.get('registrant_country', ''))
                reg_email = sanitize_whois_field(legal_info.get('registrant_email', ''))
                reg_phone = sanitize_whois_field(legal_info.get('registrant_phone', ''))

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
                     street_address, postal_code, city, country,
                     legal_email, legal_phone, fax_number,
                     dpo_name, dpo_email,
                     phone, email,
                     registrant_name, registrant_address, registrant_city, registrant_zip, registrant_country, registrant_email, registrant_phone,
                     legal_notice_url, extraction_confidence, run_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 
                            ?, ?, ?, ?,
                            ?, ?, ?, ?, ?, ?, ?,
                            ?, ?, ?, ?, ?, ?, ?,
                            ?, ?, ?)
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
                    street,
                    zip_code,
                    city,
                    country,
                    legal_email,
                    legal_phone,
                    legal_info.get('fax', ''),
                    legal_info.get('dpo_name', ''),
                    legal_info.get('dpo_email', ''),
                    primary_phone,
                    primary_email,
                    reg_name,
                    reg_addr,
                    reg_city,
                    reg_zip,
                    reg_country,
                    reg_email,
                    reg_phone,
                    legal_info.get('legal_notice_url', ''),
                    legal_info.get('confidence', 0),
                    self.run_id
                ))
                
            await db.commit()

    async def worker(self, queue):
        """Worker process with timeout protection."""
        # Longer timeout when LLM is enabled (LLM calls can take 30-90s)
        # Increased default timeout to 5 minutes to accommodate retries and critical page crawling
        domain_timeout = 600.0 if self.use_llm else 300.0
        timeout_label = "10min" if self.use_llm else "5min"
        
        # Initialize Crawler context per worker (efficient reuse)
        # Move AsyncWebCrawler inside the loop to recreate it on critical failure
        while True:
            try:
                # Re-initialize crawler if it crashed or was closed
                async with AsyncWebCrawler(verbose=False) as crawler:
                    while True:
                        domain_row = await queue.get()
                        try:
                            await asyncio.wait_for(
                                self.process_domain(domain_row, crawler),
                                timeout=domain_timeout
                            )
                        except asyncio.TimeoutError:
                            logger.error(f"Domain timeout ({timeout_label}): {domain_row['domain']}")
                            
                            # Emergency WHOIS Fallback on Timeout
                            try:
                                # We rely on process_domain to handle the WHOIS fallback internally now.
                                # This catch block is just a safety net for the hard worker timeout.
                                await update_domain_status(domain_row['id'], "FAILED_TIMEOUT")
                                self.session_stats['failed'] += 1
                            except Exception:
                                pass
                    
                        except Exception as e:
                            # Check for browser/context closed error
                            error_str = str(e)
                            if "Target page, context or browser has been closed" in error_str:
                                logger.error(f"Browser context crashed: {e}. Restarting crawler instance...")
                                queue.task_done() # Mark current task as done (failed)
                                self.session_stats['failed'] += 1
                                break # Break inner loop to restart crawler context
                            
                            logger.exception(f"Worker Error: {e}")
                            self.session_stats['failed'] += 1
                        finally:
                            queue.task_done()
            except Exception as e:
                logger.error(f"Critical Worker Restart: {e}")
                await asyncio.sleep(5) # Cool down before restarting worker loop

    async def run(self):
        logger.info(f"Starting Crawl Run {self.run_id} with {self.concurrency} workers.")
        logger.info(f"Press Ctrl+C or create STOP file to stop and export results.")
        
        # Get total pending count for progress tracking
        async with aiosqlite.connect(DB_PATH, timeout=60.0) as db:
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
                
                # Keep workers fed: Fetch at least 20 items per worker
                min_batch = self.concurrency * 20
                batch_size = min(min_batch, remaining) if self.limit > 0 else min_batch
                
                batch = await get_pending_domains(limit=batch_size, tld_filter=self.tld_filter)
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
            
            logger.info(f"")
            logger.info(f"=" * 60)
            logger.info(f"  CRAWL FINISHED")
            logger.info(f"=" * 60)
            logger.info(f"  Run ID:      {self.run_id}")
            logger.info(f"  Processed:   {self.session_stats['processed']}")
            logger.info(f"  Successful:  {self.session_stats['success']}")
            logger.info(f"  Legal Found: {self.session_stats['legal_found']}")
            logger.info(f"  Failed:      {self.session_stats['failed']}")
            logger.info(f"  Time:        {elapsed/60:.1f} minutes")
            logger.info(f"=" * 60)
            logger.info(f"")
            logger.info(f"  To export results, run:")
            logger.info(f"  python main.py export --legal-only --run-id {self.run_id} --include-incomplete")
            logger.info(f"")

    async def _progress_reporter(self):
        """Report progress every 30 seconds."""
        while True:
            await asyncio.sleep(30)
            await self._print_progress()
    
    async def _print_progress(self):
        """Print current progress stats."""
        # Show global stats from DB
        async with aiosqlite.connect(DB_PATH, timeout=60.0) as db:
            # Get current counts
            cursor = await db.execute("""
                SELECT status, COUNT(*) FROM queue 
                WHERE status IN ('COMPLETED', 'PENDING', 'PROCESSING', 
                                 'FAILED_DNS', 'FAILED_FETCH', 'FAILED_HTTP', 
                                 'FAILED_TIMEOUT', 'FAILED_UNKNOWN', 'PARKED', 'BLACKLISTED',
                                 'PARTIAL_TIMEOUT', 'PARTIAL_DNS', 'PARTIAL_HTTP', 'PARTIAL_FETCH')
                GROUP BY status
            """)
            counts = dict(await cursor.fetchall())
        
        # Calculate session rates
        elapsed = asyncio.get_event_loop().time() - self.stats['start_time']
        session_rate = (self.session_stats['processed']) / elapsed * 60 if elapsed > 0 else 0
        
        # Get pending count from DB (accurate)
        pending = counts.get('PENDING', 0)
        
        # Calculate total completed (Completed + Partial)
        total_success = (
            counts.get('COMPLETED', 0) + 
            counts.get('PARTIAL_TIMEOUT', 0) + 
            counts.get('PARTIAL_DNS', 0) + 
            counts.get('PARTIAL_HTTP', 0) +
            counts.get('PARTIAL_FETCH', 0)
        )
        
        logger.info(f"")
        logger.info(f"  [SESSION] Processed: {self.session_stats['processed']} | "
                   f"Success: {self.session_stats['success']} | "
                   f"Failed: {self.session_stats['failed']} | "
                   f"Legal Found: {self.session_stats['legal_found']} | "
                   f"Rate: {session_rate:.1f}/min")
        logger.info(f"  [GLOBAL]  Total Completed: {total_success} | "
                   f"Total Pending: {pending}")
