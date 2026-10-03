#!/usr/bin/env python3
"""Read Claude's 5-hour and weekly plan usage through the Claude Code CLI.

The helper runs ``claude -p /usage``. In print mode ``/usage`` is a local
command: it makes no model request and costs nothing, and the signed-in CLI
fetches the plan limits itself. The command prints lines such as:

    Current session: 3% used · resets Oct 3, 7:40pm (Africa/Johannesburg)
    Current week (all models): 1% used · resets Oct 8, 12am (Africa/Johannesburg)

"Current session" is the 5-hour window and "Current week (all models)" is
the weekly limit. The helper never reads Claude credentials; the CLI manages
its own sign-in (``claude login``).
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


REQUEST_TIMEOUT_SECONDS = 45

# Line labels printed by /usage for the two limits the widget shows.
FIVE_HOUR_LABEL = "Current session"
WEEKLY_LABEL = "Current week (all models)"

# Match "<label>: 3% used" with an optional "· resets <when> (<timezone>)" suffix.
LIMIT_LINE_PATTERN = r"^{label}:\s*(?P<used>\d+(?:\.\d+)?)%\s*used(?:\s*·\s*resets\s+(?P<when>[^(]+?)\s*\((?P<zone>[^)]+)\))?"

# Reset times look like "Oct 3, 7:40pm" or "Oct 8, 12am"; the date is
# omitted when the reset is today, for example "7:40pm".
RESET_PATTERN = re.compile(
    r"^(?:(?P<month>[A-Za-z]{3})\s+(?P<day>\d{1,2}),\s*)?"
    r"(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?\s*(?P<meridiem>am|pm)$",
    re.IGNORECASE,
)


class UsageError(RuntimeError):
    """An expected failure while retrieving or interpreting Claude usage data."""


def find_claude() -> str:
    """Find the Claude Code CLI in the desktop session or its common user location."""
    override = os.environ.get("CLAUDE_BIN")
    if override:
        path = Path(override).expanduser()
        if path.is_file() and os.access(path, os.X_OK):
            return str(path)
        raise UsageError("CLAUDE_BIN does not point to an executable file")

    discovered = shutil.which("claude")
    if discovered:
        return discovered

    user_install = Path.home() / ".local" / "bin" / "claude"
    if user_install.is_file() and os.access(user_install, os.X_OK):
        return str(user_install)

    raise UsageError("Claude Code CLI was not found; install it or set CLAUDE_BIN")


def cli_environment() -> Dict[str, str]:
    """Copy the environment without variables that mark a nested Claude Code session.

    When the helper is started from inside a Claude Code session (for example
    while testing), those variables make the CLI use the parent's sign-in
    instead of its own. Plasma never sets them, so this is a no-op there.
    """
    return {
        key: value
        for key, value in os.environ.items()
        if key != "CLAUDECODE" and not key.startswith("CLAUDE_CODE_")
    }


def usage_text() -> str:
    """Run the CLI's local /usage command and return its printed text."""
    try:
        completed = subprocess.run(
            [
                find_claude(),
                "-p",
                "/usage",
                "--output-format",
                "json",
                "--no-session-persistence",
            ],
            cwd=str(Path.home()),
            env=cli_environment(),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise UsageError("Timed out while reading usage data from Claude") from exc
    except OSError as exc:
        raise UsageError(f"Could not run Claude Code: {exc}") from exc

    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        detail = (completed.stderr or completed.stdout).strip()
        if detail:
            raise UsageError(detail.splitlines()[-1]) from exc
        raise UsageError("Claude Code returned no usage data") from exc

    text = result.get("result") if isinstance(result, dict) else None
    if not isinstance(text, str) or result.get("is_error"):
        raise UsageError(str(text or "Claude Code returned an error"))
    return text


def parse_reset(when: str, zone_name: str, now: datetime) -> int:
    """Convert a /usage reset time in a named timezone to Unix seconds.

    The CLI omits the year, so the reset is placed in the current year and
    moved to the next year when that would put it more than a day in the past
    (a reset on Jan 2 seen on Dec 30).
    """
    match = RESET_PATTERN.match(when.strip())
    if match is None:
        raise UsageError(f"Claude returned an unrecognized reset time: {when}")
    try:
        zone = ZoneInfo(zone_name.strip())
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise UsageError(f"Claude returned an unknown timezone: {zone_name}") from exc

    # Convert the 12-hour clock to 24-hour time.
    hour = int(match.group("hour")) % 12
    if match.group("meridiem").lower() == "pm":
        hour += 12
    minute = int(match.group("minute") or 0)

    local_now = now.astimezone(zone)
    if match.group("month"):
        try:
            month = datetime.strptime(match.group("month").title(), "%b").month
        except ValueError as exc:
            raise UsageError(f"Claude returned an unrecognized reset month: {when}") from exc
        day = int(match.group("day"))
    else:
        month, day = local_now.month, local_now.day

    reset = datetime(local_now.year, month, day, hour, minute, tzinfo=zone)
    if reset < local_now - timedelta(days=1):
        reset = reset.replace(year=reset.year + 1)
    return int(reset.timestamp())


def limit_summary(text: str, label: str, now: datetime) -> Dict[str, Any]:
    """Find one limit line and summarize it as remaining percentage and reset time."""
    pattern = re.compile(LIMIT_LINE_PATTERN.format(label=re.escape(label)), re.MULTILINE)
    match = pattern.search(text)
    if match is None:
        raise UsageError(f"Claude /usage did not report '{label}'; is the CLI signed in?")

    used_percent = int(round(float(match.group("used"))))
    used_percent = min(100, max(0, used_percent))

    reset_at: Optional[int] = None
    if match.group("when") and match.group("zone"):
        reset_at = parse_reset(match.group("when"), match.group("zone"), now)

    return {"remainingPercent": 100 - used_percent, "resetAt": reset_at}


def summarize(text: Optional[str] = None, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Return the small, authentication-free payload consumed by the widget."""
    usage = usage_text() if text is None else text
    current_time = now or datetime.now().astimezone()
    return {
        "ok": True,
        "fiveHour": limit_summary(usage, FIVE_HOUR_LABEL, current_time),
        "weekly": limit_summary(usage, WEEKLY_LABEL, current_time),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read Claude's 5-hour and weekly plan usage."
    )
    parser.add_argument("--pretty", action="store_true", help="indent the JSON output")
    args = parser.parse_args()

    try:
        payload = summarize()
        exit_code = 0
    except UsageError as exc:
        payload = {"ok": False, "error": str(exc)}
        exit_code = 1
    except Exception as exc:  # Keep the widget output machine-readable on unexpected failures.
        payload = {"ok": False, "error": f"Unexpected error: {exc}"}
        exit_code = 1

    print(json.dumps(payload, indent=2 if args.pretty else None, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
