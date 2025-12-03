"""
Robust Legal Extractor - Multi-pass extraction with validation.
Orchestrates section isolation, country-specific extractors, and field validation.
Uses trafilatura for clean text extraction and extruct for JSON-LD.
"""
import json
import re
from typing import Dict, Optional, List
from datetime import datetime
from bs4 import BeautifulSoup

try:
    import trafilatura
    TRAFILATURA_AVAILABLE = True
except ImportError:
    TRAFILATURA_AVAILABLE = False

try:
    import extruct
    EXTRUCT_AVAILABLE = True
except ImportError:
    EXTRUCT_AVAILABLE = False

from .section_extractor import SectionExtractor
from .field_validators import FieldValidators
from .country_extractors.german_extractor import GermanExtractor
from .country_extractors.uk_extractor import UKExtractor
from .country_extractors.french_extractor import FrenchExtractor
from .country_extractors.generic_extractor import GenericExtractor

class RobustLegalExtractor:
    """
    Robust multi-pass legal data extractor.
    
    Extraction Strategy:
    1. Pass 1: Extract from structured data (JSON-LD, Schema.org)
    2. Pass 2: Section-based extraction with country-specific patterns
    3. Pass 3: Merge results and validate all fields
    """
    
    def __init__(self):
        self.section_extractor = SectionExtractor()
        self.german_extractor = GermanExtractor()
        self.uk_extractor = UKExtractor()
        self.french_extractor = FrenchExtractor()
        self.generic_extractor = GenericExtractor()
        
    def extract(self, html: str, url: str) -> Dict:
        """
        Extract legal information using multi-pass strategy.
        
        Args:
            html: Raw HTML content
            url: Source URL for context
            
        Returns:
            Dict with validated legal entity information
        """
        soup = BeautifulSoup(html, 'lxml')
        
        # Determine country from URL/content
        country = self._detect_country(url, soup)
        
        # PASS 1: Extract from structured data (JSON-LD via extruct - highest priority)
        structured_data = self._extract_with_extruct(html, url) if EXTRUCT_AVAILABLE else {}
        if not structured_data:
            structured_data = self._extract_from_structured_data(soup)
        
        # PASS 2: Section-based extraction with trafilatura clean text
        if TRAFILATURA_AVAILABLE:
            # Trafilatura removes nav, ads, boilerplate - much cleaner for regex
            clean_text = trafilatura.extract(html, include_comments=False, include_tables=True) or ""
            sections = {}
        else:
            clean_text, sections = self.section_extractor.extract_legal_content(html)
        
        section_data = self._extract_from_sections(clean_text, sections, country)
        
        # PASS 3: Merge and validate
        result = self._merge_and_validate(structured_data, section_data, country)
        
        # Add metadata
        result['legal_notice_url'] = url
        result['extraction_date'] = datetime.now().isoformat()
        result['extraction_confidence'] = FieldValidators.calculate_data_quality_score(result)
        
        # Set status based on what we found - CRITICAL for save flow!
        key_fields = ['legal_name', 'legal_form', 'registration_number', 'ceo_name', 'directors', 'email', 'phone']
        found_fields = sum(1 for f in key_fields if result.get(f))
        if found_fields >= 2:
            result['status'] = 'SUCCESS'
        else:
            result['status'] = 'NO_DATA'
        
        return result
    
    def _extract_with_extruct(self, html: str, url: str) -> Dict:
        """Extract structured data using extruct (more reliable than BeautifulSoup)."""
        result = {}
        try:
            data = extruct.extract(html, base_url=url, syntaxes=['json-ld', 'microdata', 'opengraph'])
            
            # Process JSON-LD first (highest quality)
            for item in data.get('json-ld', []):
                item_type = item.get('@type', '')
                if item_type in ['Organization', 'LocalBusiness', 'Corporation', 'LegalService']:
                    # Company name
                    name = item.get('legalName') or item.get('name')
                    if name and not result.get('legal_name'):
                        validated = FieldValidators.validate_company_name(name)
                        if validated:
                            result['legal_name'] = validated
                    
                    # VAT ID
                    vat = item.get('vatID') or item.get('taxID')
                    if vat:
                        result['vat_id'] = vat
                    
                    # Address
                    addr = item.get('address', {})
                    if isinstance(addr, dict):
                        if addr.get('streetAddress'):
                            result['street_address'] = addr['streetAddress']
                        if addr.get('postalCode'):
                            result['postal_code'] = addr['postalCode']
                        if addr.get('addressLocality'):
                            result['city'] = addr['addressLocality']
                        if addr.get('addressCountry'):
                            result['country'] = addr['addressCountry']
                    
                    # Contact
                    if item.get('email'):
                        result['email'] = item['email']
                    if item.get('telephone'):
                        result['phone'] = item['telephone']
                        
            # Process OpenGraph for company name fallback
            og = data.get('opengraph', [{}])[0] if data.get('opengraph') else {}
            if og.get('og:site_name') and not result.get('legal_name'):
                result['legal_name'] = og['og:site_name']
                
        except Exception:
            pass
        return result

    def _detect_country(self, url: str, soup: BeautifulSoup) -> str:
        """Detect country from URL TLD and content."""
        # Check TLD
        tld_map = {
            '.de': 'DE', '.at': 'AT', '.ch': 'CH',
            '.co.uk': 'GB', '.uk': 'GB',
            '.fr': 'FR',
            '.it': 'IT',
            '.es': 'ES',
            '.nl': 'NL',
            '.be': 'BE',
        }
        
        url_lower = url.lower()
        for tld, country in tld_map.items():
            if tld in url_lower:
                return country
                
        # Check content for language hints
        text = soup.get_text().lower()
        
        if 'impressum' in text or 'gemäß' in text or 'handelsregister' in text:
            return 'DE'
        elif 'mentions légales' in text or 'siège social' in text:
            return 'FR'
        elif 'companies house' in text or 'registered in england' in text:
            return 'GB'
        elif 'partita iva' in text or 'note legali' in text:
            return 'IT'
        elif 'aviso legal' in text:
            return 'ES'
            
        return 'UNKNOWN'

    def _extract_from_structured_data(self, soup: BeautifulSoup) -> Dict:
        """Extract from JSON-LD and other structured data."""
        result = {}
        
        # Find JSON-LD scripts
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(script.string or '{}')
                
                # Handle @graph format
                if isinstance(data, dict) and '@graph' in data:
                    items = data['@graph']
                elif isinstance(data, list):
                    items = data
                else:
                    items = [data]
                    
                for item in items:
                    if not isinstance(item, dict):
                        continue
                        
                    item_type = item.get('@type', '')
                    
                    if item_type in ['Organization', 'Corporation', 'LocalBusiness', 'Company']:
                        # Company name
                        name = item.get('legalName') or item.get('name')
                        if name:
                            validated = FieldValidators.validate_company_name(name)
                            if validated:
                                result['legal_name'] = validated
                                
                        # VAT ID
                        vat = item.get('vatID') or item.get('taxID')
                        if vat:
                            validated = FieldValidators.validate_vat_id(vat)
                            if validated:
                                result['vat_id'] = validated
                                
                        # Address
                        address = item.get('address', {})
                        if isinstance(address, dict):
                            if address.get('streetAddress'):
                                result['street_address'] = address['streetAddress']
                            if address.get('postalCode'):
                                result['postal_code'] = address['postalCode']
                            if address.get('addressLocality'):
                                result['city'] = address['addressLocality']
                            if address.get('addressCountry'):
                                result['country'] = address['addressCountry']
                                
                        # Contact
                        phone = item.get('telephone')
                        if phone:
                            validated = FieldValidators.validate_phone(phone)
                            if validated:
                                result['phone'] = validated
                                
                        email = item.get('email')
                        if email:
                            validated = FieldValidators.validate_email(email)
                            if validated:
                                result['email'] = validated
                                
                        fax = item.get('faxNumber')
                        if fax:
                            validated = FieldValidators.validate_fax(fax)
                            if validated:
                                result['fax'] = validated
                                
            except (json.JSONDecodeError, AttributeError):
                continue
                
        return result

    def _extract_from_sections(self, text: str, sections: Dict, country: str) -> Dict:
        """Extract from cleaned text using country-specific extractor."""
        
        # Select appropriate extractor
        if country in ['DE', 'AT', 'CH']:
            extractor = self.german_extractor
        elif country == 'GB':
            extractor = self.uk_extractor
        elif country == 'FR':
            extractor = self.french_extractor
        else:
            extractor = self.generic_extractor
            
        # Extract from main text
        result = extractor.extract(text)
        
        # Also try extracting from structured sections
        for heading in sections.get('headings', []):
            content = f"{heading['title']}\n{heading['content']}"
            section_result = extractor.extract(content)
            # Merge new findings
            for key, value in section_result.items():
                if key not in result or not result[key]:
                    result[key] = value
                    
        # Try address blocks
        for address in sections.get('address_blocks', []):
            if not result.get('street_address'):
                addr_result = extractor.extract(address)
                if addr_result.get('street_address'):
                    result['street_address'] = addr_result['street_address']
                if addr_result.get('postal_code'):
                    result['postal_code'] = addr_result['postal_code']
                if addr_result.get('city'):
                    result['city'] = addr_result['city']
                    
        return result

    def _merge_and_validate(self, structured: Dict, section: Dict, country: str) -> Dict:
        """Merge results with priority to country-specific patterns over JSON-LD."""
        result = {}
        
        # CHANGED PRIORITY: section (country-specific) > structured (JSON-LD)
        # JSON-LD often contains ads, registrar info, payment processors
        all_keys = set(structured.keys()) | set(section.keys())
        
        for key in all_keys:
            # Prefer country-specific extraction over JSON-LD
            value = section.get(key) or structured.get(key)
            if value:
                result[key] = value
                
        # Ensure country is set
        if not result.get('country'):
            country_names = {
                'DE': 'Germany', 'AT': 'Austria', 'CH': 'Switzerland',
                'GB': 'United Kingdom', 'FR': 'France', 'IT': 'Italy',
                'ES': 'Spain', 'NL': 'Netherlands', 'BE': 'Belgium',
            }
            result['country'] = country_names.get(country, country)
            
        # Extract legal form if not already set
        if not result.get('legal_form') and result.get('legal_name'):
            form = FieldValidators.validate_legal_form(
                self._find_legal_form_in_name(result['legal_name'])
            )
            if form:
                result['legal_form'] = form
                
        # Convert directors list to string if needed
        if isinstance(result.get('directors'), list):
            result['directors'] = ', '.join(result['directors'])
            
        return result

    def _find_legal_form_in_name(self, name: str) -> Optional[str]:
        """Find legal form in company name."""
        all_forms = [
            'GmbH', 'AG', 'KG', 'UG', 'OHG', 'GbR', 'e.K.', 'KGaA', 'PartG', 'eG', 'e.V.',
            'Ltd', 'Ltd.', 'Limited', 'PLC', 'LLP', 'CIC',
            'Inc.', 'Inc', 'LLC', 'Corp.', 'Corp', 'Corporation',
            'SARL', 'SAS', 'SASU', 'SA', 'EURL', 'SNC',
            'S.r.l.', 'Srl', 'S.p.A.', 'SpA',
            'S.L.', 'SL', 'S.A.',
            'B.V.', 'BV', 'N.V.', 'NV',
        ]
        for form in all_forms:
            if form in name:
                return form
        return None

    def extract_batch(self, pages: List[Dict]) -> List[Dict]:
        """
        Extract legal information from multiple pages.
        
        Args:
            pages: List of dicts with 'html' and 'url' keys
            
        Returns:
            List of extraction results
        """
        results = []
        for page in pages:
            try:
                result = self.extract(page['html'], page['url'])
                results.append(result)
            except Exception as e:
                results.append({
                    'legal_notice_url': page.get('url'),
                    'extraction_error': str(e),
                    'extraction_confidence': 0
                })
        return results
