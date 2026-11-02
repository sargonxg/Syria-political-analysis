"""Explicit write contracts for analyst-authored records."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..core import canonical_url

Kind = Literal["source", "document", "claim", "note", "actor", "event", "theme"]


class RecordWrite(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    kind: Kind
    title: str = Field(min_length=1, max_length=300)
    body: str = Field(default="", max_length=100_000)
    url: str = Field(default="", max_length=2000)
    source_id: str | None = None
    document_id: str | None = None
    excerpt: str = Field(default="", max_length=10_000)
    locator: str = Field(default="", max_length=1000)
    published_on: date | None = None
    reviewed_on: date | None = None
    event_on: date | None = None
    confidence: Literal["unassessed", "low", "medium", "high"] = "unassessed"
    confidence_reason: str = Field(default="", max_length=3000)
    tags: list[str] = Field(default_factory=list, max_length=30)
    links: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("url")
    @classmethod
    def public_reference(cls, value):
        return canonical_url(value) if value else ""

    @field_validator("tags")
    @classmethod
    def tidy_tags(cls, values):
        if any(not v.strip() or len(v) > 60 for v in values):
            raise ValueError("Tags must be nonempty and at most 60 characters")
        return list(dict.fromkeys(v.strip() for v in values))

    @model_validator(mode="after")
    def citation_contract(self):
        if self.kind == "source" and not self.url:
            raise ValueError("A source needs an original public URL")
        if self.kind == "document" and not self.source_id:
            raise ValueError("A document needs a source record")
        if self.kind == "claim" and not (
            self.document_id and self.excerpt and self.locator
        ):
            raise ValueError(
                "A claim needs a document, exact excerpt and passage locator"
            )
        if self.confidence != "unassessed" and not self.confidence_reason:
            raise ValueError("Assessed confidence needs a written rationale")
        if self.kind != "claim" and (self.document_id or self.excerpt or self.locator):
            raise ValueError("Claim citation fields belong only to claims")
        return self


class RecordUpdate(RecordWrite):
    revision: int = Field(ge=1)


class CaseWrite(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=150)


class Login(BaseModel):
    model_config = ConfigDict(extra="forbid")
    access_key: str = Field(min_length=1, max_length=1000)
