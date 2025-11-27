"""
LLM-powered extraction using Crawl4AI + Ollama/DeepSeek.
"""
import json
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from .utils import logger

# Schema for legal entity extraction
class LegalEntitySchema(BaseModel):
    company_name: str = Field(description="Official registered company name including legal form (e.g., 'BurdaForward GmbH')")
    legal_form: str = Field(description="Legal form only (GmbH, AG, Ltd, Inc, etc.)")
    street_address: str = Field(description="Street name and number (e.g., 'St.-Martin-Straße 66')")
    postal_code: str = Field(description="ZIP/postal code (e.g., '81541')")
    city: str = Field(description="City name (e.g., 'München')")
    country: str = Field(description="Country name or code (e.g., 'Germany' or 'DE')")
    ceo_name: str = Field(description="CEO or Managing Director name")
    directors: list[str] = Field(description="List of other directors or board members")
    register_court: str = Field(description="Registration court (e.g., 'Amtsgericht München')")
    registration_number: str = Field(description="Registration number (e.g., 'HRB 213375')")
    vat_id: str = Field(description="VAT/Tax ID (e.g., 'DE296466883')")
    phone: str = Field(description="Primary phone number in international format")
    email: str = Field(description="Primary contact email")
    fax: str = Field(description="Fax number if available")

class LLMExtractor:
    def __init__(self, provider: str = "ollama/deepseek-r1:7b", api_base: str = "http://localhost:11434"):
        self.provider = provider
        self.api_base = api_base
        self.strategy = None
        self._init_strategy()
    
    def _init_strategy(self):
        """Initialize LLM extraction strategy."""
        try:
            from crawl4ai.extraction_strategy import LLMExtractionStrategy
            
            self.strategy = LLMExtractionStrategy(
                provider=self.provider,
                api_base=self.api_base,
                schema=LegalEntitySchema.model_json_schema(),
                extraction_type="schema",
                instruction="""
                Extract legal entity information from this German Impressum/Legal Notice page.
                Focus on finding:
                - The official company name with legal form (GmbH, AG, etc.)
                - Complete address (street, ZIP, city, country)
                - CEO/Geschäftsführer name(s)
                - Registration details (Amtsgericht, HRB number)
                - VAT ID (USt-IdNr)
                - Contact info (phone, email, fax)
                
                Return empty string "" for fields you cannot find.
                Be precise - only extract actual data, don't guess.
                """,
                verbose=False
            )
            logger.info(f"LLM Extractor initialized with {self.provider}")
        except ImportError as e:
            logger.error(f"Failed to import LLMExtractionStrategy: {e}")
            self.strategy = None
        except Exception as e:
            logger.error(f"Failed to initialize LLM strategy: {e}")
            self.strategy = None
    
    def is_available(self) -> bool:
        """Check if LLM extraction is available."""
        return self.strategy is not None
    
    async def extract(self, crawler, url: str) -> Optional[Dict[str, Any]]:
        """Extract legal entity data using LLM."""
        if not self.strategy:
            return None
            
        try:
            result = await crawler.arun(
                url=url,
                extraction_strategy=self.strategy,
                bypass_cache=True
            )
            
            if result.success and result.extracted_content:
                # Parse the extracted JSON
                data = json.loads(result.extracted_content)
                if isinstance(data, list) and len(data) > 0:
                    return data[0]
                elif isinstance(data, dict):
                    return data
                    
        except json.JSONDecodeError as e:
            logger.warning(f"LLM returned invalid JSON: {e}")
        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            
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
