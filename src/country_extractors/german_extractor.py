"""
German Legal Entity Extractor - Specialized patterns for German companies.
Handles HRB/HRA numbers, Geschäftsführer, Amtsgericht, GmbH & Co KG forms.
"""
import re
from typing import Dict, Optional, List
from ..utils import logger


class GermanExtractor:
    """Extract legal data from German company impressum pages."""
    
    def __init__(self):
        # German legal patterns - IMPROVED for better extraction
        self.patterns = {
            # HRB/HRA with optional letter suffix (handles "HRB 142663 B")
            'hrb_number': re.compile(
                r'(HRB|HRA)\s*(\d+)\s*([A-Z])?', 
                re.IGNORECASE
            ),
            
            # Full registration with court: "Amtsgericht München, HRB 12345"
            'registration_full': re.compile(
                r'(?:Amtsgericht|Registergericht|AG|eingetragen\s+(?:beim?\s+)?)\s*([A-ZÄÖÜa-zäöüß\s\-]+?)[,\s]+(?:unter\s+)?(HRB|HRA)\s*(\d+)\s*([A-Z])?',
                re.IGNORECASE
            ),
            
            # Geschäftsführer - more flexible pattern
            'geschaeftsfuehrer': re.compile(
                r'(?:Geschäftsführer|Geschäftsführung|Vorstand|Inhaber|Vertretungsberechtigt|Geschäftsleitung)[:\s]+([A-ZÄÖÜ][a-zäöüßA-ZÄÖÜ\s,&\.\-]+?)(?=\n\s*\n|\n[A-ZÄÖÜ]|\.|Sitz|Register|Tel|Fax|E-Mail|USt|Amtsgericht|Handelsregister|Steuer|$)',
                re.IGNORECASE | re.MULTILINE
            ),
            
            # Directors list - broader capture
            'directors_list': re.compile(
                r'(?:Geschäftsführer|Vorstand|Geschäftsleitung)[:\s]+(.+?)(?=\n\s*\n|\nSitz|\nRegister|\nTel|\nE-Mail|\nUSt|\nHandels|\nAmts|$)',
                re.IGNORECASE | re.DOTALL
            ),
            
            # German legal forms - expanded list
            'legal_form': re.compile(
                r'\b(GmbH\s*&?\s*Co\.?\s*K?G|GmbH|AG|UG\s*\(?haftungsbeschränkt\)?|UG|SE|KG|OHG|e\.?\s*V\.?|eG|Genossenschaft|mbH|Ltd\.?|Limited|GbR|PartG|KGaA)\b',
                re.IGNORECASE
            ),
            
            # USt-IdNr (German VAT) - more flexible
            'ust_id': re.compile(
                r'(?:USt\.?-?Id\.?-?Nr\.?|Umsatzsteuer-?Identifikations-?nummer|UID|VAT)[:\s]*(DE\s?\d{9})',
                re.IGNORECASE
            ),
            
            # German address - flexible multi-line (street with number)
            'address_street': re.compile(
                r'([A-ZÄÖÜ][a-zäöüßA-ZÄÖÜ\s\-]*(?:str(?:aße|\.)?|weg|platz|allee|gasse|ring|damm|ufer|chaussee|promenade)\s*\d+[a-zA-Z]?)',
                re.IGNORECASE
            ),
            
            # German postal code + city
            'address_city': re.compile(
                r'(\d{5})\s+([A-ZÄÖÜ][a-zäöüß\s\-]+?)(?=\n|,|$|Deutschland|Germany|Tel|Fax|E-Mail)',
                re.IGNORECASE
            ),
            
            # Combined address pattern
            'address': re.compile(
                r'([A-ZÄÖÜ][a-zäöüßA-ZÄÖÜ\s\-]*(?:str(?:aße|\.)?|weg|platz|allee|gasse|ring|damm)\s*\d+[a-zA-Z]?)\s*[,\n]\s*(\d{5})\s+([A-ZÄÖÜ][a-zäöüß\s\-]+)',
                re.IGNORECASE | re.MULTILINE
            ),
            
            # Amtsgericht / Registergericht - standalone
            'court': re.compile(
                r'(?:Amtsgericht|Registergericht)\s+([A-ZÄÖÜ][a-zäöüß\s\-]+?)(?=\s*[,\n]|\s*HRB|\s*HRA|\s*$)',
                re.IGNORECASE
            ),
            
            # Phone numbers - multiple German formats
            'phone': re.compile(
                r'(?:Tel(?:efon)?\.?|Fon|Phone)[:\s]*([+0][\d\s\-/().]{8,20})',
                re.IGNORECASE
            ),
            
            # Email addresses - standalone
            'email': re.compile(
                r'(?:E-?Mail|Mail)[:\s]*([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})',
                re.IGNORECASE
            ),
            
            # Any email in text
            'email_any': re.compile(
                r'\b([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})\b'
            ),
            
            # Company name with legal form (e.g., "Firma GmbH", "Test AG")
            # Use [^\n] instead of \s to avoid matching across newlines
            'company_name': re.compile(
                r'^([A-ZÄÖÜ][a-zäöüßA-ZÄÖÜ0-9 &\.\-]+?)\s+(GmbH\s*&?\s*Co\.?\s*K?G|GmbH|AG|UG\s*\(?haftungsbeschränkt\)?|UG|SE|KG|OHG|Ltd\.?|Limited|GbR|e\.?\s*V\.?|eG)(?:\s|$|,)',
                re.IGNORECASE | re.MULTILINE
            ),
            
            # Company name after label (single line only, must end with legal form or newline)
            'company_name_labeled': re.compile(
                r'(?:Firma|Unternehmen|Betreiber|Diensteanbieter|Anbieter)[:\s]+([A-ZÄÖÜ][a-zäöüßA-ZÄÖÜ0-9 &\.\-]+?)(?:\s+(?:GmbH|AG|UG|KG|OHG|Ltd|eG|e\.V\.)|$|\n)',
                re.IGNORECASE
            ),
        }

    def extract(self, clean_text: str) -> Dict[str, str]:
        """
        Extract German legal entity data from cleaned impressum text.
        
        Args:
            clean_text: Clean text from impressum page
            
        Returns:
            Dict with extracted legal data
        """
        if not clean_text:
            return {}
            
        result = {}
        
        try:
            # Extract full registration (court + HRB/HRA) first - most reliable
            reg_full_match = self.patterns['registration_full'].search(clean_text)
            if reg_full_match:
                court = reg_full_match.group(1).strip()
                reg_type = reg_full_match.group(2).upper()
                reg_num = reg_full_match.group(3)
                reg_suffix = reg_full_match.group(4) or ''
                result['register_court'] = f"Amtsgericht {court}"
                result['register_type'] = reg_type
                result['registration_number'] = f"{reg_type} {reg_num}{' ' + reg_suffix if reg_suffix else ''}".strip()
            else:
                # Fallback: Extract just HRB/HRA number
                hrb_match = self.patterns['hrb_number'].search(clean_text)
                if hrb_match:
                    reg_type = hrb_match.group(1).upper()
                    reg_num = hrb_match.group(2)
                    reg_suffix = hrb_match.group(3) or ''
                    result['register_type'] = reg_type
                    result['registration_number'] = f"{reg_type} {reg_num}{' ' + reg_suffix if reg_suffix else ''}".strip()
                
                # Try to get court separately
                court_match = self.patterns['court'].search(clean_text)
                if court_match:
                    result['register_court'] = f"Amtsgericht {court_match.group(1).strip()}"
                
            # Extract company name
            company_name = self._extract_company_name(clean_text)
            if company_name:
                result['legal_name'] = company_name
                
            # Extract Geschäftsführer (directors/CEOs)
            directors = self._extract_directors(clean_text)
            if directors:
                result['directors'] = '; '.join(directors)
                result['ceo_name'] = directors[0]  # First director as CEO
                
            # Extract legal form
            form_match = self._find_best_legal_form(clean_text)
            if form_match:
                result['legal_form'] = form_match
                
            # Extract USt-IdNr (German VAT)
            ust_match = self.patterns['ust_id'].search(clean_text)
            if ust_match:
                result['vat_id'] = ust_match.group(1).replace(' ', '')
                
            # Extract address components (improved)
            address_data = self._extract_address(clean_text)
            result.update(address_data)
                
            # Extract contact info - phone
            phone_match = self.patterns['phone'].search(clean_text)
            if phone_match:
                result['phone'] = phone_match.group(1).strip()
                
            # Extract email - try labeled first, then any email
            email_match = self.patterns['email'].search(clean_text)
            if email_match:
                result['email'] = email_match.group(1).strip()
            else:
                # Fallback: find any email
                any_email = self.patterns['email_any'].search(clean_text)
                if any_email:
                    result['email'] = any_email.group(1).strip()
                
            # Calculate confidence based on fields found
            result['extraction_confidence'] = self._calculate_confidence(result)
            
            logger.debug(f"German extraction found {len(result)} fields")
            return result
            
        except Exception as e:
            logger.error(f"German extraction failed: {e}")
            return {}

    def _extract_directors(self, text: str) -> List[str]:
        """Extract list of directors/Geschäftsführer."""
        directors = []
        
        # Try directors list pattern first
        list_match = self.patterns['directors_list'].search(text)
        if list_match:
            directors_text = list_match.group(1).strip()
            
            # Split on common delimiters
            director_names = re.split(r'[,;&]|\sund\s', directors_text)
            
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
                    
        return directors[:3]  # Limit to 3 directors

    def _clean_director_name(self, name: str) -> Optional[str]:
        """Clean and validate director name."""
        if not name:
            return None
            
        name = name.strip()
        
        # Remove common prefixes/suffixes
        prefixes = ['herr', 'frau', 'dr.', 'prof.', 'dipl.-ing.', 'ing.']
        for prefix in prefixes:
            if name.lower().startswith(prefix):
                name = name[len(prefix):].strip()
                
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
        priority = ['GmbH & Co. KG', 'GmbH & Co KG', 'GmbH', 'UG', 'AG', 'SE', 'KG', 'OHG']
        
        for form in priority:
            for match in matches:
                if form.lower().replace(' ', '').replace('.', '') == match.lower().replace(' ', '').replace('.', ''):
                    return form
                    
        return matches[0]  # Return first match if no priority match

    def _extract_address(self, text: str) -> Dict[str, str]:
        """Extract address components (street, postal code, city)."""
        address_data = {}
        
        # Try combined pattern first (street + zip + city on same/adjacent lines)
        address_match = self.patterns['address'].search(text)
        if address_match:
            street = address_match.group(1).strip()
            postal_code = address_match.group(2)
            city = address_match.group(3).strip()
            
            # Clean city (remove trailing garbage)
            city = re.sub(r'\s+(Deutschland|Germany|Tel|Fax|E-Mail).*', '', city, flags=re.IGNORECASE).strip()
            
            address_data.update({
                'street': street,
                'postal_code': postal_code,
                'city': city,
                'country': 'Germany'
            })
        else:
            # Try separate extraction
            street_match = self.patterns['address_street'].search(text)
            city_match = self.patterns['address_city'].search(text)
            
            if street_match:
                address_data['street'] = street_match.group(1).strip()
            
            if city_match:
                address_data['postal_code'] = city_match.group(1)
                city = city_match.group(2).strip()
                # Clean city
                city = re.sub(r'\s+(Deutschland|Germany|Tel|Fax|E-Mail).*', '', city, flags=re.IGNORECASE).strip()
                address_data['city'] = city
                address_data['country'] = 'Germany'
            
        return address_data

    def _extract_company_name(self, text: str) -> Optional[str]:
        """Extract company name from text."""
        # Try company name + legal form pattern FIRST (more reliable - looks for "Name GmbH")
        company_match = self.patterns['company_name'].search(text)
        if company_match:
            name = company_match.group(1).strip()
            legal_form = company_match.group(2).strip()
            
            # Combine name and legal form
            full_name = f"{name} {legal_form}"
            
            # Validate - reject if too short, too long, or has garbage
            if len(name) >= 2 and len(name) <= 80:
                # Check for garbage patterns
                garbage = ['impressum', 'kontakt', 'navigation', 'menu', 'cookie', 'datenschutz', 'hinweis', 'sollten']
                if not any(g in name.lower() for g in garbage):
                    return full_name
        
        # Fallback: Try labeled pattern (Firma: XXX)
        labeled_match = self.patterns['company_name_labeled'].search(text)
        if labeled_match:
            name = labeled_match.group(1).strip()
            # Clean trailing legal forms and garbage
            name = re.sub(r'\s+(GmbH|AG|UG|SE|KG|OHG|Ltd|Limited|GbR|e\.?V\.?|eG).*', '', name, flags=re.IGNORECASE).strip()
            if len(name) >= 3 and len(name) <= 100:
                return name
        
        return None

    def _calculate_confidence(self, extracted_data: Dict) -> int:
        """Calculate extraction confidence score (0-100)."""
        # Weight different fields by importance
        field_weights = {
            'legal_name': 20,          # Company name important
            'registration_number': 30,  # HRB number most important
            'directors': 25,           # CEO/directors very important
            'legal_form': 15,          # Legal form important
            'vat_id': 10,             # USt-IdNr useful
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

    def is_german_content(self, text: str) -> bool:
        """Check if text appears to be German legal content."""
        if not text:
            return False
            
        german_indicators = [
            'geschäftsführer', 'handelsregister', 'amtsgericht', 'hrb', 'hra',
            'gmbh', 'ust-idnr', 'registergericht', 'deutschland', 'germany'
        ]
        
        text_lower = text.lower()
        matches = sum(1 for indicator in german_indicators if indicator in text_lower)
        
        return matches >= 2  # At least 2 German indicators


# Global instance
german_extractor = GermanExtractor()
