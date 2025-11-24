import asyncio
import aiodns
from .utils import logger

class DNSChecker:
    def __init__(self):
        self.resolver = aiodns.DNSResolver()

    async def check_domain(self, domain: str) -> bool:
        """
        Checks if a domain resolves to an IP.
        Returns True if resolves, False if NXDOMAIN/Timeout.
        """
        try:
            # Query A record
            await self.resolver.query(domain, 'A')
            return True
        except aiodns.error.DNSError as e:
            # Error 4 is Domain name not found
            # Error 1 is Format error
            # logger.debug(f"DNS Check failed for {domain}: {e.args[0]}")
            return False
        except Exception as e:
            logger.debug(f"DNS unexpected error for {domain}: {e}")
            return False
