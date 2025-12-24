<p align="center">
    <img src="chat_anonymizer.png" alt="Anonymizer Logo" width="50" style="border-radius: 50%; vertical-align: middle; margin-right: 10px;" />
    <span style="font-size:2em; vertical-align: middle;"><b>PII Anonymizer</b></span>
</p>

[![CheshireCat AI Plugin - PII Anonymizer](https://custom-icon-badges.demolab.com/static/v1?label=&message=awesome+plugin&color=F4F4F5&style=for-the-badge&logo=cheshire_cat_black)](https://)

Protect sensitive personal information by intelligently anonymizing emails, phone numbers, and fiscal codes in both chat conversations and documents!

## Description

**PII Anonymizer** is a plugin for Cheshire Cat AI that automatically detects and anonymizes Personally Identifiable Information (PII) to protect user privacy and ensure compliance with data protection regulations.

The plugin provides four core functionalities:
1. **Chat Anonymization**: Automatically anonymizes PII in user messages with optional reversible restoration in responses
2. **Document Anonymization**: Protects PII in scraped websites and uploaded documents before storing in memory
3. **Trusted Sources**: Allows whitelisting of trusted websites to skip anonymization
4. **Smart Allowedlist**: Automatically learns entities from ingested documents to prevent anonymizing known entities in chat

## Features

- Automatically detects and anonymizes emails, phone numbers, and Italian fiscal codes using regex patterns
- **Advanced multilingual detection** using SpaCy models (`xx_ent_wiki_sm`, `en_core_web_sm`) for names, organizations and addresses
- Reversible anonymization for chat messages - original data restored in AI responses while keeping memory clean
- Document anonymization for rabbit hole content with trusted website exceptions
- **Smart Allowedlist** that learns from your documents to improve chat context
- Configurable debug logging for detailed anonymization process monitoring
- Privacy-first approach - only anonymizes when explicitly enabled for documents

## Requirements

- Cheshire Cat AI
- PII Anonymizer plugin enabled in Cheshire Cat AI
- **Optional**: SpaCy for advanced multilingual detection

## Settings

- **`reversible_chat`**: *(Boolean, default: True)* - If enabled, PII in chat messages is anonymized reversibly, restoring original data in responses. If disabled, anonymization is permanent. The un-anonymized text is stored in the `message.deanonymized` field so that, even in subsequent messages, the LLM never sees personal data, but it can be shown in the frontend correctly.

- **`anonymize_rabbit_hole`**: *(Boolean, default: False)* - If enabled, anonymize documents before inserting into memory (rabbit hole).

- **`allowed_websites`**: *(Text Area, default: "")* - Comma-separated list of websites (domains) that should NOT be anonymized during memory insertion. E.g., 'example.com, https://foo.com/bar'

- **`enable_allowedlist`**: *(Boolean, default: True)* - Enable the allowedlist functionality. Entities found in documents will be added to the allowedlist and not anonymized in chat.

- **`sqlite_db_path`**: *(String, default: "cat/data/anon_allowedlist.db")* - Path to the SQLite database for the allowedlist.

- **`reset_db`**: *(Boolean, default: False)* - If checked, the allowedlist database will be deleted when settings are saved. This action cannot be undone.

- **`enable_spacy_detection`**: *(Boolean, default: False)* - Enable advanced multilingual detection using SpaCy models for names, organizations, and addresses. Models download automatically.

## Allowedlist Mechanism

The plugin features a smart **Allowedlist** mechanism designed to balance privacy with utility.

1. **Learning Phase**: When you upload documents or scrape websites via the Rabbit Hole, the plugin detects entities (names, locations, organizations) in the content.
2. **Storage**: These entities are stored in a local SQLite database (`cat/data/anon_allowedlist.db`) and loaded into memory for fast access.
   - **Normalization**: Entities are stored in lowercase to ensure case-insensitive matching. Phone numbers are further normalized by removing all spaces.
3. **Chat Phase**: When a user sends a message, the plugin checks if any detected entities match the allowedlist. If a match is found, that specific entity is **NOT** anonymized.
   - **Matching**: The check is performed on the normalized version of the entity (lowercase and no spaces for phones), so "John Doe" matches "john doe" and "+1 234 567" matches "+1234567".

This ensures that if your documents contain public information about "John Doe", and a user asks about "John Doe", the name remains visible to the LLM, allowing it to retrieve the correct information from memory.

## Technical Details

### Detection Method
- **Regex patterns**: Detects emails, phone numbers, and Italian fiscal codes using comprehensive regular expressions
- **SpaCy NER**: When enabled, uses Named Entity Recognition to detect person names, organizations, and locations in multiple languages

### Hooks Used

- **`before_cat_reads_message`**: Anonymizes user messages before processing while storing mappings for restoration
- **`before_cat_sends_message`**: Restores original PII data in responses when reversible chat is enabled
- **`before_rabbithole_insert_memory`**: Anonymizes documents before inserting into memory when enabled

---

Author: OpenCity Labs

LinkedIn: https://www.linkedin.com/company/opencity-italia/

## Log Schema

This plugin uses structured JSON logging to facilitate monitoring and debugging. All logs follow this base structure:

```json
{
  "component": "ccat_anonymizer",
  "event": "<event_name>",
  "data": {
    ... <event_specific_data>
  }
}
```

### Event Types

| Event Name | Description | Data Fields |
|------------|-------------|-------------|
| `pii_detection` | Logged when entities are detected in text | `total_found`, `entity_types` |
| `text_anonymization` | Logged when text is successfully anonymized | `context`, `original_length`, `anonymized_length`, `entities_replaced`, `entities_skipped_allowedlist`, `allowed_entities` |
| `text_deanonymization` | Logged when restoring original data | `mappings_available`, `success`, `restored_count` |
| `allowedlist_update` | Logged when new entities are learned | `source`, `entities_added_count` |
| `initialization` | Logged on startup/db init | `status`, `db_path`, `loaded_entities` |
| `anonymization_skipped` | Logged when anonymization is skipped (e.g. allowed website) | `reason`, `url` |
| `detection_fallback` | Logged when SpaCy detection fails and falls back to regex | `error` |
| `*_error` | Error events (`detection_error`, `anonymization_error`, `deanonymization_error`, `allowedlist_error`) | `error`, `context` |
