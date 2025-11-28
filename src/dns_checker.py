import asyncio
import aiodns
from .utils import logger

class DNSChecker:
    def __init__(self):
        self.resolver = aiodns.DNSResolver()

    async def check_domain(self, domain: str) -> bool:
        """
        Checks if a domain (or www.domain) resolves to an IP.
        Returns True if resolves, False if NXDOMAIN/Timeout.
        """
        try:
            # Query A record for root domain
            await self.resolver.query(domain, 'A')
            return True
        except (aiodns.error.DNSError, Exception):
            # Fallback: Try www.domain
            # Many sites (especially universities/older sites) only have records for www
            try:
                await self.resolver.query(f"www.{domain}", 'A')
                return True
            except Exception:
                return False

