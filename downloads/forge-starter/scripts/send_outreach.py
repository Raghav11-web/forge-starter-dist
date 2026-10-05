#!/usr/bin/env python3
"""Send approved outreach. Default is DRY-RUN. Use --send only with env credentials.

Never sends to real recipients unless --send is passed AND SMTP env is set.
Optional --test-only forces FORGE_TEST_TO as the only recipient.
"""
from __future__ import annotations

import argparse
import os
import smtplib
import sys
from email.mime.text import MIMEText
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import ensure_dirs, load_queue, save_queue, utc_now_iso  # noqa: E402


def load_dotenv() -> None:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip("\"'"))


def smtp_send(to_addr: str, subject: str, body: str) -> None:
    host = os.environ.get("FORGE_SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("FORGE_SMTP_PORT", "587"))
    user = os.environ.get("FORGE_SMTP_USER") or os.environ.get("FORGE_FROM_EMAIL")
    password = os.environ.get("FORGE_SMTP_PASS")
    from_email = os.environ.get("FORGE_FROM_EMAIL") or user
    from_name = os.environ.get("FORGE_FROM_NAME", "Raghav")
    if not user or not password or not from_email:
        raise RuntimeError("Missing FORGE_SMTP_USER / FORGE_SMTP_PASS / FORGE_FROM_EMAIL")

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{from_email}>"
    msg["To"] = to_addr
    # Soft STOP footer reminder
    msg["X-Forge-Product"] = "Forge"

    with smtplib.SMTP(host, port, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(user, password)
        smtp.sendmail(from_email, [to_addr], msg.as_string())


def main() -> int:
    parser = argparse.ArgumentParser(description="Send approved outreach (dry-run by default)")
    parser.add_argument("--send", action="store_true", help="Actually send (requires SMTP env)")
    parser.add_argument(
        "--test-only",
        action="store_true",
        help="Force recipient to FORGE_TEST_TO only",
    )
    parser.add_argument("--ids", nargs="*", help="Only these queue ids (default: all approved)")
    args = parser.parse_args()

    load_dotenv()
    ensure_dirs()
    items = load_queue()
    approved = [
        it
        for it in items
        if it.get("status") == "approved"
        and (not args.ids or it["id"] in args.ids or it.get("lead_id") in (args.ids or []))
    ]

    if not approved:
        print("No approved items to send. Approve with: python3 scripts/queue_outreach.py --approve all")
        return 0

    test_to = os.environ.get("FORGE_TEST_TO", "").strip()
    sent = 0
    for it in approved:
        if args.test_only and not test_to:
            print("FORGE_TEST_TO not set; cannot --test-only", file=sys.stderr)
            return 2
        if args.test_only:
            to_addr = test_to
        else:
            to_addr = (it.get("to_email") or "").strip()
        if not to_addr:
            if not args.send:
                to_addr = "(no to_email set — fill queue item or use --test-only)"
            else:
                print(f"  SKIP {it['id']}: no to_email (set on queue item or use --test-only)")
                continue

        subject = it.get("subject") or "Quick note"
        body = it.get("body") or ""
        if "STOP" not in body.upper():
            body = body.rstrip() + "\n\nIf this is not relevant, reply STOP and I will not write again.\n"

        if not args.send:
            print(f"[DRY-RUN] would send → {to_addr}")
            print(f"  Subject: {subject}")
            print(f"  Preview: {body[:120].replace(chr(10), ' ')}…")
            continue

        try:
            smtp_send(to_addr, subject, body)
            it["status"] = "sent"
            it["sent_at"] = utc_now_iso()
            it["sent_to"] = to_addr
            it["updated_at"] = utc_now_iso()
            sent += 1
            print(f"[SENT] {it['id']} → {to_addr}")
        except Exception as e:
            print(f"[ERROR] {it['id']}: {e}", file=sys.stderr)

    if args.send:
        save_queue(items)
        print(f"Sent {sent}/{len(approved)}")
    else:
        print(f"\nDry-run complete for {len(approved)} approved item(s). Pass --send to deliver.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
