"""Calculate STT word and character error rates for one spoken test phrase."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evals.speech_quality import calculate_transcription_quality


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", required=True, help="The exact sentence you intended to say")
    parser.add_argument("--hypothesis", required=True, help="The sentence produced by STT")
    args = parser.parse_args()
    try:
        quality = calculate_transcription_quality(args.reference, args.hypothesis)
    except ValueError as error:
        parser.error(str(error))
    print(f"WER: {quality.word_error_rate:.3f}")
    print(f"CER: {quality.character_error_rate:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
