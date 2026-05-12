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
		attachments = attachments or []
		if len(attachments) > 10:
			frappe.throw(_("You can attach up to 10 files per ticket."))
		for file_url in attachments:
			file_meta = frappe.db.get_value(
				"File",
				{"file_url": file_url},
				["name", "owner", "attached_to_name"],
				as_dict=True,
			)
			if not file_meta:
				frappe.throw(_("File {0} not found.").format(file_url))
			if file_meta.owner != frappe.session.user:
				frappe.throw(_("You can only attach files you uploaded."))
			if file_meta.attached_to_name:
				frappe.throw(
					_("File {0} is already attached to another document.").format(file_url)
				)
			file_doc = frappe.get_doc("File", file_meta.name)
			file_doc.attached_to_doctype = doc.doctype
			file_doc.attached_to_name = doc.name
			file_doc.save()

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
	FAQ = frappe.qb.DocType("HR FAQ")
	q = (
		frappe.qb.from_(FAQ)
		.select(FAQ.name, FAQ.title, FAQ.category, FAQ.views)
		.where(FAQ.published == 1)
	)

	if query:
		q = q.where((FAQ.title.like(f"%{query}%")) | (FAQ.body.like(f"%{query}%")))
	if category:
		q = q.where(FAQ.category == category)

	return q.orderby(FAQ.views, order=frappe.qb.desc).orderby(FAQ.modified, order=frappe.qb.desc).limit(5).run(as_dict=True)


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
