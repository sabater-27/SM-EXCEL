"""Utilities for comparing and grouping surveys by question structure.

Two surveys are considered "structurally compatible" when they share the
same ordered sequence of (question_heading, family, subtype) tuples.  This
is intentionally loose: it ignores choice-level differences so that surveys
with the same conceptual questions but minor wording variations can still be
consolidated.  The threshold can be tightened by enabling strict mode.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections import defaultdict
from typing import NamedTuple

from sm_excel.models import Survey

logger = logging.getLogger(__name__)


class QuestionSignature(NamedTuple):
    """Minimal, hashable representation of a question for comparison."""

    heading: str
    family: str
    subtype: str


def get_question_signatures(survey: Survey) -> tuple[QuestionSignature, ...]:
    """Extract an ordered tuple of :class:`QuestionSignature` from a survey.

    Ordering follows the page position then question position within each page.

    Args:
        survey: A parsed :class:`~sm_excel.models.Survey`.

    Returns:
        Immutable ordered tuple of signatures – suitable for use as a dict key.
    """
    pages = sorted(survey.pages, key=lambda p: p.position)
    sigs: list[QuestionSignature] = []
    for page in pages:
        questions = sorted(page.questions, key=lambda q: q.position)
        for q in questions:
            sigs.append(
                QuestionSignature(
                    heading=q.heading.strip(),
                    family=q.family,
                    subtype=q.subtype,
                )
            )
    return tuple(sigs)


def structure_hash(survey: Survey) -> str:
    """Return a short SHA-256 fingerprint of a survey's question structure.

    The hash is derived from the JSON serialisation of the ordered question
    signatures, so two surveys with the same structure will always produce the
    same hash.

    Args:
        survey: A parsed :class:`~sm_excel.models.Survey`.

    Returns:
        12-character hex string (first 12 chars of SHA-256 digest).
    """
    sigs = get_question_signatures(survey)
    payload = json.dumps([s._asdict() for s in sigs], sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:12]


def surveys_are_compatible(survey_a: Survey, survey_b: Survey) -> bool:
    """Determine whether two surveys share the same question structure.

    Args:
        survey_a: First survey.
        survey_b: Second survey.

    Returns:
        ``True`` if both surveys have identical ordered question signatures.
    """
    return get_question_signatures(survey_a) == get_question_signatures(survey_b)


def group_surveys_by_structure(
    surveys: list[Survey],
) -> dict[str, list[Survey]]:
    """Partition a list of surveys into groups that share the same structure.

    Surveys within the same group are structurally compatible and can be
    consolidated into a single Excel file.

    Args:
        surveys: List of parsed :class:`~sm_excel.models.Survey` instances.

    Returns:
        Dictionary mapping a structure fingerprint (hash) to the list of
        surveys that share that structure.  Groups with a single survey will
        also appear in the result.
    """
    groups: dict[str, list[Survey]] = defaultdict(list)
    for survey in surveys:
        key = structure_hash(survey)
        groups[key].append(survey)
        logger.debug(
            "Survey %s ('%s') → structure group %s",
            survey.survey_id,
            survey.title,
            key,
        )
    return dict(groups)
