import re

from interviewflow.interviewer import INTERVIEW_INSTRUCTIONS


def test_prompt_has_regression_rules_from_live_evaluation():
    prompt = INTERVIEW_INSTRUCTIONS.lower()

    assert re.search(r"clearly different\s+competency or experience", prompt)
    assert "do not ask about the same project" in prompt
    assert "never end with only a refusal" in prompt
    assert "source-based opening question must contain" in prompt
    assert "exactly one information target" in prompt
    assert "correction honored" in prompt
    assert re.search(r"one-sentence\s+introduction", prompt)
    assert "another named project or experience" in prompt
    assert "citation supports its exact claim" in prompt
    assert "interrogative sentence must not contain the word \"and\"" in prompt
    assert "previous subject is invalid" in prompt
    assert "repeat, rephrase, or clarify" in prompt
    assert "do not treat this as an answer" in prompt
    assert "only announce a topic switch" in prompt
    assert "cannot recall" in prompt
    assert "fragmented" in prompt
    assert "without announcing a topic switch" in prompt
    assert "use both the resume and the job description" in prompt
    assert "within the first four assessment questions" in prompt
    assert "never ask more than two consecutive resume-grounded questions" in prompt


def test_prompt_rules_are_role_and_resume_independent():
    prompt = INTERVIEW_INSTRUCTIONS.lower()

    for fixture_specific_term in ("postgresql", "mongodb", "recall@5", "python api"):
        assert fixture_specific_term not in prompt
