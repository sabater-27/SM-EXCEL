"""Data models (dataclasses) for SurveyMonkey API objects."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Choice:
    """A single answer choice for a question."""

    choice_id: str
    text: str
    position: int = 0


@dataclass
class Question:
    """Represents a single survey question."""

    question_id: str
    heading: str
    family: str  # e.g. "single_choice", "open_ended", "rating", ...
    subtype: str
    position: int
    page_id: str
    choices: list[Choice] = field(default_factory=list)


@dataclass
class Page:
    """Represents a page inside a survey."""

    page_id: str
    title: str
    position: int
    questions: list[Question] = field(default_factory=list)


@dataclass
class Survey:
    """Represents a SurveyMonkey survey with its full structure."""

    survey_id: str
    title: str
    pages: list[Page] = field(default_factory=list)

    @property
    def all_questions(self) -> list[Question]:
        """Return a flat list of all questions across all pages."""
        return [q for page in self.pages for q in page.questions]


@dataclass
class TrendDataPoint:
    """A single data-point from the trends endpoint."""

    question_id: str
    choice_id: str
    choice_text: str
    period_start: str
    period_end: str
    count: int
    percent: float
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Folder:
    """Represents a SurveyMonkey folder (collection)."""

    folder_id: str
    title: str
    survey_ids: list[str] = field(default_factory=list)
