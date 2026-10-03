#!/usr/bin/env python3
"""Read the ChatGPT-backed Codex weekly rate limit through Codex app-server."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import selectors
import shutil
import subprocess
import sys
import time
from typing import Any, Dict, Iterable, Optional


APP_NAME = "chatgpt-usage-monitor"
APP_VERSION = "1.0.0"
REQUEST_TIMEOUT_SECONDS = 15


class UsageError(RuntimeError):
    """An expected failure while retrieving or interpreting usage data."""


def find_codex() -> str:
    """Find the Codex CLI in the desktop session or its common user location."""
    override = os.environ.get("CODEX_BIN")
    if override:
        path = Path(override).expanduser()
        if path.is_file() and os.access(path, os.X_OK):
            return str(path)
        raise UsageError("CODEX_BIN does not point to an executable file")

    discovered = shutil.which("codex")
    if discovered:
        return discovered

    user_install = Path.home() / ".local" / "bin" / "codex"
    if user_install.is_file() and os.access(user_install, os.X_OK):
        return str(user_install)

    raise UsageError("Codex CLI was not found; install Codex or set CODEX_BIN")


def read_response(
    process: subprocess.Popen[str], request_id: int, timeout_seconds: int
) -> Dict[str, Any]:
    """Read newline-delimited app-server messages until the response arrives."""
    if process.stdout is None:
        raise UsageError("Codex app server has no output stream")

    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    deadline = time.monotonic() + timeout_seconds

    try:
        while time.monotonic() < deadline:
            remaining = max(0.0, deadline - time.monotonic())
            if not selector.select(remaining):
                break

            line = process.stdout.readline()
            if not line:
                break

            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue

            if message.get("id") != request_id:
                continue

            if "error" in message:
                error = message.get("error") or {}
                detail = error.get("message") or "Codex app server returned an error"
                raise UsageError(str(detail))

            result = message.get("result")
            if not isinstance(result, dict):
                raise UsageError("Codex app server returned an invalid response")
            return result
    finally:
        selector.close()

    if process.poll() is not None:
        detail = ""
        if process.stderr is not None:
            detail = process.stderr.read().strip()
        if detail:
            raise UsageError(detail.splitlines()[-1])
        raise UsageError("Codex app server exited before returning usage data")

    raise UsageError("Timed out while reading usage data from Codex")


def send_request(
    process: subprocess.Popen[str], request_id: int, method: str, params: Any = None
) -> None:
    """Send one newline-delimited JSON-RPC-style app-server request."""
    if process.stdin is None:
        raise UsageError("Codex app server has no input stream")

    request: Dict[str, Any] = {"id": request_id, "method": method}
    if params is not None:
        request["params"] = params

    process.stdin.write(json.dumps(request, separators=(",", ":")) + "\n")
    process.stdin.flush()


def app_server_usage() -> Dict[str, Any]:
    """Fetch the current account rate-limit snapshot from Codex app-server."""
    process = subprocess.Popen(
        [find_codex(), "app-server", "--stdio"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    try:
        send_request(
            process,
            1,
            "initialize",
            {
                "clientInfo": {
                    "name": APP_NAME,
                    "title": "ChatGPT Usage Monitor",
                    "version": APP_VERSION,
                }
            },
        )
        read_response(process, 1, REQUEST_TIMEOUT_SECONDS)

        send_request(process, 2, "account/rateLimits/read")
        return read_response(process, 2, REQUEST_TIMEOUT_SECONDS)
    except (BrokenPipeError, OSError) as exc:
        raise UsageError(f"Could not communicate with Codex: {exc}") from exc
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)


def rate_limit_snapshot(result: Dict[str, Any]) -> Dict[str, Any]:
    """Select the default Codex rate-limit bucket."""
    by_limit_id = result.get("rateLimitsByLimitId")
    if isinstance(by_limit_id, dict):
        codex = by_limit_id.get("codex")
        if isinstance(codex, dict):
            return codex

    snapshot = result.get("rateLimits")
    if isinstance(snapshot, dict):
        return snapshot

    raise UsageError("Codex did not return a subscription rate limit")


def weekly_window(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """Select the longest window, which represents the weekly allowance."""
    windows: Iterable[Any] = (snapshot.get("primary"), snapshot.get("secondary"))
    available = [window for window in windows if isinstance(window, dict)]
    if not available:
        raise UsageError("Codex did not return a weekly usage window")

    return max(
        available,
        key=lambda window: int(window.get("windowDurationMins") or 0),
    )


def summarize(result: Dict[str, Any]) -> Dict[str, Any]:
    """Return the small, authentication-free payload consumed by the widget."""
    snapshot = rate_limit_snapshot(result)
    window = weekly_window(snapshot)

    try:
        used_percent = int(round(float(window["usedPercent"])))
    except (KeyError, TypeError, ValueError) as exc:
        raise UsageError("Codex returned an invalid used percentage") from exc

    used_percent = min(100, max(0, used_percent))
    reset_at: Optional[int]
    try:
        reset_at = int(window["resetsAt"]) if window.get("resetsAt") else None
    except (TypeError, ValueError) as exc:
        raise UsageError("Codex returned an invalid reset time") from exc

    return {
        "ok": True,
        "remainingPercent": 100 - used_percent,
        "resetAt": reset_at,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read the weekly Codex allowance on a ChatGPT subscription."
    )
    parser.add_argument("--pretty", action="store_true", help="indent the JSON output")
    args = parser.parse_args()

    try:
        payload = summarize(app_server_usage())
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
