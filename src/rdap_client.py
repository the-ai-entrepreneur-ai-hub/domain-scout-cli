"""
RDAP Client for domain registration lookup.
RDAP (Registration Data Access Protocol) is the ICANN-mandated replacement for WHOIS.
Returns standardized JSON responses instead of unstructured text.
"""
import asyncio
import aiohttp
from typing import Dict, Optional, Any
from datetime import datetime
from .utils import logger

RDAP_BOOTSTRAP_URL = "https://rdap.org"
REQUEST_TIMEOUT = 10


class RDAPClient:
    """Async client for RDAP domain lookups."""
    
    def __init__(self, timeout: int = REQUEST_TIMEOUT):
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._cache: Dict[str, Dict] = {}
    
    async def lookup(self, domain: str) -> Dict[str, Any]:
        """
        Look up domain registration data via RDAP.
        
        Args:
            domain: Domain name (e.g., 'example.de')
            
        Returns:
            Dict with registrar, created, expires, registrant info
        """
        # Check cache first
        if domain in self._cache:
            return self._cache[domain]
        
        result = {
            'domain': domain,
            'source': 'rdap',
            'success': False,
        }
        
        try:
            url = f"{RDAP_BOOTSTRAP_URL}/domain/{domain}"
            
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        result = self._parse_rdap_response(data, domain)
                        result['success'] = True
                    elif resp.status == 404:
                        result['error'] = 'Domain not found in RDAP'
                    else:
                        result['error'] = f'RDAP returned status {resp.status}'
                        
        except asyncio.TimeoutError:
            result['error'] = 'RDAP request timed out'
        except aiohttp.ClientError as e:
            result['error'] = f'RDAP connection error: {str(e)}'
        except Exception as e:
            result['error'] = f'RDAP lookup failed: {str(e)}'
        
        # Cache the result
        self._cache[domain] = result
        return result
    
    def _parse_rdap_response(self, data: Dict, domain: str) -> Dict[str, Any]:
        """Parse RDAP JSON response into structured format."""
        result = {
            'domain': domain,
            'source': 'rdap',
            'registrar': '',
            'created': '',
            'expires': '',
            'updated': '',
            'status': [],
            'registrant_name': '',
            'registrant_org': '',
            'registrant_country': '',
        }
        
        # Extract registrar from entities
        for entity in data.get('entities', []):
            roles = entity.get('roles', [])
            
            if 'registrar' in roles:
                # Get registrar name from vcardArray
                vcard = entity.get('vcardArray', [])
                if len(vcard) > 1:
                    for item in vcard[1]:
                        if item[0] == 'fn':
                            result['registrar'] = item[3] if len(item) > 3 else ''
                            break
                
                # Fallback to handle field
                if not result['registrar']:
                    result['registrar'] = entity.get('handle', '')
            
            if 'registrant' in roles:
                vcard = entity.get('vcardArray', [])
                if len(vcard) > 1:
                    for item in vcard[1]:
                        if item[0] == 'fn':
                            result['registrant_name'] = item[3] if len(item) > 3 else ''
                        elif item[0] == 'org':
                            result['registrant_org'] = item[3] if len(item) > 3 else ''
                        elif item[0] == 'adr':
                            # Address is complex, extract country (last element)
                            if len(item) > 3 and isinstance(item[3], list):
                                result['registrant_country'] = item[3][-1] if item[3] else ''
        
        # Extract dates from events
        for event in data.get('events', []):
            action = event.get('eventAction', '')
            date = event.get('eventDate', '')
            
            if action == 'registration':
                result['created'] = self._format_date(date)
            elif action == 'expiration':
                result['expires'] = self._format_date(date)
            elif action == 'last changed':
                result['updated'] = self._format_date(date)
        
        # Extract status
        result['status'] = data.get('status', [])
        
        return result
    
    def _format_date(self, date_str: str) -> str:
        """Format RDAP date string to YYYY-MM-DD."""
        if not date_str:
            return ''
        try:
            # RDAP uses ISO 8601 format
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return dt.strftime('%Y-%m-%d')
        except (ValueError, AttributeError):
            return date_str[:10] if len(date_str) >= 10 else date_str
    
    def clear_cache(self):
        """Clear the lookup cache."""
        self._cache.clear()


async def lookup_domain(domain: str) -> Dict[str, Any]:
    """
    Convenience function for one-off domain lookups.
    
    Args:
        domain: Domain name to look up
        
    Returns:
        Dict with registration data
    """
    client = RDAPClient()
    return await client.lookup(domain)


# For testing
if __name__ == "__main__":
    async def test():
        client = RDAPClient()
        result = await client.lookup("google.com")
        print(f"Result: {result}")
    
    asyncio.run(test())
