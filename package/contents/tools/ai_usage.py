#!/usr/bin/env python3
"""Combine the usage of each AI subscription into one JSON payload for the widget.

The widget shows the Claude subscription that the Claude Code CLI is signed
in to. The ChatGPT reader stays available but is off; set
``INCLUDE_CHATGPT`` to True to read it again.

Each provider is read independently, so a failure in one still leaves the
other reading intact. The output has this shape, with the ``chatgpt`` key
only when it is enabled:

    {"claude": {"ok": ...}, "chatgpt": {"ok": ...}}
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


# The ChatGPT reading is off. Its helper starts the Codex app server, so it
# is skipped completely instead of being read and then hidden.
INCLUDE_CHATGPT = False


def read_provider(reader: Callable[[], Dict[str, Any]], expected_error: type) -> Dict[str, Any]:
    """Run one provider reader and convert any failure into an error payload."""
    try:
        return reader()
    except expected_error as exc:
        return {"ok": False, "error": str(exc)}
    except Exception as exc:  # Keep the widget output machine-readable on unexpected failures.
        return {"ok": False, "error": f"Unexpected error: {exc}"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Read the usage of each AI subscription together.")
    parser.add_argument("--pretty", action="store_true", help="indent the JSON output")
    args = parser.parse_args()

    payload = {
        "claude": read_provider(claude_usage.summarize, claude_usage.UsageError),
    }
    if INCLUDE_CHATGPT:
        payload["chatgpt"] = read_provider(
            lambda: chatgpt_usage.summarize(chatgpt_usage.app_server_usage()),
            chatgpt_usage.UsageError,
        )
    print(json.dumps(payload, indent=2 if args.pretty else None, sort_keys=True))

    # Report failure only when no provider produced a reading.
    any_ok = any(section.get("ok") for section in payload.values())
    return 0 if any_ok else 1


if __name__ == "__main__":
    sys.exit(main())
