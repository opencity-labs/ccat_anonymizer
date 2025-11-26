<p align="center">
    <img src="chat_anonymizer.png" alt="Anonymizer Logo" width="50" style="border-radius: 50%; vertical-align: middle; margin-right: 10px;" />
    <span style="font-size:2em; vertical-align: middle;"><b>PII Anonymizer</b></span>
</p>

[![CheshireCat AI Plugin - PII Anonymizer](https://custom-icon-badges.demolab.com/static/v1?label=&message=awesome+plugin&color=F4F4F5&style=for-the-badge&logo=cheshire_cat_black)](https://)

Protect sensitive personal information by intelligently anonymizing emails, phone numbers, and fiscal codes in both chat conversations and documents!

## Description

**PII Anonymizer** is a plugin for Cheshire Cat AI that automatically detects and anonymizes Personally Identifiable Information (PII) to protect user privacy and ensure compliance with data protection regulations.

The plugin provides three core functionalities:
1. **Chat Anonymization**: Automatically anonymizes PII in user messages with optional reversible restoration in responses
2. **Document Anonymization**: Protects PII in scraped websites and uploaded documents before storing in memory
3. **Trusted Sources**: Allows whitelisting of trusted websites to skip anonymization

## Features

- Automatically detects and anonymizes emails, phone numbers, and Italian fiscal codes using regex patterns
- **Advanced multilingual detection** using SpaCy models (`xx_ent_wiki_sm`, `en_core_web_sm`) for names, organizations and addresses
- Reversible anonymization for chat messages - original data restored in AI responses while keeping memory clean
- Document anonymization for rabbit hole content with trusted website exceptions
- Configurable debug logging for detailed anonymization process monitoring
- Privacy-first approach - only anonymizes when explicitly enabled for documents

## Requirements

- Cheshire Cat AI
- PII Anonymizer plugin enabled in Cheshire Cat AI
- **Optional**: SpaCy for advanced multilingual detection

## Settings

- **`reversible_chat`**: *(Boolean, default: True)* - If enabled, PII in chat messages is anonymized reversibly, restoring original data in responses. If disabled, anonymization is permanent. The un-anonymized text is stored in the `message.deanonymized` field so that, even in subsequent messages, the LLM never sees personal data, but it can be shown in the frontend correctly.

- **`anonymize_rabbit_hole`**: *(Boolean, default: False)* - If enabled, anonymize documents before inserting into memory (rabbit hole).

- **`debug_logging`**: *(Boolean, default: False)* - If enabled, show detailed debug logs for anonymization process.

- **`allowed_websites`**: *(Text Area, default: "")* - Comma-separated list of websites (domains) that should NOT be anonymized during memory insertion. E.g., 'example.com, https://foo.com/bar'

- **`enable_spacy_detection`**: *(Boolean, default: False)* - Enable advanced multilingual detection using SpaCy models for names, organizations, and addresses. Models download automatically.

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