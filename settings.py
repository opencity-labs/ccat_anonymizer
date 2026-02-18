from pydantic import BaseModel, Field, validator
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
    enable_allowedlist: bool = Field(
        title="Enable Allowedlist",
        default=True,
        description="Enable the allowedlist functionality. Entities found in documents will be added to the allowedlist and not anonymized in chat.",
    )
    sqlite_db_path: str = Field(
        title="SQLite DB Path",
        default="cat/data/anon_allowedlist.db",
        description="Path to the SQLite database for the allowedlist.",
    )
    allowed_websites: str = Field(
        title="Allowed Websites",
        default="",
        description="Comma-separated list of websites (domains) that should NOT be anonymized during memory insertion. E.g., 'example.com, https://foo.com/bar'",
        extra={"type": "TextArea"},
    )
    reset_db: bool = Field(
        title="Reset Allowedlist Database",
        default=False,
        description="If checked, the allowedlist database will be deleted when settings are saved. This action cannot be undone.",
    )
    confidence_threshold: float = Field(
        title="Confidence Threshold",
        default=0.45,
        description="Minimum confidence score for entity detection using SpaCy NER. Must be between 0 and 1.",
    )

    @validator("confidence_threshold")
    def validate_confidence_threshold(cls, v):
        """Validate that confidence_threshold is between 0 and 1."""
        if not 0 <= v <= 1:
            raise ValueError("Confidence threshold must be between 0 and 1.")
        return v


@plugin
def settings_model():
    return PluginSettings
