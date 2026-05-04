---
name: frappe-doctype-dev
description: Use when the user asks about creating, modifying, or understanding Frappe DocTypes, fields, schemas, controllers, or hooks.
---

Frappe DocType development guidelines:
- DocType directories: `hrms/hr/doctype/<name>/` and `hrms/payroll/doctype/<name>/`
- Files: `<name>.json` (schema), `<name>.py` (controller), `test_<name>.py`, `<name>.js` (client script), `<name>_list.js`, `<name>_tree.js`, `<name>_calendar.js`
- Controllers extend `Document`. Override `validate`, `before_submit`, `on_submit`, `on_cancel`, `on_trash`, `after_insert`, etc.
- Use `frappe.get_doc(doctype, name)` to fetch, `doc.insert()`, `doc.save()`, `doc.submit()`, `doc.cancel()`
- Register event hooks in `hrms/hooks.py` under `doc_events`
- Field types: Data, Select, Link, Dynamic Link, Date, Datetime, Int, Float, Currency, Check, Text, Text Editor, HTML, Attach, Table, etc.
- Use `frappe.db.exists(doctype, filters)` before creating records in setup/fixtures
- For client-side: use `cur_frm`, `frappe.ui.form.on`, `frappe.call`
