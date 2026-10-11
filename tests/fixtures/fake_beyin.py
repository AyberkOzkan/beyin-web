from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path


def main() -> int:
    arguments = sys.argv[1:]
    log = os.environ.get("FAKE_BEYIN_LOG")
    if log:
        with Path(log).open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(arguments, ensure_ascii=False) + "\n")
    mode = os.environ.get("FAKE_BEYIN_MODE", "ok")
    if mode == "fail":
        return 3
    if mode == "badjson":
        print("{broken")
        return 0
    if mode == "slow":
        time.sleep(60)

    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor")
    context = commands.add_parser("context")
    context.add_argument("--no-sync", action="store_true", required=True)
    context.add_argument("--limit", type=int, required=True)
    context.add_argument("--budget-chars", type=int, required=True)
    context.add_argument("--project")
    context.add_argument("query")
    args = parser.parse_args(arguments)
    if args.command == "doctor":
        output = {
            "status": "ok",
            "updates": {
                "current_version": "0.1.0", "version": "0.1.0",
                "status": "up_to_date", "release_url": "", "checked_at": 1767225600.0,
            },
            "hook-health.json": {
                "at": 1767225600.0,
                "sync": {
                    "status": "succeeded", "indexed": 2, "deleted": 0,
                    "warnings": [], "conflicts": [], "potential_missing_receipts": 1,
                },
            },
            "hook-error.json": None,
            "potential_missing_receipts": 1,
            "companion_hygiene": {
                "status": "ok", "directory": "🔮 850-Companion",
                "limits": {"Last-Session.md": 1200, "Threads.md": 2400},
                "files": {
                    "Core.md": {"chars": 90}, "Kurallar.md": {"chars": 100},
                    "Journal.md": {"chars": 110},
                    "Last-Session.md": {"chars": 120, "limit": 1200, "over_limit": False},
                    "Threads.md": {"chars": 130, "limit": 2400, "over_limit": False},
                },
                "over_limit": [],
            },
        }
    else:
        output = {
            "records": [{
                "id": "fake-1", "kind": "note", "revision": 1,
                "source": "notes/Çınar Projesi.md", "source_sha256": "0" * 64,
                "text": "Sentetik bağlam", "visibility": "internal",
                "text_truncated": False, "facts": {}, "supersedes": [],
            }],
            "citations": [{"id": "fake-1", "source": "notes/Çınar Projesi.md"}],
            "abstained": False, "truncated": False, "omitted_count": 0,
            "used_chars": 15, "budget_chars": args.budget_chars, "stale_count": 0,
            "source_sync": {"status": "skipped", "reason": "--no-sync"},
        }
    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
