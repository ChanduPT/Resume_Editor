#!/usr/bin/env python3
"""Quick smoke test to verify LLM output from configured provider."""

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.utils import chat_completion


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check whether the configured LLM provider returns output."
    )
    parser.add_argument(
        "--prompt",
        default="Reply with exactly: LLM_OK",
        help="Prompt to send to the model.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Optional model override.",
    )
    args = parser.parse_args()

    print("[LLM CHECK] Sending test prompt...")

    try:
        output = chat_completion(args.prompt, model=args.model)
    except Exception as exc:
        print(f"[LLM CHECK] FAILED: {type(exc).__name__}: {exc}")
        return 1

    if not output or not output.strip():
        print("[LLM CHECK] FAILED: Model returned empty output.")
        return 2

    print("[LLM CHECK] SUCCESS: Received output from model.")
    print("[LLM CHECK] OUTPUT:")
    print(output.strip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
