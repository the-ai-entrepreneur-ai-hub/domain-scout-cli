"""
Stealth Middleware - Anti-detection measures for web scraping
- User-Agent rotation
- Request header randomization
- Referer spoofing
- Cookie management
"""

import random
import logging
from typing import Optional
from scrapy import signals
from scrapy.http import Request, Response

logger = logging.getLogger(__name__)

# Real browser User-Agents (updated 2024)
USER_AGENTS = [
    # Chrome Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    # Chrome Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    # Firefox Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    # Firefox Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
    # Safari
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    # Edge
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
]

# Accept-Language headers for German/Swiss sites
ACCEPT_LANGUAGES = [
    "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
    "de-CH,de;q=0.9,en;q=0.8",
    "de,en-US;q=0.9,en;q=0.8",
    "de-AT,de;q=0.9,en;q=0.8",
]

# Common referers
REFERERS = [
    "https://www.google.de/",
    "https://www.google.ch/",
    "https://www.google.com/",
    "https://www.bing.com/",
    "https://duckduckgo.com/",
    None,  # Sometimes no referer is more natural
]


class StealthMiddleware:
    """Middleware for anti-detection measures"""
    
    def __init__(self, settings):
        self.enabled = settings.getbool('STEALTH_ENABLED', True)
        self.rotate_user_agent = settings.getbool('ROTATE_USER_AGENT', True)
        self.randomize_delay = settings.getbool('RANDOMIZE_DELAY', True)
        
    @classmethod
    def from_crawler(cls, crawler):
        middleware = cls(crawler.settings)
        return middleware
    
    def process_request(self, request: Request, spider) -> Optional[Request]:
        if not self.enabled:
            return None
        
        # Rotate User-Agent
        if self.rotate_user_agent:
            request.headers['User-Agent'] = random.choice(USER_AGENTS)
        
        # Set Accept-Language for German sites
        request.headers['Accept-Language'] = random.choice(ACCEPT_LANGUAGES)
        
        # Set Accept headers
        request.headers['Accept'] = 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8'
        request.headers['Accept-Encoding'] = 'gzip, deflate, br'
        
        # Random referer
        referer = random.choice(REFERERS)
        if referer:
            request.headers['Referer'] = referer
        
        # Additional stealth headers
        request.headers['Sec-Ch-Ua'] = '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"'
        request.headers['Sec-Ch-Ua-Mobile'] = '?0'
        request.headers['Sec-Ch-Ua-Platform'] = '"Windows"'
        request.headers['Sec-Fetch-Dest'] = 'document'
        request.headers['Sec-Fetch-Mode'] = 'navigate'
        request.headers['Sec-Fetch-Site'] = 'none' if not referer else 'cross-site'
        request.headers['Sec-Fetch-User'] = '?1'
        request.headers['Upgrade-Insecure-Requests'] = '1'
        
        # Don't track
        request.headers['DNT'] = '1'
        
        return None
    
    def process_response(self, request: Request, response: Response, spider) -> Response:
        # Log blocked responses
        if response.status in [403, 429, 503]:
            logger.warning(f"Possible blocking detected: {response.status} for {request.url}")
        return response


class ProxyRotationMiddleware:
    """Middleware for rotating free proxies"""
    
    def __init__(self, settings):
        self.enabled = settings.getbool('PROXY_ENABLED', False)
        self._proxy_manager = None
    
    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler.settings)
    
    @property
    def proxy_manager(self):
        if self._proxy_manager is None:
            from legal_crawler.proxy_manager import get_proxy_manager
            self._proxy_manager = get_proxy_manager()
        return self._proxy_manager
    
    def process_request(self, request: Request, spider) -> Optional[Request]:
        if not self.enabled:
            return None
        
        # Skip if proxy already set
        if 'proxy' in request.meta:
            return None
        
        # Get a random proxy
        proxy = self.proxy_manager.get_proxy()
        if proxy:
            request.meta['proxy'] = proxy
            logger.debug(f"Using proxy: {proxy}")
        
        return None
    
    def process_exception(self, request: Request, exception, spider):
        # Blacklist failed proxy
        proxy = request.meta.get('proxy')
        if proxy:
            self.proxy_manager.blacklist_proxy(proxy)
            logger.info(f"Blacklisted failed proxy: {proxy}")


class RandomDelayMiddleware:
    """Add random delay between requests"""
    
    def __init__(self, settings):
        self.min_delay = settings.getfloat('RANDOM_DELAY_MIN', 0.5)
        self.max_delay = settings.getfloat('RANDOM_DELAY_MAX', 3.0)
    
    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler.settings)
    
    def process_request(self, request: Request, spider) -> Optional[Request]:
        import time
        delay = random.uniform(self.min_delay, self.max_delay)
        time.sleep(delay)
        return None
