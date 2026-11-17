# Security

This repo cleans an expiry spreadsheet, serves a read API, drafts reminders for a person to approve, and shows the same records in Odoo for Colombo and Dubai. It does not send email.

## 1. Secrets and passwords

[Done] `.gitignore` ignores `.env`. `.env.example` has dummy values only: `dev-api-key-change-me`, `manager-key-change-me`, and database name `bluepalm`.

[Done] `API_KEY` guards reads (`task2_api/auth.py`, `GET /drafts`). `MANAGER_API_KEY` guards only approve and reject (`task4_agent/main.py`).

[Done] If `APP_ENV=production` and either key is `dev-api-key-change-me`, `task4_agent/main.py` refuses to start. `manager-key-change-me` is not blocked.

[Done] `task2_api/config.py` reads `DATABASE_URL`. If unset, the API uses SQLite.

[Done] The prompt is only type, name, expiry date, and days left (`task4_agent/reminder_agent.py`). A passport, a phone number, and an email are stripped first (`task4_agent/redact.py`). The log stores item reference, branch, draft id, action, status, and the person who approved or rejected, not email or notes (`task4_agent/audit.py`). `GET /activity` returns that history.

[Planned] Secrets manager, rotation every 90 days or when someone leaves, and one key per person. `docker-compose.yml` still has the demo database password.

## 2. Database backups

[Planned] This repo does not dump, encrypt, copy, or restore the database.

For production: nightly Postgres `pg_dump`, plus a weekly full backup, encrypted and stored off the server. Keep 14 daily and 12 monthly copies. Each month, restore one into a scratch database, check the row count against production, and log it. Lose at most 24 hours of data. Restore within 2 hours.

## 3. Who gets what access

| Who | Access | In this repo |
| --- | --- | --- |
| Founders | Read reports | [Planned] No login |
| Branch staff | Own branch only | [Planned] No login |
| Managers | Approve or reject | [Done] `MANAGER_API_KEY` |
| IT admin | Server, database, backups; two people, MFA | [Planned] |
| API clients | Read key only | [Done] `API_KEY` cannot approve |

[Done] Odoo limits each user to their own companies (`task3_odoo/blue_palm_expiry/security/security.xml`). [Done] Callers can filter by Colombo or Dubai (`task2_api/main.py`, `task4_agent/main.py`). [Planned] A read key is not locked to one branch; omitting `branch` returns both.

[Done] Passports and phone numbers are redacted before a draft is built (`task4_agent/redact.py`), omitted from item responses (`task2_api/schemas.py`), and omitted from the audit log (`task4_agent/audit.py`). [Done] Approve and reject send nothing (`task4_agent/approve.py`).

## 4. If the disk is full

1. Stay calm. Do not delete database files or write-ahead logs.
2. Run `df -h` and `du` (logs, old backups, or unused images).
3. Rotate or compress logs. Delete old local backups only after the off-server copy is confirmed. Prune unused Docker images only.
4. If still full, enlarge the volume and restart the containers.
5. Check a row count and `/items`, then note when it happened, what filled the disk, and what was removed.
6. Prevention is [Planned]: alert at 80% full, log rotation, backup retention, and monitoring. None of this is in the repo.

## 5. Known limitations

- The approver name is free text. There is no user login (`task4_agent/main.py`).
- The read key and the manager key are each one shared value.
- SQLite is only a demo fallback when `DATABASE_URL` is unset (`task2_api/config.py`).
