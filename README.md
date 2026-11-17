# Blue Palm expiry tracker

This project keeps track of licences and other items that expire in Colombo and Dubai.

Four pieces work together:

1. A cleaned spreadsheet of the items.
2. A web page that lists those items and the reminder drafts.
3. An optional Odoo screen where a person can add items.
4. Reminder drafts that wait for a person to approve or reject them.

Nothing is emailed. A draft stays in the system until someone approves it.

The review date used everywhere is **1 December 2026**, not today's date on your computer.

The company names and the notes are fictional. The original spreadsheet notes contain dummy personal data, such as made-up passport and phone numbers. The clean file replaces those with `[REDACTED]`.

The keys shown below are demo keys. They are not secret production passwords.

## How to run it

You need Python 3.11 or newer. Docker Desktop is optional. Use one option, not both at the same time, because both use port 8000.

Open PowerShell and go to the project folder:

```powershell
cd C:\blue-palm-expiry
```

### Option A. Docker

Docker Desktop must be running. This starts Postgres and the demo together, loads the spreadsheet, and creates the reminder drafts once.

```powershell
docker compose up
```

Leave that window open.

### Option B. Python on this PC

This creates a local `.venv` the first time, installs the libraries, loads the spreadsheet into a file on this PC, creates the drafts once, and starts the page.

```powershell
.\run_demo.ps1
```

If Windows refuses to run the file, use:

```powershell
powershell -ExecutionPolicy Bypass -File .\run_demo.ps1
```

Leave that window open.

### Then open the page

Open http://localhost:8000/docs.

Each action has a box named `x-api-key`.

- To read the list, type `dev-api-key-change-me`.
- To approve or reject a draft, type `manager-key-change-me`. The read key cannot approve.
- In `by`, type a real name. The word `string` is rejected.
- Use the small draft `id` from the list (1, 2, 3), not the item number.

Stop the demo with Ctrl+C.

### Odoo (optional)

Odoo is optional. The module in this repo was tried on the author's machine. This repo does not contain a `task3_odoo/screenshots` folder.

To install the module in Odoo 17:

1. Tell Odoo to look in the `task3_odoo` folder for extra add-ons, then restart Odoo.
2. Open http://localhost:8069/web.
3. Turn on developer mode.
4. Open Apps and choose Update Apps List.
5. Search for Blue Palm Expiry and press Activate.

## The numbers

Counted on 1 December 2026 from the clean spreadsheet. "Expired" means a date before that day. "Due in December" means 1 December through 31 December 2026.

| Branch | Expired | Due 1–31 Dec 2026 |
| --- | --- | --- |
| Colombo | 3 | 10 |
| Dubai | 3 | 5 |
| Total | 6 | 15 |

BP-1005 is stored as Colombo, and that is how the table above counts it. The row is flagged because the item name and the email look like Dubai. If that one row were counted as Dubai instead, December would be Colombo 9 and Dubai 6.

BP-1020 appears twice, with two different dates. The date 13 November 2026 is one of the three Colombo expired rows. The other date is 13 November 2027, so it is not in this table.

Three items have no date. They are left out of this table.

## Assumptions

- The review date is fixed at 1 December 2026.
- The only branches are Colombo and Dubai.
- A date that could be read two ways, and an email that is not a real address, are left blank. They are not guessed.
- If the item name and the email point at the other city, the branch is not switched.
- A cost of 0, and a negative cost, are kept and flagged for a person.
- An exact duplicate row is removed. The same id with two different dates is kept as two rows.
- Reminder text is a local template. No paid AI service is called.
- If an item already has a pending or approved draft for the same expiry date, a second draft is not created.
- Nothing is sent.

## Five questions before a real system

1. Who is allowed to approve a reminder, and what is that person's name in the system?
2. Should someone in Colombo be blocked from seeing Dubai items?
3. When the yearly cost is 0, does that mean the item is free, or that the cost was never entered?
4. For the date written `08/12/2026`, is that 8 December 2026 or 12 August 2026?
5. After a person approves a draft, should a colleague send the email, or should the system send it?

## What two more weeks would be used for

- Replace the two shared keys with a login for each person.
- Limit each person to their own branch.
- Store the data in Postgres rather than the demo file on one PC. Option A already starts Postgres for a demo.
- Practise restoring a backup and check the row count.
- Decide the 12 rows that are still flagged.
- Add a send step only after those decisions, and still require a person to approve first.

## Folder map

| Folder or file | What it is |
| --- | --- |
| `clean.py`, `clean_items.csv`, `data_issues.md` | The spreadsheet clean-up and the notes about rows a person must still decide |
| `task2_api` | The item list |
| `task3_odoo` | The optional Odoo module |
| `task4_agent` | The reminder drafts |
| `run_demo.ps1` | Starts the demo on this PC |
| `docker-compose.yml` | Starts the demo with Postgres |
| `SECURITY.md` | What is protected today, and what is still to do |
| `AI_USAGE.md` | Which assistant was used, and one mistake that was caught |

## Known limitations

- The approver name is typed in by hand. There is no user login.
- The read key and the approve key are each one shared demo value.
- Option B stores data in a SQLite file on this PC. That is for a demo. Option A uses Postgres.
- A read key can still ask for both branches. It is not locked to one city.
- Nothing is sent when a draft is approved.

## More detail

- [SECURITY.md](SECURITY.md)
- [AI_USAGE.md](AI_USAGE.md)
- [data_issues.md](data_issues.md)

API means the web page of lists at port 8000. Odoo means the optional business screen at port 8069. Docker means the tool that starts the database and the demo together.

## Time spent

Hours below are approximate. Fill them in.

| Task | What it was | Hours |
| --- | --- | --- |
| Setup | Getting the machine ready | |
| 1 | Clean the spreadsheet | |
| 2 | Item list | |
| 3 | Odoo screen | |
| 4 | Reminder drafts | |
| 5 | Security note | |
| 6 | This guide and the demo start | |
| Total | | |
