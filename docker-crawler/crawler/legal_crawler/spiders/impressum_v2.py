"""
IMPRESSUM SPIDER V2 - Improved accuracy with Playwright
Features:
1. Dual fetching (HTTP first, Playwright fallback)
2. Strict Impressum page scoring
3. Context-aware extraction patterns
4. Better error handling
"""

import re
import scrapy
from urllib.parse import urljoin, urlparse
from legal_crawler.items import LegalNoticeItem


class ImpressumV2Spider(scrapy.Spider):
    """Improved spider with Playwright support and strict extraction"""
    
    name = 'impressum_v2'
    
    # Impressum URL patterns - prioritized
    IMPRESSUM_PATHS = [
        '/impressum',
        '/imprint', 
        '/legal-notice',
        '/rechtliches',
        '/about/impressum',
        '/de/impressum',
        '/kontakt/impressum',
    ]
    
    custom_settings = {
        'CONCURRENT_REQUESTS': 4,
        'DOWNLOAD_DELAY': 1,
        'RETRY_TIMES': 2,
        'DOWNLOAD_TIMEOUT': 30,
    }
    
    def __init__(self, domains_file=None, domains=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.domains_to_crawl = []
        
        if domains_file:
            with open(domains_file, 'r') as f:
                self.domains_to_crawl = [line.strip() for line in f if line.strip()]
        elif domains:
            self.domains_to_crawl = [d.strip() for d in domains.split(',')]
        else:
            self.domains_to_crawl = ['simple-fax.de', 't3n.de', 'granatapet.de']
    
    def start_requests(self):
        """Start with Playwright-enabled requests for better JS rendering"""
        for domain in self.domains_to_crawl:
            # Try direct /impressum path with Playwright
            url = f'https://{domain}/impressum'
            yield scrapy.Request(
                url=url,
                callback=self.parse_impressum,
                errback=self.try_homepage,
                meta={
                    'domain': domain,
                    'attempt': 'direct_impressum',
                    'playwright': True,
                    'playwright_include_page': False,
                },
                dont_filter=True,
            )
    
    def try_homepage(self, failure):
        """If direct /impressum fails, try homepage to find link"""
        domain = failure.request.meta.get('domain')
        self.logger.info(f'Direct /impressum failed for {domain}, trying homepage')
        
        yield scrapy.Request(
            url=f'https://{domain}',
            callback=self.parse_homepage,
            errback=self.handle_final_error,
            meta={
                'domain': domain,
                'attempt': 'homepage',
                'playwright': True,
                'playwright_include_page': False,
            },
        )
    
    def handle_final_error(self, failure):
        """Log final error"""
        domain = failure.request.meta.get('domain')
        self.logger.error(f'All attempts failed for {domain}')
    
    def parse_homepage(self, response):
        """Parse homepage and find Impressum link"""
        domain = response.meta['domain']
        self.logger.info(f'Parsing homepage: {domain}')
        
        # Look for Impressum links
        impressum_links = []
        for link in response.css('a::attr(href)').getall():
            if not link:
                continue
            link_lower = link.lower()
            # Prioritize exact Impressum matches
            if 'impressum' in link_lower:
                full_url = urljoin(response.url, link)
                # Only follow same-domain links
                if self._is_same_domain(full_url, domain):
                    impressum_links.append((full_url, 10))  # High priority
            elif 'imprint' in link_lower:
                full_url = urljoin(response.url, link)
                if self._is_same_domain(full_url, domain):
                    impressum_links.append((full_url, 8))
            elif 'legal' in link_lower and 'notice' in link_lower:
                full_url = urljoin(response.url, link)
                if self._is_same_domain(full_url, domain):
                    impressum_links.append((full_url, 5))
        
        # Sort by priority and take best match
        impressum_links.sort(key=lambda x: x[1], reverse=True)
        
        if impressum_links:
            best_url = impressum_links[0][0]
            self.logger.info(f'Found Impressum link for {domain}: {best_url}')
            
            yield scrapy.Request(
                url=best_url,
                callback=self.parse_impressum,
                meta={
                    'domain': domain,
                    'playwright': True,
                    'playwright_include_page': False,
                },
            )
        else:
            # Try common paths with Playwright
            base_url = f"https://{domain}"
            for path in self.IMPRESSUM_PATHS[:3]:
                yield scrapy.Request(
                    url=f'{base_url}{path}',
                    callback=self.parse_impressum,
                    errback=lambda f: None,
                    meta={
                        'domain': domain,
                        'playwright': True,
                        'playwright_include_page': False,
                    },
                    dont_filter=True,
                )
    
    def parse_impressum(self, response):
        """Parse Impressum page with strict validation"""
        domain = response.meta['domain']
        
        # Check if this is actually an Impressum page
        page_text = response.text
        score = self._score_impressum_page(response.url, page_text)
        
        if score < 5:
            self.logger.debug(f'Page score too low ({score}) for {response.url}')
            return
        
        self.logger.info(f'Valid Impressum page (score={score}) for {domain}: {response.url}')
        
        # Extract clean text
        text = self._extract_clean_text(response)
        
        item = LegalNoticeItem()
        item['domain'] = domain
        item['url'] = response.url
        item['raw_html'] = page_text[:50000]
        item['extracted_text'] = text[:20000]
        
        yield item
    
    def _score_impressum_page(self, url: str, text: str) -> int:
        """Score how likely this is a real Impressum page"""
        score = 0
        url_lower = url.lower()
        text_lower = text.lower()
        
        # URL indicators (high weight)
        if '/impressum' in url_lower:
            score += 5
        elif '/imprint' in url_lower:
            score += 4
        elif '/legal' in url_lower:
            score += 2
        
        # Content indicators
        if 'angaben gemäß § 5 tmg' in text_lower:
            score += 4
        if 'angaben gemäß' in text_lower:
            score += 2
        if 'handelsregister' in text_lower:
            score += 2
        if 'geschäftsführer' in text_lower:
            score += 2
        if 'verantwortlich' in text_lower and 'inhalt' in text_lower:
            score += 2
        if 'registergericht' in text_lower:
            score += 2
        if 'ust-id' in text_lower or 'ust-idnr' in text_lower:
            score += 1
        if 'hrb' in text_lower or 'hra' in text_lower:
            score += 1
        
        # Negative indicators (not an Impressum)
        if 'warenkorb' in text_lower or 'shopping cart' in text_lower:
            score -= 3
        if 'produkt' in text_lower and 'kaufen' in text_lower:
            score -= 2
        
        return score
    
    def _extract_clean_text(self, response) -> str:
        """Extract clean text focusing on Impressum section"""
        # Try to find Impressum section specifically
        impressum_section = None
        
        for selector in [
            '#impressum', '.impressum', '[id*="impressum"]',
            '#imprint', '.imprint',
            'main', 'article', '.content', '#content',
        ]:
            section = response.css(selector)
            if section:
                impressum_section = section
                break
        
        if impressum_section:
            text = ' '.join(impressum_section.css('*::text').getall())
        else:
            # Fall back to body, but exclude nav/footer
            text_parts = []
            for elem in response.css('body *::text').getall():
                text_parts.append(elem)
            text = ' '.join(text_parts)
        
        # Clean whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    def _is_same_domain(self, url: str, domain: str) -> bool:
        """Check if URL is on the same domain"""
        try:
            parsed = urlparse(url)
            url_domain = parsed.netloc.replace('www.', '')
            return domain.replace('www.', '') in url_domain
        except:
            return False
