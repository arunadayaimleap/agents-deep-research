"""Pydantic models for legal research and judgment processing."""

from datetime import date
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class PrecedentRelationship(str, Enum):
    """How a cited case is used in the judgment."""

    RELIES_ON = "RELIES_ON"
    FOLLOWS = "FOLLOWS"
    DISTINGUISHES = "DISTINGUISHES"
    OVERRULES = "OVERRULES"
    REFERS_TO = "REFERS_TO"
    APPLIES = "APPLIES"


class CaseMetadata(BaseModel):
    """Case name, court, bench, date, citation string."""

    case_name: str = Field(description="Standardized case name (e.g., State of Bihar v XYZ)")
    court: str = Field(description="Court name (e.g., Supreme Court, High Court of X)")
    bench: Optional[str] = Field(default=None, description="Bench composition, e.g., Justice A, Justice B")
    judgment_date: Optional[date] = Field(default=None, alias="date", description="Date of judgment")
    citation_string: Optional[str] = Field(default=None, description="Official citation string")


class Citation(BaseModel):
    """A case citation found in the judgment."""

    citation_text: str = Field(description="Raw citation string, e.g., (1996) 2 SCC 384")
    case_name: Optional[str] = Field(default=None, description="Extracted case name")
    paragraph: Optional[int] = Field(default=None, description="Paragraph number where cited")
    resolved_case_id: Optional[str] = Field(default=None, description="Canonical case ID after resolution")


class CitationRelationship(BaseModel):
    """Relationship between source case and a cited case."""

    source_case_id: str = Field(description="ID of the case containing the citation")
    target_case_id: str = Field(description="ID of the cited case")
    relationship: PrecedentRelationship = Field(description="How the citation is used")
    citation_text: Optional[str] = Field(default=None, description="Citation string as it appeared")


class StatuteReference(BaseModel):
    """A statutory provision referenced in the judgment."""

    statute: str = Field(description="Act/Code name, e.g., Indian Penal Code")
    section: Optional[str] = Field(default=None, description="Section or Article number")
    paragraph: Optional[int] = Field(default=None, description="Paragraph where referenced")


class LegalIssue(BaseModel):
    """A legal question addressed in the judgment."""

    issue_text: str = Field(description="The legal question or issue")
    supporting_paragraphs: List[int] = Field(default_factory=list, description="Paragraph numbers")


class RatioDecidendi(BaseModel):
    """The binding legal principle from the judgment."""

    ratio: str = Field(description="Binding legal principle (ratio decidendi)")
    supporting_paragraphs: List[int] = Field(default_factory=list, description="Paragraph numbers")


class Headnote(BaseModel):
    """SCC-style condensed headnote."""

    headnote_text: str = Field(description="Structured headnote text")
    topic_chain: Optional[List[str]] = Field(default=None, description="Topic hierarchy, e.g., Criminal Law — Evidence — FIR")


class TaxonomyTag(BaseModel):
    """Legal taxonomy classification."""

    path: List[str] = Field(description="Hierarchical path, e.g., ['Criminal Law', 'Evidence', 'FIR Delay']")


class CaseRecord(BaseModel):
    """Full structured case record - output of the legal pipeline."""

    judgment_id: Optional[str] = Field(default=None, description="Unique ID for this judgment")
    metadata: CaseMetadata = Field(description="Case metadata")
    citations: List[Citation] = Field(default_factory=list, description="Cases cited")
    citation_relationships: List[CitationRelationship] = Field(default_factory=list, description="How citations are used")
    statutes: List[StatuteReference] = Field(default_factory=list, description="Statutory references")
    issues: List[LegalIssue] = Field(default_factory=list, description="Legal issues addressed")
    ratio: Optional[RatioDecidendi] = Field(default=None, description="Ratio decidendi")
    headnotes: List[Headnote] = Field(default_factory=list, description="Headnotes")
    taxonomy_tags: List[TaxonomyTag] = Field(default_factory=list, description="Legal taxonomy classification")
    case_summary: Optional[str] = Field(default=None, description="Concise research summary")
    raw_text: Optional[str] = Field(default=None, description="Cleaned judgment text (optional, for reference)")
