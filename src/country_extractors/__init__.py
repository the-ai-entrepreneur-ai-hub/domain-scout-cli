"""Country-specific legal extractors."""
from .german_extractor import GermanExtractor
from .uk_extractor import UKExtractor
from .french_extractor import FrenchExtractor
from .generic_extractor import GenericExtractor

__all__ = ['GermanExtractor', 'UKExtractor', 'FrenchExtractor', 'GenericExtractor']
