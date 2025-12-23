from cat.mad_hatter.decorators import hook, plugin
from cat.looking_glass.stray_cat import StrayCat
from langchain.docstore.document import Document
from typing import Dict, Tuple, List
import uuid
import json
import os
from cat.log import log
from urllib.parse import urlparse

from .detectors import create_detector
from .allowedlist import init_allowedlist, add_entity, is_allowed


@hook
def after_cat_bootstrap(cat):
    settings = cat.mad_hatter.get_plugin().load_settings()
    if settings.get('enable_allowedlist', True):
        db_path = settings.get('sqlite_db_path', 'cat/data/anon_allowedlist.db')
        init_allowedlist(db_path)


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


def _detect_entities(text: str, cat: StrayCat) -> List[Tuple[int, int, str, str]]:
    settings = cat.mad_hatter.get_plugin().load_settings()
    
    # Check if any SpaCy detection is enabled
    enable_spacy = (settings.get('anonymize_names', True) or 
                   settings.get('anonymize_locations', True) or 
                   settings.get('anonymize_organizations', True))
    
    all_spans = []
    
    # Always use regex for emails, phones, and fiscal codes
    try:
        regex_detector = create_detector('regex', settings=settings)
        regex_spans = regex_detector.detect(text)
        all_spans.extend(regex_spans)
        
    except Exception as e:
        log.error(json.dumps({
            "component": "ccat_anonymizer",
            "event": "detection_error",
            "data": {
                "detector": "regex",
                "error": str(e)
            }
        }))
    
    # Optionally use SpaCy for names, organizations, and addresses
    if enable_spacy:
        try:
            spacy_detector = create_detector('spacy', settings=settings)
            spacy_spans = spacy_detector.detect(text)
            all_spans.extend(spacy_spans)
            
        except RuntimeError as e:
            log.error(json.dumps({
                "component": "ccat_anonymizer",
                "event": "detection_error",
                "data": {
                    "detector": "spacy",
                    "error": str(e)
                }
            }))
            log.info(json.dumps({
                "component": "ccat_anonymizer",
                "event": "detection_fallback",
                "data": {
                    "message": "Continuing with regex detection only"
                }
            }))
        except Exception as e:
            log.error(json.dumps({
                "component": "ccat_anonymizer",
                "event": "detection_error",
                "data": {
                    "detector": "spacy",
                    "error": str(e)
                }
            }))
    
    # Remove overlapping spans
    all_spans = _remove_overlapping_spans(all_spans)
    return all_spans


def anonymize_text(text: str, cat: StrayCat, check_allowedlist: bool = True) -> Tuple[str, Dict[str, str]]:
    """
    Anonymize text using regex detection for emails, phones, and Italian fiscal codes,
    and optionally SpaCy detection for names, organizations, and addresses.

    Returns:
        Tuple of (anonymized_text, mapping_dict)
    """
    settings = cat.mad_hatter.get_plugin().load_settings()
    enable_allowedlist = settings.get('enable_allowedlist', True)
    
    all_spans = _detect_entities(text, cat)
    
    if all_spans:
        entity_types = [span[2] for span in all_spans]
        log.info(json.dumps({
            "component": "ccat_anonymizer",
            "event": "pii_detection",
            "data": {
                "total_found": len(all_spans),
                "entity_types": list(set(entity_types))
            }
        }))
    
    # Sort spans by start position in reverse order to avoid offset issues
    all_spans.sort(key=lambda x: x[0], reverse=True)
    
    anonymized_text = text
    mapping = {}
    skipped_allowed = []
    
    for start, end, entity_type, entity_text in all_spans:
        # Check allowedlist
        if check_allowedlist and enable_allowedlist and is_allowed(entity_text):
            skipped_allowed.append(entity_text)
            continue

        placeholder = generate_placeholder(entity_type)
        anonymized_text = anonymized_text[:start] + placeholder + anonymized_text[end:]
        mapping[placeholder] = entity_text
    
    if mapping or skipped_allowed:
        log.info(json.dumps({
            "component": "ccat_anonymizer",
            "event": "text_anonymization",
            "data": {
                "original_length": len(text),
                "anonymized_length": len(anonymized_text),
                "entities_replaced": len(mapping),
                "entities_skipped_allowedlist": len(skipped_allowed),
                "allowed_entities": skipped_allowed
            }
        }))
    
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
    enable_allowedlist = settings.get('enable_allowedlist', True)
    
    # Detect entities and add to allowedlist
    if enable_allowedlist:
        try:
            spans = _detect_entities(doc.page_content, cat)
            added_count = 0
            source = doc.metadata.get('source', 'unknown')
            for _, _, entity_type, entity_text in spans:
                # add_entity checks for duplicates, but we don't get a return value.
                # We'll just count detected entities for now.
                add_entity(entity_text, entity_type, source)
                added_count += 1
            
            if added_count > 0:
                log.info(json.dumps({
                    "component": "ccat_anonymizer",
                    "event": "allowedlist_update",
                    "data": {
                        "source": source,
                        "entities_added_count": added_count
                    }
                }))
        except Exception as e:
            log.error(json.dumps({
                "component": "ccat_anonymizer",
                "event": "allowedlist_error",
                "data": {
                    "error": str(e)
                }
            }))

    # Check if rabbit hole anonymization is enabled
    anonymize_rabbit_hole = settings.get('anonymize_rabbit_hole', False)
    if not anonymize_rabbit_hole:
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
                    log.info(json.dumps({
                        "component": "ccat_anonymizer",
                        "event": "anonymization_skipped",
                        "data": {
                            "reason": "allowed_website",
                            "source": source
                        }
                    }))
                    return doc
    
    try:
        anonymized_content, mapping = anonymize_text(doc.page_content, cat, check_allowedlist=False)
        
        # Create a new document with anonymized content
        anonymized_doc = Document(
            page_content=anonymized_content,
            metadata=doc.metadata
        )

        return anonymized_doc

    except Exception as e:
        log.error(json.dumps({
            "component": "ccat_anonymizer",
            "event": "anonymization_error",
            "data": {
                "context": "document",
                "error": str(e)
            }
        }))
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

        if not user_message:
            return user_message_json

        anonymized_message, mapping = anonymize_text(user_message, cat)
        
        # Check if reversible chat is enabled
        reversible_chat = settings.get('reversible_chat', True)
        
        if reversible_chat:
            # Store the mapping in the StrayCat instance for this session
            if not hasattr(cat, '_pii_mapping'):
                cat._pii_mapping = {}

            # Merge mappings (in case there are multiple calls)
            cat._pii_mapping.update(mapping)

        # Update the user message with anonymized content
        user_message_json.text = anonymized_message

        return user_message_json

    except Exception as e:
        log.error(json.dumps({
            "component": "ccat_anonymizer",
            "event": "anonymization_error",
            "data": {
                "context": "user_message",
                "error": str(e)
            }
        }))
        return user_message_json


@hook(priority=1)
def before_cat_sends_message(message: Dict, cat: StrayCat) -> Dict:
    """
    Deanonymize the cat's response before sending to user.
    This restores the original PII data in the response.
    """
    try:
        settings = cat.mad_hatter.get_plugin().load_settings()
        
        # Check if reversible chat is enabled
        reversible_chat = settings.get('reversible_chat', True)
        
        if not reversible_chat:
            return message

        # Check if we have a mapping from the current session
        if not hasattr(cat, '_pii_mapping') or not cat._pii_mapping:
            return message

        content = message.get('content', '')

        if not content:
            return message

        # Deanonymize the content
        deanonymized_content = deanonymize_text(content, cat._pii_mapping)
        
        # Check if content actually changed
        if deanonymized_content != content:
            log.info(json.dumps({
                "component": "ccat_anonymizer",
                "event": "text_deanonymization",
                "data": {
                    "mappings_available": len(cat._pii_mapping),
                    "success": True,
                    "restored_count": len([k for k in cat._pii_mapping if k in content]) # Approximate count
                }
            }))

        # Update the message with deanonymized content
        message.deanonymized = deanonymized_content

        return message

    except Exception as e:
        log.error(json.dumps({
            "component": "ccat_anonymizer",
            "event": "deanonymization_error",
            "data": {
                "error": str(e)
            }
        }))
        return message

def save_plugin_settings_to_file(settings, plugin_path):
    settings_file_path = os.path.join(plugin_path, "settings.json")
    
    # Load old settings to preserve any fields not in the new settings (if any)
    old_settings = {}
    if os.path.exists(settings_file_path):
        try:
            with open(settings_file_path, "r") as json_file:
                old_settings = json.load(json_file)
        except Exception as e:
            log.error(f"Unable to load old plugin settings: {e}")
    
    # Merge new settings with old ones
    updated_settings = {**old_settings, **settings}
    
    # Save settings to file
    try:
        with open(settings_file_path, "w") as json_file:
            json.dump(updated_settings, json_file, indent=4)
        return updated_settings
    except Exception as e:
        log.error(f"Unable to save plugin settings: {e}")
        return {}


@plugin
def save_settings(settings):
    """Handle plugin settings save with optional database deletion."""
    reset_db = settings.get("reset_db", False)
    
    if reset_db:
        db_path = settings.get("sqlite_db_path", "cat/data/anon_allowedlist.db")
        
        # Handle sqlite:/// prefix if present
        if db_path.startswith("sqlite:///"):
            file_path = db_path[10:]
        else:
            file_path = db_path
            
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                log.info(json.dumps({
                    "component": "ccat_anonymizer",
                    "event": "database_reset",
                    "data": {
                        "status": "success",
                        "path": file_path
                    }
                }))
                
                # Re-initialize the allowedlist (empty)
                init_allowedlist(db_path)
                
            else:
                log.warning(json.dumps({
                    "component": "ccat_anonymizer",
                    "event": "database_reset",
                    "data": {
                        "status": "warning",
                        "message": "File does not exist",
                        "path": file_path
                    }
                }))
        except Exception as e:
            log.error(json.dumps({
                "component": "ccat_anonymizer",
                "event": "database_reset",
                "data": {
                    "status": "error",
                    "error": str(e),
                    "path": file_path
                }
            }))
        
        # Reset the flag
        settings["reset_db"] = False
    
    # Save settings
    plugin_path = os.path.dirname(os.path.abspath(__file__))
    return save_plugin_settings_to_file(settings, plugin_path)
