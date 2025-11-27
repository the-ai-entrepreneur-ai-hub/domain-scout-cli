"""
LLM-powered extraction using Ollama/DeepSeek directly via litellm.
"""
import json
import re
from typing import Dict, Any, Optional
from .utils import logger

EXTRACTION_PROMPT = """Extract legal entity information from this German Impressum page.
Return a JSON object with these fields (use empty string "" if not found):

{
  "company_name": "Official company name with legal form",
  "legal_form": "Legal form only (GmbH, AG, etc.)",
  "street_address": "Street and number",
  "postal_code": "ZIP code",
  "city": "City name",
  "country": "Country",
  "ceo_name": "CEO/Geschäftsführer name",
  "directors": ["other directors"],
  "register_court": "e.g. Amtsgericht München",
  "registration_number": "e.g. HRB 12345",
  "vat_id": "VAT/USt-IdNr",
  "phone": "Phone number",
  "email": "Email address",
  "fax": "Fax number"
}

PAGE CONTENT:
"""

class LLMExtractor:
    def __init__(self, provider: str = "ollama/deepseek-r1:7b", api_base: str = "http://localhost:11434"):
        self.provider = provider
        self.api_base = api_base
        self.available = False
        self._init_litellm()
    
    def _init_litellm(self):
        """Initialize litellm for direct Ollama calls."""
        try:
            import litellm
            # Set Ollama API base
            litellm.api_base = self.api_base
            self.litellm = litellm
            self.available = True
            logger.info(f"LLM Extractor initialized with {self.provider}")
        except ImportError:
            logger.error("litellm not installed. Run: pip install litellm")
            self.available = False
        except Exception as e:
            logger.error(f"Failed to initialize litellm: {e}")
            self.available = False
    
    def is_available(self) -> bool:
        """Check if LLM extraction is available."""
        return self.available
    
    async def extract_from_text(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract legal entity data from text using LLM."""
        if not self.available:
            return None
        
        # Truncate text to avoid token limits (approx 4000 chars)
        text = text[:4000]
        prompt = EXTRACTION_PROMPT + text
        
        try:
            logger.info(f"LLM: Calling {self.provider}...")
            
            response = await self.litellm.acompletion(
                model=self.provider,
                messages=[{"role": "user", "content": prompt}],
                api_base=self.api_base,
                temperature=0.1,
                max_tokens=1000
            )
            
            content = response.choices[0].message.content
            logger.info(f"LLM response length: {len(content)}")
            
            # Extract JSON from response (handle markdown code blocks)
            json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', content)
            if json_match:
                json_str = json_match.group(1).strip()
            else:
                # Try to find raw JSON
                json_match = re.search(r'\{[\s\S]*\}', content)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    logger.warning("No JSON found in LLM response")
                    return None
            
            data = json.loads(json_str)
            logger.info(f"LLM extracted: {list(data.keys())}")
            return data
            
        except json.JSONDecodeError as e:
            logger.warning(f"LLM returned invalid JSON: {e}")
        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            
        return None
    
    async def extract(self, crawler, url: str) -> Optional[Dict[str, Any]]:
        """Extract from URL by first fetching content."""
        try:
            result = await crawler.arun(url=url, bypass_cache=True)
            if result.success and result.markdown:
                return await self.extract_from_text(result.markdown)
        except Exception as e:
            logger.error(f"Failed to fetch {url} for LLM: {e}")
        return None
    
    def merge_with_regex(self, llm_data: Dict, regex_data: Dict) -> Dict:
        """Merge LLM extraction with regex extraction, preferring LLM for key fields."""
        merged = regex_data.copy()
        
        if not llm_data:
            return merged
            
        # LLM takes priority for these fields (often more accurate)
        priority_fields = [
            ('company_name', 'legal_name'),
            ('legal_form', 'legal_form'),
            ('street_address', 'registered_street'),
            ('postal_code', 'registered_zip'),
            ('city', 'registered_city'),
            ('country', 'registered_country'),
            ('ceo_name', 'ceo'),
            ('register_court', 'register_court'),
            ('registration_number', 'registration_number'),
            ('vat_id', 'vat_id'),
            ('phone', 'legal_phone'),
            ('email', 'legal_email'),
            ('fax', 'fax'),
        ]
        
        for llm_key, regex_key in priority_fields:
            llm_val = llm_data.get(llm_key, '')
            if llm_val and str(llm_val).strip():
                merged[regex_key] = str(llm_val).strip()
        
        # Handle directors list
        if llm_data.get('directors'):
            merged['directors'] = llm_data['directors']
            
        return merged
