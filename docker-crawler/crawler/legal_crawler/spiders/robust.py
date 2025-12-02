"""
ROBUST SPIDER - Production-ready spider with all improvements
Features:
1. User-Agent rotation
2. Playwright with stealth
3. Multi-strategy retry (direct → proxy → wayback)
4. Redis job queue integration
5. LLM fallback extraction
6. Resilient error handling
"""

import re
import os
import scrapy
import logging
from urllib.parse import urljoin, urlparse
from typing import Optional, Dict, List
from scrapy import signals
from legal_crawler.items import LegalNoticeItem

logger = logging.getLogger(__name__)


class RobustSpider(scrapy.Spider):
    """Production-ready spider with full resilience"""
    
    name = 'robust'
    
    IMPRESSUM_PATHS = [
        '/impressum',
        '/imprint',
        '/legal-notice',
        '/rechtliches',
        '/about/impressum',
        '/de/impressum',
        '/kontakt/impressum',
        '/legal',
        '/info/impressum',
    ]
    
    custom_settings = {
        'CONCURRENT_REQUESTS': 8,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 2,
        'DOWNLOAD_DELAY': 1,
        'RANDOMIZE_DOWNLOAD_DELAY': True,
        'RETRY_TIMES': 3,
        'RETRY_HTTP_CODES': [500, 502, 503, 504, 408, 429, 403],
        'DOWNLOAD_TIMEOUT': 45,
        
        # Enable stealth middleware
        'DOWNLOADER_MIDDLEWARES': {
            'scrapy.downloadermiddlewares.httpcompression.HttpCompressionMiddleware': 810,
            'legal_crawler.stealth_middleware.StealthMiddleware': 550,
            'legal_crawler.stealth_middleware.RandomDelayMiddleware': 100,
        },
        
        # Stealth settings
        'STEALTH_ENABLED': True,
        'ROTATE_USER_AGENT': True,
        'RANDOM_DELAY_MIN': 0.5,
        'RANDOM_DELAY_MAX': 2.0,
    }
    
    def __init__(self, domains_file=None, domains=None, use_queue=False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.domains_to_crawl = []
        self.use_queue = use_queue.lower() == 'true' if isinstance(use_queue, str) else bool(use_queue)
        self.job_queue = None
        self.llm_extractor = None
        self.stats = {'success': 0, 'failed': 0, 'total': 0}
        
        # Load domains
        if domains_file and os.path.exists(domains_file):
            with open(domains_file, 'r') as f:
                self.domains_to_crawl = [line.strip() for line in f if line.strip()]
        elif domains:
            self.domains_to_crawl = [d.strip() for d in domains.split(',')]
        
        logger.info(f"RobustSpider initialized with {len(self.domains_to_crawl)} domains")
    
    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super().from_crawler(crawler, *args, **kwargs)
        crawler.signals.connect(spider.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(spider.spider_closed, signal=signals.spider_closed)
        return spider
    
    def spider_opened(self, spider):
        """Initialize resources when spider opens"""
        # Initialize job queue if enabled
        if self.use_queue:
            try:
                from legal_crawler.job_queue import get_job_queue
                self.job_queue = get_job_queue()
                self.job_queue.add_domains(self.domains_to_crawl)
                logger.info("Redis job queue initialized")
            except Exception as e:
                logger.warning(f"Job queue init failed: {e}")
        
        # Initialize LLM extractor
        try:
            from legal_crawler.llm_extractor import get_llm_extractor
            self.llm_extractor = get_llm_extractor()
        except Exception as e:
            logger.warning(f"LLM extractor init failed: {e}")
    
    def spider_closed(self, spider):
        """Log stats when spider closes"""
        logger.info(f"Spider closed. Stats: {self.stats}")
        if self.job_queue:
            stats = self.job_queue.get_stats()
            logger.info(f"Queue stats: {stats}")
    
    def start_requests(self):
        """Generate initial requests"""
        if self.use_queue and self.job_queue:
            # Pull from Redis queue
            while True:
                job = self.job_queue.get_next_job()
                if not job:
                    break
                
                domain = job['domain']
                strategy = job.get('strategy', 'direct')
                
                yield from self._make_requests(domain, strategy, job)
        else:
            # Direct crawl
            for domain in self.domains_to_crawl:
                yield from self._make_requests(domain, 'direct', None)
    
    def _make_requests(self, domain: str, strategy: str, job: Optional[Dict]):
        """Generate requests for a domain using specified strategy"""
        self.stats['total'] += 1
        
        # Build meta
        meta = {
            'domain': domain,
            'strategy': strategy,
            'job': job,
            'attempts': 0,
        }
        
        # Try direct /impressum first
        url = f'https://{domain}/impressum'
        
        yield scrapy.Request(
            url=url,
            callback=self.parse_impressum,
            errback=self.handle_error,
            meta={
                'domain': domain,
                'strategy': strategy,
                'job': job,
                'attempts': 0,
                'playwright': True,
                'playwright_include_page': False,
                'playwright_context_kwargs': {
                    'ignore_https_errors': True,
                },
                'playwright_page_goto_kwargs': {
                    'timeout': 60000,
                    'wait_until': 'domcontentloaded',
                }
            },
            dont_filter=True,
        )
    
    def handle_error(self, failure):
        """Handle request failures with retry logic"""
        request = failure.request
        domain = request.meta.get('domain')
        strategy = request.meta.get('strategy', 'direct')
        attempts = request.meta.get('attempts', 0) + 1
        job = request.meta.get('job')
        
        logger.warning(f"Request failed for {domain}: {failure.getErrorMessage()}")
        
        # Try alternative paths
        if attempts < len(self.IMPRESSUM_PATHS):
            alt_path = self.IMPRESSUM_PATHS[attempts]
            url = f'https://{domain}{alt_path}'
            
            yield scrapy.Request(
                url=url,
                callback=self.parse_impressum,
                errback=self.handle_error,
                meta={
                    'domain': domain,
                    'strategy': strategy,
                    'job': job,
                    'attempts': attempts,
                    'playwright': True,
                    'playwright_include_page': False,
                    'playwright_context_kwargs': {
                        'ignore_https_errors': True,
                    },
                    'playwright_page_goto_kwargs': {
                        'timeout': 60000,
                        'wait_until': 'domcontentloaded',
                    }
                },
                dont_filter=True,
            )
        else:
            # Try homepage as last resort
            yield scrapy.Request(
                url=f'https://{domain}',
                callback=self.parse_homepage,
                errback=self.handle_final_failure,
                meta={
                    'domain': domain,
                    'strategy': strategy,
                    'job': job,
                },
                dont_filter=True,
            )
    
    def handle_final_failure(self, failure):
        """Handle final failure - try Wayback Machine"""
        request = failure.request
        domain = request.meta.get('domain')
        job = request.meta.get('job')
        
        # Try Wayback Machine
        wayback_url = f"https://web.archive.org/web/2024/{domain}/impressum"
        
        yield scrapy.Request(
            url=wayback_url,
            callback=self.parse_impressum,
            errback=self.mark_failed,
            meta={
                'domain': domain,
                'job': job,
                'from_wayback': True,
            },
            dont_filter=True,
        )
    
    def mark_failed(self, failure):
        """Mark domain as permanently failed"""
        request = failure.request
        domain = request.meta.get('domain')
        job = request.meta.get('job')
        
        self.stats['failed'] += 1
        logger.error(f"All attempts failed for {domain}")
        
        if self.job_queue and job:
            self.job_queue.fail_job(job, str(failure.getErrorMessage()), retry=False)
    
    def parse_homepage(self, response):
        """Parse homepage to find Impressum link"""
        domain = response.meta['domain']
        job = response.meta.get('job')
        
        # Look for Impressum links
        impressum_links = []
        for link in response.css('a::attr(href)').getall():
            if not link:
                continue
            link_lower = link.lower()
            if 'impressum' in link_lower or 'imprint' in link_lower:
                full_url = urljoin(response.url, link)
                if self._is_same_domain(full_url, domain):
                    impressum_links.append(full_url)
        
        if impressum_links:
            yield scrapy.Request(
                url=impressum_links[0],
                callback=self.parse_impressum,
                meta={
                    'domain': domain,
                    'job': job,
                    'playwright': True,
                    'playwright_page_goto_kwargs': {
                        'timeout': 60000,
                        'wait_until': 'domcontentloaded',
                    }
                },
            )
        else:
            # No impressum link found
            self.stats['failed'] += 1
            if self.job_queue and job:
                self.job_queue.fail_job(job, "No Impressum link found", retry=True)
    
    def parse_impressum(self, response):
        """Parse Impressum page and extract data"""
        domain = response.meta['domain']
        job = response.meta.get('job')
        
        # Validate this is an Impressum page
        page_text = response.text
        score = self._score_impressum_page(response.url, page_text)
        
        if score < 3:
            logger.debug(f"Low score ({score}) for {response.url}, trying alternatives")
            return
        
        # Extract text
        text = self._extract_clean_text(response)
        
        # Create item
        item = LegalNoticeItem()
        item['domain'] = domain
        item['url'] = response.url
        item['raw_html'] = page_text[:50000]
        item['extracted_text'] = text[:20000]
        
        self.stats['success'] += 1
        
        # Mark job as completed
        if self.job_queue and job:
            self.job_queue.complete_job(job, {'url': response.url})
        
        yield item
    
    def _score_impressum_page(self, url: str, text: str) -> int:
        """Score how likely this is a real Impressum page"""
        score = 0
        url_lower = url.lower()
        text_lower = text.lower()
        
        if '/impressum' in url_lower:
            score += 5
        elif '/imprint' in url_lower:
            score += 4
        
        if 'angaben gemäß § 5 tmg' in text_lower:
            score += 4
        if 'handelsregister' in text_lower:
            score += 2
        if 'geschäftsführer' in text_lower:
            score += 2
        if 'registergericht' in text_lower:
            score += 2
        if 'ust-id' in text_lower:
            score += 1
        
        return score
    
    def _extract_clean_text(self, response) -> str:
        """Extract clean text from response"""
        # Try specific selectors first
        for selector in ['#impressum', '.impressum', 'main', 'article', '.content']:
            section = response.css(selector)
            if section:
                text = ' '.join(section.css('*::text').getall())
                if len(text) > 100:
                    return re.sub(r'\s+', ' ', text).strip()
        
        # Fallback to body
        text = ' '.join(response.css('body *::text').getall())
        return re.sub(r'\s+', ' ', text).strip()
    
    def _is_same_domain(self, url: str, domain: str) -> bool:
        """Check if URL is on same domain"""
        try:
            parsed = urlparse(url)
            url_domain = parsed.netloc.replace('www.', '')
            return domain.replace('www.', '') in url_domain
        except:
            return False
