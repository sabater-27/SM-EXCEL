"""Shared fixtures and helpers for the test suite."""
import pytest

from sm_excel.models import Choice, Page, Question, Survey


def make_question(
    question_id: str = "q1",
    heading: str = "How satisfied are you?",
    family: str = "single_choice",
    subtype: str = "vertical",
    position: int = 1,
    page_id: str = "p1",
    choices: list | None = None,
) -> Question:
    if choices is None:
        choices = [
            Choice("c1", "Very satisfied", 1),
            Choice("c2", "Satisfied", 2),
            Choice("c3", "Neutral", 3),
        ]
    return Question(
        question_id=question_id,
        heading=heading,
        family=family,
        subtype=subtype,
        position=position,
        page_id=page_id,
        choices=choices,
    )


def make_survey(
    survey_id: str = "111",
    title: str = "Test Survey",
    questions: list | None = None,
) -> Survey:
    if questions is None:
        questions = [make_question()]
    page = Page(page_id="p1", title="Page 1", position=1, questions=questions)
    return Survey(survey_id=survey_id, title=title, pages=[page])
