import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "score_transcript.py"


def test_score_transcript_cli_reports_zero_for_exact_transcript():
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--reference",
            "I measured API latency",
            "--hypothesis",
            "I measured API latency",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout.splitlines() == ["WER: 0.000", "CER: 0.000"]
