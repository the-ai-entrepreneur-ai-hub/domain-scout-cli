"""
Field Validators for Legal Data Extraction.
Validates and cleans extracted data before storage.
"""
import re
from typing import Optional, Dict, List
import phonenumbers
from phonenumbers import NumberParseException

class FieldValidators:
    """Validates and cleans extracted legal entity fields."""
    
    # Noise words that indicate bad extraction
    NOISE_WORDS = [
        'navigation', 'menu', 'cookie', 'newsletter', 'anmelden', 'login',
        'suche', 'search', 'warenkorb', 'cart', 'wishlist', 'account',
        'registrieren', 'register', 'abonnieren', 'subscribe', 'footer',
        'header', 'sidebar', 'widget', 'banner', 'popup', 'modal',
        'javascript', 'undefined', 'null', 'error', 'loading',
        # German sentence fragments (from test results)
        'unterlieg', 'haben wir', 'einer plattform', 'einfluss', 'zurück',
        'webseite', 'dieser', 'seite', 'sowie', 'werden', 'können',
        'müssen', 'sollten', 'dürfen', 'sollen', 'wurde', 'wird',
        'darüber', 'hinaus', 'jedoch', 'daher', 'somit', 'dabei',
        'zudem', 'außerdem', 'weiterhin', 'darauf', 'hierbei',
        'allen frag', 'jeweiligen', 'keinen einfluss', 'in der reg',
        'movingimag', 'des tools', 'übertrag', 'angegebenen',
        'dar. der vertrag', 'vereinsreg',
        # Common false positives from test results
        'offenlegung', 'disclosure', 'registrar', 'namesilo',
        'unicredit bank', 'paypal', 'stripe', 'klarna', 'amazon payments',
        'google analytics', 'facebook pixel', 'twitter', 'instagram',
        'datenschutz', 'impressum', 'legal notice', 'privacy policy'
    ]
    
    # VAT patterns by country
    VAT_PATTERNS = {
        'DE': r'^DE\d{9}$',
        'AT': r'^ATU\d{8}$',
        'CH': r'^CHE\d{9}(MWST)?$',
        'GB': r'^GB\d{9,12}$',
        'FR': r'^FR[A-Z0-9]{2}\d{9}$',
        'IT': r'^IT\d{11}$',
        'ES': r'^ES[A-Z0-9]\d{7}[A-Z0-9]$',
        'NL': r'^NL\d{9}B\d{2}$',
        'BE': r'^BE0\d{9}$',
        'PL': r'^PL\d{10}$',
        'PT': r'^PT\d{9}$',
        'SE': r'^SE\d{12}$',
        'DK': r'^DK\d{8}$',
        'FI': r'^FI\d{8}$',
        'IE': r'^IE\d{7}[A-Z]{1,2}$',
        'LU': r'^LU\d{8}$',
    }
    
    # Legal forms by country
    LEGAL_FORMS = {
        'DE': ['GmbH', 'AG', 'KG', 'OHG', 'GbR', 'e.K.', 'UG', 'KGaA', 'PartG', 'eG', 'e.V.'],
        'AT': ['GmbH', 'AG', 'KG', 'OG', 'GesbR', 'e.U.'],
        'CH': ['AG', 'GmbH', 'Sarl', 'SA', 'Sagl', 'KlG', 'GmbH & Co. KG'],
        'US': ['Inc.', 'Inc', 'LLC', 'Corp.', 'Corp', 'Corporation', 'Ltd.', 'LLP', 'LP', 'PC'],
        'UK': ['Ltd', 'Ltd.', 'Limited', 'PLC', 'LLP', 'CIC'],
        'FR': ['SARL', 'SA', 'SAS', 'SASU', 'EURL', 'SNC', 'SCS', 'SCA'],
        'IT': ['S.r.l.', 'Srl', 'S.p.A.', 'SpA', 'S.a.s.', 'S.n.c.'],
        'ES': ['S.L.', 'SL', 'S.A.', 'SA', 'S.L.L.', 'S.C.'],
        'NL': ['B.V.', 'BV', 'N.V.', 'NV', 'V.O.F.', 'C.V.'],
        'BE': ['BVBA', 'NV', 'CVBA', 'VOF', 'BV', 'SRL'],
    }

    @classmethod
    def validate_company_name(cls, name: str) -> Optional[str]:
        """Validate and clean company name."""
        if not name:
            return None
        
        # Handle list input (JSON-LD can return lists) - CRITICAL BUG FIX
        if isinstance(name, list):
            if not name:
                return None
            # Take first non-empty string from list
            name = next((item for item in name if isinstance(item, str) and item.strip()), '')
            if not name:
                return None
        
        # Ensure it's a string
        if not isinstance(name, str):
            return None
            
        # Convert to string if needed (handles other types)
        name = str(name)
            
        # Clean whitespace
        name = ' '.join(name.split())
        
        # Reject if too long (likely captured menu/navigation)
        if len(name) > 120:
            return None
            
        # Reject if too short
        if len(name) < 3:
            return None
            
        # Reject if contains noise words
        name_lower = name.lower()
        if any(noise in name_lower for noise in cls.NOISE_WORDS):
            return None
            
        # Reject if mostly numbers
        letter_count = sum(1 for c in name if c.isalpha())
        if letter_count < len(name) * 0.3:
            return None
            
        # Reject if contains too many special characters
        special_count = sum(1 for c in name if not c.isalnum() and c not in ' .-&')
        if special_count > len(name) * 0.2:
            return None
        
        # Reject sentence-like text (contains common sentence-ending patterns)
        sentence_patterns = [
            r'\.\s+[A-Z]',  # Period followed by capital letter
            r'\?\s*$',      # Ends with question mark
            r'!\s*$',       # Ends with exclamation
            r',\s+[a-z]',   # Comma followed by lowercase (mid-sentence)
            r'\b(der|die|das|und|oder|aber|denn|für|mit|von|zu|bei|nach|vor|über|unter|zwischen)\b',  # German articles/prepositions
        ]
        
        for pattern in sentence_patterns:
            if re.search(pattern, name, re.IGNORECASE):
                return None
        
        # Must contain at least one capital letter (proper noun)
        if not any(c.isupper() for c in name):
            return None
        
        # Reject known registrar companies and service providers
        registrar_companies = [
            'namesilo', 'godaddy', 'namecheap', 'domains by proxy',
            'whoisguard', 'perfect privacy', 'privacy protection',
            'unicredit bank austria', 'raiffeisen', 'erste bank',
            'paypal', 'stripe', 'klarna', 'amazon web services',
        ]
        
        name_lower = name.lower()
        for registrar in registrar_companies:
            if registrar in name_lower:
                return None
        
        # Reject if starts with disclosure/legal terms
        disclosure_prefixes = [
            'offenlegung', 'disclosure', 'impressum', 'legal notice',
            'datenschutz', 'privacy policy', 'terms of service',
            'nutzungsbedingungen', 'allgemeine geschäftsbedingungen'
        ]
        
        for prefix in disclosure_prefixes:
            if name_lower.startswith(prefix):
                return None
            
        return name.strip()

    @classmethod
    def validate_legal_form(cls, form: str) -> Optional[str]:
        """Validate legal form against known patterns."""
        if not form:
            return None
            
        form = form.strip()
        
        # Check against all known legal forms
        for country, forms in cls.LEGAL_FORMS.items():
            for known_form in forms:
                if form.upper() == known_form.upper():
                    return known_form
                    
        return form if len(form) <= 20 else None

    @classmethod
    def validate_vat_id(cls, vat: str) -> Optional[str]:
        """Validate VAT ID format by country."""
        if not vat:
            return None
            
        # Clean the VAT ID
        vat_clean = re.sub(r'\s', '', vat).upper()
        
        # Check against all country patterns
        for country, pattern in cls.VAT_PATTERNS.items():
            if re.match(pattern, vat_clean):
                return vat_clean
                
        return None

    @classmethod
    def validate_registration_number(cls, reg_num: str) -> Optional[str]:
        """Validate registration number format."""
        if not reg_num:
            return None
            
        reg_num = reg_num.strip()
        
        # German HRB/HRA pattern
        hrb_match = re.match(r'^(HRB|HRA)\s*(\d+)\s*([A-Z])?$', reg_num, re.IGNORECASE)
        if hrb_match:
            prefix = hrb_match.group(1).upper()
            number = hrb_match.group(2)
            suffix = hrb_match.group(3) or ''
            return f"{prefix} {number}{suffix}".strip()
            
        # UK company number (8 digits)
        uk_match = re.match(r'^(\d{8})$', reg_num)
        if uk_match:
            return uk_match.group(1)
            
        # French RCS
        rcs_match = re.match(r'^RCS\s+([A-Za-z]+)\s+(\d+)$', reg_num, re.IGNORECASE)
        if rcs_match:
            return f"RCS {rcs_match.group(1).title()} {rcs_match.group(2)}"
            
        # Generic: accept if reasonable length and contains digits
        if 3 <= len(reg_num) <= 30 and any(c.isdigit() for c in reg_num):
            return reg_num
            
        return None

    @classmethod
    def validate_address(cls, street: str = None, zip_code: str = None, 
                        city: str = None, country: str = None) -> Dict[str, str]:
        """Validate and structure address components."""
        result = {}
        
        # Validate street
        if street:
            street = ' '.join(street.split())
            if 3 <= len(street) <= 150 and not any(noise in street.lower() for noise in cls.NOISE_WORDS):
                result['street'] = street
                
        # Validate ZIP code
        if zip_code:
            zip_clean = re.sub(r'\s', '', zip_code)
            if re.match(r'^\d{4,6}$', zip_clean):  # Most European ZIPs
                result['zip'] = zip_clean
            elif re.match(r'^[A-Z]{1,2}\d{1,2}\s*\d[A-Z]{2}$', zip_clean.upper()):  # UK postcode
                result['zip'] = zip_clean.upper()
                
        # Validate city
        if city:
            city = ' '.join(city.split())
            # City should be mostly letters
            if 2 <= len(city) <= 50 and sum(1 for c in city if c.isalpha()) > len(city) * 0.7:
                result['city'] = city
                
        # Validate country
        if country:
            country = country.strip()
            # Map common variations
            country_map = {
                'deutschland': 'Germany', 'germany': 'Germany', 'de': 'Germany',
                'osterreich': 'Austria', 'austria': 'Austria', 'at': 'Austria',
                'schweiz': 'Switzerland', 'switzerland': 'Switzerland', 'ch': 'Switzerland',
                'united kingdom': 'United Kingdom', 'uk': 'United Kingdom', 'gb': 'United Kingdom',
                'england': 'United Kingdom',
                'france': 'France', 'fr': 'France',
                'italy': 'Italy', 'italia': 'Italy', 'it': 'Italy',
                'spain': 'Spain', 'espana': 'Spain', 'es': 'Spain',
                'netherlands': 'Netherlands', 'nederland': 'Netherlands', 'nl': 'Netherlands',
                'belgium': 'Belgium', 'belgique': 'Belgium', 'belgie': 'Belgium', 'be': 'Belgium',
            }
            country_lower = country.lower()
            result['country'] = country_map.get(country_lower, country.title() if len(country) > 2 else country.upper())
            
        return result

    @classmethod
    def validate_phone(cls, phone: str, country_hint: str = 'DE') -> Optional[str]:
        """Validate and format phone number."""
        if not phone:
            return None
            
        try:
            # Parse the phone number
            parsed = phonenumbers.parse(phone, country_hint)
            
            if phonenumbers.is_valid_number(parsed):
                # Format in international format
                return phonenumbers.format_number(
                    parsed, 
                    phonenumbers.PhoneNumberFormat.INTERNATIONAL
                )
        except NumberParseException:
            pass
            
        # Fallback: basic cleanup for numbers that might still be useful
        cleaned = re.sub(r'[^\d+\s\-()]', '', phone)
        if len(re.sub(r'\D', '', cleaned)) >= 7:
            return cleaned.strip()
            
        return None

    @classmethod
    def validate_email(cls, email: str) -> Optional[str]:
        """Validate email format."""
        if not email:
            return None
            
        email = email.strip().lower()
        
        # Basic email pattern
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if re.match(pattern, email):
            # Reject common placeholder/fake emails
            fake_patterns = ['example.com', 'test.com', 'email.com', 'domain.com']
            if not any(fake in email for fake in fake_patterns):
                return email
                
        return None

    @classmethod
    def validate_person_name(cls, name: str) -> Optional[str]:
        """Validate a person's name (CEO, director, etc.)."""
        if not name:
            return None
            
        name = ' '.join(name.split())
        
        # Reject if too long or too short
        if len(name) < 3 or len(name) > 80:
            return None
            
        # Reject if contains noise words
        if any(noise in name.lower() for noise in cls.NOISE_WORDS):
            return None
            
        # Should be mostly letters
        letter_count = sum(1 for c in name if c.isalpha() or c in ' .-')
        if letter_count < len(name) * 0.8:
            return None
            
        # Should not contain too many special characters
        if any(c in name for c in ['@', '#', '$', '%', '&', '*', '/', '\\']):
            return None
            
        return name

    @classmethod
    def validate_fax(cls, fax: str, country_hint: str = 'DE') -> Optional[str]:
        """Validate fax number (same as phone)."""
        return cls.validate_phone(fax, country_hint)

    @classmethod
    def calculate_data_quality_score(cls, data: Dict) -> float:
        """Calculate overall data quality score (0-100)."""
        score = 0.0
        weights = {
            'legal_name': 20,
            'legal_form': 10,
            'street_address': 15,
            'postal_code': 5,
            'city': 10,
            'country': 5,
            'registration_number': 15,
            'vat_id': 10,
            'ceo_name': 5,
            'phone': 3,
            'email': 2,
        }
        
        for field, weight in weights.items():
            if data.get(field):
                score += weight
                
        return min(score, 100.0)
