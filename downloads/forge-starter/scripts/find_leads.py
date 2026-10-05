#!/usr/bin/env python3
"""Find freelance-friendly leads from legal public APIs/RSS only.

Sources:
  - Remotive public API (https://remotive.com/api/remote-jobs) — attribute Remotive
  - We Work Remotely public RSS (programming + all) — attribute WWR
  - RemoteOK public API (https://remoteok.com/api) — attribute RemoteOK

Does NOT scrape Upwork/LinkedIn or use logged-in browser harvest.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import (  # noqa: E402
    LEADS_DIR,
    ensure_dirs,
    http_get,
    snippet,
    stamp,
    strip_html,
    utc_now_iso,
    write_json,
    write_leads_csv,
)

FREELANCE_HINTS = {
    "freelance",
    "freelancer",
    "contract",
    "contractor",
    "consultant",
    "part-time",
    "part time",
    "gig",
    "hourly",
    "project-based",
    "fixed price",
    "independent",
}

AUTO_KEYWORDS = {
    "automation",
    "chatbot",
    "bot",
    "whatsapp",
    "ai",
    "openai",
    "llm",
    "n8n",
    "zapier",
    "make.com",
    "nocode",
    "no-code",
    "api",
    "python",
    "javascript",
    "integration",
    "crm",
    "lead",
    "support",
    "customer support",
    "booking",
    "webhook",
}


def _lead_id(source: str, url: str, title: str) -> str:
    raw = f"{source}|{url}|{title}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:12]


def _extract_keywords(text: str) -> list[str]:
    low = text.lower()
    found = sorted({k for k in AUTO_KEYWORDS if k in low})
    return found


def _base_score(text: str, job_type: str = "") -> float:
    low = (text + " " + job_type).lower()
    score = 0.0
    for h in FREELANCE_HINTS:
        if h in low:
            score += 2.0
    for k in AUTO_KEYWORDS:
        if k in low:
            score += 1.0
    if "full_time" in low or "full-time" in low or "full time" in low:
        score -= 0.5
    if job_type.lower() in {"freelance", "contract", "part_time", "part-time"}:
        score += 3.0
    return score


def fetch_remotive() -> list[dict]:
    import json

    raw = http_get("https://remotive.com/api/remote-jobs")
    data = json.loads(raw.decode("utf-8"))
    leads = []
    for job in data.get("jobs", []):
        title = (job.get("title") or "").strip()
        company = (job.get("company_name") or "").strip()
        url = (job.get("url") or "").strip()
        if not title or not url:
            continue
        desc = job.get("description") or ""
        tags = job.get("tags") or []
        job_type = job.get("job_type") or ""
        blob = f"{title} {company} {job_type} {' '.join(tags)} {strip_html(desc)}"
        leads.append(
            {
                "id": _lead_id("remotive", url, title),
                "title": title,
                "company": company,
                "url": url,
                "source": "remotive",
                "snippet": snippet(desc),
                "match_score": round(_base_score(blob, job_type), 2),
                "keywords": _extract_keywords(blob) or list(tags)[:8],
                "job_type": job_type,
                "posted": job.get("publication_date") or "",
                "category": job.get("category") or "",
            }
        )
    return leads


def _parse_wwr_title(title: str) -> tuple[str, str]:
    # "Company: Role"
    if ": " in title:
        company, role = title.split(": ", 1)
        return role.strip(), company.strip()
    return title.strip(), ""


def fetch_wwr(feed_url: str) -> list[dict]:
    raw = http_get(feed_url)
    root = ET.fromstring(raw)
    leads = []
    for item in root.findall("./channel/item"):
        raw_title = (item.findtext("title") or "").strip()
        url = (item.findtext("link") or "").strip()
        desc = item.findtext("description") or ""
        category = item.findtext("category") or ""
        if not raw_title or not url:
            continue
        title, company = _parse_wwr_title(raw_title)
        blob = f"{title} {company} {category} {strip_html(desc)}"
        # WWR often has contract roles; boost contract/freelance wording
        leads.append(
            {
                "id": _lead_id("wwr", url, title),
                "title": title,
                "company": company,
                "url": url,
                "source": "weworkremotely",
                "snippet": snippet(desc),
                "match_score": round(_base_score(blob), 2),
                "keywords": _extract_keywords(blob),
                "job_type": "contract" if "contract" in blob.lower() else category,
                "posted": item.findtext("pubDate") or "",
                "category": category,
            }
        )
    return leads


def fetch_remoteok() -> list[dict]:
    import json

    raw = http_get("https://remoteok.com/api")
    data = json.loads(raw.decode("utf-8"))
    leads = []
    for job in data:
        if not isinstance(job, dict) or "id" not in job or job.get("id") == "legal":
            continue
        # first element is often legal notice without position
        title = (job.get("position") or job.get("title") or "").strip()
        company = (job.get("company") or "").strip()
        url = (job.get("url") or job.get("apply_url") or "").strip()
        if not url and job.get("slug"):
            url = f"https://remoteok.com/remote-jobs/{job['slug']}"
        if not title or not url:
            continue
        tags = job.get("tags") or []
        if isinstance(tags, str):
            tags = [tags]
        desc = job.get("description") or ""
        blob = f"{title} {company} {' '.join(tags)} {strip_html(desc)}"
        leads.append(
            {
                "id": _lead_id("remoteok", url, title),
                "title": title,
                "company": company,
                "url": url,
                "source": "remoteok",
                "snippet": snippet(desc),
                "match_score": round(_base_score(blob), 2),
                "keywords": _extract_keywords(blob) or list(tags)[:8],
                "job_type": "remote",
                "posted": job.get("date") or "",
                "category": ", ".join(tags[:3]) if tags else "",
            }
        )
    return leads


def dedupe(leads: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out = []
    for lead in leads:
        key = re.sub(r"\W+", "", (lead.get("url") or "").lower()) or lead["id"]
        if key in seen:
            continue
        seen.add(key)
        out.append(lead)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Forge lead finder (public APIs/RSS only)")
    parser.add_argument("--limit", type=int, default=25, help="Max leads to keep after sort")
    parser.add_argument(
        "--sources",
        default="remotive,wwr,remoteok",
        help="Comma list: remotive,wwr,remoteok",
    )
    parser.add_argument("--min-score", type=float, default=0.0, help="Drop leads below this base score")
    args = parser.parse_args()

    ensure_dirs()
    sources = {s.strip().lower() for s in args.sources.split(",") if s.strip()}
    all_leads: list[dict] = []
    errors: list[str] = []

    if "remotive" in sources:
        try:
            got = fetch_remotive()
            print(f"[remotive] {len(got)} jobs")
            all_leads.extend(got)
        except Exception as e:
            errors.append(f"remotive: {e}")
            print(f"[remotive] ERROR: {e}", file=sys.stderr)

    if "wwr" in sources or "weworkremotely" in sources:
        for feed in (
            "https://weworkremotely.com/categories/remote-programming-jobs.rss",
            "https://weworkremotely.com/categories/remote-full-stack-programming-jobs.rss",
            "https://weworkremotely.com/remote-jobs.rss",
        ):
            try:
                got = fetch_wwr(feed)
                print(f"[wwr] {len(got)} from {feed.split('/')[-1]}")
                all_leads.extend(got)
            except Exception as e:
                errors.append(f"wwr:{feed}: {e}")
                print(f"[wwr] ERROR {feed}: {e}", file=sys.stderr)
            break  # one feed is enough for MVP; programming feed preferred

    if "remoteok" in sources:
        try:
            got = fetch_remoteok()
            print(f"[remoteok] {len(got)} jobs")
            all_leads.extend(got)
        except Exception as e:
            errors.append(f"remoteok: {e}")
            print(f"[remoteok] ERROR: {e}", file=sys.stderr)

    leads = dedupe(all_leads)
    leads = [L for L in leads if float(L.get("match_score") or 0) >= args.min_score]
    leads.sort(key=lambda L: float(L.get("match_score") or 0), reverse=True)
    leads = leads[: args.limit]

    ts = stamp()
    payload = {
        "generated_at": utc_now_iso(),
        "attribution": [
            "Remotive (https://remotive.com) — jobs attributed to Remotive URLs",
            "We Work Remotely (https://weworkremotely.com) — RSS attributed to WWR",
            "RemoteOK (https://remoteok.com) — API attributed to RemoteOK",
        ],
        "count": len(leads),
        "errors": errors,
        "leads": leads,
    }
    json_path = LEADS_DIR / f"leads-{ts}.json"
    csv_path = LEADS_DIR / f"leads-{ts}.csv"
    latest_json = LEADS_DIR / "leads-latest.json"
    latest_csv = LEADS_DIR / "leads-latest.csv"
    write_json(json_path, payload)
    write_json(latest_json, payload)
    write_leads_csv(csv_path, leads)
    write_leads_csv(latest_csv, leads)

    print(f"\nSaved {len(leads)} leads → {json_path.name} / {csv_path.name}")
    for i, L in enumerate(leads[:10], 1):
        print(
            f"  {i}. [{L['match_score']:>4}] {L['title'][:50]} @ {L['company'][:24]} ({L['source']})"
        )
        print(f"     {L['url']}")
    return 0 if leads else (1 if errors else 0)


if __name__ == "__main__":
    raise SystemExit(main())
