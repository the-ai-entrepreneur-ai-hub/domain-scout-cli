"""
WHOIS Enrichment Module (v2.0 - Aggressive Multi-Source)
Uses asyncwhois for RDAP + WHOIS with authoritative server lookups.
Implements multi-source verification for maximum data accuracy.
"""
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime

try:
    import asyncwhois
    ASYNCWHOIS_AVAILABLE = True
except ImportError:
    ASYNCWHOIS_AVAILABLE = False

from .utils import logger


class WhoisEnricher:
    """
    Multi-source WHOIS/RDAP enricher with confidence scoring.
    Priority: RDAP (structured JSON) > WHOIS authoritative > WHOIS TLD registry
    """
    
    # TLD-specific timeout configurations (strict registries)
    TLD_TIMEOUTS = {
        'de': 20,   # DENIC is strict
        'at': 20,   # nic.at rate limits
        'ch': 20,   # SWITCH is strict
        'uk': 15,   # Nominet
        'com': 10,  # VeriSign (fast)
        'net': 10,
        'org': 10,
    }
    
    def __init__(self, use_rdap: bool = True, timeout: int = 15):
        self.use_rdap = use_rdap
        self.default_timeout = timeout
        self._cache: Dict[str, Dict] = {}
        self._cache_ttl: Dict[str, datetime] = {}
        self._cache_duration = 3600  # 1 hour cache
        
        if ASYNCWHOIS_AVAILABLE:
            self._domain_client = asyncwhois.DomainClient(
                find_authoritative_server=True,
                ignore_not_found=True,
                timeout=timeout
            )
            logger.info("WhoisEnricher initialized with asyncwhois (RDAP + WHOIS)")
        else:
            self._domain_client = None
            logger.warning("asyncwhois not available, WHOIS enrichment disabled")
    
    def _get_tld_timeout(self, domain: str) -> int:
        """Get TLD-specific timeout for rate-limited registries."""
        tld = domain.split('.')[-1].lower()
        return self.TLD_TIMEOUTS.get(tld, self.default_timeout)
    
    def _is_cache_valid(self, domain: str) -> bool:
        """Check if cached data is still valid."""
        if domain not in self._cache:
            return False
        cached_time = self._cache_ttl.get(domain)
        if not cached_time:
            return False
        age = (datetime.now() - cached_time).total_seconds()
        return age < self._cache_duration
    
    def _empty_result(self) -> Dict[str, Any]:
        """Return empty result template with all fields."""
        return {
            'registrant_name': '',
            'registrant_address': '',
            'registrant_city': '',
            'registrant_zip': '',
            'registrant_country': '',
            'registrant_email': '',
            'registrant_phone': '',
            'registrar': '',
            'created_date': '',
            'expiry_date': '',
            'updated_date': '',
            'name_servers': [],
            'status': [],
            'raw_whois': '',
            'source': '',
            'whois_confidence': 0.0,
        }
    
    async def _try_rdap(self, domain: str) -> Dict[str, Any]:
        """Attempt RDAP lookup (structured JSON, highest accuracy)."""
        result = self._empty_result()
        
        if not self._domain_client:
            return result
        
        try:
            timeout = self._get_tld_timeout(domain)
            query_str, parsed = await asyncio.wait_for(
                self._domain_client.aio_rdap(domain),
                timeout=timeout
            )
            
            if parsed:
                result['registrant_name'] = parsed.get('registrant_organization') or parsed.get('registrant_name') or parsed.get('registrant', '')
                result['registrant_country'] = parsed.get('registrant_country') or ''
                result['registrant_address'] = parsed.get('registrant_address') or ''
                result['registrar'] = parsed.get('registrar') or ''
                result['created_date'] = str(parsed.get('created')) if parsed.get('created') else ''
                result['expiry_date'] = str(parsed.get('expires')) if parsed.get('expires') else ''
                result['updated_date'] = str(parsed.get('updated')) if parsed.get('updated') else ''
                result['name_servers'] = parsed.get('name_servers') or []
                result['status'] = parsed.get('status') or []
                result['source'] = 'rdap'
                result['raw_whois'] = str(query_str)[:2000] if query_str else ''
                
                logger.debug(f"RDAP success for {domain}: registrant={result['registrant_name']}")
                
        except asyncio.TimeoutError:
            logger.debug(f"RDAP timeout for {domain}")
        except asyncwhois.NotFoundError:
            logger.debug(f"RDAP not found for {domain}")
        except Exception as e:
            logger.debug(f"RDAP error for {domain}: {e}")
        
        return result
    
    async def _try_whois(self, domain: str) -> Dict[str, Any]:
        """Attempt WHOIS lookup with authoritative server chain."""
        result = self._empty_result()
        
        if not self._domain_client:
            return result
        
        try:
            timeout = self._get_tld_timeout(domain)
            query_str, parsed = await asyncio.wait_for(
                self._domain_client.aio_whois(domain),
                timeout=timeout
            )
            
            if parsed:
                # Extract registrant info (field names vary by registry)
                result['registrant_name'] = (
                    parsed.get('registrant_organization') or 
                    parsed.get('registrant_name') or 
                    parsed.get('registrant') or
                    parsed.get('org') or
                    parsed.get('organization') or
                    ''
                )
                result['registrant_address'] = parsed.get('registrant_address') or parsed.get('address') or ''
                result['registrant_city'] = parsed.get('registrant_city') or parsed.get('city') or ''
                result['registrant_zip'] = parsed.get('registrant_postal_code') or parsed.get('postal_code') or ''
                result['registrant_country'] = parsed.get('registrant_country') or parsed.get('country') or ''
                result['registrant_email'] = parsed.get('registrant_email') or ''
                
                # Registrar and dates
                result['registrar'] = parsed.get('registrar') or ''
                result['created_date'] = str(parsed.get('created')) if parsed.get('created') else ''
                result['expiry_date'] = str(parsed.get('expires')) if parsed.get('expires') else ''
                result['updated_date'] = str(parsed.get('updated')) if parsed.get('updated') else ''
                result['name_servers'] = parsed.get('name_servers') or []
                result['status'] = parsed.get('status') or []
                result['source'] = 'whois'
                result['raw_whois'] = str(query_str)[:2000] if query_str else ''
                
                logger.debug(f"WHOIS success for {domain}: registrant={result['registrant_name']}")
                
        except asyncio.TimeoutError:
            logger.debug(f"WHOIS timeout for {domain}")
        except asyncwhois.NotFoundError:
            logger.debug(f"WHOIS not found for {domain}")
        except Exception as e:
            logger.debug(f"WHOIS error for {domain}: {e}")
        
        return result
    
    def _calculate_confidence(self, rdap: Dict, whois: Dict) -> float:
        """
        Calculate confidence score based on data quality and source agreement.
        Score: 0.0 - 1.0
        """
        score = 0.0
        
        # RDAP data available (structured JSON = high quality)
        if rdap.get('source') == 'rdap' and rdap.get('registrant_name'):
            score += 0.4
        
        # WHOIS data available
        if whois.get('source') == 'whois' and whois.get('registrant_name'):
            score += 0.2
        
        # Source agreement on registrant name
        rdap_name = (rdap.get('registrant_name') or '').lower().strip()
        whois_name = (whois.get('registrant_name') or '').lower().strip()
        if rdap_name and whois_name:
            if rdap_name == whois_name:
                score += 0.2  # Exact match
            elif rdap_name in whois_name or whois_name in rdap_name:
                score += 0.1  # Partial match
        
        # Country field populated
        if rdap.get('registrant_country') or whois.get('registrant_country'):
            score += 0.1
        
        # Address fields populated
        if rdap.get('registrant_address') or whois.get('registrant_address'):
            score += 0.1
        
        return min(score, 1.0)
    
    def _merge_sources(self, rdap: Dict, whois: Dict) -> Dict[str, Any]:
        """
        Merge RDAP and WHOIS data, prioritizing RDAP for structured fields.
        """
        result = self._empty_result()
        
        # Priority: RDAP > WHOIS for each field
        field_mappings = [
            'registrant_name', 'registrant_address', 'registrant_city',
            'registrant_zip', 'registrant_country', 'registrant_email',
            'registrant_phone', 'registrar', 'created_date', 'expiry_date',
            'updated_date'
        ]
        
        for field in field_mappings:
            rdap_val = rdap.get(field, '')
            whois_val = whois.get(field, '')
            result[field] = rdap_val if rdap_val else whois_val
        
        # Merge name servers (deduplicate)
        ns_set = set()
        for ns in (rdap.get('name_servers') or []):
            ns_set.add(ns.lower() if isinstance(ns, str) else str(ns).lower())
        for ns in (whois.get('name_servers') or []):
            ns_set.add(ns.lower() if isinstance(ns, str) else str(ns).lower())
        result['name_servers'] = list(ns_set)
        
        # Merge status
        status_set = set()
        for s in (rdap.get('status') or []):
            status_set.add(s)
        for s in (whois.get('status') or []):
            status_set.add(s)
        result['status'] = list(status_set)
        
        # Determine source label
        if rdap.get('source') == 'rdap' and whois.get('source') == 'whois':
            result['source'] = 'rdap+whois'
        elif rdap.get('source') == 'rdap':
            result['source'] = 'rdap'
        elif whois.get('source') == 'whois':
            result['source'] = 'whois'
        else:
            result['source'] = 'none'
        
        # Combine raw data
        raw_parts = []
        if rdap.get('raw_whois'):
            raw_parts.append(f"=== RDAP ===\n{rdap['raw_whois']}")
        if whois.get('raw_whois'):
            raw_parts.append(f"=== WHOIS ===\n{whois['raw_whois']}")
        result['raw_whois'] = '\n\n'.join(raw_parts)[:4000]
        
        # Calculate confidence
        result['whois_confidence'] = self._calculate_confidence(rdap, whois)
        
        return result
    
    async def get_whois_data_async(self, domain: str) -> Dict[str, Any]:
        """
        Main async method: Multi-source WHOIS lookup with verification.
        Tries RDAP first (structured JSON), then WHOIS with authoritative lookups.
        Returns merged result with confidence score.
        """
        # Check cache
        if self._is_cache_valid(domain):
            logger.debug(f"Cache hit for {domain}")
            return self._cache[domain]
        
        if not ASYNCWHOIS_AVAILABLE or not self._domain_client:
            logger.warning("asyncwhois not available, returning empty result")
            return self._empty_result()
        
        # Run RDAP and WHOIS concurrently for speed
        rdap_result, whois_result = await asyncio.gather(
            self._try_rdap(domain),
            self._try_whois(domain),
            return_exceptions=True
        )
        
        # Handle exceptions
        if isinstance(rdap_result, Exception):
            logger.debug(f"RDAP exception for {domain}: {rdap_result}")
            rdap_result = self._empty_result()
        if isinstance(whois_result, Exception):
            logger.debug(f"WHOIS exception for {domain}: {whois_result}")
            whois_result = self._empty_result()
        
        # Merge results
        merged = self._merge_sources(rdap_result, whois_result)
        
        # Cache result
        self._cache[domain] = merged
        self._cache_ttl[domain] = datetime.now()
        
        # Log summary
        logger.info(f"WHOIS enrichment for {domain}: source={merged['source']}, "
                   f"confidence={merged['whois_confidence']:.2f}, "
                   f"registrant={merged['registrant_name'][:50] if merged['registrant_name'] else 'N/A'}")
        
        return merged
    
    def get_whois_data(self, domain: str) -> Dict[str, Any]:
        """Sync wrapper for async method."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If already in async context, create new task
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, self.get_whois_data_async(domain))
                    return future.result(timeout=30)
            else:
                return loop.run_until_complete(self.get_whois_data_async(domain))
        except Exception as e:
            logger.error(f"Sync WHOIS lookup failed for {domain}: {e}")
            return self._empty_result()
    
    async def batch_lookup(self, domains: List[str], max_concurrent: int = 5) -> Dict[str, Dict]:
        """
        Batch WHOIS lookup with rate limiting.
        Returns dict mapping domain -> whois_data.
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def limited_lookup(domain: str) -> tuple:
            async with semaphore:
                result = await self.get_whois_data_async(domain)
                # Small delay between lookups to avoid rate limiting
                await asyncio.sleep(0.5)
                return domain, result
        
        results = await asyncio.gather(
            *[limited_lookup(d) for d in domains],
            return_exceptions=True
        )
        
        output = {}
        for item in results:
            if isinstance(item, tuple):
                domain, data = item
                output[domain] = data
            elif isinstance(item, Exception):
                logger.error(f"Batch lookup error: {item}")
        
        return output
    
    def clear_cache(self):
        """Clear the lookup cache."""
        self._cache.clear()
        self._cache_ttl.clear()
        logger.info("WHOIS cache cleared")


# Convenience function for one-off lookups
async def lookup_domain(domain: str) -> Dict[str, Any]:
    """Quick async lookup for a single domain."""
    enricher = WhoisEnricher()
    return await enricher.get_whois_data_async(domain)
