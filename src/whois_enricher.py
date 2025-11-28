"""
WHOIS Enrichment Module
Fetches and parses WHOIS data to identify the domain registrant.
"""
import re
import whois
from typing import Dict, Optional
from .utils import logger

class WhoisEnricher:
    def __init__(self):
        pass

    def get_whois_data(self, domain: str) -> Dict[str, str]:
        """
        Fetch WHOIS data for a domain and extract registrant information.
        Returns a dictionary with standardized keys.
        """
        result = {
            'registrant_name': '',
            'registrant_address': '',
            'registrant_city': '',
            'registrant_zip': '',
            'registrant_country': '',
            'registrant_email': '',
            'registrant_phone': '',
            'raw_whois': ''
        }

        try:
            # Fetch WHOIS
            w = whois.whois(domain)
            
            # Capture raw text if available (some libraries put it in 'text' or just return dict)
            raw_text = str(w)
            result['raw_whois'] = raw_text

            # 1. Try standard library fields first (best case)
            if w.org:
                result['registrant_name'] = w.org
            elif w.name:
                result['registrant_name'] = w.name
                
            if w.address:
                if isinstance(w.address, list):
                    result['registrant_address'] = ", ".join(w.address)
                else:
                    result['registrant_address'] = w.address
            
            if w.city: result['registrant_city'] = w.city
            if w.zipcode: result['registrant_zip'] = w.zipcode
            if w.country: result['registrant_country'] = w.country
            
            if w.emails:
                if isinstance(w.emails, list):
                    result['registrant_email'] = w.emails[0]
                else:
                    result['registrant_email'] = w.emails

            # 2. Regex Fallback for Raw Text (Crucial for .at, .ch which often return unstructured text)
            # Example: "organization: JC New Retail AG"
            if not result['registrant_name']:
                org_match = re.search(r'(?:organization|org|registrant organization):\s*(.*)', raw_text, re.IGNORECASE)
                if org_match:
                    result['registrant_name'] = org_match.group(1).strip()
            
            if not result['registrant_address']:
                addr_match = re.search(r'(?:street address|address|street):\s*(.*)', raw_text, re.IGNORECASE)
                if addr_match:
                    result['registrant_address'] = addr_match.group(1).strip()
                    
            if not result['registrant_city']:
                city_match = re.search(r'(?:city):\s*(.*)', raw_text, re.IGNORECASE)
                if city_match:
                    result['registrant_city'] = city_match.group(1).strip()
                    
            if not result['registrant_zip']:
                zip_match = re.search(r'(?:postal code|zipcode|zip):\s*(.*)', raw_text, re.IGNORECASE)
                if zip_match:
                    result['registrant_zip'] = zip_match.group(1).strip()
                    
            if not result['registrant_country']:
                country_match = re.search(r'(?:country):\s*(.*)', raw_text, re.IGNORECASE)
                if country_match:
                    result['registrant_country'] = country_match.group(1).strip()

            # Clean up common WHOIS placeholders
            for k, v in result.items():
                if v and isinstance(v, str):
                    if 'redacted' in v.lower() or 'privacy' in v.lower() or 'gdpr' in v.lower():
                        result[k] = '[REDACTED]'

            return result

        except Exception as e:
            logger.warning(f"WHOIS lookup failed for {domain}: {e}")
            return result
