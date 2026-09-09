from interviewflow.transcript import Transcript


def test_consecutive_stt_fragments_become_one_candidate_answer():
    transcript = Transcript()

    for fragment in (
        "Key design is when that actually",
        "reduce their time.",
        "We designed",
        "a full end to end RAG system.",
    ):
        transcript.append_candidate_fragment(fragment, "main_interview")

    assert len(transcript.turns) == 1
    assert transcript.turns[0].turn_id == "turn-0001"
    assert transcript.turns[0].text == (
        "Key design is when that actually reduce their time. "
        "We designed a full end to end RAG system."
    )


def test_interviewer_response_closes_candidate_answer_boundary():
    transcript = Transcript()
    transcript.append_candidate_fragment("First fragment.", "main_interview")
    transcript.append("interviewer", "A follow-up question?", "main_interview")
    transcript.append_candidate_fragment("Second answer.", "main_interview")

    assert [turn.role for turn in transcript.turns] == [
        "candidate", "interviewer", "candidate",
    ]
    assert transcript.turns[-1].turn_id == "turn-0003"
