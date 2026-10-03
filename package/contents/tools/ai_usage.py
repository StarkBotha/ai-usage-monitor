#!/usr/bin/env python3
"""Combine ChatGPT and Claude usage into one JSON payload for the widget.

Each provider is read independently, so a failure in one (for example Codex
being signed out) still leaves the other provider's reading intact. The
output always has this shape:

    {"chatgpt": {"ok": ...}, "claude": {"ok": ...}}
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Callable, Dict

# Import the sibling helpers regardless of the caller's working directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import chatgpt_usage  # noqa: E402
import claude_usage  # noqa: E402


def read_provider(reader: Callable[[], Dict[str, Any]], expected_error: type) -> Dict[str, Any]:
    """Run one provider reader and convert any failure into an error payload."""
    try:
        return reader()
    except expected_error as exc:
        return {"ok": False, "error": str(exc)}
    except Exception as exc:  # Keep the widget output machine-readable on unexpected failures.
        return {"ok": False, "error": f"Unexpected error: {exc}"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Read ChatGPT and Claude usage together.")
    parser.add_argument("--pretty", action="store_true", help="indent the JSON output")
    args = parser.parse_args()

    payload = {
        "chatgpt": read_provider(
            lambda: chatgpt_usage.summarize(chatgpt_usage.app_server_usage()),
            chatgpt_usage.UsageError,
        ),
        "claude": read_provider(claude_usage.summarize, claude_usage.UsageError),
    }
    print(json.dumps(payload, indent=2 if args.pretty else None, sort_keys=True))

    # Report failure only when neither provider produced a reading.
    any_ok = payload["chatgpt"].get("ok") or payload["claude"].get("ok")
    return 0 if any_ok else 1


if __name__ == "__main__":
    sys.exit(main())
