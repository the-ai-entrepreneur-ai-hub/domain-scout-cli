"""
Section Extractor - Isolates legal content from HTML noise.
Removes navigation, menus, headers, footers before extraction.
"""
import re
from typing import Optional, Tuple
from bs4 import BeautifulSoup, Tag, NavigableString

class SectionExtractor:
    """Extracts and isolates legal content sections from HTML."""
    
    # CSS selectors for noise elements to remove
    NOISE_SELECTORS = [
        'nav', 'header', 'footer', 'aside',
        '.navigation', '.nav', '.menu', '.navbar', '.header', '.footer',
        '.sidebar', '.widget', '.banner', '.ad', '.advertisement',
        '.cookie', '.cookies', '.cookie-banner', '.cookie-consent',
        '.newsletter', '.subscribe', '.subscription',
        '.social', '.social-media', '.share',
        '.breadcrumb', '.breadcrumbs',
        '.search', '.search-form',
        '.cart', '.basket', '.wishlist',
        '.login', '.register', '.account',
        '.popup', '.modal', '.overlay',
        '#nav', '#navigation', '#menu', '#header', '#footer',
        '#sidebar', '#cookie', '#newsletter',
        '[role="navigation"]', '[role="banner"]', '[role="contentinfo"]',
    ]
    
    # Keywords to identify legal sections
    LEGAL_SECTION_KEYWORDS = [
        'impressum', 'imprint', 'legal', 'rechtlich',
        'angaben', 'gemäß', 'tmg', 'telemedien',
        'anbieterkennzeichnung', 'pflichtangaben',
        'company information', 'legal notice',
        'mentions légales', 'aviso legal', 'note legali',
    ]
    
    # IDs/classes that likely contain legal content
    LEGAL_SECTION_PATTERNS = [
        r'impressum', r'imprint', r'legal', r'rechtlich',
        r'main[-_]?content', r'content[-_]?main',
        r'page[-_]?content', r'content[-_]?area',
        r'article', r'main', r'primary',
    ]

    def remove_noise(self, soup: BeautifulSoup) -> BeautifulSoup:
        """Remove navigation, headers, footers, and other noise elements."""
        # Make a copy to avoid modifying the original
        soup = BeautifulSoup(str(soup), 'lxml')
        
        # Remove script and style elements
        for element in soup(['script', 'style', 'noscript', 'iframe', 'svg']):
            element.decompose()
            
        # Remove noise elements by selector
        for selector in self.NOISE_SELECTORS:
            try:
                for element in soup.select(selector):
                    element.decompose()
            except:
                pass  # Some selectors might not be valid
                
        return soup

    def find_legal_section(self, soup: BeautifulSoup) -> Optional[Tag]:
        """Find the main legal content section."""
        
        # Strategy 1: Look for element with legal-related ID or class
        for pattern in self.LEGAL_SECTION_PATTERNS:
            # By ID
            element = soup.find(id=re.compile(pattern, re.IGNORECASE))
            if element and len(element.get_text(strip=True)) > 100:
                return element
                
            # By class
            element = soup.find(class_=re.compile(pattern, re.IGNORECASE))
            if element and len(element.get_text(strip=True)) > 100:
                return element
        
        # Strategy 2: Look for main/article elements
        for tag in ['main', 'article']:
            element = soup.find(tag)
            if element and len(element.get_text(strip=True)) > 100:
                return element
                
        # Strategy 3: Find div with most legal keywords
        best_div = None
        best_score = 0
        
        for div in soup.find_all(['div', 'section']):
            text = div.get_text().lower()
            score = sum(1 for kw in self.LEGAL_SECTION_KEYWORDS if kw in text)
            if score > best_score and len(text) > 200:
                best_score = score
                best_div = div
                
        if best_div and best_score >= 2:
            return best_div
            
        # Strategy 4: Look for the body content
        body = soup.find('body')
        return body

    def extract_clean_text(self, soup: BeautifulSoup) -> str:
        """Extract clean text from soup, preserving some structure."""
        # Remove noise first
        clean_soup = self.remove_noise(soup)
        
        # Find legal section
        legal_section = self.find_legal_section(clean_soup)
        
        if legal_section:
            # Get text with newlines for structure
            text = legal_section.get_text(separator='\n', strip=True)
        else:
            text = clean_soup.get_text(separator='\n', strip=True)
            
        # Clean up multiple newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text

    def extract_structured_sections(self, soup: BeautifulSoup) -> dict:
        """Extract text organized by HTML structure (headings, paragraphs)."""
        clean_soup = self.remove_noise(soup)
        legal_section = self.find_legal_section(clean_soup) or clean_soup
        
        sections = {
            'headings': [],
            'paragraphs': [],
            'lists': [],
            'tables': [],
            'address_blocks': [],
        }
        
        # Extract headings with their following content
        for heading in legal_section.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
            heading_text = heading.get_text(strip=True)
            if heading_text:
                # Get content until next heading
                content = []
                for sibling in heading.find_next_siblings():
                    if sibling.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                        break
                    if sibling.name in ['p', 'div', 'span']:
                        text = sibling.get_text(strip=True)
                        if text:
                            content.append(text)
                            
                sections['headings'].append({
                    'title': heading_text,
                    'content': '\n'.join(content)
                })
                
        # Extract paragraphs
        for p in legal_section.find_all('p'):
            text = p.get_text(strip=True)
            if text and len(text) > 10:
                sections['paragraphs'].append(text)
                
        # Extract lists
        for ul in legal_section.find_all(['ul', 'ol']):
            items = [li.get_text(strip=True) for li in ul.find_all('li')]
            if items:
                sections['lists'].append(items)
                
        # Extract address blocks
        for addr in legal_section.find_all('address'):
            text = addr.get_text(separator=', ', strip=True)
            if text:
                sections['address_blocks'].append(text)
                
        # Extract tables (often used for legal info)
        for table in legal_section.find_all('table'):
            rows = []
            for tr in table.find_all('tr'):
                cells = [td.get_text(strip=True) for td in tr.find_all(['td', 'th'])]
                if cells:
                    rows.append(cells)
            if rows:
                sections['tables'].append(rows)
                
        return sections

    def get_text_near_keyword(self, soup: BeautifulSoup, keyword: str, 
                              chars_before: int = 50, chars_after: int = 200) -> Optional[str]:
        """Get text surrounding a specific keyword."""
        clean_soup = self.remove_noise(soup)
        text = clean_soup.get_text(separator=' ', strip=True)
        
        # Find keyword position (case-insensitive)
        pattern = re.compile(re.escape(keyword), re.IGNORECASE)
        match = pattern.search(text)
        
        if match:
            start = max(0, match.start() - chars_before)
            end = min(len(text), match.end() + chars_after)
            return text[start:end]
            
        return None

    def extract_legal_content(self, html: str) -> Tuple[str, dict]:
        """
        Main method: Extract legal content from HTML.
        Returns (clean_text, structured_sections).
        """
        soup = BeautifulSoup(html, 'lxml')
        
        clean_text = self.extract_clean_text(soup)
        structured = self.extract_structured_sections(soup)
        
        return clean_text, structured
