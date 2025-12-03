"""
Context-Aware Legal Entity Extractor - Coordinate country-specific extractors.
Implements the new 5-step workflow: navigate → fetch → clean → extract → validate.
"""
import re
from typing import Dict, Optional, List, Tuple
from urllib.parse import urlparse

from .legal_navigation import legal_navigator
from .content_cleaner import content_cleaner
from .country_extractors.austrian_extractor import austrian_extractor
from .country_extractors.german_extractor import german_extractor
from .country_extractors.uk_extractor import uk_extractor
from .utils import logger


class ContextAwareExtractor:
    """Enhanced extraction using clean content and country-specific patterns."""
    
    def __init__(self):
        self.extractors = {
            'austrian': austrian_extractor,
            'german': german_extractor,
            'uk': uk_extractor,
        }
        
        # Country detection patterns
        self.country_indicators = {
            'austrian': [
                'österreich', 'austria', 'geschäftsführer', 'firmenbuch', 
                'fn ', 'handelsgericht', 'uid', 'atu', 'm.b.h'
            ],
            'german': [
                'deutschland', 'germany', 'handelsregister', 'amtsgericht',
                'hrb', 'hra', 'ust-idnr', 'registergericht'
            ],
            'uk': [
                'united kingdom', 'england', 'wales', 'scotland', 
                'companies house', 'company number', 'registered office',
                'limited', 'ltd', 'plc', 'director'
            ]
        }

    async def extract_enhanced(self, domain: str, homepage_html: str, 
                              fetch_func) -> Tuple[Dict[str, str], Dict[str, str]]:
        """
        Enhanced 5-step extraction workflow.
        
        Args:
            domain: Domain name (e.g., 'kurier.at')
            homepage_html: Raw homepage HTML
            fetch_func: Async function to fetch URLs
            
        Returns:
            Tuple of (extracted_data, metadata)
        """
        metadata = {
            'domain': domain,
            'extraction_method': 'enhanced_context_aware',
            'steps_completed': [],
            'errors': [],
            'urls_tried': []
        }
        
        try:
            # Step 1: Find Legal Notice URLs
            legal_urls = legal_navigator.find_legal_notice_urls(domain, homepage_html)
            metadata['urls_tried'] = legal_urls
            metadata['steps_completed'].append('legal_url_discovery')
            
            # Step 2: Fetch Legal Page Content
            legal_html = None
            legal_url = None
            
            for url in legal_urls:
                try:
                    legal_html = await fetch_func(url)
                    if legal_html and len(legal_html) > 500:  # Minimum content check
                        legal_url = url
                        break
                except Exception as e:
                    metadata['errors'].append(f"Failed to fetch {url}: {e}")
                    continue
                    
            if not legal_html:
                # Fallback to homepage
                legal_html = homepage_html
                legal_url = f"https://{domain}"
                metadata['errors'].append("No legal page found, using homepage")
                
            metadata['final_url'] = legal_url
            metadata['steps_completed'].append('legal_page_fetch')
            
            # Step 3: Clean Content
            clean_text = content_cleaner.extract_clean_content(legal_html, legal_url)
            content_quality = content_cleaner.get_content_quality_score(legal_html, clean_text)
            
            metadata.update({
                'raw_html_length': len(legal_html),
                'clean_text_length': len(clean_text),
                'content_quality_score': content_quality
            })
            metadata['steps_completed'].append('content_cleaning')
            
            if not clean_text or len(clean_text) < 100:
                metadata['errors'].append("Insufficient clean text extracted")
                return {}, metadata
                
            # Step 4: Context-Aware Country Detection
            country_type = self._detect_country_context(domain, clean_text)
            metadata['detected_country'] = country_type
            metadata['steps_completed'].append('country_detection')
            
            # Step 5: Extract Using Country-Specific Patterns
            extractor = self.extractors.get(country_type)
            if not extractor:
                metadata['errors'].append(f"No extractor for country: {country_type}")
                return {}, metadata
                
            extracted_data = extractor.extract(clean_text)
            metadata['fields_extracted'] = len(extracted_data)
            metadata['steps_completed'].append('legal_data_extraction')
            
            # Add metadata to results
            if extracted_data:
                extracted_data.update({
                    'extraction_source': 'context_aware',
                    'source_url': legal_url,
                    'content_quality': content_quality
                })
                
            logger.info(f"Enhanced extraction for {domain}: {len(extracted_data)} fields, quality: {content_quality}")
            
            return extracted_data, metadata
            
        except Exception as e:
            metadata['errors'].append(f"Extraction failed: {e}")
            logger.error(f"Enhanced extraction error for {domain}: {e}")
            return {}, metadata

    def _detect_country_context(self, domain: str, clean_text: str) -> str:
        """
        Detect country/legal system from domain TLD and content.
        
        Returns:
            Country identifier for extractor selection
        """
        text_lower = clean_text.lower()
        
        # Primary detection: TLD-based
        domain_lower = domain.lower()
        if domain_lower.endswith('.at'):
            return 'austrian'
        elif domain_lower.endswith('.de'):
            return 'german'
        elif domain_lower.endswith(('.co.uk', '.uk')):
            return 'uk'
            
        # Secondary detection: Content-based scoring
        country_scores = {}
        
        for country, indicators in self.country_indicators.items():
            score = sum(1 for indicator in indicators if indicator in text_lower)
            if score > 0:
                country_scores[country] = score
                
        # Return highest scoring country, or default to TLD-based guess
        if country_scores:
            best_country = max(country_scores.keys(), key=lambda k: country_scores[k])
            return best_country
            
        # Fallback based on common TLDs
        tld_fallbacks = {
            '.fr': 'german',  # No French extractor yet, German similar
            '.ch': 'german',  # Switzerland uses German patterns
            '.es': 'uk',      # Default to English patterns
            '.it': 'uk',
        }
        
        for tld, fallback in tld_fallbacks.items():
            if domain_lower.endswith(tld):
                return fallback
                
        return 'uk'  # Default fallback

    def extract_from_clean_text(self, clean_text: str, country_hint: str = None) -> Dict[str, str]:
        """
        Extract legal data from already cleaned text.
        
        Args:
            clean_text: Pre-cleaned text content
            country_hint: Optional country hint ('austrian', 'german', 'uk')
            
        Returns:
            Extracted legal entity data
        """
        if not clean_text:
            return {}
            
        # Auto-detect country if not provided
        if not country_hint:
            country_hint = self._detect_country_from_text(clean_text)
            
        extractor = self.extractors.get(country_hint)
        if not extractor:
            logger.warning(f"Unknown country hint: {country_hint}, trying all extractors")
            return self._try_all_extractors(clean_text)
            
        return extractor.extract(clean_text)

    def _detect_country_from_text(self, text: str) -> str:
        """Detect country from text content only."""
        text_lower = text.lower()
        
        country_scores = {}
        for country, indicators in self.country_indicators.items():
            score = sum(1 for indicator in indicators if indicator in text_lower)
            if score > 0:
                country_scores[country] = score
                
        if country_scores:
            return max(country_scores.keys(), key=lambda k: country_scores[k])
            
        return 'uk'  # Default

    def _try_all_extractors(self, clean_text: str) -> Dict[str, str]:
        """Try all extractors and return best result."""
        best_result = {}
        best_confidence = 0
        
        for country, extractor in self.extractors.items():
            try:
                result = extractor.extract(clean_text)
                confidence = result.get('extraction_confidence', 0)
                
                if confidence > best_confidence:
                    best_result = result
                    best_confidence = confidence
                    
            except Exception as e:
                logger.debug(f"Extractor {country} failed: {e}")
                continue
                
        return best_result

    def get_extraction_quality_report(self, extracted_data: Dict, metadata: Dict) -> Dict:
        """Generate quality assessment report."""
        report = {
            'extraction_success': len(extracted_data) > 0,
            'fields_found': len(extracted_data),
            'confidence_score': extracted_data.get('extraction_confidence', 0),
            'content_quality': metadata.get('content_quality_score', 0),
            'steps_completed': len(metadata.get('steps_completed', [])),
            'errors': len(metadata.get('errors', [])),
            'data_completeness': 0
        }
        
        # Calculate data completeness
        key_fields = ['registration_number', 'directors', 'legal_form', 'vat_id', 'street', 'postal_code']
        fields_with_data = sum(1 for field in key_fields if extracted_data.get(field))
        report['data_completeness'] = round(fields_with_data / len(key_fields) * 100)
        
        # Overall quality grade
        if report['confidence_score'] >= 80 and report['data_completeness'] >= 80:
            report['quality_grade'] = 'A'
        elif report['confidence_score'] >= 60 and report['data_completeness'] >= 60:
            report['quality_grade'] = 'B'
        elif report['confidence_score'] >= 40 and report['data_completeness'] >= 40:
            report['quality_grade'] = 'C'
        else:
            report['quality_grade'] = 'D'
            
        return report


# Global instance
context_extractor = ContextAwareExtractor()
