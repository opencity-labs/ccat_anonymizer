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
    enable_spacy_detection: bool = Field(
        title="Enable SpaCy Detection",
        default=False,
        description="Enable advanced multilingual PII detection using SpaCy models for names, organizations, and addresses.",
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