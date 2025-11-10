from pydantic import BaseModel, Field
from cat.mad_hatter.decorators import plugin


class PluginSettings(BaseModel):
    reversible_chat: bool = Field(
        title="Reversible Chat Anonymization",
        default=True,
        description="If enabled, PII in chat messages is anonymized reversibly, restoring original data in responses. If disabled, anonymization is permanent.",
    )
    anonymize_rabbit_hole: bool = Field(
        title="Anonymize Rabbit Hole",
        default=False,
        description="If enabled, anonymize documents before inserting into memory (rabbit hole).",
    )
    debug_logging: bool = Field(
        title="Debug Logging",
        default=False,
        description="If enabled, show detailed debug logs for anonymization process.",
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