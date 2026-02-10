"""
PII Detection Models for regex-based and SpaCy-based detection.

This module contains PII detection implementations:
- RegexPIIDetector: Pattern-based detection using regular expressions
- SpacyPIIDetector: NER-based detection using SpaCy models
"""

import re
import subprocess
import sys
from typing import List, Tuple
from collections import defaultdict
from cat.log import log

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
        _spacy_available = False
    
    return _spacy_available

def _download_model(model_name: str) -> bool:
    """Download a SpaCy model if not present."""
    try:
        result = subprocess.run([
            sys.executable, "-m", "spacy", "download", model_name
        ], capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            return True
        else:
            return False
    except subprocess.TimeoutExpired:
        return False
    except Exception as e:
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
            return nlp
        except OSError:
            # Model not found, try to download it
            if _download_model(model_name):
                # Try loading again after download
                try:
                    nlp = spacy.load(model_name)
                    _spacy_models[model_name] = nlp
                    return nlp
                except OSError:
                    return None
            else:
                return None
    except ImportError:
        return None


class RegexPIIDetector:
    """
    Regex-based PII detection for emails, phone numbers, and Italian fiscal codes.
    
    This detector uses regular expressions to identify emails, phone numbers, and Italian fiscal codes.
    """
    
    def __init__(self, settings=None):
        self.settings = settings or {}
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
        if self.settings.get('anonymize_email', True):
            for match in self.email_pattern.finditer(text):
                spans.append((match.start(), match.end(), 'EMAIL', match.group()))
        
        # Phone detection - simple approach: 7+ consecutive digits
        if self.settings.get('anonymize_phone', True):
            for match in self.phone_pattern.finditer(text):
                phone_text = match.group().strip()
                digits_only = re.sub(r'[^\d]', '', phone_text)
                
                # Must have 7-15 digits to be considered a phone
                if 7 <= len(digits_only) <= 15:
                    spans.append((match.start(), match.end(), 'PHONE', phone_text))
        
        # Italian fiscal code detection
        if self.settings.get('anonymize_fiscal_code', True):
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
    
    def __init__(self, model_preference: List[str] = None, settings=None, confidence_threshold: float = 0.65):
        """
        Initialize SpaCy detector with automatic model downloading.

        Args:
            model_preference: List of model names to try in order of preference
            settings: Settings dictionary for conditional detection
            confidence_threshold: Minimum confidence score for entity detection
        """
        if model_preference is None:
            model_preference = ["xx_ent_wiki_sm", "en_core_web_sm"]

        self.settings = settings or {}
        self.nlp = None
        self.model_name = None
        self.confidence_threshold = confidence_threshold

        if not _check_spacy_availability():
            raise RuntimeError("SpaCy not available. Please install with: pip install spacy")

        # Try to load models in order of preference, downloading if necessary
        for model_name in model_preference:
            nlp = _get_spacy_model(model_name)
            if nlp is not None:
                self.nlp = nlp
                self.model_name = model_name
                break
            else:
                pass

        if self.nlp is None:
            # If no preferred models work, try downloading a basic English model as fallback
            fallback_model = "en_core_web_sm"
            nlp = _get_spacy_model(fallback_model)
            if nlp is not None:
                self.nlp = nlp
                self.model_name = fallback_model
            else:
                raise RuntimeError(
                    "Failed to load any SpaCy models. Please check your internet connection "
                    "and ensure you have sufficient permissions to download models."
                )

    def detect(self, text: str) -> List[Tuple[int, int, str, str]]:
        """
        Detect person names, organizations, and locations using SpaCy NER with confidence scores.

        Args:
            text: Input text to analyze

        Returns:
            List of tuples: (start_pos, end_pos, entity_type, entity_text)
        """
        if self.nlp is None:
            return []

        spans = []

        try:
            detected_entities = []
            
            # Check if there is an NER pipe and if it supports beam search
            # Note: beam search is available for transition-based NER (most sm/md/lg models)
            if "ner" in self.nlp.pipe_names:
                ner = self.nlp.get_pipe("ner")
                
                # Pre-process doc with preceding pipes (tok2vec, tagger, etc.)
                doc = self.nlp.make_doc(text)
                for name, proc in self.nlp.pipeline:
                    if name != "ner":
                        doc = proc(doc)
                
                # Use beam search to get multiple parses and aggregate scores
                # beam_width can be adjusted for speed vs accuracy
                beams = ner.beam_parse([doc], beam_width=16, beam_density=0.0001)
                
                entity_scores = defaultdict(float)
                for score, ents in ner.moves.get_beam_parses(beams[0]):
                    for start, end, label in ents:
                        # Aggregate probability of paths containing this entity
                        entity_scores[(start, end, label)] += score
                
                for (start, end, label), confidence in entity_scores.items():
                    span = doc[start:end]
                    detected_entities.append({
                        "text": span.text,
                        "label": label,
                        "start": span.start_char,
                        "end": span.end_char,
                        "confidence": confidence
                    })
            else:
                # Fallback to standard doc.ents if NER pipe is not found
                doc = self.nlp(text)
                for ent in doc.ents:
                    detected_entities.append({
                        "text": ent.text,
                        "label": ent.label_,
                        "start": ent.start_char,
                        "end": ent.end_char,
                        "confidence": 1.0  # Default confidence
                    })

            for ent in detected_entities:
                entity_type = None
                label = ent["label"]
                confidence = ent["confidence"]

                # Map SpaCy entity labels to our types
                if label in ["PERSON", "PER"] and self.settings.get('anonymize_names', True):
                    entity_type = "PERSON"
                elif label in ["ORG", "ORGANIZATION"] and self.settings.get('anonymize_organizations', True):
                    entity_type = "ORGANIZATION"
                elif label in ["GPE", "LOC", "LOCATION", "FAC", "FACILITY"] and self.settings.get('anonymize_locations', True):
                    entity_type = "LOCATION"

                if entity_type:
                    # Filter by confidence threshold
                    log.error(f"Entity '{ent['text']}' ({entity_type}) detected with confidence: {confidence:.4f}")
                    if confidence < self.confidence_threshold:
                        log.error(f"Entity '{ent['text']}' skipped (confidence below threshold {self.confidence_threshold})")
                        continue
                    
                    spans.append((
                        ent["start"],
                        ent["end"],
                        entity_type,
                        ent["text"]
                    ))

        except Exception as e:
            log.error(f"Error in SpaCy detection: {e}")
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
        return RegexPIIDetector(settings=kwargs.get('settings'))
    elif detector_type == 'spacy':
        if not _check_spacy_availability():
            raise RuntimeError("SpaCy not available. Please install with: pip install spacy")
        try:
            return SpacyPIIDetector(settings=kwargs.get('settings'), **{k: v for k, v in kwargs.items() if k != 'settings'})
        except RuntimeError as e:
            raise
    else:
        raise ValueError(f"Unknown detector type: {detector_type}. Supported types: 'regex', 'spacy'")


def check_and_download_spacy_models(model_preference: List[str] = None) -> bool:
    """
    Explicitly check for and download Spacy models if needed.
    """
    if model_preference is None:
        model_preference = ["xx_ent_wiki_sm", "en_core_web_sm"]
        
    if not _check_spacy_availability():
        return False
        
    for model_name in model_preference:
        if _get_spacy_model(model_name):
            return True
            
    # Fallback
    fallback_model = "en_core_web_sm"
    if _get_spacy_model(fallback_model):
        return True
        
    return False
