# Blue Palm Expiry

Odoo 17 Community add-on that tracks licences, policies, and other items that expire.

## Status

Status is stored and computed from the expiry date:

- no date: No date
- before today: Expired
- within 30 days, including today: Expiring within 30 days
- later: Valid

The review date is the system parameter `blue_palm_expiry.today`, seeded as `2026-12-01`. If that parameter is empty, Odoo uses the user's today. A daily scheduled action, Update expiry status, recomputes every record so stored statuses stay current.

## Access

Internal users can read, create, and update items. They cannot delete them. Users in Expiry Tracker / Manager can also delete. A record rule limits every user to items of their own companies.

## Install

Add the `task3_odoo` directory to the Odoo addons path, update the app list, and install Blue Palm Expiry. This module does not load personal data.
