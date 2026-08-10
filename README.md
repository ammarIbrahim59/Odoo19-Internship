# Odoo 19 Internship Modules

Custom Odoo 19 modules built during my internship. Two installable addons:

| Module | Type | What it does |
| --- | --- | --- |
| [`library_management`](#library_management) | Application | A library catalog with per-copy lending, a reservation/hold queue, and automated due-date reminders. |
| [`custom_partner_extension`](#custom_partner_extension) | Extension | Adds VIP and instructor-bio fields to `res.partner`, with a server-enforced auto-VIP rule. |

Both target **Odoo 19.0** and use the Odoo 19 ORM idioms (`models.Constraint`, `@api.model_create_multi`, computed+searchable fields).

---

## Quick start

These modules are addons — they need an Odoo 19 installation to run.

### Option A: Docker (fastest)

```bash
git clone https://github.com/ammarIbrahim59/odoo19-internship.git
cd odoo19-internship
docker compose up
```

Open <http://localhost:8069>, create a database, then install **Library Management** from Apps.

### Option B: Run against a local Odoo source tree

```bash
# 1. Get Odoo 19 (shallow clone — you don't need its full history)
git clone https://github.com/odoo/odoo --depth 1 --branch 19.0

# 2. Get these modules
git clone https://github.com/ammarIbrahim59/odoo19-internship.git

# 3. Set up a virtualenv
python3 -m venv venv
./venv/bin/pip install -r odoo/requirements.txt
./venv/bin/pip install -r odoo19-internship/requirements.txt

# 4. Run, with this repo on the addons path
./venv/bin/python odoo/odoo-bin \
    --addons-path=odoo/addons,odoo19-internship \
    -d library_db \
    -i library_management,custom_partner_extension
```

Use `-u <module>` instead of `-i` to upgrade after pulling changes — new fields, views, and security rules only load on install/upgrade.

> **Setup note:** on Python 3.13, Odoo's pinned `psycopg2==2.9.10` needs local build tooling. Installing `psycopg2-binary==2.9.10` instead avoids that with no code changes.

---

## `library_management`

An application for running a small library: what titles exist, which physical copies exist, who has them, and who's waiting.

**Menus:** Library → Books · Loans · Copies · Tags · Reservations

### Data model

```
library.book  ──1:N──▶  library.book.copy  ──1:N──▶  library.book.loan
     │                        (physical item)            (who borrowed it)
     └──N:M──▶ library.book.tag
     └──1:N──▶ library.book.reservation   (queue for when no copy is free)
```

| Model | Purpose |
| --- | --- |
| `library.book` | Title-level catalog record: `name` (unique), `author_id`, `tag_ids`, `pages`, `publication_date`. |
| `library.book.tag` | Genre/tag records with a color index. |
| `library.book.copy` | One record per physical copy. `copy_number` auto-increments per book; `status` is draft / available / borrowed / reserved / lost. |
| `library.book.loan` | A borrowing record: `copy_id`, `borrower_id`, `borrow_date`, `due_date`, `return_date`, `state`. |
| `library.book.reservation` | A hold request, with chatter via `mail.thread`. `state` is requested / ready / fulfilled / expired / cancelled. |

### Design decisions worth calling out

**Availability is derived, never manually set.** An earlier version had a manually-editable `status` on `library.book`, which could silently disagree with reality — marked "available" while every copy was out on loan. It was replaced with a stored computed `availability` field that depends on `copy_ids.status`. Book-level state is now always a function of actual copy state.

**Lending state lives on the copy, not the title.** A library owning three copies of the same book needs to track them independently, so `library.book.copy` is the unit of lending and `library.book` is purely bibliographic.

**SQL constraints use Odoo 19's `models.Constraint` syntax**, not the legacy `_sql_constraints` list:

```python
_check_pages_positive = models.Constraint(
    'CHECK(pages > 0)', 'The page count must be greater than zero!'
)
_name_uniq = models.Constraint(
    'UNIQUE(name)', 'A book with this title already exists!'
)
```

### Reservation & hold workflow

The interesting part. A member reserves a book that has no free copies; the system hands them one automatically the moment a copy frees up.

1. **Request** — a `library.book.reservation` is created in `requested` state.
2. **Auto-assign** — whenever a copy's `status` becomes `available` (via `create()` or `write()`), `_assign_pending_reservations` looks for the oldest `requested` reservation for that book (`order='request_date asc', limit=1`) and calls `_assign_copy`. That stamps `ready_date` / `hold_expiry`, flips the copy to `reserved`, and posts to the chatter.
3. **`reserved` status exists specifically to prevent theft of a hold** — a copy earmarked for someone's pickup is no longer `available`, so it can't be handed to a walk-in borrower.
4. **Expiry** — a daily `ir.cron` (`_cron_expire_reservations`) expires `ready` holds past `hold_expiry` and releases the copy back to `available`. That release cascades back into step 2 for the next person in the queue, for free.
5. **Fulfillment** — `action_fulfill` (a header button, visible only in `ready` state) creates the real `library.book.loan` and closes the reservation as `fulfilled`.

FIFO ordering resolves the two-holds-racing-for-one-copy case: exactly the oldest waiting reservation gets each freed copy.

### Automated due-date reminders

A daily `ir.cron` (`ir_cron_send_loan_due_reminders`, running as `base.user_root`) calls `library.book.loan._cron_send_due_date_reminders()`, which emails borrowers whose `ongoing` loan is due tomorrow using the `mail_template_loan_due_reminder` template.

Three non-obvious bugs came out of building this, each fixed in the code:

- **`mail.template.use_default_to` defaults to `True`**, which makes Odoo ignore the template's own `email_to` / `partner_to` and fall back to `_message_get_default_recipients()` — a heuristic that only looks for a field literally named `partner_id`. `library.book.loan` names its field `borrower_id`, so the reminder silently sent to nobody until `use_default_to` was explicitly set to `False`.
- **`body_html` is QWeb-rendered, not Jinja-rendered.** Only `t-out="expr"` interpolates; a literal `{{ object.x }}` in the body is emitted as plain text. (Inline Jinja *does* work in `subject` / `email_to`, which is what makes this easy to get wrong.)
- **Timezone.** `fields.Date.context_today()` depends on the executing user's `tz`, and `base.user_root` has none set. `fields.Date.today()` avoids that but still resolves to the server process's date — and Odoo pins its process timezone to UTC internally regardless of the host OS, so neither matches a library in a non-UTC location. The cron localizes `datetime.utcnow()` into an explicit `Africa/Cairo` zone instead. The fix is deliberately scoped to this one method rather than setting a `tz` on `base.user_root`, which is shared by nearly every core Odoo cron.

### Searchable computed fields

`library.book.loan.is_overdue` is computed and non-stored, with a custom `_search_is_overdue` so it still works in filters and domains. The gotcha: Odoo 19 normalizes `('field', '=', True)` into an `in` domain before calling a custom `search=` method, passing an `OrderedSet` as the value. Handling only `=` / `!=` silently inverts the filter for the most common case, so the method handles `in` / `not in` too.

---

## `custom_partner_extension`

Extends `res.partner` (`application: False` — it's an extension, not an app).

| Field | Type | Notes |
| --- | --- | --- |
| `is_vip` | Boolean | "VIP Member" flag. |
| `instructor_bio` | Text | Only meaningful for individuals — hidden via `invisible="is_company"`. |
| `bio_character_count` | Integer | Stored computed length of the bio. |

**The auto-VIP rule is enforced in two places, deliberately.** If a bio mentions "vip" or "partner", the contact is marked VIP:

- `_onchange_instructor_bio` gives immediate feedback in the form before saving.
- `_apply_vip_from_bio`, called from `create()` and `write()` overrides, is what makes the rule *authoritative* — onchange handlers don't fire for API calls, CSV imports, or server actions, so UI-only enforcement would leave those paths unguarded.

The module also inherits `base.view_res_partner_filter` to add a **VIP** filter and a **Group By → VIP** option to the Contacts search panel.

---

## Repository layout

```
odoo19-internship/
├── library_management/
│   ├── __manifest__.py
│   ├── models/          # book, tag, copy, loan, reservation
│   ├── views/           # list/form/search views + menus
│   ├── security/        # ir.model.access.csv
│   └── data/            # mail template + 2 ir.cron records
├── custom_partner_extension/
│   ├── __manifest__.py
│   ├── models/          # res_partner.py
│   └── views/           # form + search view inherits
├── docker-compose.yml   # Odoo 19 + PostgreSQL, this repo mounted as an addon
├── requirements.txt
└── README.md
```

Odoo itself is intentionally **not** vendored here. It's a versioned dependency (19.0), installed via the quick-start steps above.

---

## Known limitations

Honest list of what isn't built, rather than pretending it's finished:

- No reporting views for loan history or reservation throughput.
- No concurrency guard if two staff members click **Confirm Pickup** on the same reservation simultaneously. Fine for a portfolio project; not safe for a genuinely concurrent deployment.
- No automated test suite yet — the modules were verified manually through the UI.

## License

LGPL-3, matching Odoo Community.
