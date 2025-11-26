"""
Enhanced data extractor with structured data support, validation, and ML capabilities.
"""
import re
import json
from typing import Dict, List, Optional, Any, Tuple
from bs4 import BeautifulSoup
import warnings
import extruct
import phonenumbers
from phonenumbers import geocoder, carrier
from email_validator import validate_email, EmailNotValidError
from langdetect import detect
from urllib.parse import urljoin, urlparse
import trafilatura
from datetime import datetime
from .utils import logger

# Suppress warnings
warnings.filterwarnings("ignore")

class EnhancedExtractor:
    def __init__(self):
        # Regex patterns
        self.email_regex = re.compile(
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        )
        self.phone_regex = re.compile(
            r'[\+]?[(]?[0-9]{1,4}[)]?[-\s\.]?[(]?[0-9]{1,4}[)]?[-\s\.]?[0-9]{1,5}[-\s\.]?[0-9]{1,5}'
        )
        self.vat_regex = re.compile(
            r'(?:VAT|USt[-\s]?Id[-\s]?Nr\.?|UID|TVA|IVA|NIF|BTW|MWST|GST)[\s:]*([A-Z]{2}[\s]?[\d\s]+)',
            re.IGNORECASE
        )
        self.copyright_regex = re.compile(
            r'(?:©|Copyright|Copr\.?)\s*(?:\d{4})?\s*(?:by\s+)?([^|,\n]{3,50})',
            re.IGNORECASE
        )
        
        # Critical pages to explore
        self.critical_paths = [
            '/about', '/about-us', '/uber-uns', '/chi-siamo', '/qui-sommes-nous',
            '/contact', '/contact-us', '/kontakt', '/contacto', '/contatti',
            '/impressum', '/imprint', '/legal', '/legal-notice',
            '/company', '/unternehmen', '/azienda', '/entreprise',
            '/team', '/our-team', '/unser-team', '/equipe'
        ]
        
        # Business email prefixes (not personal)
        self.business_prefixes = {
            'info', 'contact', 'support', 'sales', 'admin', 'office',
            'hello', 'team', 'service', 'help', 'inquiry', 'general',
            'reception', 'mail', 'email', 'customer', 'business'
        }
        
        # Parked domain indicators
        self.parked_indicators = [
            'domain for sale', 'domain is for sale', 'buy this domain',
            'domain parked', 'under construction', 'coming soon',
            'website coming soon', 'godaddy', 'namecheap', 'sedo.com',
            'dan.com', 'afternic', 'this domain is available',
            'get this domain', 'domain expired', 'renew now'
        ]

    def extract_structured_data(self, html: str, base_url: str) -> Dict[str, Any]:
        """Extract all structured data formats from HTML."""
        try:
            data = extruct.extract(
                html,
                base_url=base_url,
                syntaxes=['json-ld', 'microdata', 'rdfa', 'opengraph', 'microformat']
            )
            return data
        except Exception as e:
            logger.debug(f"Structured data extraction error: {e}")
            return {}

    def extract_from_jsonld(self, structured_data: Dict) -> Dict[str, Any]:
        """Extract business information from JSON-LD data."""
        result = {}
        
        for item in structured_data.get('json-ld', []):
            if not isinstance(item, dict):
                continue
                
            item_type = item.get('@type', '')
            
            # Handle Organization/LocalBusiness types
            if any(t in str(item_type) for t in ['Organization', 'Corporation', 'LocalBusiness', 'Company']):
                result['company_name'] = item.get('name', '')
                result['description'] = item.get('description', '')
                
                # Extract address
                if 'address' in item:
                    addr = item['address']
                    if isinstance(addr, dict):
                        parts = []
                        for key in ['streetAddress', 'addressLocality', 'addressRegion', 'postalCode', 'addressCountry']:
                            if key in addr:
                                parts.append(str(addr[key]))
                        if parts:
                            result['address'] = ', '.join(parts)
                
                # Extract contact info
                result['phone'] = item.get('telephone', '')
                result['email'] = item.get('email', '')
                
                # Extract social profiles
                same_as = item.get('sameAs', [])
                if isinstance(same_as, list):
                    result['social_profiles'] = same_as
                elif isinstance(same_as, str):
                    result['social_profiles'] = [same_as]
                
                # Business hours
                if 'openingHoursSpecification' in item:
                    result['business_hours'] = item['openingHoursSpecification']
                    
            # Handle ContactPoint
            elif 'ContactPoint' in str(item_type):
                if not result.get('phone'):
                    result['phone'] = item.get('telephone', '')
                if not result.get('email'):
                    result['email'] = item.get('email', '')
                    
        return result

    def extract_from_microdata(self, structured_data: Dict) -> Dict[str, Any]:
        """Extract from microdata format."""
        result = {}
        
        for item in structured_data.get('microdata', []):
            if not isinstance(item, dict):
                continue
                
            props = item.get('properties', {})
            item_type = item.get('type', [''])[0] if isinstance(item.get('type'), list) else ''
            
            if 'Organization' in item_type or 'LocalBusiness' in item_type:
                result['company_name'] = props.get('name', [''])[0] if props.get('name') else ''
                result['description'] = props.get('description', [''])[0] if props.get('description') else ''
                result['phone'] = props.get('telephone', [''])[0] if props.get('telephone') else ''
                result['email'] = props.get('email', [''])[0] if props.get('email') else ''
                
                # Address
                if 'address' in props and props['address']:
                    addr = props['address'][0] if isinstance(props['address'], list) else props['address']
                    if isinstance(addr, dict):
                        addr_props = addr.get('properties', {})
                        parts = []
                        for key in ['streetAddress', 'addressLocality', 'postalCode']:
                            if key in addr_props:
                                val = addr_props[key]
                                parts.append(val[0] if isinstance(val, list) else val)
                        if parts:
                            result['address'] = ', '.join(parts)
                            
        return result

    def extract_from_opengraph(self, structured_data: Dict) -> Dict[str, Any]:
        """Extract from OpenGraph metadata."""
        result = {}
        og_data = structured_data.get('opengraph', [{}])[0] if structured_data.get('opengraph') else {}
        
        if og_data:
            result['company_name'] = og_data.get('og:site_name', '')
            result['description'] = og_data.get('og:description', '')
            result['image'] = og_data.get('og:image', '')
            
        return result

    def validate_email(self, email: str) -> Tuple[bool, str]:
        """Validate email address and check if it's business-related."""
        try:
            # Validate format and deliverability
            validation = validate_email(email, check_deliverability=False)
            email = validation.normalized
            
            # Check if it's a business email
            local_part = email.split('@')[0].lower()
            domain = email.split('@')[1].lower()
            
            # Skip generic providers unless it has business prefix
            generic_domains = {'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com'}
            if domain in generic_domains and local_part not in self.business_prefixes:
                return False, ""
                
            # Check for personal patterns (firstname.lastname)
            if '.' in local_part and len(local_part.split('.')) == 2:
                parts = local_part.split('.')
                if all(len(p) > 2 and p.isalpha() for p in parts):
                    # Likely personal unless it's a business prefix
                    if local_part not in self.business_prefixes:
                        return False, ""
                        
            return True, email
            
        except EmailNotValidError:
            return False, ""

    def validate_phone(self, phone: str, country_hint: str = None) -> Tuple[bool, str]:
        """Validate and format phone number."""
        try:
            # Clean input first
            phone_clean = re.sub(r'[^\d\+]', '', phone)
            if len(phone_clean) < 7: # Too short
                return False, ""
                
            # Try to parse the phone number
            if country_hint:
                parsed = phonenumbers.parse(phone, country_hint)
            else:
                # Try to detect country from number (must start with +)
                if not phone.strip().startswith('+'):
                     return False, ""
                parsed = phonenumbers.parse(phone, None)
                
            if phonenumbers.is_valid_number(parsed):
                # Format in international format
                formatted = phonenumbers.format_number(
                    parsed, 
                    phonenumbers.PhoneNumberFormat.INTERNATIONAL
                )
                return True, formatted
                
        except Exception:
            pass
            
        return False, ""

    def extract_company_name(self, soup: BeautifulSoup, structured_data: Dict, domain: str) -> str:
        """Extract company name from multiple sources."""
        candidates = []
        
        # 1. From structured data
        for extractor in [self.extract_from_jsonld, self.extract_from_microdata, self.extract_from_opengraph]:
            data = extractor(structured_data)
            if data.get('company_name'):
                candidates.append((data['company_name'], 10))  # Highest priority
                
        # 2. From copyright notice
        footer = soup.find('footer') or soup
        copyright_text = footer.get_text()
        copyright_match = self.copyright_regex.search(copyright_text)
        if copyright_match:
            company = copyright_match.group(1).strip()
            if company and len(company) > 2:
                candidates.append((company, 8))
                
        # 3. From VAT/Tax ID
        vat_match = self.vat_regex.search(soup.get_text())
        if vat_match:
            # Often followed by company name
            context = soup.get_text()[max(0, vat_match.start()-100):vat_match.end()+100]
            lines = context.split('\n')
            for line in lines:
                if len(line) > 3 and not any(x in line.lower() for x in ['vat', 'ust', 'uid']):
                    candidates.append((line.strip()[:50], 5))
                    break
                    
        # 4. From title tag
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
            # Clean common patterns
            for sep in [' | ', ' - ', ' :: ', ' — ']:
                if sep in title:
                    parts = title.split(sep)
                    # Usually company name is first or last
                    candidates.append((parts[0].strip(), 3))
                    if len(parts) > 1:
                        candidates.append((parts[-1].strip(), 3))
                        
        # 5. From h1 tag
        h1 = soup.find('h1')
        if h1:
            text = h1.get_text().strip()
            if text and len(text) < 100:
                candidates.append((text, 2))
                
        # Select best candidate
        if candidates:
            # Sort by priority
            candidates.sort(key=lambda x: x[1], reverse=True)
            return candidates[0][0]
            
        return domain

    def extract_all_emails(self, soup: BeautifulSoup, text: str) -> List[str]:
        """Extract all valid business emails from the page."""
        emails = set()
        
        # 1. From mailto links
        for link in soup.find_all('a', href=re.compile(r'^mailto:')):
            email = link.get('href', '').replace('mailto:', '').split('?')[0]
            if email:
                emails.add(email.lower())
                
        # 2. From text content
        found = self.email_regex.findall(text)
        emails.update(e.lower() for e in found)
        
        # 3. Validate and filter
        valid_emails = []
        for email in emails:
            is_valid, normalized = self.validate_email(email)
            if is_valid:
                valid_emails.append(normalized)
                
        return valid_emails

    def extract_all_phones(self, soup: BeautifulSoup, text: str, country_hint: str = None) -> List[str]:
        """Extract all valid phone numbers."""
        phones = set()
        
        # 1. From tel: links
        for link in soup.find_all('a', href=re.compile(r'^tel:')):
            phone = link.get('href', '').replace('tel:', '')
            if phone:
                phones.add(phone)
                
        # 2. From text near phone keywords
        phone_contexts = re.finditer(
            r'(?:phone|tel|telefon|telephone|mobile|cell|fax)[\s:]*([+\d\s\-\(\)]{7,})',
            text, re.IGNORECASE
        )
        for match in phone_contexts:
            phones.add(match.group(1))
            
        # 3. General phone pattern
        found = self.phone_regex.findall(text)
        phones.update(found)
        
        # 4. Validate and format
        valid_phones = []
        for phone in phones:
            is_valid, formatted = self.validate_phone(phone, country_hint)
            if is_valid:
                valid_phones.append(formatted)
                
        return valid_phones

    def extract_address(self, soup: BeautifulSoup, structured_data: Dict) -> Dict[str, str]:
        """Extract physical address components."""
        address = {
            'street': '',
            'zip': '',
            'city': '',
            'country': ''
        }
        
        # 1. From structured data
        for extractor in [self.extract_from_jsonld, self.extract_from_microdata]:
            data = extractor(structured_data)
            if data.get('address'):
                # Often structured data returns a string, try to parse it if so
                if isinstance(data['address'], str):
                    parsed = self.parse_address_string(data['address'])
                    if parsed['city']:
                        return parsed
                elif isinstance(data.get('address'), dict):
                     # Direct mapping if available in extractor
                     pass 
        
        # 2. From address tags
        address_tag = soup.find('address')
        if address_tag:
            addr_text = address_tag.get_text(separator=', ').strip()
            if addr_text and len(addr_text) > 10:
                return self.parse_address_string(addr_text)
                
        # 3. From footer or contact section (Heuristic)
        # Look for patterns like: "Musterstraße 1, 12345 Musterstadt"
        text = soup.get_text(separator=' ')
        # German address pattern: Street Num, ZIP City
        de_pattern = re.compile(r'([A-Za-zäöüß\s\.-]+)\s+(\d+)[,\s]+(\d{5})\s+([A-Za-zäöüß\s-]+)')
        match = de_pattern.search(text)
        if match:
            return {
                'street': f"{match.group(1).strip()} {match.group(2)}",
                'zip': match.group(3),
                'city': match.group(4).strip(),
                'country': 'DE' # Inference
            }

        return address

    def parse_address_string(self, addr_text: str, country_hint: str = None) -> Dict[str, str]:
        """Best-effort parsing of address string with international ZIP support."""
        result = {'street': '', 'zip': '', 'city': '', 'country': country_hint or ''}
        
        # Normalize multi-line to single line
        addr_text = re.sub(r'[\n\r]+', ', ', addr_text.strip())
        addr_text = re.sub(r'\s+', ' ', addr_text)
        
        # International ZIP patterns based on country hint
        zip_patterns = [
            # UK postcodes: AA9A 9AA format
            (r'\b([A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2})\b', 'GB'),
            # Swiss: 4 digits
            (r'\b(\d{4})\b', 'CH'),
            # German/Austrian/French: 5 digits
            (r'\b(\d{5})\b', 'DE'),
            # US: 5 digits or 5+4
            (r'\b(\d{5}(?:-\d{4})?)\b', 'US'),
        ]
        
        # Try country-specific pattern first if hint provided
        zip_found = False
        if country_hint:
            for pattern_str, country_code in zip_patterns:
                if country_hint == country_code:
                    match = re.search(pattern_str, addr_text, re.IGNORECASE)
                    if match:
                        result['zip'] = match.group(1).strip()
                        zip_found = True
                        break
        
        # Fallback: try all patterns
        if not zip_found:
            for pattern_str, _ in zip_patterns:
                match = re.search(pattern_str, addr_text, re.IGNORECASE)
                if match:
                    result['zip'] = match.group(1).strip()
                    break
        
        if result['zip']:
            # Split around ZIP to find street and city
            parts = addr_text.split(result['zip'])
            if len(parts) > 1:
                # City is likely immediately after ZIP
                after_zip = parts[1].strip().split(',')[0].strip()
                # Take first few words as city, filter out country names
                city_words = after_zip.split()[:3]
                result['city'] = ' '.join(w for w in city_words if w.lower() not in 
                    ['germany', 'deutschland', 'france', 'uk', 'switzerland', 'austria'])
                
                # Street is likely before ZIP
                before_zip = parts[0].strip()
                # Get the last comma-separated segment before ZIP
                street_parts = before_zip.split(',')
                result['street'] = street_parts[-1].strip() if street_parts else ''
        
        return result

    def extract_social_profiles(self, soup: BeautifulSoup, structured_data: Dict) -> Dict[str, str]:
        """Extract social media profiles."""
        profiles = {}
        
        # From structured data
        jsonld_data = self.extract_from_jsonld(structured_data)
        if jsonld_data.get('social_profiles'):
            for url in jsonld_data['social_profiles']:
                if 'linkedin' in url.lower():
                    profiles['linkedin'] = url
                elif 'facebook' in url.lower():
                    profiles['facebook'] = url
                elif 'twitter' in url.lower() or 'x.com' in url.lower():
                    profiles['twitter'] = url
                elif 'instagram' in url.lower():
                    profiles['instagram'] = url
                    
        # From links
        social_patterns = {
            'linkedin': r'linkedin\.com/company/[^/\s]+',
            'facebook': r'facebook\.com/[^/\s]+',
            'twitter': r'(?:twitter|x)\.com/[^/\s]+',
            'instagram': r'instagram\.com/[^/\s]+',
            'youtube': r'youtube\.com/(?:c/|channel/|user/)[^/\s]+'
        }
        
        for link in soup.find_all('a', href=True):
            href = link['href']
            for platform, pattern in social_patterns.items():
                if re.search(pattern, href):
                    profiles[platform] = href
                    
        return profiles

    def is_parked_domain(self, soup: BeautifulSoup, text: str) -> bool:
        """Detect if the domain is parked."""
        text_lower = text.lower()[:3000]  # Check first 3000 chars
        title = soup.title.string.lower() if soup.title else ""
        
        # Check for parking indicators
        for indicator in self.parked_indicators:
            if indicator in title or indicator in text_lower:
                return True
                
        # Check meta tags
        for meta in soup.find_all('meta'):
            content = (meta.get('content', '') or '').lower()
            if any(ind in content for ind in self.parked_indicators):
                return True
                
        # Check for too little content
        if len(text.strip()) < 100:
            return True
            
        return False

    def calculate_confidence_score(self, data: Dict) -> float:
        """Calculate confidence score for extracted data."""
        score = 0.0
        max_score = 100.0
        
        # Company name (25 points)
        if data.get('company_name'):
            score += 25
            
        # Email (20 points)
        if data.get('emails'):
            score += 20
            
        # Phone (20 points)
        if data.get('phones'):
            score += 20
            
        # Address (15 points)
        if data.get('address') or (data.get('city') and data.get('zip')):
            score += 15
            
        # Description (10 points)
        if data.get('description'):
            score += 10
            
        # Social profiles (5 points)
        if data.get('social_profiles'):
            score += 5
            
        # Industry (5 points)
        if data.get('industry'):
            score += 5
            
        return min(score, max_score)

    def extract_industry(self, text: str, description: str) -> str:
        """Simple industry classification based on keywords."""
        industries = {
            'Technology': ['software', 'technology', 'it', 'digital', 'cloud', 'saas', 'app', 'platform'],
            'Healthcare': ['health', 'medical', 'clinic', 'hospital', 'pharma', 'doctor', 'patient'],
            'Finance': ['bank', 'finance', 'investment', 'insurance', 'fintech', 'payment', 'loan'],
            'Retail': ['shop', 'store', 'retail', 'ecommerce', 'product', 'sell', 'buy'],
            'Education': ['education', 'school', 'university', 'training', 'course', 'learning'],
            'Manufacturing': ['manufacture', 'production', 'factory', 'industrial', 'engineering'],
            'Consulting': ['consulting', 'advisory', 'consultancy', 'strategy', 'management'],
            'Marketing': ['marketing', 'advertising', 'agency', 'creative', 'media', 'pr'],
            'Real Estate': ['real estate', 'property', 'housing', 'realty', 'apartment', 'rent'],
            'Legal': ['law', 'legal', 'attorney', 'lawyer', 'litigation', 'court']
        }
        
        combined_text = f"{text[:2000]} {description}".lower()
        
        scores = {}
        for industry, keywords in industries.items():
            score = sum(1 for kw in keywords if kw in combined_text)
            if score > 0:
                scores[industry] = score
                
        if scores:
            return max(scores, key=scores.get)
            
        return ""

    def extract(self, html: str, domain: str, base_url: str) -> Dict[str, Any]:
        """Main extraction method."""
        try:
            soup = BeautifulSoup(html, 'lxml')
            
            # Clean HTML
            for tag in soup(['script', 'style', 'noscript']):
                tag.decompose()
                
            text = soup.get_text(separator=' ', strip=True)
            
            # Check if parked
            if self.is_parked_domain(soup, text):
                return {'status': 'PARKED', 'domain': domain}
                
            # Extract structured data
            structured_data = self.extract_structured_data(html, base_url)
            
            # Try to detect country for phone validation
            country_hint = None
            if '.de' in domain:
                country_hint = 'DE'
            elif '.ch' in domain:
                country_hint = 'CH'
            elif '.at' in domain:
                country_hint = 'AT'
            elif '.fr' in domain:
                country_hint = 'FR'
            elif '.it' in domain:
                country_hint = 'IT'
            elif '.uk' in domain or '.co.uk' in domain:
                country_hint = 'GB'
                
            # Extract main content using trafilatura
            main_content = trafilatura.extract(html, include_comments=False, 
                                              include_tables=False, 
                                              deduplicate=True) or ""
                                              
            # Build result
            result = {
                'status': 'SUCCESS',
                'domain': domain,
                'company_name': self.extract_company_name(soup, structured_data, domain),
                'emails': self.extract_all_emails(soup, text),
                'phones': self.extract_all_phones(soup, text, country_hint),
                'address': self.extract_address(soup, structured_data),
                'social_profiles': self.extract_social_profiles(soup, structured_data),
            }
            
            # Extract description
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            og_desc = soup.find('meta', property='og:description')
            result['description'] = ''
            if meta_desc:
                result['description'] = meta_desc.get('content', '')[:500]
            elif og_desc:
                result['description'] = og_desc.get('content', '')[:500]
            elif main_content:
                result['description'] = main_content[:500]
                
            # Industry classification
            result['industry'] = self.extract_industry(text, result['description'])
            
            # Language detection
            try:
                result['language'] = detect(text[:1000])
            except:
                result['language'] = ''
                
            # VAT/Tax ID
            vat_match = self.vat_regex.search(text)
            if vat_match:
                result['vat_id'] = vat_match.group(1).strip()
                
            # Calculate confidence score
            result['confidence_score'] = self.calculate_confidence_score(result)
            
            # Get critical pages for multi-page crawling
            result['critical_pages'] = []
            for path in self.critical_paths:
                full_url = urljoin(base_url, path)
                # Check if link exists on page
                if soup.find('a', href=lambda x: x and path in x):
                    result['critical_pages'].append(full_url)
                    
            return result
            
        except Exception as e:
            logger.error(f"Enhanced extraction error for {domain}: {e}")
            return {
                'status': 'EXTRACTION_FAILED',
                'domain': domain,
                'error': str(e)
            }
