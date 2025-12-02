"""
Free Proxy Manager - Fetches and manages free proxies from GitHub lists
No paid services - 100% free proxies
"""

import os
import time
import random
import logging
import requests
from typing import List, Optional
from threading import Lock

logger = logging.getLogger(__name__)


class FreeProxyManager:
    """Manages free proxy rotation from public GitHub lists"""
    
    # Free proxy sources (GitHub raw URLs)
    PROXY_SOURCES = [
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
        "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
        "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
        "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",
    ]
    
    def __init__(self, cache_file: str = "/app/proxies/proxies.txt", refresh_interval: int = 3600):
        self.cache_file = cache_file
        self.refresh_interval = refresh_interval
        self.proxies: List[str] = []
        self.blacklist: set = set()
        self.last_refresh = 0
        self._lock = Lock()
        
        # Ensure cache directory exists
        os.makedirs(os.path.dirname(cache_file), exist_ok=True)
        
        # Load initial proxies
        self._load_or_refresh()
    
    def _load_or_refresh(self):
        """Load proxies from cache or refresh from sources"""
        if os.path.exists(self.cache_file):
            cache_age = time.time() - os.path.getmtime(self.cache_file)
            if cache_age < self.refresh_interval:
                self._load_from_cache()
                return
        
        self.refresh_proxies()
    
    def _load_from_cache(self):
        """Load proxies from cache file"""
        try:
            with open(self.cache_file, 'r') as f:
                self.proxies = [line.strip() for line in f if line.strip() and ':' in line]
            logger.info(f"Loaded {len(self.proxies)} proxies from cache")
        except Exception as e:
            logger.warning(f"Failed to load proxy cache: {e}")
            self.refresh_proxies()
    
    def refresh_proxies(self):
        """Fetch fresh proxies from all sources"""
        with self._lock:
            all_proxies = set()
            
            for source_url in self.PROXY_SOURCES:
                try:
                    response = requests.get(source_url, timeout=10)
                    if response.status_code == 200:
                        lines = response.text.strip().split('\n')
                        for line in lines:
                            proxy = line.strip()
                            if proxy and ':' in proxy:
                                # Normalize format
                                if not proxy.startswith('http'):
                                    proxy = f"http://{proxy}"
                                all_proxies.add(proxy)
                        logger.info(f"Fetched {len(lines)} proxies from {source_url}")
                except Exception as e:
                    logger.warning(f"Failed to fetch from {source_url}: {e}")
            
            self.proxies = list(all_proxies - self.blacklist)
            random.shuffle(self.proxies)
            self.last_refresh = time.time()
            
            # Save to cache
            try:
                with open(self.cache_file, 'w') as f:
                    f.write('\n'.join(self.proxies))
            except Exception as e:
                logger.warning(f"Failed to save proxy cache: {e}")
            
            logger.info(f"Total proxies available: {len(self.proxies)}")
    
    def get_proxy(self) -> Optional[str]:
        """Get a random working proxy"""
        if not self.proxies:
            self.refresh_proxies()
        
        if not self.proxies:
            return None
        
        # Check if refresh needed
        if time.time() - self.last_refresh > self.refresh_interval:
            self.refresh_proxies()
        
        return random.choice(self.proxies) if self.proxies else None
    
    def get_proxies(self, count: int = 10) -> List[str]:
        """Get multiple random proxies"""
        if not self.proxies:
            self.refresh_proxies()
        
        count = min(count, len(self.proxies))
        return random.sample(self.proxies, count) if self.proxies else []
    
    def blacklist_proxy(self, proxy: str):
        """Mark a proxy as dead/blocked"""
        with self._lock:
            self.blacklist.add(proxy)
            if proxy in self.proxies:
                self.proxies.remove(proxy)
            logger.debug(f"Blacklisted proxy: {proxy}")
    
    def validate_proxy(self, proxy: str, test_url: str = "https://httpbin.org/ip", timeout: int = 5) -> bool:
        """Test if a proxy is working"""
        try:
            response = requests.get(
                test_url,
                proxies={"http": proxy, "https": proxy},
                timeout=timeout
            )
            return response.status_code == 200
        except:
            return False
    
    def get_validated_proxy(self, max_attempts: int = 5) -> Optional[str]:
        """Get a validated working proxy"""
        for _ in range(max_attempts):
            proxy = self.get_proxy()
            if proxy and self.validate_proxy(proxy):
                return proxy
            elif proxy:
                self.blacklist_proxy(proxy)
        return None
    
    @property
    def count(self) -> int:
        return len(self.proxies)


# Singleton instance
_proxy_manager = None

def get_proxy_manager() -> FreeProxyManager:
    global _proxy_manager
    if _proxy_manager is None:
        _proxy_manager = FreeProxyManager()
    return _proxy_manager
