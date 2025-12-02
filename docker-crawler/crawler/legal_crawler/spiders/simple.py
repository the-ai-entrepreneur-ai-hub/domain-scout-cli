import re
import scrapy
from urllib.parse import urljoin, urlparse
from legal_crawler.items import LegalNoticeItem


class SimpleSpider(scrapy.Spider):
    """Simple spider without Splash - uses standard HTTP requests"""
    
    name = 'simple'
    
    LEGAL_LINK_PATTERNS = [
        r'impressum', r'imprint', r'legal', r'rechtliche',
        r'kontakt', r'contact', r'about', r'uber-uns',
    ]
    
    custom_settings = {
        'CONCURRENT_REQUESTS': 8,
        'DOWNLOAD_DELAY': 0.5,
        'RETRY_TIMES': 2,
        'DOWNLOAD_TIMEOUT': 30,
        'DOWNLOADER_MIDDLEWARES': {
            'scrapy.downloadermiddlewares.httpcompression.HttpCompressionMiddleware': 810,
        },
        'SPIDER_MIDDLEWARES': {},
        'DUPEFILTER_CLASS': 'scrapy.dupefilters.RFPDupeFilter',
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
        for domain in self.domains_to_crawl:
            url = f'https://{domain}'
            yield scrapy.Request(
                url=url,
                callback=self.parse_homepage,
                meta={'domain': domain},
                errback=self.handle_error,
            )
    
    def handle_error(self, failure):
        domain = failure.request.meta.get('domain')
        url = f'http://{domain}'
        self.logger.info(f'HTTPS failed for {domain}, trying HTTP')
        yield scrapy.Request(
            url=url,
            callback=self.parse_homepage,
            meta={'domain': domain},
            errback=lambda f: self.logger.error(f'Failed: {domain}'),
        )
    
    def parse_homepage(self, response):
        domain = response.meta['domain']
        self.logger.info(f'Parsing homepage: {domain}')
        
        all_links = response.css('a::attr(href)').getall()
        legal_links = set()
        
        for link in all_links:
            if link and any(re.search(p, link.lower()) for p in self.LEGAL_LINK_PATTERNS):
                full_url = urljoin(response.url, link)
                if urlparse(full_url).netloc.replace('www.', '') == domain.replace('www.', ''):
                    legal_links.add(full_url)
        
        if not legal_links:
            base = response.url.rstrip('/')
            for path in ['/impressum', '/imprint', '/legal', '/kontakt']:
                legal_links.add(f'{base}{path}')
        
        self.logger.info(f'Found {len(legal_links)} legal pages for {domain}')
        
        for url in legal_links:
            yield scrapy.Request(
                url=url,
                callback=self.parse_legal_page,
                meta={'domain': domain},
                errback=lambda f: self.logger.warning(f'Legal page failed: {f.request.url}'),
            )
    
    def parse_legal_page(self, response):
        domain = response.meta['domain']
        page_text = response.text.lower()
        
        indicators = ['impressum', 'angaben gemäß', 'verantwortlich', 'geschäftsführer',
                      'handelsregister', 'hrb', 'hra', 'ust-idnr', 'rechtliche']
        
        if not any(ind in page_text for ind in indicators):
            return
        
        self.logger.info(f'Found legal page for {domain}: {response.url}')
        
        text = ' '.join(response.css('body *::text').getall())
        text = re.sub(r'\s+', ' ', text).strip()
        
        item = LegalNoticeItem()
        item['domain'] = domain
        item['url'] = response.url
        item['raw_html'] = response.text[:50000]
        item['extracted_text'] = text[:20000]
        
        yield item
