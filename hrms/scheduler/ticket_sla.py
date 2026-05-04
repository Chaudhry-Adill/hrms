# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import now_datetime

PRIORITY_LADDER = ("Low", "Medium", "High", "Critical")
TERMINAL_STATUSES = ("Resolved", "Closed")


def _bump_priority(current: str | None) -> str:
	if not current or current not in PRIORITY_LADDER:
		return "Medium"
	idx = PRIORITY_LADDER.index(current)
	return PRIORITY_LADDER[min(idx + 1, len(PRIORITY_LADDER) - 1)]


def escalate_breached_slas() -> int:
	"""Escalate any tickets whose SLA has elapsed but aren't yet resolved/closed.

	Bumps priority one rung (Critical stays Critical) and sends a PWA notification
	to the department head if `assigned_team` is set. Designed to run hourly.
	Returns the count of tickets escalated for observability.
	"""
	tickets = frappe.get_all(
		"HR Ticket",
		filters={
			"sla_due_at": ["<", now_datetime()],
			"status": ["not in", TERMINAL_STATUSES],
		},
		fields=["name", "priority", "assigned_team", "subject", "raised_by"],
	)

	escalated = 0
	for ticket in tickets:
		new_priority = _bump_priority(ticket.priority)
		if new_priority != ticket.priority:
			frappe.db.set_value(
				"HR Ticket",
				ticket.name,
				"priority",
				new_priority,
				update_modified=False,
			)

		_notify_department_head(ticket, new_priority)
		escalated += 1

	if escalated:
		frappe.db.commit()  # noqa: scheduler context, not test

	return escalated


def _notify_department_head(ticket: dict, new_priority: str) -> None:
	"""Push a Notification Log entry to the department head if available."""
	if not ticket.get("assigned_team"):
		return

	leader = frappe.db.get_value("Department", ticket.assigned_team, "leader")
	if not leader:
		return

	leader_user = frappe.db.get_value("Employee", leader, "user_id")
	if not leader_user:
		return

	try:
		frappe.get_doc(
			{
				"doctype": "Notification Log",
				"subject": f"SLA breached: {ticket.subject}",
				"email_content": (
					f"Ticket {ticket.name} has breached its SLA and has been "
					f"escalated to priority {new_priority}."
				),
				"for_user": leader_user,
				"type": "Alert",
				"document_type": "HR Ticket",
				"document_name": ticket.name,
				"from_user": frappe.session.user or "Administrator",
			}
		).insert(ignore_permissions=True)
	except Exception:
		frappe.log_error(
			title="HR Ticket SLA escalation notification failed",
			message=frappe.get_traceback(),
		)
