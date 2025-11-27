"""
Legal and Company Disclosure Extractor Module
Extracts comprehensive legal entity information from websites' legal notice sections.
"""
import re
import json
from typing import Dict, List, Optional, Tuple, Any
from bs4 import BeautifulSoup, Tag
from langdetect import detect
import phonenumbers
from .utils import logger

class LegalExtractor:
    def __init__(self):
        # Legal page paths in multiple languages
        self.legal_paths = [
            '/impressum', '/imprint', '/legal-notice', '/legal',
            '/mentions-legales', '/aviso-legal', '/note-legali',
            '/privacy', '/datenschutz', '/terms', '/disclaimer',
            '/about/legal', '/company/legal', '/kontakt/impressum'
        ]
        
        # Legal forms by country/region
        self.legal_forms = {
            'DE': ['GmbH', 'AG', 'KG', 'OHG', 'GbR', 'e.K.', 'UG', 'KGaA', 'PartG', 'eG'],
            'AT': ['GmbH', 'AG', 'KG', 'OG', 'GesbR', 'e.U.'],
            'CH': ['AG', 'GmbH', 'Sàrl', 'SA', 'Sagl'],
            'US': ['Inc.', 'LLC', 'Corp.', 'Corporation', 'Ltd.', 'LLP', 'LP', 'PC'],
            'UK': ['Ltd', 'Limited', 'PLC', 'LLP', 'CIC'],
            'FR': ['SARL', 'SA', 'SAS', 'EURL', 'SNC', 'SCS'],
            'IT': ['S.r.l.', 'S.p.A.', 'S.a.s.', 'S.n.c.'],
            'ES': ['S.L.', 'S.A.', 'S.L.L.', 'S.C.'],
            'NL': ['B.V.', 'N.V.', 'V.O.F.', 'C.V.'],
            'BE': ['BVBA', 'NV', 'CVBA', 'VOF']
        }
        
        # Registration patterns
        self.register_patterns = {
            # German registers - Combined patterns for common formats
            # Note: \b ensures we don't capture trailing letters like HRB 123B -> just 123
            'HRB': re.compile(r'HRB\s*[:.]?\s*(\d+)\b', re.IGNORECASE),
            'HRA': re.compile(r'HRA\s*[:.]?\s*(\d+)\b', re.IGNORECASE),
            # Amtsgericht pattern - capture city name only (1-3 words, no GmbH/AG etc)
            'Amtsgericht': re.compile(r'Amtsgericht\s+([A-Za-zÄÖÜäöüß]+(?:[\s\-][A-Za-zÄÖÜäöüß]+){0,2})(?:[,\s]+(?:HRB|HRA)|[,\s]*$)', re.IGNORECASE),
            'Registergericht': re.compile(r'Registergericht\s*[:.]?\s*([^,\n]+)', re.IGNORECASE),
            # Bug Fix #5: Combined pattern for "Handelsregister: Amtsgericht München, HRB 12345"
            'Handelsregister_Combined': re.compile(
                r'Handelsregister\s*[:.]?\s*(?:Amtsgericht\s+)?([A-Za-zÄÖÜäöüß\s\-]+?)[,\s]+(HRB|HRA)\s*(\d+)',
                re.IGNORECASE
            ),
            # Alternative: "eingetragen beim Amtsgericht München unter HRB 12345"
            'Eingetragen_Amtsgericht': re.compile(
                r'(?:eingetragen\s+(?:beim|im)\s+)?Amtsgericht\s+([A-Za-zÄÖÜäöüß\s\-]+?)(?:\s+unter\s+)?(HRB|HRA)\s*(\d+)',
                re.IGNORECASE
            ),
            
            # UK registers
            'Companies House': re.compile(r'(?:Company\s*(?:Number|No\.?)|Registration\s*(?:Number|No\.?))\s*[:.]?\s*(\d{6,8})', re.IGNORECASE),
            'Registered in England': re.compile(r'Registered\s+in\s+England(?:\s+(?:and|&)\s+Wales)?\s*(?:No\.?|Number)?\s*[:.]?\s*(\d+)', re.IGNORECASE),
            
            # French registers
            'RCS': re.compile(r'RCS\s+([A-Za-z]+)\s*[:.]?\s*(\d+)', re.IGNORECASE),
            'SIRET': re.compile(r'SIRET\s*[:.]?\s*(\d{14})', re.IGNORECASE),
            'SIREN': re.compile(r'SIREN\s*[:.]?\s*(\d{9})', re.IGNORECASE),
            
            # EU VAT
            'VAT': re.compile(r'(?:VAT|USt[-\s]?Id[-\s]?Nr\.?|UID|TVA|P\.?\s*IVA|BTW|MWST)\s*[:.]?\s*([A-Z]{2}[\s]?[\d\s]+)', re.IGNORECASE),
            
            # US registers
            'EIN': re.compile(r'EIN\s*[:.]?\s*(\d{2}-\d{7})', re.IGNORECASE),
            'Delaware': re.compile(r'Delaware\s+(?:Corporation|Company)\s*(?:File\s*)?(?:Number|No\.?)?\s*[:.]?\s*(\d+)', re.IGNORECASE)
        }
        
        # Multi-language patterns for key terms
        self.multilang_patterns = {
            'managing_director': {
                'DE': [r'Geschäftsführer:?\s*([^,\n]+)', r'Vorstand:?\s*([^,\n]+)'],
                'EN': [r'(?:Managing\s+)?Directors?:?\s*([^,\n]+)', r'CEO:?\s*([^,\n]+)'],
                'FR': [r'Gérant:?\s*([^,\n]+)', r'Directeur\s+Général:?\s*([^,\n]+)'],
                'IT': [r'Amministratore:?\s*([^,\n]+)', r'Direttore:?\s*([^,\n]+)'],
                'ES': [r'Administrador:?\s*([^,\n]+)', r'Director\s+General:?\s*([^,\n]+)']
            },
            'authorized_rep': {
                'DE': [r'Vertretungsberechtigte?r?:?\s*([^,\n]+)', r'Vertreten\s+durch:?\s*([^,\n]+)'],
                'EN': [r'Authorized\s+Representatives?:?\s*([^,\n]+)', r'Represented\s+by:?\s*([^,\n]+)'],
                'FR': [r'Représentant\s+légal:?\s*([^,\n]+)'],
                'IT': [r'Rappresentante\s+legale:?\s*([^,\n]+)'],
                'ES': [r'Representante\s+legal:?\s*([^,\n]+)']
            },
            'register_court': {
                'DE': [r'Registergericht:?\s*([^,\n]+)', r'Handelsregister:?\s*([^,\n]+)'],
                'EN': [r'Register(?:ed)?\s+(?:at|with):?\s*([^,\n]+)', r'Court\s+of\s+Registration:?\s*([^,\n]+)'],
                'FR': [r'Registre\s+du\s+Commerce:?\s*([^,\n]+)', r'Tribunal\s+de\s+Commerce:?\s*([^,\n]+)'],
                'IT': [r'Registro\s+(?:delle\s+)?Imprese:?\s*([^,\n]+)'],
                'ES': [r'Registro\s+Mercantil:?\s*([^,\n]+)']
            },
            'legal_form': {
                'DE': [r'Rechtsform:?\s*([^,\n]+)', r'Gesellschaftsform:?\s*([^,\n]+)'],
                'EN': [r'Legal\s+Form:?\s*([^,\n]+)', r'Company\s+Type:?\s*([^,\n]+)'],
                'FR': [r'Forme\s+juridique:?\s*([^,\n]+)'],
                'IT': [r'Forma\s+giuridica:?\s*([^,\n]+)'],
                'ES': [r'Forma\s+jurídica:?\s*([^,\n]+)']
            }
        }
        
        # Legal keywords for page detection
        self.legal_keywords = {
            'DE': ['impressum', 'handelsregister', 'geschäftsführer', 'vertretungsberechtigter', 
                   'registergericht', 'ust-idnr', 'amtsgericht', 'sitz der gesellschaft'],
            'EN': ['legal notice', 'company registration', 'registered office', 'directors',
                   'company number', 'vat number', 'registered address', 'legal information'],
            'FR': ['mentions légales', 'siège social', 'rcs', 'siret', 'gérant', 'siren',
                   'tribunal de commerce', 'forme juridique'],
            'IT': ['note legali', 'sede legale', 'registro imprese', 'partita iva',
                   'rappresentante legale', 'forma giuridica'],
            'ES': ['aviso legal', 'registro mercantil', 'domicilio social', 'nif', 'cif',
                   'administrador', 'forma jurídica']
        }
        
        # DPO patterns
        self.dpo_patterns = [
            re.compile(r'(?:Data\s+Protection\s+Officer|DPO|Datenschutzbeauftragter)\s*[:.]?\s*([^,\n]+)', re.IGNORECASE),
            re.compile(r'(?:Privacy\s+Officer|Délégué\s+à\s+la\s+protection)\s*[:.]?\s*([^,\n]+)', re.IGNORECASE)
        ]
        
        # Fax patterns
        self.fax_patterns = [
            re.compile(r'(?:Fax|Telefax|Télécopie)\s*[:.]?\s*([\+\d\s\-\(\)]+)', re.IGNORECASE)
        ]

    def detect_language(self, text: str) -> str:
        """Detect the primary language of the text."""
        try:
            return detect(text[:1000])  # Use first 1000 chars for speed
        except:
            return 'en'  # Default to English

    def extract_legal_form(self, text: str) -> Optional[str]:
        """Extract the legal form of the company."""
        text_upper = text.upper()
        
        # Check all known legal forms
        for country, forms in self.legal_forms.items():
            for form in forms:
                # Create pattern with word boundaries
                pattern = r'\b' + re.escape(form.upper()) + r'\b'
                if re.search(pattern, text_upper):
                    return form
                    
        # Check language-specific patterns
        lang = self.detect_language(text)
        lang_key = lang.upper()[:2] if lang else 'EN'
        
        if lang_key in self.multilang_patterns['legal_form']:
            for pattern_str in self.multilang_patterns['legal_form'][lang_key]:
                pattern = re.compile(pattern_str, re.IGNORECASE)
                match = pattern.search(text)
                if match:
                    return match.group(1).strip()
                    
        return None

    def extract_registration_info(self, text: str) -> Dict[str, str]:
        """Extract company registration information."""
        registration = {}
        
        # Bug Fix #5: First try combined patterns that capture court + number together
        combined_patterns = ['Handelsregister_Combined', 'Eingetragen_Amtsgericht']
        for pattern_name in combined_patterns:
            pattern = self.register_patterns.get(pattern_name)
            if pattern:
                match = pattern.search(text)
                if match:
                    court = match.group(1).strip()
                    reg_type = match.group(2).upper()
                    reg_num = match.group(3)
                    registration['register_court'] = f"Amtsgericht {court}"
                    registration['registration_number'] = f"{reg_type} {reg_num}"
                    registration['register_type'] = f"Handelsregister {'B' if reg_type == 'HRB' else 'A'}"
                    break
        
        # Check all registration patterns
        for reg_type, pattern in self.register_patterns.items():
            # Skip combined patterns already processed
            if reg_type in combined_patterns:
                continue
                
            matches = pattern.findall(text)
            if matches:
                if reg_type == 'VAT':
                    registration['vat_id'] = matches[0].strip()
                elif reg_type == 'HRB' and not registration.get('registration_number'):
                    registration['registration_number'] = f"HRB {matches[0]}"
                    registration['register_type'] = 'Handelsregister B'
                elif reg_type == 'HRA' and not registration.get('registration_number'):
                    registration['registration_number'] = f"HRA {matches[0]}"
                    registration['register_type'] = 'Handelsregister A'
                elif reg_type == 'Amtsgericht' and not registration.get('register_court'):
                    registration['register_court'] = f"Amtsgericht {matches[0].strip()}"
                elif reg_type == 'Companies House':
                    registration['registration_number'] = matches[0]
                    registration['register_type'] = 'Companies House'
                elif reg_type == 'RCS':
                    registration['registration_number'] = f"RCS {matches[0][0]} {matches[0][1]}"
                    registration['register_type'] = 'RCS'
                    registration['register_court'] = matches[0][0]
                elif reg_type == 'SIRET':
                    registration['siret'] = matches[0]
                elif reg_type == 'SIREN':
                    registration['siren'] = matches[0]
                elif reg_type == 'EIN':
                    registration['tax_id'] = matches[0]
                    registration['register_type'] = 'IRS'
                    
        return registration

    def extract_representatives(self, text: str) -> Dict[str, Any]:
        """Extract information about company representatives."""
        representatives = {
            'ceo': None,
            'directors': [],
            'authorized_reps': []
        }
        
        lang = self.detect_language(text)
        lang_key = lang.upper()[:2] if lang else 'EN'
        
        # Extract managing directors/CEO
        if lang_key in self.multilang_patterns['managing_director']:
            for pattern_str in self.multilang_patterns['managing_director'][lang_key]:
                pattern = re.compile(pattern_str, re.IGNORECASE | re.MULTILINE)
                matches = pattern.findall(text)
                if matches:
                    # Clean and split names
                    for match in matches:
                        names = re.split(r'[,;]|\s+und\s+|\s+and\s+|\s+et\s+', match)
                        for name in names:
                            name = name.strip()
                            if name and len(name) > 3 and not any(char.isdigit() for char in name):
                                if not representatives['ceo']:
                                    representatives['ceo'] = name
                                else:
                                    representatives['directors'].append(name)
                                    
        # Extract authorized representatives
        if lang_key in self.multilang_patterns['authorized_rep']:
            for pattern_str in self.multilang_patterns['authorized_rep'][lang_key]:
                pattern = re.compile(pattern_str, re.IGNORECASE | re.MULTILINE)
                matches = pattern.findall(text)
                if matches:
                    for match in matches:
                        names = re.split(r'[,;]|\s+und\s+|\s+and\s+|\s+et\s+', match)
                        for name in names:
                            name = name.strip()
                            if name and len(name) > 3 and not any(char.isdigit() for char in name):
                                representatives['authorized_reps'].append(name)
                                
        # Remove duplicates
        representatives['directors'] = list(set(representatives['directors']))
        representatives['authorized_reps'] = list(set(representatives['authorized_reps']))
        
        return representatives

    def extract_addresses(self, soup: BeautifulSoup, text: str) -> Dict[str, Dict[str, str]]:
        """Extract registered and postal addresses."""
        addresses = {
            'registered': {},
            'postal': {}
        }
        
        # Look for address microformats
        for addr_tag in soup.find_all('address'):
            addr_text = addr_tag.get_text(separator=' ', strip=True)
            if 'registered' in addr_text.lower() or 'sitz' in addr_text.lower():
                addresses['registered'] = self.parse_address(addr_text)
            else:
                addresses['postal'] = self.parse_address(addr_text)
                
        # Look for structured data addresses
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and 'address' in data:
                    addr = data['address']
                    if isinstance(addr, dict):
                        parsed = {
                            'street': addr.get('streetAddress', ''),
                            'zip': addr.get('postalCode', ''),
                            'city': addr.get('addressLocality', ''),
                            'state': addr.get('addressRegion', ''),
                            'country': addr.get('addressCountry', '')
                        }
                        if not addresses['registered']:
                            addresses['registered'] = parsed
                        elif not addresses['postal']:
                            addresses['postal'] = parsed
            except:
                pass
                
        # Pattern-based extraction if not found
        if not addresses['registered']:
            # Look for registered office patterns
            patterns = [
                re.compile(r'(?:Sitz der Gesellschaft|Registered Office|Siège social|Sede legale)[:.]?\s*([^,\n]+(?:,\s*[^,\n]+){2,4})', re.IGNORECASE),
                re.compile(r'(?:Firmensitz|Company Seat|Domicilio social)[:.]?\s*([^,\n]+(?:,\s*[^,\n]+){2,4})', re.IGNORECASE)
            ]
            
            for pattern in patterns:
                match = pattern.search(text)
                if match:
                    addresses['registered'] = self.parse_address(match.group(1))
                    break
        
        # NEW: Direct German address pattern extraction
        if not addresses['registered'].get('street'):
            # Pattern: "Straße/Weg/Platz NUMBER, ZIP CITY" or "Straße NUMBER ZIP CITY"
            de_addr_patterns = [
                # Street Number, ZIP City
                re.compile(
                    r'([A-Za-zäöüÄÖÜß\.\-]+(?:straße|str\.|weg|platz|allee|ring|gasse|damm|ufer|chaussee))\s*(\d+[a-zA-Z]?)\s*[,\s]+(\d{5})\s+([A-Za-zäöüÄÖÜß\-]+)',
                    re.IGNORECASE
                ),
                # Street NUMBER\nZIP City (multiline)
                re.compile(
                    r'([A-Za-zäöüÄÖÜß\.\-]+(?:straße|str\.|weg|platz|allee|ring|gasse|damm|ufer|chaussee))\s+(\d+[a-zA-Z]?)\s+(\d{5})\s+([A-Za-zäöüÄÖÜß\-]+)',
                    re.IGNORECASE
                ),
            ]
            for pattern in de_addr_patterns:
                match = pattern.search(text)
                if match:
                    addresses['registered'] = {
                        'street': f"{match.group(1)} {match.group(2)}".strip(),
                        'zip': match.group(3),
                        'city': match.group(4).strip(),
                        'state': '',
                        'country': 'Germany'
                    }
                    break
                    
        return addresses

    def parse_address(self, address_text: str) -> Dict[str, str]:
        """Parse an address string into components with multi-line and international support."""
        parsed = {
            'street': '',
            'zip': '',
            'city': '',
            'state': '',
            'country': ''
        }
        
        # Clean and normalize the address (handle multi-line)
        address_text = re.sub(r'[\n\r]+', ', ', address_text.strip())
        address_text = re.sub(r'\s+', ' ', address_text)
        address_text = re.sub(r',\s*,', ',', address_text)
        
        # Country detection with removal
        countries = {
            'Germany': ['Germany', 'Deutschland', 'DE'],
            'United Kingdom': ['United Kingdom', 'UK', 'GB', 'England', 'Wales', 'Scotland'],
            'France': ['France', 'FR'],
            'Italy': ['Italy', 'Italia', 'IT'],
            'Spain': ['Spain', 'España', 'ES'],
            'Austria': ['Austria', 'Österreich', 'AT'],
            'Switzerland': ['Switzerland', 'Schweiz', 'Suisse', 'Svizzera', 'CH'],
            'Netherlands': ['Netherlands', 'Nederland', 'NL'],
            'Belgium': ['Belgium', 'België', 'Belgique', 'BE'],
            'USA': ['United States', 'USA', 'US'],
            'Ireland': ['Ireland', 'IE'],
            'Poland': ['Poland', 'Polska', 'PL'],
            'Czech Republic': ['Czech Republic', 'Czechia', 'CZ'],
        }
        
        for country, variations in countries.items():
            for var in variations:
                pattern = re.compile(r'\b' + re.escape(var) + r'\b', re.IGNORECASE)
                if pattern.search(address_text):
                    parsed['country'] = country
                    address_text = pattern.sub('', address_text).strip(' ,')
                    break
            if parsed['country']:
                break
        
        # International ZIP code patterns
        zip_patterns = [
            # UK: AA9A 9AA, A9A 9AA, A9 9AA, A99 9AA, AA9 9AA, AA99 9AA
            (r'\b([A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2})\b', 'UK'),
            # Germany/Austria/Switzerland (4-5 digits): 12345, 1234
            (r'\b(\d{4,5})\b', 'DE'),
            # France: 5 digits
            (r'\b(\d{5})\b', 'FR'),
            # US: 5 digits or 5+4
            (r'\b(\d{5}(?:-\d{4})?)\b', 'US'),
        ]
        
        for pattern_str, country_hint in zip_patterns:
            match = re.search(pattern_str, address_text, re.IGNORECASE)
            if match:
                parsed['zip'] = match.group(1).strip()
                break
        
        # German/EU address pattern: "Straße 123, 12345 Stadt"
        # Improved Regex: Captures street name more precisely, max 4 words prefix
        de_pattern = re.compile(
            r'((?:(?:\b[A-Za-zäöüÄÖÜß\.\-]+\s+){0,4}[A-Za-zäöüÄÖÜß\.\-]+(?:straße|str\.|weg|platz|allee|ring|gasse|damm)))\s*(\d+[a-zA-Z]?)?'
            r'[,\s]+(\d{4,5})\s+([A-Za-zäöüÄÖÜß\s\-]+)',
            re.IGNORECASE
        )
        de_match = de_pattern.search(address_text)
        if de_match:
            street_name = de_match.group(1).strip()
            street_num = de_match.group(2) or ''
            parsed['street'] = f"{street_name} {street_num}".strip()
            parsed['zip'] = de_match.group(3)
            # Clean city name - extract only the first 1-2 words
            city = de_match.group(4).strip()
            # Split on common noise and take first part
            noise_patterns = [
                r'\s+Tel[.:\s]', r'\s+Fax[.:\s]', r'\s+Mobil', r'\s+E-?Mail', r'\s+Web', 
                r'\s+Userservice', r'\s+Kontakt', r'\s+Telefon', r'\s+Geschäftsführ',
                r'\s+Registergericht', r'\s+HRB', r'\s+USt', r'\s+Postfach', r'\s+https?:',
                r'\s+[A-ZÄÖÜ][a-zäöüß]+\s+[A-ZÄÖÜ][a-zäöüß]+\s+GmbH',  # Stop at "Name Name GmbH"
            ]
            for noise in noise_patterns:
                city = re.split(noise, city, flags=re.IGNORECASE)[0].strip()
            # Also limit to max 3 words
            city_words = city.split()[:3]
            parsed['city'] = ' '.join(city_words)
            return parsed
        
        # UK address pattern: "123 Street Name, City, POSTCODE"
        uk_pattern = re.compile(
            r'(\d+[a-zA-Z]?\s+[A-Za-z\s\.\-]+?)[,\s]+([A-Za-z\s]+?)[,\s]+([A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2})',
            re.IGNORECASE
        )
        uk_match = uk_pattern.search(address_text)
        if uk_match:
            parsed['street'] = uk_match.group(1).strip()
            parsed['city'] = uk_match.group(2).strip()
            parsed['zip'] = uk_match.group(3).strip()
            return parsed
        
        # Fallback: Split by comma and infer components
        parts = [p.strip() for p in address_text.split(',') if p.strip()]
        
        if parts:
            # First non-empty part is usually street
            parsed['street'] = parts[0]
            
            # Look for ZIP+city in remaining parts
            for part in parts[1:]:
                if parsed['zip'] and parsed['zip'] in part:
                    # This part contains ZIP, extract city
                    parsed['city'] = part.replace(parsed['zip'], '').strip()
                elif re.match(r'^\d{4,5}\s+\S+', part):
                    # Looks like "12345 City"
                    match = re.match(r'^(\d{4,5})\s+(.+)$', part)
                    if match:
                        parsed['zip'] = match.group(1)
                        parsed['city'] = match.group(2).strip()
                elif not parsed['city'] and len(part) > 2:
                    # Assume it's city if we don't have one yet
                    parsed['city'] = part
                    
        return parsed

    def extract_legal_contacts(self, soup: BeautifulSoup, text: str) -> Dict[str, str]:
        """Extract legal-specific contact information."""
        contacts = {
            'legal_email': None,
            'legal_phone': None,
            'fax': None,
            'dpo_email': None,
            'dpo_name': None
        }
        
        # Extract DPO information
        for pattern in self.dpo_patterns:
            match = pattern.search(text)
            if match:
                dpo_info = match.group(1).strip()
                # Check if it contains an email
                email_pattern = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
                email_match = email_pattern.search(dpo_info)
                if email_match:
                    contacts['dpo_email'] = email_match.group(0)
                    contacts['dpo_name'] = dpo_info.replace(email_match.group(0), '').strip(' ,')
                else:
                    contacts['dpo_name'] = dpo_info
                    
        # Extract fax number
        for pattern in self.fax_patterns:
            match = pattern.search(text)
            if match:
                contacts['fax'] = match.group(1).strip()
                
        # Look for legal department email
        legal_email_pattern = re.compile(r'(?:legal|recht|juridique)[@\w\.-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', re.IGNORECASE)
        legal_email = legal_email_pattern.search(text)
        if legal_email:
            contacts['legal_email'] = legal_email.group(0)
            
        return contacts

    def is_legal_page(self, soup: BeautifulSoup, url: str, text: str) -> Tuple[bool, float]:
        """Determine if a page contains legal information and confidence score."""
        score = 0.0
        max_score = 100.0
        
        # Ensure text is not None
        text = text or ""
        url = url or ""
        
        # Check URL
        url_lower = url.lower()
        for path in self.legal_paths:
            if path in url_lower:
                score += 30
                break
                
        # Check title
        title = soup.title.string.lower() if soup.title and soup.title.string else ""
        legal_title_keywords = ['impressum', 'legal', 'imprint', 'mentions', 'aviso']
        if any(kw in title for kw in legal_title_keywords):
            score += 20
            
        # Check content for legal keywords
        text_lower = text.lower()
        keyword_density = 0
        
        # Detect language and use appropriate keywords
        lang = self.detect_language(text)
        lang_key = lang.upper()[:2] if lang else 'EN'
        
        if lang_key in self.legal_keywords:
            keywords = self.legal_keywords[lang_key]
            for keyword in keywords:
                if keyword in text_lower:
                    keyword_density += 1
                    
        # Score based on keyword density
        if keyword_density >= 5:
            score += 30
        elif keyword_density >= 3:
            score += 20
        elif keyword_density >= 1:
            score += 10
            
        # Check for registration numbers
        has_registration = False
        for pattern in self.register_patterns.values():
            if pattern.search(text):
                has_registration = True
                break
                
        if has_registration:
            score += 20
            
        confidence = min(score / max_score, 1.0) * 100
        is_legal = confidence >= 40  # Consider it a legal page if confidence >= 40%
        
        return is_legal, confidence

    def extract(self, html: str, url: str) -> Dict[str, Any]:
        """Main extraction method for legal information."""
        try:
            soup = BeautifulSoup(html, 'lxml')
            
            # Clean HTML
            for tag in soup(['script', 'style', 'noscript']):
                tag.decompose()
                
            text = soup.get_text(separator=' ', strip=True)
            
            # Check if this is a legal page
            is_legal, confidence = self.is_legal_page(soup, url, text)
            
            if not is_legal:
                return {
                    'status': 'NOT_LEGAL_PAGE',
                    'confidence': confidence
                }
                
            # Extract all legal information
            result = {
                'status': 'SUCCESS',
                'confidence': confidence,
                'legal_notice_url': url
            }
            
            # Extract legal form
            legal_form = self.extract_legal_form(text)
            if legal_form:
                result['legal_form'] = legal_form
                
            # Extract registration information
            registration = self.extract_registration_info(text)
            result.update(registration)
            
            # Extract representatives
            representatives = self.extract_representatives(text)
            result.update(representatives)
            
            # Extract addresses
            addresses = self.extract_addresses(soup, text)
            for addr_type, addr_data in addresses.items():
                if addr_data:
                    for key, value in addr_data.items():
                        result[f'{addr_type}_{key}'] = value
                        
            # Extract legal contacts
            contacts = self.extract_legal_contacts(soup, text)
            result.update(contacts)
            
            # Extract company name from legal context
            legal_name = self.extract_legal_name(text, legal_form)
            if legal_name:
                result['legal_name'] = legal_name
                
            return result
            
        except Exception as e:
            logger.error(f"Legal extraction error: {e}")
            return {
                'status': 'EXTRACTION_FAILED',
                'error': str(e)
            }

    def clean_legal_name(self, name: str) -> Optional[str]:
        """Clean junk from legal name."""
        if not name:
            return None
            
        # Junk prefixes to strip (Case Insensitive)
        junk_prefixes = [
            r"^.*?(?=\b[A-ZÄÖÜ][a-zäöüß]*(?:\s+[A-ZÄÖÜ][a-zäöüß]*)*\s+(?:GmbH|AG|KG|Ltd|Inc|SE)\b)",  # Strip everything before Company + LegalForm
            r"verantwortlich[.:\s]+(?:für\s+den\s+inhalt)?[.:\s]*", 
            r"text-\s*und\s+data-mining[^A-Z]*",
            r"impressum\s*(?:angaben\s+gemäß)?\s*[§0-9a-z\s]*[.:]*",
            r"herausgeber[.:\s]*", 
            r"angaben\s+gemäß\s+§\s*\d+\s+tmg",
            r"für\s+das\s+angebot\s+unter[.:\s]*",
            r"responsible\s+for[.:\s]*", 
            r"provider\s+identification[.:\s]*",
            r"datenschutzhinweise[.:\s]*", 
            r"name\s+und\s+anschrift[.:\s]*",
            r"firmensitz\s+und\s+standort[.:\s]*",
            r"information\s+(?:about|über)[.:\s]*",
            r"geschäftsführer(?:in)?[.:\s]*",
            r"geschäftsführung[.:\s]*",
            r"(?:amtsgericht|registergericht)\s+[a-zäöüß\s\-]+\s*(?:hrb|hra)\s*\d+.*",
            r"(?:hrb|hra)\s*\d+.*",
            r"erin[.:\s]+",
            r"er[.:\s]+",
            r"so\s+erreichen\s+sie\s+uns.*",
            r"kontakt\s+zu\s+.*",
            # NEW: More junk patterns (applied to full string, not just start)
            r"adresse\s+",
            r"anschrift\s+",
            r"über\s+uns.*",
            r"^verlag\s+",
            r"^die\s+",
            r"^der\s+",
            r"^d[A-Z]",  # Lowercase 'd' followed by uppercase (encoding issue)
            r"ein\s+partner.*",
            r"triff\s+das\s+team.*",
            r"jobs\s+presse.*",
            r"siehe\s+nachfolgend.*",
            r"im\s+einzelnen\s+aufgelistet.*",
            r"essen\s+&\s+trinken.*",
            r"fitness\s+&\s+wellness.*",
        ]
        
        cleaned = name
        for pattern in junk_prefixes:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
        
        # Truncate at registration info (Amtsgericht, HRB, etc.)
        truncate_patterns = [
            r'\s+Amtsgericht\s+.*',
            r'\s+Registergericht\s+.*',
            r'\s+HRB\s+\d+.*',
            r'\s+HRA\s+\d+.*',
            r'\s+eingetragen\s+.*',
        ]
        for pattern in truncate_patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
            
        # Remove leading/trailing non-alphanumeric
        cleaned = cleaned.strip(" \t\n\r:.,;-")
        
        # Check if it looks like a real name
        if len(cleaned) < 3:
            return None
            
        # If it's just a legal form (e.g. "GmbH"), it's junk
        if cleaned.lower() in [f.lower() for forms in self.legal_forms.values() for f in forms]:
            return None
            
        return cleaned

    def extract_legal_name(self, text: str, legal_form: Optional[str] = None) -> Optional[str]:
        """Extract the official legal name of the company."""
        candidates = []
        
        patterns = [
            # German patterns
            re.compile(r'(?:Firma|Firmenname|Gesellschaft)[:.]?\s*([^,\n]+)', re.IGNORECASE),
            # English patterns
            re.compile(r'(?:Company Name|Legal Name|Registered Name)[:.]?\s*([^,\n]+)', re.IGNORECASE),
            # French patterns
            re.compile(r'(?:Raison sociale|Dénomination sociale)[:.]?\s*([^,\n]+)', re.IGNORECASE),
            # Italian patterns
            re.compile(r'(?:Ragione sociale|Denominazione)[:.]?\s*([^,\n]+)', re.IGNORECASE),
            # Spanish patterns
            re.compile(r'(?:Razón social|Denominación social)[:.]?\s*([^,\n]+)', re.IGNORECASE)
        ]
        
        for pattern in patterns:
            match = pattern.search(text)
            if match:
                raw_name = match.group(1)
                cleaned = self.clean_legal_name(raw_name)
                if cleaned:
                    candidates.append((cleaned, 10)) # High priority

        # Try to find company name with legal form
        if legal_form:
            # Look for [Name] [Legal Form] - more restrictive pattern
            # Company names typically: 1-5 capitalized words + legal form
            # Examples: "Telekom Deutschland GmbH", "STRATO GmbH", "Otto GmbH"
            pattern = re.compile(
                rf'((?:[A-ZÄÖÜ][a-zäöüß]*|[A-ZÄÖÜ0-9]+)(?:[\s&\-\.]+(?:[A-ZÄÖÜ][a-zäöüß]*|[A-ZÄÖÜ0-9]+)){{0,4}}\s+{re.escape(legal_form)})',
                re.MULTILINE
            )
            matches = pattern.findall(text)
            for match in matches:
                cleaned = self.clean_legal_name(match)
                if cleaned and len(cleaned) > 5:
                    candidates.append((cleaned, 5))

        if candidates:
            candidates.sort(key=lambda x: x[1], reverse=True)
            return candidates[0][0]
            
        return None

    def validate_vat_number(self, vat_number: str) -> bool:
        """Validate VAT number format (basic validation)."""
        # Remove spaces and uppercase
        vat = vat_number.replace(' ', '').upper()
        
        # Basic VAT patterns by country
        vat_patterns = {
            'AT': r'^ATU\d{8}$',
            'BE': r'^BE0\d{9}$',
            'DE': r'^DE\d{9}$',
            'FR': r'^FR[A-Z0-9]{2}\d{9}$',
            'GB': r'^GB\d{9}$|^GB\d{12}$',
            'IT': r'^IT\d{11}$',
            'NL': r'^NL\d{9}B\d{2}$',
            'ES': r'^ES[A-Z]\d{7}[A-Z0-9]$|^ES\d{8}[A-Z]$',
            'CH': r'^CHE\d{9}$'
        }
        
        # Check country code
        country_code = vat[:2]
        if country_code in vat_patterns:
            pattern = re.compile(vat_patterns[country_code])
            return bool(pattern.match(vat))
            
        return False
