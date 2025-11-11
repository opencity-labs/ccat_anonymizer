"""
PII Detection Models for regex-based detection.

This module contains regex-based PII detection implementation:
- RegexPIIDetector: Pattern-based detection using regular expressions
"""

import re
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)


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
        
        # Phone patterns for international formats
        self.phone_pattern = re.compile(r'''
            (?:\+\d{1,3}[-.\s]?)?          # Optional country code
            (?:\(\d{1,4}\)|[\d]{1,4})      # Area code (parentheses or digits)
            [-.\s]?                        # Optional separator
            \d{2,4}                        # First part
            [-.\s]?                        # Optional separator
            \d{2,4}                        # Second part
            (?:[-.\s]?\d{1,4})?            # Optional extension
            (?:\s+ext\.?\s*\d+)?           # Optional "ext" extension
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
        
        # Phone detection
        for match in self.phone_pattern.finditer(text):
            phone_text = match.group().strip()
            # Filter out obvious non-phone patterns
            digits_only = re.sub(r'[^\d]', '', phone_text)
            if 7 <= len(digits_only) <= 15:  # Reasonable phone number length
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


def create_detector(detector_type: str, **kwargs) -> object:
    """
    Factory function to create PII detectors.
    
    Args:
        detector_type: Type of detector ('regex')
        **kwargs: Additional arguments for specific detectors
        
    Returns:
        Detector instance
    """
    detector_type = detector_type.lower()
    
    if detector_type == 'regex':
        return RegexPIIDetector()
    
    else:
        raise ValueError(f"Unknown detector type: {detector_type}")