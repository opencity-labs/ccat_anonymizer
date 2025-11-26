"""
PII Detection Models for regex-based and SpaCy-based detection.

This module contains PII detection implementations:
- RegexPIIDetector: Pattern-based detection using regular expressions
- SpacyPIIDetector: NER-based detection using SpaCy models
"""

import re
import logging
import subprocess
import sys
from typing import List, Tuple

logger = logging.getLogger(__name__)

# Global variables for SpaCy models to avoid repeated loading
_spacy_models = {}
_spacy_available = None

def _check_spacy_availability() -> bool:
    """Check if SpaCy is available."""
    global _spacy_available
    if _spacy_available is not None:
        return _spacy_available
    
    try:
        import spacy
        _spacy_available = True
    except ImportError:
        logger.warning("SpaCy not installed. Install with: pip install spacy")
        _spacy_available = False
    
    return _spacy_available

def _download_model(model_name: str) -> bool:
    """Download a SpaCy model if not present."""
    try:
        logger.info(f"Downloading SpaCy model: {model_name}")
        result = subprocess.run([
            sys.executable, "-m", "spacy", "download", model_name
        ], capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            logger.info(f"Successfully downloaded {model_name}")
            return True
        else:
            logger.error(f"Failed to download {model_name}: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        logger.error(f"Timeout downloading {model_name}")
        return False
    except Exception as e:
        logger.error(f"Error downloading {model_name}: {e}")
        return False

def _get_spacy_model(model_name: str):
    """Get or load a SpaCy model, downloading if necessary."""
    global _spacy_models
    
    if model_name in _spacy_models:
        return _spacy_models[model_name]
    
    try:
        import spacy
        
        # First try to load the model
        try:
            nlp = spacy.load(model_name)
            _spacy_models[model_name] = nlp
            logger.info(f"Loaded SpaCy model: {model_name}")
            return nlp
        except OSError:
            # Model not found, try to download it
            logger.info(f"SpaCy model '{model_name}' not found, attempting to download...")
            if _download_model(model_name):
                # Try loading again after download
                try:
                    nlp = spacy.load(model_name)
                    _spacy_models[model_name] = nlp
                    logger.info(f"Successfully loaded downloaded model: {model_name}")
                    return nlp
                except OSError:
                    logger.error(f"Failed to load model '{model_name}' even after download")
                    return None
            else:
                logger.error(f"Failed to download model '{model_name}'")
                return None
    except ImportError:
        logger.error("SpaCy not installed")
        return None


class RegexPIIDetector:
    """
    Regex-based PII detection for emails, phone numbers, and Italian fiscal codes.
    
    This detector uses regular expressions to identify emails, phone numbers, and Italian fiscal codes.
    """
    
    def __init__(self):
        # Email pattern - comprehensive but not overly permissive
        self.email_pattern = re.compile(
            r'\b[A-Za-z0-9]([A-Za-z0-9._+-]*[A-Za-z0-9])?@[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,}\b'
        )
        
        # Simple phone pattern: 7+ digits that may be separated by spaces
        self.phone_pattern = re.compile(r'''
            (?:
                # International with + prefix (digits may have spaces)
                \+(?:\d[\s]?){6,14}\d |
                # International with 00 prefix (digits may have spaces)  
                (?<!\d)00(?:\d[\s]?){5,13}\d(?!\d) |
                # Any sequence of 7+ digits (may have spaces between them)
                (?<!\d)(?:\d[\s]?){6,14}\d(?!\d)
            )
        ''', re.VERBOSE)
        
        # Italian fiscal code pattern: 6 letters, 2 numbers, 1 letter, 2 numbers, 1 letter, 3 numbers, 1 letter
        self.fiscal_code_pattern = re.compile(r'\b[A-Z]{6}[0-9]{2}[A-Z][0-9]{2}[A-Z][0-9]{3}[A-Z]\b')
    
    def detect(self, text: str) -> List[Tuple[int, int, str, str]]:
        """
        Detect email, phone number, and Italian fiscal code PII entities in text using regex patterns.
        
        Args:
            text: Input text to analyze
            
        Returns:
            List of tuples: (start_pos, end_pos, entity_type, entity_text)
        """
        spans = []
        
        # Email detection
        for match in self.email_pattern.finditer(text):
            spans.append((match.start(), match.end(), 'EMAIL', match.group()))
        
        # Phone detection - simple approach: 7+ consecutive digits
        for match in self.phone_pattern.finditer(text):
            phone_text = match.group().strip()
            digits_only = re.sub(r'[^\d]', '', phone_text)
            
            # Must have 7-15 digits to be considered a phone
            if 7 <= len(digits_only) <= 15:
                spans.append((match.start(), match.end(), 'PHONE', phone_text))
        
        # Italian fiscal code detection
        for match in self.fiscal_code_pattern.finditer(text):
            spans.append((match.start(), match.end(), 'FISCAL_CODE', match.group()))
        
        # Remove overlapping spans (prefer longer ones, then by position)
        return self._remove_overlaps(spans)
    
    def _remove_overlaps(self, spans: List[Tuple[int, int, str, str]]) -> List[Tuple[int, int, str, str]]:
        """Remove overlapping spans, preferring longer matches."""
        if not spans:
            return spans
            
        # Sort by start position, then by length (descending)
        spans.sort(key=lambda x: (x[0], -(x[1] - x[0])))
        
        non_overlapping = []
        last_end = -1
        
        for span in spans:
            start, end, entity_type, text = span
            if start >= last_end:
                non_overlapping.append(span)
                last_end = end
        
        return non_overlapping


class SpacyPIIDetector:
    """
    SpaCy-based PII detection for names, organizations, and addresses.
    
    This detector uses SpaCy's Named Entity Recognition (NER) to identify
    person names, organization names, and location/address information.
    Supports multilingual detection.
    """
    
    def __init__(self, model_preference: List[str] = None):
        """
        Initialize SpaCy detector with automatic model downloading.
        
        Args:
            model_preference: List of model names to try in order of preference
        """
        if model_preference is None:
            model_preference = ["xx_ent_wiki_sm", "en_core_web_sm"]
        
        self.nlp = None
        self.model_name = None
        
        if not _check_spacy_availability():
            raise RuntimeError("SpaCy not available. Please install with: pip install spacy")
        
        # Try to load models in order of preference, downloading if necessary
        for model_name in model_preference:
            logger.info(f"Attempting to load SpaCy model: {model_name}")
            nlp = _get_spacy_model(model_name)
            if nlp is not None:
                self.nlp = nlp
                self.model_name = model_name
                logger.info(f"Successfully initialized SpaCy detector with model: {model_name}")
                break
            else:
                logger.warning(f"Failed to load model: {model_name}")
        
        if self.nlp is None:
            # If no preferred models work, try downloading a basic English model as fallback
            fallback_model = "en_core_web_sm"
            logger.info(f"No preferred models available, trying fallback model: {fallback_model}")
            nlp = _get_spacy_model(fallback_model)
            if nlp is not None:
                self.nlp = nlp
                self.model_name = fallback_model
                logger.info(f"Successfully initialized SpaCy detector with fallback model: {fallback_model}")
            else:
                raise RuntimeError(
                    "Failed to load any SpaCy models. Please check your internet connection "
                    "and ensure you have sufficient permissions to download models."
                )
    
    def detect(self, text: str) -> List[Tuple[int, int, str, str]]:
        """
        Detect person names, organizations, and locations using SpaCy NER.
        
        Args:
            text: Input text to analyze
            
        Returns:
            List of tuples: (start_pos, end_pos, entity_type, entity_text)
        """
        if self.nlp is None:
            return []
        
        spans = []
        
        try:
            # Process text with SpaCy
            doc = self.nlp(text)
            
            for ent in doc.ents:
                entity_type = None
                
                # Map SpaCy entity labels to our types
                if ent.label_ in ["PERSON", "PER"]:
                    entity_type = "PERSON"
                elif ent.label_ in ["ORG", "ORGANIZATION"]:
                    entity_type = "ORGANIZATION"
                elif ent.label_ in ["GPE", "LOC", "LOCATION", "FAC", "FACILITY"]:
                    # GPE: Countries, cities, states
                    # LOC: Mountain ranges, bodies of water
                    # FAC: Buildings, airports, highways, bridges
                    entity_type = "LOCATION"
                
                if entity_type:
                    spans.append((
                        ent.start_char,
                        ent.end_char,
                        entity_type,
                        ent.text
                    ))
            
        except Exception as e:
            logger.error(f"Error in SpaCy NER processing: {e}")
            return []
        
        # Remove overlapping spans
        return self._remove_overlaps(spans)
    
    def _remove_overlaps(self, spans: List[Tuple[int, int, str, str]]) -> List[Tuple[int, int, str, str]]:
        """Remove overlapping spans, preferring longer matches."""
        if not spans:
            return spans
            
        # Sort by start position, then by length (descending)
        spans.sort(key=lambda x: (x[0], -(x[1] - x[0])))
        
        non_overlapping = []
        last_end = -1
        
        for span in spans:
            start, end, entity_type, text = span
            if start >= last_end:
                non_overlapping.append(span)
                last_end = end
        
        return non_overlapping


def create_detector(detector_type: str, **kwargs) -> object:
    """
    Factory function to create PII detectors.
    
    Args:
        detector_type: Type of detector ('regex', 'spacy')
        **kwargs: Additional arguments for specific detectors
        
    Returns:
        Detector instance
    """
    detector_type = detector_type.lower()
    
    if detector_type == 'regex':
        return RegexPIIDetector()
    elif detector_type == 'spacy':
        if not _check_spacy_availability():
            raise RuntimeError("SpaCy not available. Please install with: pip install spacy")
        try:
            return SpacyPIIDetector(**kwargs)
        except RuntimeError as e:
            logger.error(f"Failed to initialize SpaCy detector: {e}")
            raise
    else:
        raise ValueError(f"Unknown detector type: {detector_type}. Supported types: 'regex', 'spacy'")
    