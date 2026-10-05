"""Shared helpers for Forge Freelancer Ops scripts."""
from __future__ import annotations

import csv
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
LEADS_DIR = DATA / "leads"
PROPOSALS_DIR = DATA / "proposals"
QUEUE_DIR = DATA / "queue"
PROFILES_DIR = ROOT / "profiles"

USER_AGENT = "ForgeLeadFinder/1.0 (+https://github.com/Raghav11-web; personal research; attribution to sources)"


def ensure_dirs() -> None:
    for d in (LEADS_DIR, PROPOSALS_DIR, QUEUE_DIR):
        d.mkdir(parents=True, exist_ok=True)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def load_yaml(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(text)
        if not isinstance(data, dict):
            raise ValueError("profile must be a mapping")
        return data
    except ImportError:
        return _simple_yaml(text)


def _simple_yaml(text: str) -> dict[str, Any]:
    """Tiny subset reader if PyYAML is missing: scalars + flat lists."""
    data: dict[str, Any] = {}
    key: str | None = None
    list_mode = False
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if list_mode and line.lstrip().startswith("- "):
            assert key is not None
            data.setdefault(key, []).append(line.lstrip()[2:].strip().strip("\"'"))
            continue
        list_mode = False
        if ":" in line and not line.lstrip().startswith("-"):
            k, v = line.split(":", 1)
            key = k.strip()
            v = v.strip()
            if v == "" or v == ">" or v == "|":
                data[key] = [] if v == "" else ""
                list_mode = v == ""
                if v in (">", "|"):
                    # fold following indented lines into string
                    pass
            else:
                data[key] = v.strip("\"'")
                list_mode = False
        elif key and (line.startswith("  ") or line.startswith("\t")):
            # continuation for > block or nested map start — store as string append
            if isinstance(data.get(key), list) and not line.lstrip().startswith("-"):
                # nested map under rate_band etc — skip nested for simple parser
                continue
            if isinstance(data.get(key), str):
                data[key] = (data[key] + " " + line.strip()).strip()
    # rate_band nested: leave empty; matcher handles missing
    return data


def strip_html(html: str) -> str:
    text = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
    text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&#39;|&apos;", "'", text)
    text = re.sub(r"&quot;", '"', text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def snippet(text: str, n: int = 220) -> str:
    t = strip_html(text) if "<" in text else re.sub(r"\s+", " ", text).strip()
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_leads_csv(path: Path, leads: list[dict[str, Any]]) -> None:
    fields = [
        "id",
        "title",
        "company",
        "url",
        "source",
        "snippet",
        "match_score",
        "keywords",
        "job_type",
        "posted",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for lead in leads:
            row = dict(lead)
            if isinstance(row.get("keywords"), list):
                row["keywords"] = ", ".join(row["keywords"])
            w.writerow({k: row.get(k, "") for k in fields})


def latest_leads_file() -> Path | None:
    files = sorted(LEADS_DIR.glob("leads-*.json"), reverse=True)
    return files[0] if files else None


def latest_matched_file() -> Path | None:
    files = sorted(LEADS_DIR.glob("matched-*.json"), reverse=True)
    return files[0] if files else None


def queue_path() -> Path:
    return QUEUE_DIR / "outreach_queue.json"


def load_queue() -> list[dict[str, Any]]:
    p = queue_path()
    if not p.exists():
        return []
    data = read_json(p)
    return data if isinstance(data, list) else data.get("items", [])


def save_queue(items: list[dict[str, Any]]) -> None:
    write_json(queue_path(), {"updated_at": utc_now_iso(), "items": items})


def http_get(url: str, timeout: int = 30) -> bytes:
    import urllib.request

    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def slugify(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")[:60] or "item"


if __name__ == "__main__":
    print("ROOT", ROOT)
    ensure_dirs()
