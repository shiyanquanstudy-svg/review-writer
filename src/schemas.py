from pydantic import BaseModel, Field
from typing import List, Optional


class Section(BaseModel):
    number: int
    title: str
    focus: str
    key_questions: List[str] = Field(default_factory=list)


class ReviewSpec(BaseModel):
    review_title: str
    review_type: str = "narrative_review"
    language: str = "中文"
    core_entities: List[str] = Field(default_factory=list)
    background_topics: List[str] = Field(default_factory=list)
    sections: List[Section] = Field(default_factory=list)
    abstract_requirements: List[str] = Field(default_factory=list)
    evidence_types: List[str] = Field(default_factory=list)
    time_range: str = ""
    target_audience: str = ""


class SourceRecord(BaseModel):
    source_id: str
    source_type: str
    title: str
    authors: List[str] = Field(default_factory=list)
    journal: Optional[str] = None
    year: Optional[int] = None
    doi: Optional[str] = None
    url: Optional[str] = None
    abstract: Optional[str] = None
    key_findings: List[str] = Field(default_factory=list)
    relevance_score: float = 0.0