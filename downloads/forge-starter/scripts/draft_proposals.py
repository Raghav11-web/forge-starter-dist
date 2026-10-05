#!/usr/bin/env python3
"""Draft short plain-English proposals for top matched leads. Never auto-sends."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import (  # noqa: E402
    PROFILES_DIR,
    PROPOSALS_DIR,
    ensure_dirs,
    latest_matched_file,
    load_yaml,
    slugify,
    stamp,
    utc_now_iso,
    write_json,
)


def draft_body(lead: dict, profile: dict) -> str:
    name = profile.get("display_name") or profile.get("name") or "there"
    niche = profile.get("niche") or "automation"
    portfolio = profile.get("portfolio") or []
    port_line = portfolio[0] if portfolio else ""
    bio = (profile.get("bio") or "").strip()
    company = lead.get("company") or "your team"
    title = lead.get("title") or "this role"
    snippet = lead.get("snippet") or ""
    hits = lead.get("match_hits") or []
    skill_hits = [h.split(":", 1)[1] for h in hits if h.startswith("skill:")][:4]
    skill_bit = ", ".join(skill_hits) if skill_hits else "automation and APIs"

    lines = [
        f"Hi {company} team,",
        "",
        f"I saw your post for {title}.",
        "",
        f"I help with {niche}. {bio}".strip(),
        "",
        f"For this role, I can help with {skill_bit}.",
    ]
    if snippet:
        lines.append("")
        lines.append(
            "From your listing, it looks like you need someone who can ship practical automation without a long setup."
        )
    lines.extend(
        [
            "",
            "I can start with a short paid demo on one real workflow, then we decide.",
            "",
        ]
    )
    if port_line:
        lines.append(f"Quick look: {port_line}")
        lines.append("")
    lines.extend(
        [
            "If this fits, reply here and I will share a 3-step plan for your use case.",
            "",
            f"Thanks,",
            name,
        ]
    )
    email = profile.get("email")
    if email:
        lines.append(email)
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Draft proposals for matched leads")
    parser.add_argument("--profile", default=str(PROFILES_DIR / "demo-freelancer.yaml"))
    parser.add_argument("--matched", default="", help="matched JSON (default: latest)")
    parser.add_argument("--top", type=int, default=5, help="Draft for top N")
    args = parser.parse_args()

    ensure_dirs()
    profile = load_yaml(Path(args.profile))
    matched_path = Path(args.matched) if args.matched else latest_matched_file()
    if not matched_path or not Path(matched_path).exists():
        print("No matched leads. Run match_leads.py first.", file=sys.stderr)
        return 2

    import json

    data = json.loads(Path(matched_path).read_text(encoding="utf-8"))
    leads = data.get("leads") or []
    leads = leads[: args.top]
    if not leads:
        print("No leads to draft.", file=sys.stderr)
        return 1

    ts = stamp()
    batch_dir = PROPOSALS_DIR / f"batch-{ts}"
    batch_dir.mkdir(parents=True, exist_ok=True)
    index = []

    for i, lead in enumerate(leads, 1):
        body = draft_body(lead, profile)
        subject = f"Re: {lead.get('title', 'your listing')} — quick fit check"
        fname = f"{i:02d}-{slugify(lead.get('company') or 'co')}-{slugify(lead.get('title') or 'role')}.md"
        path = batch_dir / fname
        md = "\n".join(
            [
                f"# Proposal draft {i}",
                "",
                f"- Lead ID: `{lead.get('id')}`",
                f"- Company: {lead.get('company')}",
                f"- Title: {lead.get('title')}",
                f"- URL: {lead.get('url')}",
                f"- Source: {lead.get('source')}",
                f"- Match score: {lead.get('match_score')}",
                f"- Status: draft (not sent)",
                f"- Generated: {utc_now_iso()}",
                "",
                f"**Subject:** {subject}",
                "",
                "---",
                "",
                body,
                "",
            ]
        )
        path.write_text(md, encoding="utf-8")
        index.append(
            {
                "file": str(path.relative_to(Path(__file__).resolve().parents[1])),
                "lead_id": lead.get("id"),
                "company": lead.get("company"),
                "title": lead.get("title"),
                "url": lead.get("url"),
                "subject": subject,
                "body": body,
                "match_score": lead.get("match_score"),
                "status": "draft",
            }
        )
        print(f"  wrote {path.name}")

    meta = {
        "generated_at": utc_now_iso(),
        "profile": profile.get("id"),
        "count": len(index),
        "proposals": index,
    }
    write_json(batch_dir / "index.json", meta)
    write_json(PROPOSALS_DIR / "latest-index.json", meta)
    print(f"\nDrafted {len(index)} proposals → {batch_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
