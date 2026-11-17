# AI usage

The coding assistant inside Cursor was used on this project. It read the existing code, wrote the reminder-draft program and its tests, explained errors in the terminal and the browser, and drafted `SECURITY.md`.

The product does not call a paid AI service. Reminder text comes from a local template. That is the default `mock` mode in `task4_agent/llm.py`.

## Where the assistant was wrong

The assistant said to open `http://localhost:8069/odoo` and `http://localhost:8069/settings`.

The browser showed **Not Found** for both addresses. The Apps page that was already open used `http://localhost:8069/web`. That is the correct address for this copy of Odoo 17. Later steps used `/web` instead of `/odoo`.
