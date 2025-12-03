"""
Austrian Legal Entity Extractor - Specialized patterns for Austrian companies.
Handles FN numbers, Geschäftsführer, m.b.H., GmbH & Co KG forms.
"""
import re
from typing import Dict, Optional, List
from ..utils import logger


class AustrianExtractor:
    """Extract legal data from Austrian company impressum pages."""
    
    def __init__(self):
        # Austrian legal patterns
        self.patterns = {
            # Firmenbuch numbers - multiple formats:
            # FN 123456a, FN 123456 a, Firmenbuchnummer: 54472G
            'fn_number': re.compile(
                r'(?:FN|Firmenbuch(?:nummer)?)[:\s|]*(\d+\s*[a-zA-Z]?)', 
                re.IGNORECASE
            ),
            
            # Geschäftsführer patterns - FLEXIBLE (handles umlauts + ASCII: ä/ae, ü/ue)
            'geschaeftsfuehrer': re.compile(
                r'Gesch(?:ä|ae)ftsf(?:ü|ue)hrer(?:in|innen)?[:\s|]+([A-Za-zÖÄÜöäü][^\n|]{5,60}?)(?:\n|\||Sitz|Firmenbuch|Telefon|E-Mail|UID|Aufsicht|Kontakt|$)', 
                re.IGNORECASE | re.MULTILINE
            ),
            
            # Alternative CEO patterns: Vorstand, Vorstände, Leitung, CEO
            # Handles table format: "Vorstände: | Name1, Name2 |"
            'ceo_alt': re.compile(
                r'(?:Vorst(?:ä|ae)nd(?:e)?|Gesch(?:ä|ae)ftsleitung|Gesch(?:ä|ae)ftsf(?:ü|ue)hrung|Leitung|CEO|Managing Director)[:\s|]+\|?\s*([A-Za-zÖÄÜöäü][^\n]{5,150}?)(?:\||Sitz|Firmenbuch|Eigent|$)',
                re.IGNORECASE | re.MULTILINE
            ),
            
            # Multiple directors - handles table format with | separators
            'directors_list': re.compile(
                r'(?:Gesch(?:ä|ae)ftsf(?:ü|ue)hrer|Vorst(?:ä|ae)nd(?:e)?)[:\s|]+([^\n|]+?)(?:\n\n|\n[A-Z]|Sitz|Firmenbuch|UID|Eigent|\|---\||$)',
                re.IGNORECASE | re.MULTILINE
            ),
            
            # Austrian legal forms (compound forms important!)
            'legal_form': re.compile(
                r'\b(GmbH\s*&\s*Co\.?\s*KG|GmbH|AG|m\.b\.H\.|Gesellschaft\s+m\.?b\.?H\.?|SE|KG|OG|Genossenschaft|eGen)\b',
                re.IGNORECASE
            ),
            
            # UID numbers (Austrian VAT) - handles ATU and ATU with space
            'uid_number': re.compile(
                r'(?:UID|USt-IdNr\.?|Umsatzsteuer-Identifikationsnummer)[:\s|]*(ATU?\s*\d{8})',
                re.IGNORECASE
            ),
            
            # Business address - handles table format: "Anschrift: | Street, 1234 City |"
            'address': re.compile(
                r'(?:Sitz|Adresse|Anschrift)[:\s|]*([^,\n|]+),?\s*(\d{4})\s*([A-ZÖÄÜa-zöäüß\s-]+?)(?:\n|\||,|Telefon|E-Mail|UID|$)',
                re.IGNORECASE | re.MULTILINE
            ),
            
            # Handelsgericht / Landesgericht / Firmenbuchgericht
            'court': re.compile(
                r'(?:Firmenbuch(?:gericht)?|Handelsgericht|Landesgericht|Gericht)[:\s|]*([A-ZÖÄÜ][a-zöäüß\s-]+?)(?:\n|\||,|FN|Firmenbuch|Kammer|$)',
                re.IGNORECASE
            ),
            
            # Phone numbers (Austrian format)
            'phone': re.compile(
                r'(?:Tel\.?|Telefon|Phone)[:\s]*(\+43[\s\d\-/()]{8,15})',
                re.IGNORECASE
            ),
            
            # Email addresses
            'email': re.compile(
                r'(?:E-Mail|Email)[:\s]*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
                re.IGNORECASE
            ),
        }

    def extract(self, clean_text: str) -> Dict[str, str]:
        """
        Extract Austrian legal entity data from cleaned impressum text.
        
        Args:
            clean_text: Clean text from impressum page
            
        Returns:
            Dict with extracted legal data
        """
        if not clean_text:
            return {}
            
        result = {}
        
        try:
            # Extract Firmenbuch number
            fn_match = self.patterns['fn_number'].search(clean_text)
            if fn_match:
                result['registration_number'] = f"FN {fn_match.group(1).strip()}"
                
            # Extract Geschäftsführer (directors/CEOs)
            directors = self._extract_directors(clean_text)
            if directors:
                result['directors'] = '; '.join(directors)
                result['ceo_name'] = directors[0]  # First director as CEO
                
            # Extract legal form
            form_match = self._find_best_legal_form(clean_text)
            if form_match:
                result['legal_form'] = form_match
                
            # Extract UID number (Austrian VAT)
            uid_match = self.patterns['uid_number'].search(clean_text)
            if uid_match:
                result['vat_id'] = uid_match.group(1)
                
            # Extract address components
            address_data = self._extract_address(clean_text)
            result.update(address_data)
            
            # Extract court
            court_match = self.patterns['court'].search(clean_text)
            if court_match:
                result['register_court'] = court_match.group(1).strip()
                
            # Extract contact info
            phone_match = self.patterns['phone'].search(clean_text)
            if phone_match:
                result['phone'] = phone_match.group(1).strip()
                
            email_match = self.patterns['email'].search(clean_text)
            if email_match:
                result['email'] = email_match.group(1).strip()
                
            # Calculate confidence based on fields found
            result['extraction_confidence'] = self._calculate_confidence(result)
            
            logger.debug(f"Austrian extraction found {len(result)} fields")
            return result
            
        except Exception as e:
            logger.error(f"Austrian extraction failed: {e}")
            return {}

    def _extract_directors(self, text: str) -> List[str]:
        """Extract list of directors/Geschäftsführer."""
        directors = []
        
        # Try directors list pattern first
        list_match = self.patterns['directors_list'].search(text)
        if list_match:
            directors_text = list_match.group(1).strip()
            
            # Split on common delimiters
            director_names = re.split(r'[,;&]|\sund\s|\su\.\s', directors_text)
            
            for name in director_names:
                cleaned_name = self._clean_director_name(name)
                if cleaned_name:
                    directors.append(cleaned_name)
        
        # Fallback: single director pattern
        if not directors:
            single_match = self.patterns['geschaeftsfuehrer'].search(text)
            if single_match:
                name = self._clean_director_name(single_match.group(1))
                if name:
                    directors.append(name)
        
        # Try alternative CEO pattern if still nothing
        if not directors:
            alt_match = self.patterns['ceo_alt'].search(text)
            if alt_match:
                name = self._clean_director_name(alt_match.group(1))
                if name:
                    directors.append(name)
                    
        return directors[:3]  # Limit to 3 directors

    def _clean_director_name(self, name: str) -> Optional[str]:
        """Clean and validate director name."""
        if not name:
            return None
            
        name = name.strip()
        
        # Remove birth dates like "geb. 22.06.1963"
        name = re.sub(r',?\s*geb\.?\s*\d{1,2}[./]\d{1,2}[./]\d{2,4}', '', name)
        
        # Remove trailing role titles
        name = re.sub(r'\s+(Vorstand|Geschäftsführer|CEO|Director|Prokurist)\s*$', '', name, flags=re.I)
        
        # Remove common prefixes/suffixes
        prefixes = ['herr', 'frau', 'dr.', 'mag.', 'ing.', 'dipl.-ing.', 'prof.', 'mba']
        for prefix in prefixes:
            if name.lower().startswith(prefix + ' '):
                name = name[len(prefix)+1:].strip()
            elif name.lower().startswith(prefix):
                name = name[len(prefix):].strip()
                
        # Must have at least 2 parts (first + last name)
        name = name.strip()
        parts = name.split()
        if len(parts) < 2:
            return None
            
        # Must start with capital letter
        if not name[0].isupper():
            return None
            
        # Remove trailing punctuation
        name = re.sub(r'[,:;.]+$', '', name)
        
        return name.strip() if len(name.strip()) >= 3 else None

    def _find_best_legal_form(self, text: str) -> Optional[str]:
        """Find the most specific legal form."""
        matches = self.patterns['legal_form'].findall(text)
        if not matches:
            return None
            
        # Priority order (more specific forms first)
        priority = ['GmbH & Co. KG', 'GmbH & Co KG', 'm.b.H.', 'GmbH', 'AG', 'SE', 'KG', 'OG']
        
        for form in priority:
            for match in matches:
                if form.lower().replace(' ', '').replace('.', '') == match.lower().replace(' ', '').replace('.', ''):
                    return form
                    
        return matches[0]  # Return first match if no priority match

    def _extract_address(self, text: str) -> Dict[str, str]:
        """Extract address components (street, postal code, city)."""
        address_data = {}
        
        address_match = self.patterns['address'].search(text)
        if address_match:
            street = address_match.group(1).strip()
            postal_code = address_match.group(2)
            city = address_match.group(3).strip()
            
            address_data.update({
                'street': street,
                'postal_code': postal_code,
                'city': city,
                'country': 'Austria'
            })
            
        return address_data

    def _calculate_confidence(self, extracted_data: Dict) -> int:
        """Calculate extraction confidence score (0-100)."""
        # Weight different fields by importance
        field_weights = {
            'registration_number': 30,  # FN number most important
            'directors': 25,           # CEO/directors very important
            'legal_form': 15,          # Legal form important
            'vat_id': 10,             # UID number useful
            'street': 8,              # Address components
            'postal_code': 5,
            'city': 5,
            'register_court': 2,      # Court less critical
        }
        
        total_score = 0
        for field, weight in field_weights.items():
            if extracted_data.get(field):
                total_score += weight
                
        return min(total_score, 100)  # Cap at 100%

    def is_austrian_content(self, text: str) -> bool:
        """Check if text appears to be Austrian legal content."""
        if not text:
            return False
            
        austrian_indicators = [
            'geschäftsführer', 'firmenbuch', 'handelsgericht', 'uid',
            'gmbh', 'm.b.h.', 'fn ', 'atu', 'österreich', 'austria'
        ]
        
        text_lower = text.lower()
        matches = sum(1 for indicator in austrian_indicators if indicator in text_lower)
        
        return matches >= 2  # At least 2 Austrian indicators


# Global instance
austrian_extractor = AustrianExtractor()
