# How to use Forge

Simple English. You build. We find the work.

## What Forge does

Forge looks at public job boards (Remotive, We Work Remotely, RemoteOK), finds gigs that match your skills, writes short proposal drafts, and puts them in a queue for you to approve.

It does **not** auto-send mail unless you clearly pass `--send` and set SMTP env vars.  
It does **not** log into Upwork or LinkedIn to scrape or mass-apply.

---

## First-time setup

1. Open this folder: `freelancer-ops`
2. (Optional) `pip install -r requirements.txt`
3. Edit or copy `profiles/demo-freelancer.yaml` → your own profile
4. Fill: name, email, skills, niche, rate band, portfolio links, preferred keywords

---

## Daily flow (copy-paste)

```bash
python3 scripts/find_leads.py --limit 15
python3 scripts/match_leads.py --profile profiles/demo-freelancer.yaml
python3 scripts/draft_proposals.py --top 5
python3 scripts/queue_outreach.py
python3 scripts/queue_outreach.py --approve all --list
python3 scripts/send_outreach.py          # dry-run — safe
python3 scripts/daily_digest.py
```

Read drafts under `data/proposals/batch-*/`.  
Edit the markdown if you want a different tone. Then approve only the ones you like.

---

## Sending mail (careful)

1. Copy `.env.example` to `.env`
2. Set `FORGE_SMTP_USER`, `FORGE_SMTP_PASS`, `FORGE_FROM_EMAIL`
3. Set `FORGE_TEST_TO` to **your own** test inbox first
4. Run: `python3 scripts/send_outreach.py --send --test-only`

If someone replies STOP, mark the queue item:

```bash
python3 scripts/queue_outreach.py --stop q-LEADID
```

---

## Hinglish short version

- Profile bharo → leads lao → match karo → draft padho → approve karo → pehle dry-run, phir send  
- Upwork/LinkedIn pe auto-apply **nahi** hai (TOS safe)  
- Tum sirf build + deliver pe focus; hunting Forge karega (jitna public boards allow karein)

---

## Tips for better matches

- Add real skills you ship (python, n8n, chatbot, whatsapp, etc.)
- Prefer keywords clients actually write in posts
- Use `avoid_keywords` for unpaid / equity-only noise
- Re-run find+match once or twice a day, not every minute (be kind to free APIs)

---

Questions? Ask Raghav — Forge is part of the Proximus parallel toolkit.
