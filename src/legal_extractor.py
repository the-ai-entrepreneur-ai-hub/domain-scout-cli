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
from urllib.parse import urlparse
from .utils import logger
from .validator import DataValidator

import trafilatura

# Import GLiNER conditionally to avoid crashing if not installed or model fails
try:
    from gliner import GLiNER
    GLINER_AVAILABLE = True
except ImportError:
    GLINER_AVAILABLE = False
    logger.warning("GLiNER library not found. Falling back to regex-only extraction.")

class LegalExtractor:
    # Known false positive organization names (tech companies, services, etc.)
    FALSE_POSITIVE_ORGS = {
        'google', 'facebook', 'meta', 'microsoft', 'apple', 'amazon', 'twitter', 'x',
        'linkedin', 'instagram', 'youtube', 'tiktok', 'whatsapp', 'telegram',
        'nginx', 'apache', 'cloudflare', 'wordpress', 'jquery', 'bootstrap',
        'analytics', 'adsense', 'adwords', 'recaptcha', 'captcha',
        'cookie', 'cookies', 'gdpr', 'dsgvo', 'datenschutz', 'privacy',
        'bundesagentur', 'bundesamt', 'ministerium', 'regierung',
        'server', 'hosting', 'domain', 'ssl', 'https', 'http',
        'contact', 'kontakt', 'impressum', 'imprint', 'legal',
        'navigation', 'menu', 'header', 'footer', 'sidebar',
    }
    
    # Third-party/partner section indicators to EXCLUDE
    PARTNER_INDICATORS = [
        'konzeption', 'gestaltung', 'programmierung', 'umsetzung', 'realisierung',
        'design', 'agentur', 'webdesign', 'webentwicklung', 'technische umsetzung',
        'partner', 'powered by', 'content management', 'cms', 'hosting',
        'typo3', 'wordpress', 'drupal', 'joomla', 'contentful',
        'bildnachweis', 'bildrechte', 'fotos', 'fotograf', 'fotografie',
        'übersetzung', 'translation', 'lektorat',
        'streitbeilegung', 'streitschlichtung', 'os-plattform', 'odr',
        'copyright', 'urheberrecht', 'haftungsausschluss', 'disclaimer',
    ]
    
    def __init__(self):
        # Initialize Validator
        self.validator = DataValidator()
        
        # Initialize GLiNER model
        self.model = None
        if GLINER_AVAILABLE:
            try:
                # Use the multi-PII model which is excellent for organization names and addresses
                logger.info("Loading GLiNER model (urchade/gliner_multi_pii-v1)...")
                self.model = GLiNER.from_pretrained("urchade/gliner_multi_pii-v1")
                logger.info("GLiNER model loaded successfully.")
            except Exception as e:
                logger.error(f"Failed to load GLiNER model: {e}. Falling back to regex.")
                self.model = None

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
        
        # Multi-language patterns for key terms (more restrictive to avoid garbage)
        self.multilang_patterns = {
            'managing_director': {
                # Require colon or "ist" after title, then capture person name (First Last format)
                'DE': [
                    r'Geschäftsführer(?:in)?[:\s]+(?:ist\s+)?([A-ZÄÖÜ][a-zäöüß]+(?:\s+(?:von\s+|van\s+|de\s+)?[A-ZÄÖÜ][a-zäöüß\-]+)+)',
                    r'Geschäftsführer(?:in)?[:\s]+(?:Herr|Frau)?\s*([A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß\-]+)+)',
                    r'(?:^|\n)Geschäftsführer(?:in)?[:\s]+([A-ZÄÖÜ][a-zäöüß\.\-]+(?:\s+[A-ZÄÖÜ][a-zäöüß\.\-]+)+)',
                ],
                'EN': [r'(?:Managing\s+)?Director[s]?[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z\-]+)+)', r'CEO[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z\-]+)+)'],
                'FR': [r'Gérant[:\s]+([A-Z][a-zéèêëàâäùûüôöîï]+(?:\s+[A-Z][a-zéèêëàâäùûüôöîï\-]+)+)'],
                'IT': [r'Amministratore[:\s]+([A-Z][a-zìòàùè]+(?:\s+[A-Z][a-zìòàùè\-]+)+)'],
                'ES': [r'Administrador[:\s]+([A-Z][a-záéíóúñ]+(?:\s+[A-Z][a-záéíóúñ\-]+)+)']
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

    def isolate_impressum_section(self, soup: BeautifulSoup, url: str) -> Tuple[Optional[BeautifulSoup], str]:
        """
        Isolate the PRIMARY Impressum section, excluding partner/third-party info.
        Returns (isolated_soup, isolated_text) or (None, full_text) if isolation fails.
        """
        # Remove nav, footer, header, aside, scripts first
        for tag in soup.find_all(['nav', 'script', 'style', 'noscript', 'aside']):
            tag.decompose()
        
        # Try to find Impressum section by ID or class
        impressum_patterns = ['impressum', 'imprint', 'legal-notice', 'legal_notice', 'legalnotice']
        impressum_section = None
        
        # 1. Look for main content area with impressum id/class
        for pattern in impressum_patterns:
            # Check by ID
            section = soup.find(id=re.compile(pattern, re.IGNORECASE))
            if section:
                impressum_section = section
                break
            # Check by class
            section = soup.find(class_=re.compile(pattern, re.IGNORECASE))
            if section:
                impressum_section = section
                break
        
        # 2. Look for article or main tag
        if not impressum_section:
            main = soup.find('main') or soup.find('article')
            if main:
                impressum_section = main
        
        # 3. Look for div with main content classes
        if not impressum_section:
            for class_name in ['content', 'main-content', 'page-content', 'entry-content', 'post-content']:
                section = soup.find('div', class_=re.compile(class_name, re.IGNORECASE))
                if section:
                    impressum_section = section
                    break
        
        # 4. Find heading "Impressum" and extract content until next major section
        if not impressum_section:
            for h_tag in soup.find_all(['h1', 'h2', 'h3']):
                if h_tag.get_text(strip=True).lower() in ['impressum', 'imprint', 'legal notice']:
                    # Get parent container
                    parent = h_tag.find_parent(['section', 'div', 'article'])
                    if parent:
                        impressum_section = parent
                        break
        
        if not impressum_section:
            # Fallback: return full content
            full_text = soup.get_text(separator='\n', strip=True)
            return None, full_text
        
        # Now filter OUT partner/third-party sections from the impressum
        filtered_soup = BeautifulSoup(str(impressum_section), 'lxml')
        
        # Find and remove partner sections
        for element in filtered_soup.find_all(['div', 'section', 'p', 'h2', 'h3', 'h4']):
            element_text = element.get_text(strip=True).lower()
            
            # Check if this element starts a partner/third-party section
            is_partner_section = False
            for indicator in self.PARTNER_INDICATORS:
                if indicator in element_text[:100]:  # Check first 100 chars
                    is_partner_section = True
                    break
            
            if is_partner_section:
                # Remove this element and all following siblings until next major heading
                element.decompose()
        
        # Extract the PRIMARY company info (usually first address block)
        # Look for "Herausgeber" or "Angaben gemäß" or first address
        primary_section = None
        for heading in filtered_soup.find_all(['strong', 'b', 'h2', 'h3', 'p']):
            heading_text = heading.get_text(strip=True).lower()
            if any(kw in heading_text for kw in ['herausgeber', 'angaben gemäß', 'anbieter', 'betreiber', 'dienstanbieter']):
                # This is the primary company section
                parent = heading.find_parent(['div', 'section']) or heading.parent
                if parent:
                    primary_section = parent
                    break
        
        # Get text from filtered soup
        filtered_text = filtered_soup.get_text(separator='\n', strip=True)
        
        # If we found a primary section, prioritize its content
        if primary_section:
            primary_text = primary_section.get_text(separator='\n', strip=True)
            # Prepend primary section to ensure it's processed first
            filtered_text = primary_text + '\n' + filtered_text
        
        return filtered_soup, filtered_text

    def extract_primary_company_block(self, text: str, domain: str) -> str:
        """
        Extract only the PRIMARY company information block from impressum text.
        Less aggressive - only stops at CLEAR partner sections.
        """
        lines = text.split('\n')
        primary_lines = []
        in_partner_section = False
        
        # Only these indicate START of partner section (must be at line start)
        partner_section_starts = [
            r'^(?:konzeption|gestaltung|design|programmierung|umsetzung|realisierung)\s*(?:und|&|:|\s*$)',
            r'^(?:technische\s+umsetzung|website\s+design|webdesign)',
            r'^(?:powered\s+by|hosted\s+by|provided\s+by|ein\s+angebot\s+von)',
            r'^(?:bildnachweis|bildrechte|fotos?:)',
            r'^(?:online-?streitbeilegung|streitschlichtung|os-plattform)',
            r'^(?:haftungsausschluss|disclaimer|copyright\s*©)',
        ]
        
        for line in lines:
            line_lower = line.lower().strip()
            
            # Skip empty lines at start
            if not primary_lines and not line.strip():
                continue
            
            # Check if this line STARTS a partner section
            for pattern in partner_section_starts:
                if re.match(pattern, line_lower):
                    in_partner_section = True
                    break
            
            if in_partner_section:
                # Check if we're back to main content
                main_content_patterns = [
                    r'^(?:kontakt|adresse|anschrift|sitz|postanschrift)',
                    r'^(?:telefon|tel\.|fax|e-mail|email)',
                    r'^(?:geschäftsführer|vorstand|vertretungsberechtigter)',
                    r'^(?:handelsregister|amtsgericht|hrb)',
                ]
                for pattern in main_content_patterns:
                    if re.match(pattern, line_lower):
                        in_partner_section = False
                        break
                
                if in_partner_section:
                    continue
            
            primary_lines.append(line)
            
            # Allow more lines for complete extraction
            if len(primary_lines) > 60:
                break
        
        return '\n'.join(primary_lines)

    def validate_company_name_for_domain(self, company_name: str, domain: str) -> bool:
        """
        Validate that the company name is likely the PRIMARY company for this domain.
        Returns True if the name seems related to the domain.
        """
        if not company_name or not domain:
            return True  # Can't validate, assume OK
        
        # Extract domain words (without TLD)
        domain_base = domain.lower().replace('www.', '')
        domain_parts = re.split(r'[.-]', domain_base)
        domain_words = [p for p in domain_parts if len(p) > 2 and p not in ['com', 'de', 'org', 'net', 'io', 'co']]
        
        company_lower = company_name.lower()
        
        # Check if any domain word appears in company name
        for word in domain_words:
            if word in company_lower:
                return True
        
        # Check if company name contains common words that wouldn't match domain
        # These are typically partner/agency companies
        partner_words = ['agentur', 'agency', 'design', 'digital', 'media', 'studio', 'solutions', 'consulting']
        for pw in partner_words:
            if pw in company_lower and not any(pw in d for d in domain_words):
                # Company has partner-type word not in domain - suspicious
                return False
        
        # If company name has legal form and no domain match, still might be OK
        legal_forms = ['gmbh', 'ag', 'kg', 'ug', 'ohg', 'ltd', 'inc', 'llc']
        has_legal_form = any(lf in company_lower for lf in legal_forms)
        
        return has_legal_form  # If it has a legal form, probably a real company

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
                elif reg_type == 'EIN':
                    registration['tax_id'] = matches[0]
                    registration['register_type'] = 'IRS'
                    
        return registration

    def extract_representatives(self, text: str) -> Dict[str, Any]:
        """Extract information about company representatives."""
        representatives = {
            'ceo': None,
            'directors': []
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
                            # Use Validator
                            validated_name = self.validator.validate_ceo_name(name)
                            if validated_name:
                                if not representatives['ceo']:
                                    representatives['ceo'] = validated_name
                                else:
                                    representatives['directors'].append(validated_name)
                                    
        # Remove duplicates
        representatives['directors'] = list(set(representatives['directors']))
        
        return representatives

    def validate_street(self, street: str) -> Optional[str]:
        """Validate and clean street address. Returns None if invalid."""
        if not street:
            return None
            
        street = ' '.join(street.split()).strip()
        
        # Length checks
        if len(street) < 5 or len(street) > 100:
            return None
            
        # Must contain at least one letter
        if not any(c.isalpha() for c in street):
            return None
            
        # Reject if it's just a label
        garbage_labels = [
            'anschrift', 'adresse', 'sitz', 'standort', 'postanschrift', 
            'address', 'location', 'registered office', 'contact',
            'kontakt', 'telefon', 'email', 'fax', 'mobil'
        ]
        if street.lower().strip(' :.') in garbage_labels:
            return None
            
        # Reject URLs
        if 'http' in street.lower() or 'www.' in street.lower():
            return None
            
        # Reject if contains common noise patterns
        noise_patterns = [
            r'@',  # Email
            r'\d{4,}',  # Long numbers (phone-like)
            r'gmbh|ag\b|ug\b|kg\b',  # Company forms in street
            r'geschäftsführer|director|ceo',
            r'registergericht|amtsgericht|hrb|hra',
            r'cookie|newsletter|datenschutz',
        ]
        street_lower = street.lower()
        for pattern in noise_patterns:
            if re.search(pattern, street_lower):
                return None
                
        return street
        
    def validate_city(self, city: str) -> Optional[str]:
        """Validate city name. Returns None if invalid."""
        if not city:
            return None
            
        city = ' '.join(city.split()).strip()
        
        # Length checks
        if len(city) < 2 or len(city) > 50:
            return None
            
        # Should be mostly letters
        letter_count = sum(1 for c in city if c.isalpha() or c in ' -')
        if letter_count < len(city) * 0.7:
            return None
            
        # Reject common garbage
        garbage = ['tel', 'fax', 'email', 'phone', 'mobil', 'web', 'http', 'gmbh', 'ag']
        if any(g in city.lower() for g in garbage):
            return None
            
        # Limit to first 3 words max
        words = city.split()[:3]
        return ' '.join(words)

    def extract_addresses(self, soup: BeautifulSoup, text: str) -> Dict[str, Dict[str, str]]:
        """Extract registered and postal addresses with strict validation."""
        addresses = {
            'registered': {},
            'postal': {}
        }
        
        # Look for address microformats - ONLY take FIRST address (primary company)
        addr_tags = soup.find_all('address')
        if addr_tags:
            # Only process first address tag (primary company)
            first_addr = addr_tags[0]
            addr_text = first_addr.get_text(separator=' ', strip=True)
            
            # Skip if this looks like a partner/third-party section
            is_partner = False
            for indicator in self.PARTNER_INDICATORS:
                if indicator in addr_text.lower():
                    is_partner = True
                    break
            
            if not is_partner:
                addresses['registered'] = self.parse_address(addr_text)
                
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
                    parsed = self.parse_address(match.group(1))
                    if self.validator.validate_address(parsed.get('street'), parsed.get('zip'), parsed.get('city')):
                        addresses['registered'] = parsed
                    break
        
        # === INTERNATIONAL ADDRESS PATTERNS ===
        # Supports: German, Swiss, Austrian, French, Italian, Dutch, Belgian
        if not addresses['registered'].get('street'):
            intl_addr_patterns = [
                # === SWISS FRENCH PATTERNS (4-digit postal, highest priority for .ch) ===
                # "Rue Jacques-Gachoud 1\n1700 Fribourg" or "Rue de la Paix 15, CH-1200 Genève"
                (re.compile(
                    r'((?:Rue|Avenue|Boulevard|Place|Chemin|Route|Ruelle)\s+[A-Za-zàâäéèêëïîôùûüç\s\-\']+)\s+(\d+[a-zA-Z]?)\s*[\n,]\s*(?:CH-?)?(\d{4})\s+([A-Za-zàâäéèêëïîôùûüç\s\-]+)',
                    re.IGNORECASE | re.MULTILINE
                ), 'Switzerland'),
                
                # === SWISS GERMAN PATTERNS (4-digit postal) ===
                # "Tellsgasse 16\n6460 Altdorf" or "Bahnhofstrasse 10, CH-8001 Zürich"
                (re.compile(
                    r'([A-Za-zäöüÄÖÜß\-]+(?:gasse|strasse|str\.|weg|platz|rain|matt|acher))\s+(\d+[a-zA-Z]?)\s*[\n,]\s*(?:CH-?)?(\d{4})\s+([A-Za-zäöüÄÖÜß\s\-]+)',
                    re.IGNORECASE | re.MULTILINE
                ), 'Switzerland'),
                
                # === SWISS ITALIAN PATTERNS (4-digit postal) ===
                # "Via Lugano 25\n6900 Lugano"
                (re.compile(
                    r'((?:Via|Viale|Piazza|Corso|Vicolo)\s+[A-Za-zàèéìòù\s\-]+)\s+(\d+[a-zA-Z]?)\s*[\n,]\s*(?:CH-?)?(\d{4})\s+([A-Za-zàèéìòù\s\-]+)',
                    re.IGNORECASE | re.MULTILINE
                ), 'Switzerland'),
                
                # === GERMAN PATTERNS (5-digit postal) ===
                # "Salzdahlumer Str. 196\n38126 Braunschweig"
                (re.compile(
                    r'([A-Za-zäöüÄÖÜß\-]+\s+(?:Str\.|Straße|Weg|Platz|Allee|Ring|Gasse))\s+(\d+[a-zA-Z]?)\s*[\n,]\s*(\d{5})\s+([A-Za-zäöüÄÖÜß\s\-]+)',
                    re.IGNORECASE | re.MULTILINE
                ), 'Germany'),
                # "Kaiserstraße 56\n60329 Frankfurt"
                (re.compile(
                    r'([A-Za-zäöüÄÖÜß\.\-]+(?:straße|str\.?|weg|platz|allee|ring|gasse|damm|ufer|chaussee))\s+(\d+[a-zA-Z]?)\s*[\n,]\s*(\d{5})\s+([A-Za-zäöüÄÖÜß\s\-]+)',
                    re.IGNORECASE | re.MULTILINE
                ), 'Germany'),
                # German named locations: "An der Mühle 3\n31860 Emmerthal"
                (re.compile(
                    r'((?:An\s+der|Am|Im|Auf\s+der|Zum|Zur)\s+[A-Za-zäöüÄÖÜß\-]+)\s+(\d+[a-zA-Z]?)\s*[\n,]\s*(\d{5})\s+([A-Za-zäöüÄÖÜß\s\-]+)',
                    re.IGNORECASE | re.MULTILINE
                ), 'Germany'),
                
                # === AUSTRIAN PATTERNS (4-digit postal with optional A- prefix) ===
                # "Stephansplatz 1\nA-1010 Wien"
                (re.compile(
                    r'([A-Za-zäöüÄÖÜß\-]+(?:gasse|straße|str\.|weg|platz|ring))\s+(\d+[a-zA-Z]?)\s*[\n,]\s*(?:A-?)?(\d{4})\s+([A-Za-zäöüÄÖÜß\s\-]+)',
                    re.IGNORECASE | re.MULTILINE
                ), 'Austria'),
                
                # === FRENCH PATTERNS (5-digit postal) ===
                # "15, rue de la Paix\n75001 Paris" or "Rue de Rivoli 25, 75001 Paris"
                (re.compile(
                    r'(?:(\d+)[,\s]+)?((?:Rue|Avenue|Boulevard|Av\.|Bd\.|Place|Chemin|Allée|Impasse|Quai)\s+[A-Za-zàâäéèêëïîôùûüç\s\-\']+)\s*(\d*)\s*[\n,]\s*(?:F-?)?(\d{5})\s+([A-Za-zàâäéèêëïîôùûüç\s\-]+)',
                    re.IGNORECASE | re.MULTILINE
                ), 'France'),
                
                # === ITALIAN PATTERNS (5-digit postal) ===
                # "Via Roma 25\n00100 Roma"
                (re.compile(
                    r'((?:Via|Viale|Piazza|Corso|Largo|Vicolo)\s+[A-Za-zàèéìòù\s\-]+)\s+(\d+[a-zA-Z]?)\s*[\n,]\s*(?:I-?)?(\d{5})\s+([A-Za-zàèéìòù\s\-]+)',
                    re.IGNORECASE | re.MULTILINE
                ), 'Italy'),
                
                # === DUTCH PATTERNS (4-digit + 2 letters) ===
                # "Damrak 1\n1012 LG Amsterdam"
                (re.compile(
                    r'([A-Za-z\-]+(?:straat|weg|plein|laan|gracht|kade|singel))\s+(\d+[a-zA-Z]?)\s*[\n,]\s*(\d{4}\s*[A-Z]{2})\s+([A-Za-z\s\-]+)',
                    re.IGNORECASE | re.MULTILINE
                ), 'Netherlands'),
                
                # === BELGIAN PATTERNS (4-digit postal) ===
                # "Rue de la Loi 16\n1000 Bruxelles"
                (re.compile(
                    r'((?:Rue|Avenue|Boulevard|Place|Straat|Laan|Plein)\s+[A-Za-zàâäéèêëïîôùûüç\s\-\']+)\s+(\d+[a-zA-Z]?)\s*[\n,]\s*(?:B-?)?(\d{4})\s+([A-Za-zàâäéèêëïîôùûüç\s\-]+)',
                    re.IGNORECASE | re.MULTILINE
                ), 'Belgium'),
                
                # === UK PATTERNS (alphanumeric postal) ===
                # "10 Downing Street\nLondon SW1A 2AA"
                (re.compile(
                    r'(\d+[a-zA-Z]?)\s+([A-Za-z\s\-]+(?:Street|St\.|Road|Rd\.|Lane|Ln\.|Avenue|Ave\.|Drive|Way|Place|Square))\s*[\n,]\s*([A-Za-z]+)\s+([A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2})',
                    re.IGNORECASE | re.MULTILINE
                ), 'United Kingdom'),
            ]
            
            for pattern, country in intl_addr_patterns:
                match = pattern.search(text)
                if match:
                    groups = match.groups()
                    
                    # Handle French/UK style "15, rue de la Paix" (number before street)
                    if country == 'France' and groups[0] and groups[0].isdigit():
                        number = groups[0]
                        street_name = groups[1].strip()
                        street = f"{street_name} {number}"
                        zip_code = groups[3].strip()
                        city = groups[4].strip()
                    elif country == 'United Kingdom':
                        street = f"{groups[0]} {groups[1].strip()}"
                        city = groups[2].strip()
                        zip_code = groups[3].strip()
                    else:
                        street = f"{groups[0].strip()} {groups[1]}".strip()
                        zip_code = groups[2].strip()
                        city = groups[3].strip()
                    
                    # Clean city (remove trailing junk)
                    city = re.split(r'[,\n]', city)[0].strip()
                    
                    # Validate before storing
                    validated_street = self.validate_street(street)
                    validated_city = self.validate_city(city)
                    
                    # Accept 4-digit (CH/AT/NL/BE) or 5-digit (DE/FR/IT) or UK format
                    zip_clean = re.sub(r'[^0-9A-Z]', '', zip_code.upper())
                    valid_zip = len(zip_clean) >= 4 and len(zip_clean) <= 8
                    
                    if validated_street and validated_city and valid_zip:
                        addresses['registered'] = {
                            'street': validated_street,
                            'zip': zip_code,
                            'city': validated_city,
                            'state': '',
                            'country': country
                        }
                        break
                    
        return addresses
    
    def _detect_country_from_zip(self, zip_code: str) -> str:
        """Detect country from postal code format."""
        zip_clean = zip_code.strip().upper()
        
        # Swiss: 4 digits, 1000-9999
        if re.match(r'^(?:CH-?)?\d{4}$', zip_clean):
            return 'Switzerland'
        # German: 5 digits
        if re.match(r'^\d{5}$', zip_clean):
            return 'Germany'
        # French: 5 digits with optional F-
        if re.match(r'^(?:F-?)?\d{5}$', zip_clean):
            return 'France'
        # Austrian: 4 digits with optional A-
        if re.match(r'^(?:A-?)?\d{4}$', zip_clean):
            return 'Austria'
        # Dutch: 4 digits + 2 letters
        if re.match(r'^\d{4}\s*[A-Z]{2}$', zip_clean):
            return 'Netherlands'
        # UK: Various alphanumeric formats
        if re.match(r'^[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}$', zip_clean):
            return 'United Kingdom'
        
        return ''

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
            'fax': None
        }
        
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
                score += 40  # Boost: Definitive URL is enough to pass
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

    def _predict_gliner(self, text: str) -> Dict[str, Any]:
        """
        Predict entities using GLiNER.
        Returns a structured dictionary with best candidates.
        """
        if not self.model:
            return {}

        # Truncate text for performance if too long (GLiNER handles this but let's be safe)
        # 5000 chars is usually enough for impressum content
        if len(text) > 5000:
            text = text[:5000]

        # Define labels we want to extract
        # "organization" -> Legal Name
        # "person" -> Representatives
        # "street_address", "city", "zip_code" -> Address
        # "commercial_register_number", "tax_id" -> Registration
        # "phone_number", "email_address" -> Contacts
        labels = [
            "organization", 
            "person", 
            "street_address", 
            "city", 
            "zip_code", 
            "phone_number", 
            "email_address", 
            "tax_id", 
            "commercial_register_number"
        ]

        try:
            entities = self.model.predict_entities(text, labels, threshold=0.3)
            
            results = {}
            # Group by label
            for entity in entities:
                label = entity["label"]
                text_val = entity["text"].strip()
                score = entity["score"]
                
                if label not in results:
                    results[label] = []
                
                # Add if not duplicate
                if not any(e['text'] == text_val for e in results[label]):
                    results[label].append({"text": text_val, "score": score})

            return results
        except Exception as e:
            logger.error(f"GLiNER prediction failed: {e}")
            return {}

    def extract(self, html: str, url: str) -> Dict[str, Any]:
        """Main extraction method for legal information."""
        try:
            soup = BeautifulSoup(html, 'lxml')
            
            # Extract domain for validation
            parsed_url = urlparse(url)
            domain = parsed_url.netloc.lower().replace('www.', '')
            
            # Clean HTML - remove scripts/styles
            for tag in soup(['script', 'style', 'noscript']):
                tag.decompose()
            
            # Get full text for legal page detection
            full_text = soup.get_text(separator='\n', strip=True)
            
            # Check if this is a legal page
            is_legal, confidence = self.is_legal_page(soup, url, full_text)
            
            if not is_legal:
                return {
                    'status': 'NOT_LEGAL_PAGE',
                    'confidence': confidence
                }
            
            # === CRITICAL: Isolate Impressum section FIRST ===
            # This prevents extracting data from partner/third-party sections
            isolated_soup, isolated_text = self.isolate_impressum_section(soup, url)
            
            # Further filter to PRIMARY company block only
            primary_text = self.extract_primary_company_block(isolated_text, domain)
            
            # Use primary_text for extraction (falls back to isolated_text if too short)
            extraction_text = primary_text if len(primary_text) > 50 else isolated_text
            extraction_soup = isolated_soup if isolated_soup else soup
                
            # Extract all legal information
            result = {
                'status': 'SUCCESS',
                'confidence': confidence,
                'legal_notice_url': url
            }
            
            # --- 1. REGEX EXTRACTION (on isolated content) ---
            legal_form = self.extract_legal_form(extraction_text)
            if legal_form:
                result['legal_form'] = legal_form
                
            registration = self.extract_registration_info(extraction_text)
            result.update(registration)
            
            representatives = self.extract_representatives(extraction_text)
            result.update(representatives)
            
            # Extract addresses from isolated soup
            addresses = self.extract_addresses(extraction_soup, extraction_text)
            for addr_type, addr_data in addresses.items():
                if addr_data:
                    for key, value in addr_data.items():
                        result[f'{addr_type}_{key}'] = value
                        
            contacts = self.extract_legal_contacts(extraction_soup, extraction_text)
            result.update(contacts)
            
            # Extract company name from isolated content
            legal_name = self.extract_legal_name(extraction_text, legal_form)
            if legal_name:
                # Validate company name matches domain
                if self.validate_company_name_for_domain(legal_name, domain):
                    result['legal_name'] = legal_name
                else:
                    # Try to find a better match in primary text
                    logger.warning(f"Company name '{legal_name}' may not match domain '{domain}'")

            # --- 2. GLiNER ENHANCEMENT (on isolated content only) ---
            if self.model:
                # Use isolated text for GLiNER - NOT full page!
                gliner_results = self._predict_gliner(extraction_text)
                
                # Merge Legal Name (with domain validation)
                if 'organization' in gliner_results:
                    valid_orgs = [
                        org for org in gliner_results['organization']
                        if org['text'].lower().strip() not in self.FALSE_POSITIVE_ORGS
                        and not any(fp in org['text'].lower() for fp in self.FALSE_POSITIVE_ORGS)
                        and self.validate_company_name_for_domain(org['text'], domain)
                    ]
                    
                    if valid_orgs:
                        best_org = max(valid_orgs, key=lambda x: x['score'])
                        if not result.get('legal_name') or best_org['score'] > 0.7:
                            cleaned_gliner_name = self.clean_legal_name(best_org['text'], aggressive=False)
                            if cleaned_gliner_name and (
                                len(cleaned_gliner_name.split()) >= 2 or
                                any(lf.lower() in cleaned_gliner_name.lower() for lf in ['gmbh', 'ag', 'kg', 'ltd', 'ug', 'ohg'])
                            ):
                                result['legal_name'] = cleaned_gliner_name
                                result['extraction_method'] = 'gliner'

                # Merge Representatives (Persons) - stricter validation
                if 'person' in gliner_results:
                    # Only take high-confidence persons from isolated content
                    gliner_persons = [p['text'] for p in gliner_results['person'] if p['score'] > 0.6]
                    
                    # Validate person names
                    validated_persons = []
                    for person in gliner_persons:
                        validated = self.validator.validate_ceo_name(person)
                        if validated:
                            validated_persons.append(validated)
                    
                    if not result.get('ceo') and validated_persons:
                        result['ceo'] = validated_persons[0]
                        if len(validated_persons) > 1:
                            result['directors'] = validated_persons[1:]
                    elif validated_persons and result.get('ceo'):
                        # Check if regex result looks like a title
                        if any(x in result['ceo'].lower() for x in ['geschäftsführer', 'director', 'manager', 'vorstand']):
                            result['ceo'] = validated_persons[0]

                # Merge Address - only from isolated content
                if 'street_address' in gliner_results:
                    best_street = max(gliner_results['street_address'], key=lambda x: x['score'])
                    if best_street['score'] > 0.6:  # Higher threshold
                        validated_street = self.validate_street(best_street['text'])
                        if validated_street:
                            # Only override if no street or current street looks suspicious
                            current_street = result.get('registered_street', '')
                            if not current_street or len(current_street) < 5:
                                result['registered_street'] = validated_street
                
                if 'city' in gliner_results:
                    best_city = max(gliner_results['city'], key=lambda x: x['score'])
                    if best_city['score'] > 0.6:
                        validated_city = self.validate_city(best_city['text'])
                        if validated_city:
                            result['registered_city'] = validated_city
                
                if 'zip_code' in gliner_results:
                    best_zip = max(gliner_results['zip_code'], key=lambda x: x['score'])
                    if best_zip['score'] > 0.6:
                        zip_text = best_zip['text'].strip()
                        if re.match(r'^\d{4,5}$', zip_text):
                            result['registered_zip'] = zip_text

                # Merge Registration Number
                if 'commercial_register_number' in gliner_results:
                    best_reg = max(gliner_results['commercial_register_number'], key=lambda x: x['score'])
                    if best_reg['score'] > 0.8:
                        curr_reg = result.get('registration_number')
                        if not curr_reg or len(curr_reg) > 20:
                            result['registration_number'] = best_reg['text']
            
            # Clean up public sector misclassifications
            result = self.sanitize_public_sector(result, url, full_text)

            return result
            
        except Exception as e:
            logger.error(f"Legal extraction error: {e}")
            return {
                'status': 'EXTRACTION_FAILED',
                'error': str(e)
            }

    def clean_legal_name(self, name: str, aggressive: bool = True) -> Optional[str]:
        """
        Clean junk from legal name.
        :param aggressive: If True, uses aggressive regex to strip prefixes (good for raw text, bad for GLiNER).
        """
        if not name:
            return None
            
        # Junk prefixes to strip (Case Insensitive)
        junk_prefixes = [
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
        
        # Aggressive stripping of everything before the "Name GmbH" pattern
        # Only use this for raw regex extraction, not for GLiNER which is already focused
        if aggressive:
             prefix_pattern = r"^.*?(?=\b[A-ZÄÖÜ][a-zäöüß0-9]*(?:\s+[A-ZÄÖÜ][a-zäöüß0-9]*)*\s+(?:GmbH|AG|KG|Ltd|Inc|SE)\b)"
             # Relaxed pattern to allow CamelCase or numbers (a-z0-9)
             cleaned = re.sub(prefix_pattern, "", cleaned, flags=re.IGNORECASE)

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
        if not self.validator.validate_legal_name(cleaned):
            return None
            
        # If it's just a legal form (e.g. "GmbH"), it's junk
        if cleaned.lower() in [f.lower() for forms in self.legal_forms.values() for f in forms]:
            return None
            
        # Final Length Check after cleaning
        if len(cleaned) > 100: # Way too long for a company name
            return None
            
        return cleaned

    def extract_legal_name(self, text: str, legal_form: Optional[str] = None) -> Optional[str]:
        """Extract the official legal name of the company."""
        candidates = []
        
        # Standard headers are risky (often contain 'Impressum' followed by 'Angaben gemäß...')
        # Instead, look specifically for "Name GmbH" structures near the top of sections
        
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
                # Use aggressive cleaning for regex
                cleaned = self.clean_legal_name(raw_name, aggressive=True)
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
                # Use aggressive cleaning for regex
                cleaned = self.clean_legal_name(match, aggressive=True)
                # Validator check is done inside clean_legal_name now
                if cleaned and len(cleaned) > 5:
                    # Give HUGE bonus if found with legal form suffix
                    candidates.append((cleaned, 20)) 

        if candidates:
            # Filter out candidates that are just common words if better options exist
            # Sort by priority
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

    def sanitize_public_sector(self, result: Dict[str, Any], url: str, text: str) -> Dict[str, Any]:
        """
        If the page clearly describes a government/public entity, drop private-company legal forms.
        """
        try:
            domain = urlparse(url).netloc.lower()
        except Exception:
            domain = ""
        text_lower = (text or "").lower()
        public_markers = ['verwaltung', 'kanton', 'government', 'ministerium', 'municipality', 'stadt', 'canton']
        if any(marker in text_lower for marker in public_markers):
            form = (result.get('legal_form') or '').lower()
            corporate_forms = {f.lower() for forms in self.legal_forms.values() for f in forms}
            if form in corporate_forms:
                result['legal_form'] = ''
        # If domain is clearly governmental (.gov or .gv.*), also strip corporate form
        if domain.endswith('.gov') or '.gov.' in domain or '.gv.' in domain:
            result['legal_form'] = ''
        return result
