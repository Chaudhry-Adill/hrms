# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import format_datetime

VALID_STAGES = ("Open", "Replied", "Shortlisted", "Rejected", "Hold", "Accepted")


@frappe.whitelist()
def bulk_update_status(applicants: list | str, status: str, note: str | None = None) -> dict:
	"""Move many Job Applicants through the Kanban in one round-trip.

	Used by the recruitment Kanban for drag-of-many. Each successful transition
	is logged via the Job Applicant `on_update` hook (no extra log writes here).
	"""
	if isinstance(applicants, str):
		applicants = frappe.parse_json(applicants)

	if status not in VALID_STAGES:
		frappe.throw(_("Invalid status: {0}").format(status))

	if not applicants:
		return {"updated": [], "skipped": []}

	updated, skipped = [], []
	for name in applicants:
		try:
			doc = frappe.get_doc("Job Applicant", name)
			frappe.has_permission(doctype="Job Applicant", doc=doc, ptype="write", throw=True)
			if doc.status == status:
				skipped.append({"name": name, "reason": "already_in_stage"})
				continue
			doc.status = status
			doc.save()
			# Override the auto-generated log row's note if a note was supplied.
			if note:
				last_log = (doc.stage_log or [])[-1] if doc.stage_log else None
				if last_log and last_log.stage == status:
					last_log.db_set("note", note, update_modified=False)
			updated.append(name)
		except frappe.PermissionError:
			skipped.append({"name": name, "reason": "no_permission"})
		except Exception as e:
			skipped.append({"name": name, "reason": str(e)})

	return {"updated": updated, "skipped": skipped}


@frappe.rate_limiter.rate_limit(key="ip", limit=20, seconds=60)
@frappe.whitelist(allow_guest=True)
def get_candidate_timeline(token: str) -> dict:
	"""Guest-readable, sanitized timeline for an applicant via opaque token.

	Returns only stage transitions and timestamps - never email, phone, or rating.
	"""
	if not token:
		frappe.throw(_("Tracking token is required"))

	applicant = frappe.db.get_value(
		"Job Applicant",
		{"tracking_token": token},
		["name", "applicant_name", "status", "job_title", "creation"],
		as_dict=True,
	)
	if not applicant:
		frappe.throw(_("Application not found"), frappe.DoesNotExistError)

	logs = frappe.get_all(
		"Job Applicant Stage Log",
		filters={"parent": applicant.name, "parenttype": "Job Applicant"},
		fields=["stage", "changed_on", "note"],
		order_by="changed_on asc",
	)

	return {
		"applicant_name": applicant.applicant_name,
		"current_status": applicant.status,
		"job_title": applicant.job_title,
		"applied_on": format_datetime(applicant.creation, "medium"),
		"timeline": [
			{
				"stage": log.stage,
				"changed_on": format_datetime(log.changed_on, "medium"),
				"note": log.note or "",
			}
			for log in logs
		],
	}
