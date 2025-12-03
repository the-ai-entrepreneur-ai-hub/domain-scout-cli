"""
UK Legal Entity Extractor - Specialized patterns for UK companies.
Handles Companies House numbers, directors, Ltd/PLC forms, UK postcodes.
"""
import re
from typing import Dict, Optional, List
from ..utils import logger


class UKExtractor:
    """Extract legal data from UK company legal notice pages."""
    
    def __init__(self):
        # UK legal patterns
        self.patterns = {
            # Companies House registration numbers
            'company_number': re.compile(
                r'(?:Company\s+(?:Registration\s+)?Number|Registered\s+Number|Companies\s+House)[:\s]*(\d{8}|\d{2}\d{6})',
                re.IGNORECASE
            ),
            
            # Directors patterns
            'directors': re.compile(
                r'(?:Director[s]?|Managing\s+Director)[:\s]+((?:[A-Z][a-z]+[\s,&-]*){1,4})(?:\n|Registered|Company|Tel|Email)',
                re.IGNORECASE | re.MULTILINE
            ),
            
            # Multiple directors
            'directors_list': re.compile(
                r'(?:Director[s]?)[:\s]+([^:\n]+?)(?:\n|Registered|Company)',
                re.IGNORECASE | re.MULTILINE
            ),
            
            # UK legal forms
            'legal_form': re.compile(
                r'\b(Limited|Ltd\.?|PLC|Public\s+Limited\s+Company|LLP|Limited\s+Liability\s+Partnership)\b',
                re.IGNORECASE
            ),
            
            # VAT numbers (UK format)
            'vat_number': re.compile(
                r'(?:VAT\s+(?:Registration\s+)?Number)[:\s]*(GB\d{9}|\d{9})',
                re.IGNORECASE
            ),
            
            # UK address with postcodes
            'address': re.compile(
                r'(?:Registered\s+(?:Office|Address)|Address)[:\s]*([^,\n]+),?\s*([A-Z]{1,2}\d{1,2}[A-Z]?\s?\d[A-Z]{2})\s*(?:\n|,|Tel|Email)',
                re.IGNORECASE | re.MULTILINE
            ),
            
            # UK phone numbers
            'phone': re.compile(
                r'(?:Tel\.?|Phone)[:\s]*(\+44[\s\d\-()]{9,15}|0[\d\s\-()]{9,12})',
                re.IGNORECASE
            ),
            
            # Email addresses
            'email': re.compile(
                r'(?:E-mail|Email)[:\s]*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
                re.IGNORECASE
            ),
        }

    def extract(self, clean_text: str) -> Dict[str, str]:
        """
        Extract UK legal entity data from cleaned legal notice text.
        
        Args:
            clean_text: Clean text from legal notice page
            
        Returns:
            Dict with extracted legal data
        """
        if not clean_text:
            return {}
            
        result = {}
        
        try:
            # Extract company number
            number_match = self.patterns['company_number'].search(clean_text)
            if number_match:
                result['registration_number'] = number_match.group(1).strip()
                
            # Extract directors
            directors = self._extract_directors(clean_text)
            if directors:
                result['directors'] = '; '.join(directors)
                result['ceo_name'] = directors[0]  # First director as CEO
                
            # Extract legal form
            form_match = self._find_best_legal_form(clean_text)
            if form_match:
                result['legal_form'] = form_match
                
            # Extract VAT number
            vat_match = self.patterns['vat_number'].search(clean_text)
            if vat_match:
                vat_num = vat_match.group(1)
                if not vat_num.startswith('GB'):
                    vat_num = f'GB{vat_num}'
                result['vat_id'] = vat_num
                
            # Extract address components
            address_data = self._extract_address(clean_text)
            result.update(address_data)
            
            # Extract contact info
            phone_match = self.patterns['phone'].search(clean_text)
            if phone_match:
                result['phone'] = phone_match.group(1).strip()
                
            email_match = self.patterns['email'].search(clean_text)
            if email_match:
                result['email'] = email_match.group(1).strip()
                
            # Set register court (always Companies House for UK)
            if result.get('registration_number'):
                result['register_court'] = 'Companies House'
                
            # Calculate confidence based on fields found
            result['extraction_confidence'] = self._calculate_confidence(result)
            
            logger.debug(f"UK extraction found {len(result)} fields")
            return result
            
        except Exception as e:
            logger.error(f"UK extraction failed: {e}")
            return {}

    def _extract_directors(self, text: str) -> List[str]:
        """Extract list of directors."""
        directors = []
        
        # Try directors list pattern first
        list_match = self.patterns['directors_list'].search(text)
        if list_match:
            directors_text = list_match.group(1).strip()
            
            # Split on common delimiters
            director_names = re.split(r'[,;&]|\sand\s', directors_text)
            
            for name in director_names:
                cleaned_name = self._clean_director_name(name)
                if cleaned_name:
                    directors.append(cleaned_name)
        
        # Fallback: single director pattern
        if not directors:
            single_match = self.patterns['directors'].search(text)
            if single_match:
                name = self._clean_director_name(single_match.group(1))
                if name:
                    directors.append(name)
                    
        return directors[:3]  # Limit to 3 directors

    def _clean_director_name(self, name: str) -> Optional[str]:
        """Clean and validate director name."""
        if not name:
            return None
            
        name = name.strip()
        
        # Remove common prefixes/suffixes
        prefixes = ['mr', 'mrs', 'ms', 'dr', 'prof', 'sir', 'lady']
        for prefix in prefixes:
            if name.lower().startswith(prefix + ' '):
                name = name[len(prefix)+1:].strip()
                
        # Must have at least 2 parts (first + last name)
        parts = name.split()
        if len(parts) < 2:
            return None
            
        # Must start with capital letter
        if not name[0].isupper():
            return None
            
        # Remove trailing punctuation
        name = re.sub(r'[,:;.]+$', '', name)
        
        return name if len(name) >= 3 else None

    def _find_best_legal_form(self, text: str) -> Optional[str]:
        """Find the most specific legal form."""
        matches = self.patterns['legal_form'].findall(text)
        if not matches:
            return None
            
        # Priority order (more specific forms first)
        priority = ['Public Limited Company', 'PLC', 'Limited Liability Partnership', 'LLP', 'Limited', 'Ltd']
        
        for form in priority:
            for match in matches:
                if form.lower() == match.lower().replace('.', ''):
                    return form
                    
        return matches[0]  # Return first match if no priority match

    def _extract_address(self, text: str) -> Dict[str, str]:
        """Extract address components."""
        address_data = {}
        
        address_match = self.patterns['address'].search(text)
        if address_match:
            address_line = address_match.group(1).strip()
            postcode = address_match.group(2).strip()
            
            # Split address into components
            address_parts = [part.strip() for part in address_line.split(',')]
            
            if len(address_parts) >= 2:
                street = address_parts[0]
                city = address_parts[-1]  # Last part usually city
                
                address_data.update({
                    'street': street,
                    'city': city,
                    'postal_code': postcode,
                    'country': 'United Kingdom'
                })
            else:
                address_data.update({
                    'street': address_line,
                    'postal_code': postcode,
                    'country': 'United Kingdom'
                })
                
        return address_data

    def _calculate_confidence(self, extracted_data: Dict) -> int:
        """Calculate extraction confidence score (0-100)."""
        # Weight different fields by importance
        field_weights = {
            'registration_number': 35,  # Company number most important for UK
            'directors': 25,           # Directors very important
            'legal_form': 15,          # Legal form important
            'vat_id': 8,              # VAT number useful
            'street': 7,              # Address components
            'postal_code': 5,
            'city': 3,
            'register_court': 2,      # Always Companies House for UK
        }
        
        total_score = 0
        for field, weight in field_weights.items():
            if extracted_data.get(field):
                total_score += weight
                
        return min(total_score, 100)  # Cap at 100%

    def is_uk_content(self, text: str) -> bool:
        """Check if text appears to be UK legal content."""
        if not text:
            return False
            
        uk_indicators = [
            'company number', 'companies house', 'registered office',
            'limited', 'ltd', 'plc', 'director', 'vat number',
            'united kingdom', 'england', 'wales', 'scotland'
        ]
        
        text_lower = text.lower()
        matches = sum(1 for indicator in uk_indicators if indicator in text_lower)
        
        return matches >= 2  # At least 2 UK indicators


# Global instance
uk_extractor = UKExtractor()
