from pydantic import BaseModel, Field
from cat.mad_hatter.decorators import plugin


class PluginSettings(BaseModel):
    reversible_chat: bool = Field(
        title="Reversible Chat Anonymization",
        default=True,
        description="PII in chat messages is anonymized reversibly, restoring original data in responses (deanonymized field in the object). If disabled, anonymization is permanent.",
    )
    anonymize_rabbit_hole: bool = Field(
        title="Anonymize Rabbit Hole",
        default=False,
        description="Anonymize documents before inserting into memory (rabbit hole).",
    )
    anonymize_email: bool = Field(
        title="Anonymize Email",
        default=True,
        description="Anonymize email addresses in text.",
    )
    anonymize_phone: bool = Field(
        title="Anonymize Phone",
        default=True,
        description="Anonymize phone numbers in text.",
    )
    anonymize_fiscal_code: bool = Field(
        title="Anonymize Fiscal Code",
        default=True,
        description="Anonymize Italian fiscal codes in text.",
    )
    anonymize_names: bool = Field(
        title="Anonymize Names",
        default=True,
        description="Anonymize person names using SpaCy NER (requires SpaCy installation).",
    )
    anonymize_locations: bool = Field(
        title="Anonymize Locations",
        default=True,
        description="Anonymize locations and addresses using SpaCy NER (requires SpaCy installation).",
    )
    anonymize_organizations: bool = Field(
        title="Anonymize Organizations",
        default=True,
        description="Anonymize organization names using SpaCy NER (requires SpaCy installation).",
    )
    debug_logging: bool = Field(
        title="Debug Logging",
        default=False,
        description="Show detailed debug logs for anonymization process.",
    )
    allowed_websites: str = Field(
        title="Allowed Websites",
        default="",
        description="Comma-separated list of websites (domains) that should NOT be anonymized during memory insertion. E.g., 'example.com, https://foo.com/bar'",
        extra={"type": "TextArea"},
    )

@plugin
def settings_model():
    return PluginSettings