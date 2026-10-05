#!/usr/bin/env python3
"""Queue proposal drafts for review. Status: draft|approved|sent|replied|stop."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import (  # noqa: E402
    PROPOSALS_DIR,
    ensure_dirs,
    load_queue,
    save_queue,
    utc_now_iso,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Queue / manage outreach drafts")
    parser.add_argument(
        "--from-index",
        default=str(PROPOSALS_DIR / "latest-index.json"),
        help="proposals index JSON from draft_proposals.py",
    )
    parser.add_argument("--approve", nargs="*", help="Approve queue item ids (or 'all')")
    parser.add_argument("--stop", nargs="*", help="Mark ids as STOP")
    parser.add_argument("--list", action="store_true", help="List queue")
    args = parser.parse_args()

    ensure_dirs()
    items = load_queue()

    if Path(args.from_index).exists() and not args.list and not args.approve and not args.stop:
        import json

        idx = json.loads(Path(args.from_index).read_text(encoding="utf-8"))
        existing_leads = {i.get("lead_id") for i in items}
        added = 0
        for p in idx.get("proposals") or []:
            lid = p.get("lead_id")
            if lid in existing_leads:
                continue
            qid = f"q-{lid}"
            items.append(
                {
                    "id": qid,
                    "lead_id": lid,
                    "company": p.get("company"),
                    "title": p.get("title"),
                    "url": p.get("url"),
                    "subject": p.get("subject"),
                    "body": p.get("body"),
                    "file": p.get("file"),
                    "match_score": p.get("match_score"),
                    "status": "draft",
                    "created_at": utc_now_iso(),
                    "updated_at": utc_now_iso(),
                    "to_email": "",  # fill before --send
                }
            )
            added += 1
        save_queue(items)
        print(f"Queued {added} new drafts (total {len(items)})")

    if args.approve is not None:
        targets = set(args.approve)
        n = 0
        for it in items:
            if "all" in targets or it["id"] in targets or it.get("lead_id") in targets:
                if it["status"] not in ("sent", "stop"):
                    it["status"] = "approved"
                    it["updated_at"] = utc_now_iso()
                    n += 1
        save_queue(items)
        print(f"Approved {n} items")

    if args.stop is not None:
        targets = set(args.stop)
        n = 0
        for it in items:
            if "all" in targets or it["id"] in targets or it.get("lead_id") in targets:
                it["status"] = "stop"
                it["updated_at"] = utc_now_iso()
                n += 1
        save_queue(items)
        print(f"STOP marked on {n} items")

    if args.list or True:
        print("\nOutreach queue:")
        if not items:
            print("  (empty)")
        for it in items:
            print(
                f"  [{it['status']:8}] {it['id']}  {it.get('company','?')[:20]} — {it.get('title','')[:40]}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
