# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def _get_session_employee() -> str | None:
	"""Resolve the Employee name linked to the current session user."""
	user = frappe.session.user
	if user in ("Administrator", "Guest"):
		return None
	return frappe.db.get_value("Employee", {"user_id": user}, "name")


@frappe.whitelist()
def create_ticket(
	subject: str,
	category: str | None = None,
	description: str = "",
	priority: str = "Medium",
	attachments: list | str | None = None,
) -> dict:
	"""Create a new HR Ticket scoped to the current user's employee record."""
	if not subject:
		frappe.throw(_("Subject is required"))

	employee = _get_session_employee()
	if not employee:
		frappe.throw(_("Only employees can create tickets"))

	doc = frappe.get_doc(
		{
			"doctype": "HR Ticket",
			"subject": subject,
			"raised_by": employee,
			"category": category,
			"description": description,
			"priority": priority or "Medium",
			"status": "Open",
		}
	)
	doc.insert(ignore_permissions=False)

	# Attach files if any were uploaded as part of the request
	if attachments:
		if isinstance(attachments, str):
			attachments = frappe.parse_json(attachments)
		for file_url in attachments or []:
			frappe.get_doc(
				{
					"doctype": "File",
					"file_url": file_url,
					"attached_to_doctype": doc.doctype,
					"attached_to_name": doc.name,
				}
			).insert(ignore_permissions=True)

	return {
		"name": doc.name,
		"subject": doc.subject,
		"status": doc.status,
		"priority": doc.priority,
		"sla_due_at": doc.sla_due_at,
	}


@frappe.whitelist()
def list_my_tickets(status_filter: str | None = None) -> list[dict]:
	"""Return tickets raised by the current user."""
	employee = _get_session_employee()
	if not employee:
		return []

	filters: dict = {"raised_by": employee}
	if status_filter:
		filters["status"] = status_filter

	return frappe.get_all(
		"HR Ticket",
		filters=filters,
		fields=[
			"name",
			"subject",
			"category",
			"priority",
			"status",
			"assigned_to",
			"assigned_team",
			"sla_due_at",
			"first_response_at",
			"resolved_at",
			"creation",
			"modified",
		],
		order_by="modified desc",
		limit=50,
	)


@frappe.whitelist()
def search_faq(query: str = "", category: str | None = None) -> list[dict]:
	"""Top 5 published FAQs matching the query, weighted by views."""
	if not query and not category:
		# Return top viewed FAQs as default
		filters = {"published": 1}
		if category:
			filters["category"] = category
		return frappe.get_all(
			"HR FAQ",
			filters=filters,
			fields=["name", "title", "category", "views"],
			order_by="views desc",
			limit=5,
		)

	conditions = ["published = 1"]
	values: dict = {}
	if query:
		conditions.append("(title LIKE %(q)s OR body LIKE %(q)s)")
		values["q"] = f"%{query}%"
	if category:
		conditions.append("category = %(category)s")
		values["category"] = category

	where = " AND ".join(conditions)
	rows = frappe.db.sql(
		f"""
		SELECT name, title, category, views
		FROM `tabHR FAQ`
		WHERE {where}
		ORDER BY views DESC, modified DESC
		LIMIT 5
		""",
		values,
		as_dict=True,
	)
	return rows


@frappe.whitelist()
def add_comment(ticket: str, body: str, is_internal: int | bool = 0) -> dict:
	"""Append a comment to a ticket. Permission-checked via has_permission."""
	if not ticket or not body:
		frappe.throw(_("Ticket and body are required"))

	doc = frappe.get_doc("HR Ticket", ticket)
	frappe.has_permission(doctype="HR Ticket", doc=doc, ptype="write", throw=True)

	doc.append(
		"comments",
		{
			"body": body,
			"is_internal": int(bool(is_internal)),
			"author": frappe.session.user,
		},
	)
	doc.save()
	return {
		"name": doc.name,
		"comment_count": len(doc.comments),
		"first_response_at": doc.first_response_at,
	}
