# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Helpdesk seed data + ESS/role profile updates.

Call _create_helpdesk_seed_data() from `hrms/setup.py:after_install` (or similar
post-install hook) so a fresh site has a usable helpdesk out of the box.
"""

import frappe

DEFAULT_SLA_NAME = "Default HR Helpdesk SLA"
DEFAULT_CATEGORIES = ("IT", "Payroll", "Leaves", "Benefits", "Other")


def _create_default_sla():
	if frappe.db.exists("HR Ticket SLA", DEFAULT_SLA_NAME):
		return DEFAULT_SLA_NAME
	frappe.get_doc(
		{
			"doctype": "HR Ticket SLA",
			"sla_name": DEFAULT_SLA_NAME,
			"first_response_hours": 4,
			"resolution_hours": 48,
		}
	).insert(ignore_permissions=True)
	return DEFAULT_SLA_NAME


def _create_default_categories(sla_name: str):
	for name in DEFAULT_CATEGORIES:
		if frappe.db.exists("HR Ticket Category", name):
			continue
		frappe.get_doc(
			{
				"doctype": "HR Ticket Category",
				"category_name": name,
				"sla": sla_name,
			}
		).insert(ignore_permissions=True)


def _grant_ess_permissions():
	"""Allow Employee Self Service users to read HR Ticket / FAQ / Category."""
	user_type = "Employee Self Service"
	if not frappe.db.exists("User Type", user_type):
		return

	doctypes = ("HR Ticket", "HR Ticket Category", "HR FAQ")
	doc = frappe.get_doc("User Type", user_type)
	existing = {row.document_type for row in (doc.get("user_doctypes") or [])}
	dirty = False
	for dt in doctypes:
		if dt in existing:
			continue
		doc.append(
			"user_doctypes",
			{
				"document_type": dt,
				"read": 1,
				"write": 1 if dt == "HR Ticket" else 0,
				"create": 1 if dt == "HR Ticket" else 0,
			},
		)
		dirty = True
	if dirty:
		doc.save(ignore_permissions=True)


def _create_helpdesk_seed_data():
	"""Idempotent seed used by hrms/setup.py after_install."""
	sla_name = _create_default_sla()
	_create_default_categories(sla_name)
	_grant_ess_permissions()
	frappe.db.commit()  # nosemgrep -- after_install context, not test
