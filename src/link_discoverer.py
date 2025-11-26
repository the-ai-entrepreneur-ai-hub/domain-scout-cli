"""
Link discoverer to find legal and important links from a webpage.
"""
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from typing import List, Set, Dict

class LinkDiscoverer:
    def __init__(self):
        # Legal keywords in multiple languages
        self.legal_keywords = {
            'de': ['impressum', 'rechtliches', 'datenschutz', 'agb', 'rechtliche hinweise'],
            'en': ['legal', 'terms', 'privacy', 'imprint', 'disclaimer'],
            'fr': ['mentions légales', 'légal', 'conditions'],
            'it': ['note legali', 'termini', 'privacy'],
            'es': ['aviso legal', 'términos', 'privacidad']
        }
        
        # Contact keywords
        self.contact_keywords = ['contact', 'kontakt', 'contatti', 'contacto', 'kontakte']
        
        # About keywords
        self.about_keywords = ['about', 'über uns', 'chi siamo', 'quiénes somos', 'qui sommes']

    def find_footer_links(self, soup: BeautifulSoup) -> List[str]:
        """Find links in the footer section."""
        links = []
        
        # Look for footer tag
        footer = soup.find('footer')
        if footer:
            for link in footer.find_all('a', href=True):
                links.append(link['href'])
                
        # Also look for divs with footer-related classes/ids
        footer_patterns = ['footer', 'foot', 'bottom', 'legal', 'site-footer']
        for pattern in footer_patterns:
            # Find by class
            elements = soup.find_all(class_=re.compile(pattern, re.I))
            for elem in elements:
                for link in elem.find_all('a', href=True):
                    links.append(link['href'])
                    
            # Find by id
            elem = soup.find(id=re.compile(pattern, re.I))
            if elem:
                for link in elem.find_all('a', href=True):
                    links.append(link['href'])
                    
        return list(set(links))  # Remove duplicates

    def find_legal_links(self, html: str, base_url: str) -> Dict[str, List[str]]:
        """Find all legal, contact, and about links from the page."""
        soup = BeautifulSoup(html, 'lxml')
        
        result = {
            'legal': [],
            'contact': [],
            'about': [],
            'footer': []
        }
        
        # Get all links
        all_links = []
        for link in soup.find_all('a', href=True):
            href = link['href']
            text = link.get_text().lower().strip()
            full_url = urljoin(base_url, href)
            
            # Skip external links
            if urlparse(full_url).netloc != urlparse(base_url).netloc:
                continue
                
            all_links.append((full_url, text, href))
        
        # Categorize links
        for url, text, href in all_links:
            href_lower = href.lower()
            
            # Check for legal links
            for lang_keywords in self.legal_keywords.values():
                if any(kw in text or kw in href_lower for kw in lang_keywords):
                    result['legal'].append(url)
                    break
                    
            # Check for contact links
            if any(kw in text or kw in href_lower for kw in self.contact_keywords):
                result['contact'].append(url)
                
            # Check for about links
            if any(kw in text or kw in href_lower for kw in self.about_keywords):
                result['about'].append(url)
        
        # Get footer links
        footer_links = self.find_footer_links(soup)
        for link in footer_links:
            full_url = urljoin(base_url, link)
            if urlparse(full_url).netloc == urlparse(base_url).netloc:
                result['footer'].append(full_url)
        
        # Remove duplicates
        for key in result:
            result[key] = list(set(result[key]))
            
        return result

    def extract_legal_links_smart(self, html: str, base_url: str) -> List[str]:
        """Smart extraction of legal links with priority ordering."""
        links = self.find_legal_links(html, base_url)
        
        # Priority order: legal links first, then footer links that might be legal
        priority_links = []
        
        # Add explicit legal links
        priority_links.extend(links['legal'])
        
        # Check footer links for legal keywords
        for footer_link in links['footer']:
            if footer_link not in priority_links:
                link_lower = footer_link.lower()
                for lang_keywords in self.legal_keywords.values():
                    if any(kw in link_lower for kw in lang_keywords):
                        priority_links.append(footer_link)
                        break
        
        # Add contact links (often contain legal info)
        for contact_link in links['contact']:
            if contact_link not in priority_links:
                priority_links.append(contact_link)
                
        return priority_links[:10]  # Return top 10 most likely legal pages
