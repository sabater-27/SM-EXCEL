"""Tests for sm_excel.processors.structure_comparator."""

import pytest

from sm_excel.models import Page, Question, Survey
from sm_excel.processors.structure_comparator import (
    get_question_signatures,
    group_surveys_by_structure,
    structure_hash,
    surveys_are_compatible,
)
from tests.conftest import make_question, make_survey


class TestGetQuestionSignatures:
    def test_returns_tuple(self):
        survey = make_survey()
        sigs = get_question_signatures(survey)
        assert isinstance(sigs, tuple)
        assert len(sigs) == 1

    def test_order_follows_position(self):
        q1 = make_question("q1", heading="First", position=1)
        q2 = make_question("q2", heading="Second", position=2)
        survey = make_survey(questions=[q2, q1])  # reversed order in list
        sigs = get_question_signatures(survey)
        assert sigs[0].heading == "First"
        assert sigs[1].heading == "Second"


class TestStructureHash:
    def test_same_structure_same_hash(self):
        s1 = make_survey("111", questions=[make_question()])
        s2 = make_survey("222", questions=[make_question()])
        assert structure_hash(s1) == structure_hash(s2)

    def test_different_structure_different_hash(self):
        s1 = make_survey(questions=[make_question(heading="Q1")])
        s2 = make_survey(questions=[make_question(heading="Q2")])
        assert structure_hash(s1) != structure_hash(s2)

    def test_hash_is_12_chars(self):
        s = make_survey()
        assert len(structure_hash(s)) == 12


class TestSurveysAreCompatible:
    def test_identical_structure(self):
        s1 = make_survey("1")
        s2 = make_survey("2")
        assert surveys_are_compatible(s1, s2)

    def test_different_family(self):
        s1 = make_survey(questions=[make_question(family="single_choice")])
        s2 = make_survey(questions=[make_question(family="open_ended")])
        assert not surveys_are_compatible(s1, s2)

    def test_different_question_count(self):
        s1 = make_survey(questions=[make_question("q1")])
        s2 = make_survey(questions=[make_question("q1"), make_question("q2")])
        assert not surveys_are_compatible(s1, s2)


class TestGroupSurveysByStructure:
    def test_compatible_surveys_grouped_together(self):
        s1 = make_survey("1")
        s2 = make_survey("2")
        groups = group_surveys_by_structure([s1, s2])
        assert len(groups) == 1
        group = list(groups.values())[0]
        assert len(group) == 2

    def test_incompatible_surveys_in_separate_groups(self):
        s1 = make_survey(questions=[make_question(family="single_choice")])
        s2 = make_survey(questions=[make_question(family="open_ended")])
        groups = group_surveys_by_structure([s1, s2])
        assert len(groups) == 2

    def test_empty_list(self):
        groups = group_surveys_by_structure([])
        assert groups == {}
