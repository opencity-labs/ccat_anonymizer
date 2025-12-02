from cat.mad_hatter.decorators import hook
from cat.looking_glass.stray_cat import StrayCat
from langchain.docstore.document import Document
from typing import Dict, Tuple, List
import uuid
from cat.log import log
from urllib.parse import urlparse

from .detectors import create_detector


def _remove_overlapping_spans(spans: List[Tuple[int, int, str, str]]) -> List[Tuple[int, int, str, str]]:
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


def generate_placeholder(entity_type: str) -> str:
    """Generate a placeholder for anonymized data."""
    # Create a unique identifier for this entity
    unique_id = str(uuid.uuid4())[:8]
    return f"[{entity_type}_{unique_id}]"


def anonymize_text(text: str, cat: StrayCat) -> Tuple[str, Dict[str, str]]:
    """
    Anonymize text using regex detection for emails, phones, and Italian fiscal codes,
    and optionally SpaCy detection for names, organizations, and addresses.

    Returns:
        Tuple of (anonymized_text, mapping_dict)
    """
    settings = cat.mad_hatter.get_plugin().load_settings()
    debug_enabled = settings.get('debug_logging', False)
    
    # Check if any SpaCy detection is enabled
    enable_spacy = (settings.get('anonymize_names', True) or 
                   settings.get('anonymize_locations', True) or 
                   settings.get('anonymize_organizations', True))
    
    if debug_enabled:
        log.debug(f"Starting PII detection on text: '{text[:100]}...'")
        log.debug(f"SpaCy detection needed: {enable_spacy}")
    
    all_spans = []
    
    # Always use regex for emails, phones, and fiscal codes
    try:
        regex_detector = create_detector('regex', settings=settings)
        regex_spans = regex_detector.detect(text)
        all_spans.extend(regex_spans)
        
        if debug_enabled and regex_spans:
            log.debug(f"Regex detector found {len(regex_spans)} entities")
    except Exception as e:
        log.error(f"Error in regex detection: {e}")
    
    # Optionally use SpaCy for names, organizations, and addresses
    if enable_spacy:
        try:
            spacy_detector = create_detector('spacy', settings=settings)
            spacy_spans = spacy_detector.detect(text)
            all_spans.extend(spacy_spans)
            
            if debug_enabled and spacy_spans:
                log.debug(f"SpaCy detector found {len(spacy_spans)} entities")
        except RuntimeError as e:
            log.error(f"Failed to initialize SpaCy detector: {e}")
            log.info("Continuing with regex detection only")
            if debug_enabled:
                log.debug("SpaCy detector initialization failed, models may be downloading in background")
        except Exception as e:
            log.error(f"Error in SpaCy detection: {e}")
            if debug_enabled:
                log.debug("Continuing with regex detection only")
    
    # Remove overlapping spans
    all_spans = _remove_overlapping_spans(all_spans)
    
    if all_spans:
        log.info(f"Detected {len(all_spans)} PII entities total")
        if debug_enabled:
            entity_types = [span[2] for span in all_spans]
            log.debug(f"Detected PII entity types: {entity_types}")
            for span in all_spans:
                log.debug(f"  {span[2]}: '{span[3]}' at position {span[0]}-{span[1]}")
    
    # Sort spans by start position in reverse order to avoid offset issues
    all_spans.sort(key=lambda x: x[0], reverse=True)
    
    anonymized_text = text
    mapping = {}
    
    for start, end, entity_type, entity_text in all_spans:
        placeholder = generate_placeholder(entity_type)
        anonymized_text = anonymized_text[:start] + placeholder + anonymized_text[end:]
        mapping[placeholder] = entity_text
        if debug_enabled:
            log.debug(f"Replaced '{entity_text}' with '{placeholder}'")
    
    if debug_enabled:
        log.debug(f"Anonymization complete. Original length: {len(text)}, Anonymized length: {len(anonymized_text)}, Mappings: {len(mapping)}")
    
    return anonymized_text, mapping


def deanonymize_text(text: str, mapping: Dict[str, str]) -> str:
    """Restore original data from anonymized text using mapping."""
    deanonymized_text = text
    for placeholder, original in mapping.items():
        deanonymized_text = deanonymized_text.replace(placeholder, original)
    return deanonymized_text


@hook(priority=1)
def before_rabbithole_insert_memory(doc: Document, cat: StrayCat) -> Document:
    """
    Anonymize document content before inserting into memory.
    This protects PII in scraped websites and uploaded documents.
    Only runs if anonymize_rabbit_hole setting is enabled.
    """
    settings = cat.mad_hatter.get_plugin().load_settings()
    debug_enabled = settings.get('debug_logging', False)
    
    # Check if rabbit hole anonymization is enabled
    anonymize_rabbit_hole = settings.get('anonymize_rabbit_hole', False)
    if not anonymize_rabbit_hole:
        if debug_enabled:
            log.debug("Rabbit hole anonymization disabled, skipping document anonymization")
        return doc
    
    allowed_websites = settings.get('allowed_websites', '')
    if allowed_websites:
        allowed_list = [w.strip() for w in allowed_websites.split(',') if w.strip()]
        source = doc.metadata.get('source', '')
        if source:
            domain = urlparse(source).netloc
            path = urlparse(source).path
            for allowed in allowed_list:
                if allowed.startswith(('http://', 'https://')):
                    parsed_allowed = urlparse(allowed)
                    allowed_domain = parsed_allowed.netloc
                    allowed_path = parsed_allowed.path
                else:
                    if '/' in allowed:
                        parts = allowed.split('/', 1)
                        allowed_domain = parts[0]
                        allowed_path = '/' + parts[1]
                    else:
                        allowed_domain = allowed
                        allowed_path = ''
                if domain == allowed_domain and path.startswith(allowed_path):
                    log.info(f"Skipping anonymization for allowed source: {source}")
                    return doc
    
    try:
        if debug_enabled:
            log.debug(f"Anonymizing document from source: {doc.metadata.get('source', 'unknown')}")
            log.debug(f"Document content length: {len(doc.page_content)}")
        
        anonymized_content, mapping = anonymize_text(doc.page_content, cat)
        
        if mapping:
            log.info(f"Document anonymized: {len(mapping)} PII entities found")
        
        # Create a new document with anonymized content
        anonymized_doc = Document(
            page_content=anonymized_content,
            metadata=doc.metadata
        )

        return anonymized_doc

    except Exception as e:
        log.error(f"Failed to anonymize document: {e}")
        return doc


@hook(priority=1)
def before_cat_reads_message(user_message_json: dict, cat) -> dict:
    """
    Anonymize user message before it goes through the normal processing flow.
    This happens when a user message arrives, before memory recall and agent processing.
    """
    try:
        user_message = user_message_json.get('text', '')
        settings = cat.mad_hatter.get_plugin().load_settings()
        debug_enabled = settings.get('debug_logging', False)

        if not user_message:
            return user_message_json

        if debug_enabled:
            log.debug(f"Anonymizing user message: '{user_message[:100]}...'")
        
        anonymized_message, mapping = anonymize_text(user_message, cat)
        
        if mapping:
            log.info(f"User message anonymized: {len(mapping)} PII entities found")
            if debug_enabled:
                log.debug(f"PII entities: {list(mapping.keys())}")

        # Check if reversible chat is enabled
        reversible_chat = settings.get('reversible_chat', True)
        
        if reversible_chat:
            # Store the mapping in the StrayCat instance for this session
            if not hasattr(cat, '_pii_mapping'):
                cat._pii_mapping = {}

            # Merge mappings (in case there are multiple calls)
            cat._pii_mapping.update(mapping)
            if debug_enabled:
                log.debug(f"Stored {len(mapping)} PII mappings for deanonymization. Total mappings: {len(cat._pii_mapping)}")

        # Update the user message with anonymized content
        user_message_json.text = anonymized_message
        if debug_enabled:
            log.debug(f"Updated user message with anonymized content: '{anonymized_message[:100]}...'")

        return user_message_json

    except Exception as e:
        log.error(f"Failed to anonymize user message: {e}")
        return user_message_json


@hook(priority=1)
def before_cat_sends_message(message: Dict, cat: StrayCat) -> Dict:
    """
    Deanonymize the cat's response before sending to user.
    This restores the original PII data in the response.
    """
    try:
        settings = cat.mad_hatter.get_plugin().load_settings()
        debug_enabled = settings.get('debug_logging', False)
        
        # Check if reversible chat is enabled
        reversible_chat = settings.get('reversible_chat', True)
        
        if not reversible_chat:
            if debug_enabled:
                log.debug("Reversible chat disabled, skipping deanonymization")
            return message

        # Check if we have a mapping from the current session
        if not hasattr(cat, '_pii_mapping') or not cat._pii_mapping:
            if debug_enabled:
                log.debug("No PII mapping available for deanonymization")
            return message

        content = message.get('content', '')

        if not content:
            return message

        if debug_enabled:
            log.debug(f"Deanonymizing response using {len(cat._pii_mapping)} PII mappings")
            log.debug(f"Current mappings: {cat._pii_mapping}")
            log.debug(f"Response content: '{content[:200]}...'")
        
        # Deanonymize the content
        deanonymized_content = deanonymize_text(content, cat._pii_mapping)
        
        # Check if content actually changed
        if deanonymized_content != content:
            log.info("Response deanonymized - original PII data restored")
            if debug_enabled:
                log.debug(f"Original: '{content[:200]}...'")
                log.debug(f"Deanonymized: '{deanonymized_content[:200]}...'")

        # Update the message with deanonymized content
        message.deanonymized = deanonymized_content

        return message

    except Exception as e:
        log.error(f"Failed to deanonymize response: {e}")
        return message
