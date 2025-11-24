import re
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
import warnings
import lxml
from .utils import logger

# Suppress BS4 warning for XML parsed as HTML
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

class Extractor:
    def __init__(self):
        self.email_regex = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
        # Loose international phone regex: +49 123 45678 or 030 123456
        self.phone_regex = re.compile(r'(?:\+\d{1,3}|0\d{1,4})[\s\.\-\/]?\d{1,5}[\s\.\-\/]?\d{3,}')
        
        # Generic providers to ignore unless found in contact context
        self.generic_emails = {
            'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'web.de', 'gmx.de', 't-online.de'
        }

    def is_parked(self, soup: BeautifulSoup, text_content: str) -> bool:
        """Checks for indicators of a parked domain."""
        keywords = [
            "domain for sale", "under construction", "parked at", "buy this domain",
            "domain is available", "website coming soon", "godaddy", "namecheap", 
            "sedo", "dan.com", "afternic"
        ]
        
        title = soup.title.string.lower() if soup.title else ""
        text = text_content.lower()[:2000] # Check first 2000 chars
        
        # Check title
        if any(k in title for k in keywords):
            return True
            
        # Check meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc:
            content = meta_desc.get('content', '').lower()
            if any(k in content for k in keywords):
                return True
                
        # Check body text (less reliable, strict match needed)
        # Often parked pages have big H1s like "example.de is for sale"
        h1 = soup.find('h1')
        if h1 and any(k in h1.get_text().lower() for k in keywords):
            return True
            
        return False

    def extract_company_name(self, soup: BeautifulSoup, domain: str) -> str:
        """
        Tries to find the official company or site name.
        Priority: OG:Site_Name -> Application Name -> Title -> H1 -> Domain
        """
        # 1. OG Site Name
        og_name = soup.find('meta', property='og:site_name')
        if og_name and og_name.get('content'):
            return og_name['content'].strip()
            
        # 2. Application Name
        app_name = soup.find('meta', attrs={'name': 'application-name'})
        if app_name and app_name.get('content'):
            return app_name['content'].strip()
            
        # 3. Title (Cleaned)
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
            # Often titles are "Home - Company Name" or "Company Name | Slogan"
            if '|' in title:
                return title.split('|')[0].strip()
            if '-' in title:
                # Check if company name is likely at the end or start
                parts = title.split('-')
                if len(parts[0]) < len(parts[-1]):
                    return parts[0].strip()
                return parts[-1].strip()
            return title
            
        # 4. H1
        h1 = soup.find('h1')
        if h1:
            return h1.get_text().strip()
            
        return domain

    def extract_emails(self, text: str) -> str:
        """Finds the best candidate email."""
        emails = set(self.email_regex.findall(text))
        
        valid_emails = []
        for email in emails:
            email = email.lower()
            # Filter image extensions (false positives in regex)
            if email.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                continue
                
            domain_part = email.split('@')[-1]
            
            # Prefer non-generic domains
            if domain_part not in self.generic_emails:
                valid_emails.insert(0, email) # Priority to business email
            else:
                valid_emails.append(email)
        
        return valid_emails[0] if valid_emails else None

    def extract(self, html_content: str, domain: str) -> dict:
        """Main extraction method."""
        try:
            soup = BeautifulSoup(html_content, 'lxml')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
                
            text = soup.get_text(separator=' ', strip=True)
            
            if self.is_parked(soup, text):
                return {"status": "PARKED"}
            
            data = {
                "company_name": self.extract_company_name(soup, domain),
                "description": None,
                "email": self.extract_emails(text),
                "phone": None, # TODO: Improve phone regex extraction from text
                "address": None # TODO: Heuristics for address
            }
            
            # Meta Description
            meta_desc = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', property='og:description')
            if meta_desc:
                data['description'] = meta_desc.get('content', '')[:500] # Truncate
                
            # Basic Phone Extraction (First match)
            # Phone regex on full text can be noisy. Limit to "Contact" context or header/footer?
            # For PoC, just finding first pattern match in text
            phone_match = self.phone_regex.search(text)
            if phone_match:
                data['phone'] = phone_match.group(0).strip()
                
            return data
            
        except Exception as e:
            logger.error(f"Extraction error for {domain}: {e}")
            return {"status": "EXTRACTION_FAILED", "error": str(e)}
