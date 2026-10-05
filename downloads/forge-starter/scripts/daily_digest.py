#!/usr/bin/env python3
"""One daily summary: new leads, pending drafts, follow-ups due."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import (  # noqa: E402
    DATA,
    LEADS_DIR,
    PROPOSALS_DIR,
    ensure_dirs,
    latest_leads_file,
    latest_matched_file,
    load_queue,
    utc_now_iso,
    write_json,
)


def main() -> int:
    ensure_dirs()
    lines = []
    lines.append(f"# Forge daily digest — {utc_now_iso()}")
    lines.append("")

    leads_path = latest_leads_file()
    if leads_path:
        data = json.loads(leads_path.read_text(encoding="utf-8"))
        leads = data.get("leads") or []
        lines.append(f"## New leads ({len(leads)}) — from `{leads_path.name}`")
        for L in leads[:8]:
            lines.append(
                f"- [{L.get('match_score')}] **{L.get('title')}** @ {L.get('company')} ({L.get('source')})"
            )
            lines.append(f"  {L.get('url')}")
        lines.append("")
    else:
        lines.append("## New leads\n- None yet. Run `python3 scripts/find_leads.py`\n")

    matched_path = latest_matched_file()
    if matched_path:
        data = json.loads(matched_path.read_text(encoding="utf-8"))
        lines.append(f"## Matched for profile `{data.get('profile')}` — {data.get('count')} leads")
        for L in (data.get("leads") or [])[:5]:
            lines.append(f"- [{L.get('match_score')}] {L.get('title')} @ {L.get('company')}")
        lines.append("")

    idx = PROPOSALS_DIR / "latest-index.json"
    if idx.exists():
        data = json.loads(idx.read_text(encoding="utf-8"))
        lines.append(f"## Proposal drafts — {data.get('count')}")
        for p in data.get("proposals") or []:
            lines.append(f"- {p.get('company')}: {p.get('file')}")
        lines.append("")

    queue = load_queue()
    by_status: dict[str, list] = {}
    for it in queue:
        by_status.setdefault(it.get("status", "unknown"), []).append(it)
    lines.append("## Outreach queue")
    if not queue:
        lines.append("- (empty)")
    else:
        for st, group in sorted(by_status.items()):
            lines.append(f"- **{st}**: {len(group)}")
    lines.append("")

    # Follow-ups: sent items older than 3 days without replied/stop
    due = []
    now = datetime.now(timezone.utc)
    for it in queue:
        if it.get("status") != "sent":
            continue
        sent_at = it.get("sent_at")
        if not sent_at:
            continue
        try:
            dt = datetime.strptime(sent_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if (now - dt).days >= 3:
            due.append(it)
    lines.append("## Follow-ups due (sent ≥ 3 days ago)")
    if not due:
        lines.append("- None")
    else:
        for it in due:
            lines.append(f"- {it.get('company')} — {it.get('title')} (id {it.get('id')})")
    lines.append("")
    lines.append("---")
    lines.append("You build. We find the work. — Forge")

    text = "\n".join(lines) + "\n"
    out_md = DATA / "daily-digest-latest.md"
    out_md.write_text(text, encoding="utf-8")
    write_json(
        DATA / "daily-digest-latest.json",
        {
            "generated_at": utc_now_iso(),
            "queue_counts": {k: len(v) for k, v in by_status.items()},
            "followups_due": len(due),
            "markdown_path": str(out_md),
        },
    )
    print(text)
    print(f"(saved {out_md})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
