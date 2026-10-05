#!/usr/bin/env python3
"""Score leads against a freelancer profile YAML and write matched-*.json."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import (  # noqa: E402
    LEADS_DIR,
    PROFILES_DIR,
    ensure_dirs,
    latest_leads_file,
    load_yaml,
    stamp,
    utc_now_iso,
    write_json,
    write_leads_csv,
)



def _contains(blob: str, term: str) -> bool:
    term = term.strip().lower()
    if not term:
        return False
    if " " in term or len(term) >= 4:
        return term in blob
    # short tokens: word-ish boundary to avoid "bot" in "about"
    return re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", blob) is not None

def score_lead(lead: dict, profile: dict) -> tuple[float, list[str]]:
    skills = [str(s).lower() for s in (profile.get("skills") or [])]
    preferred = [str(s).lower() for s in (profile.get("preferred_keywords") or [])]
    avoid = [str(s).lower() for s in (profile.get("avoid_keywords") or [])]
    niche = str(profile.get("niche") or "").lower()

    blob = " ".join(
        [
            str(lead.get("title") or ""),
            str(lead.get("company") or ""),
            str(lead.get("snippet") or ""),
            str(lead.get("job_type") or ""),
            str(lead.get("category") or ""),
            " ".join(lead.get("keywords") or []),
        ]
    ).lower()

    hits: list[str] = []
    score = float(lead.get("match_score") or 0)

    for s in skills:
        if s and _contains(blob, s):
            score += 2.5
            hits.append(f"skill:{s}")
    for p in preferred:
        if p and _contains(blob, p):
            score += 1.5
            hits.append(f"pref:{p}")
    for a in avoid:
        if a and _contains(blob, a):
            score -= 4.0
            hits.append(f"avoid:{a}")

    # niche token overlap
    for tok in niche.replace(",", " ").split():
        tok = tok.strip()
        if len(tok) > 3 and _contains(blob, tok):
            score += 0.8
            hits.append(f"niche:{tok}")

    # freelance-friendly boost
    for word in ("freelance", "contract", "consultant", "gig", "hourly"):
        if word in blob:
            score += 1.2
            hits.append(f"type:{word}")

    return round(score, 2), sorted(set(hits))


def main() -> int:
    parser = argparse.ArgumentParser(description="Match leads to freelancer profile")
    parser.add_argument(
        "--profile",
        default=str(PROFILES_DIR / "demo-freelancer.yaml"),
        help="Path to profile YAML",
    )
    parser.add_argument("--leads", default="", help="leads JSON path (default: latest)")
    parser.add_argument("--top", type=int, default=15, help="Keep top N after scoring")
    parser.add_argument("--min-score", type=float, default=3.0)
    args = parser.parse_args()

    ensure_dirs()
    profile_path = Path(args.profile)
    if not profile_path.exists():
        print(f"Profile not found: {profile_path}", file=sys.stderr)
        return 2

    profile = load_yaml(profile_path)
    leads_path = Path(args.leads) if args.leads else latest_leads_file()
    if not leads_path or not Path(leads_path).exists():
        print("No leads file. Run find_leads.py first.", file=sys.stderr)
        return 2

    import json

    data = json.loads(Path(leads_path).read_text(encoding="utf-8"))
    leads = data.get("leads") if isinstance(data, dict) else data
    if not isinstance(leads, list):
        print("Invalid leads file", file=sys.stderr)
        return 2

    scored = []
    for lead in leads:
        s, hits = score_lead(lead, profile)
        if s < args.min_score:
            continue
        row = dict(lead)
        row["match_score"] = s
        row["match_hits"] = hits
        row["profile_id"] = profile.get("id") or profile_path.stem
        scored.append(row)

    scored.sort(key=lambda L: L["match_score"], reverse=True)
    scored = scored[: args.top]

    ts = stamp()
    out = {
        "generated_at": utc_now_iso(),
        "profile": profile.get("id") or profile_path.stem,
        "profile_name": profile.get("name") or profile.get("display_name"),
        "source_leads": str(leads_path),
        "count": len(scored),
        "leads": scored,
    }
    json_path = LEADS_DIR / f"matched-{ts}.json"
    latest = LEADS_DIR / "matched-latest.json"
    csv_path = LEADS_DIR / f"matched-{ts}.csv"
    write_json(json_path, out)
    write_json(latest, out)
    write_leads_csv(csv_path, scored)

    print(f"Matched {len(scored)} leads for {out['profile_name']} → {json_path.name}")
    for i, L in enumerate(scored[:10], 1):
        print(f"  {i}. [{L['match_score']:>5}] {L['title'][:48]} @ {L['company'][:20]}")
        print(f"     hits: {', '.join(L.get('match_hits', [])[:6])}")
    return 0 if scored else 1


if __name__ == "__main__":
    raise SystemExit(main())
