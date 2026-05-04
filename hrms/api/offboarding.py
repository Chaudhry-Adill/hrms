# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt


@frappe.whitelist()
def get_offboarding_progress(employee_separation: str) -> dict:
	"""Return aggregated task progress + blockers for the employee self-service view."""
	if not employee_separation:
		frappe.throw(_("Employee Separation is required"))

	sep = frappe.get_doc("Employee Separation", employee_separation)
	frappe.has_permission(doctype="Employee Separation", doc=sep, ptype="read", throw=True)

	tasks: list[dict] = []
	completed = 0
	total = 0
	blockers: list[dict] = []

	for activity in sep.activities or []:
		row = {
			"activity_name": activity.activity_name,
			"task": activity.task,
			"status": None,
			"clearance_department": activity.get("clearance_department"),
			"is_exit_interview": bool(activity.get("is_exit_interview")),
			"requires_asset_return": bool(activity.get("requires_asset_return")),
			"progress": 0,
		}
		if activity.task:
			task_doc = frappe.db.get_value(
				"Task",
				activity.task,
				["status", "progress", "exp_end_date"],
				as_dict=True,
			)
			if task_doc:
				row["status"] = task_doc.status
				row["progress"] = flt(task_doc.progress)
				row["exp_end_date"] = task_doc.exp_end_date
				total += 1
				if task_doc.status == "Completed":
					completed += 1
				elif task_doc.status in ("Open", "Pending Review"):
					blockers.append(
						{"activity": activity.activity_name, "reason": task_doc.status}
					)
		tasks.append(row)

	pct = (completed / total * 100) if total else 0.0

	return {
		"tasks": tasks,
		"pct": round(pct, 2),
		"completed": completed,
		"total": total,
		"blockers": blockers,
		"boarding_status": sep.boarding_status,
		"employee": sep.employee,
		"employee_name": sep.employee_name,
		"resignation_letter_date": sep.resignation_letter_date,
	}


@frappe.whitelist()
def list_my_separations() -> list[dict]:
	"""Return all Employee Separation docs for the current user's employee record."""
	user = frappe.session.user
	employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
	if not employee:
		return []

	return frappe.get_all(
		"Employee Separation",
		filters={"employee": employee, "docstatus": ["<", 2]},
		fields=[
			"name",
			"employee",
			"employee_name",
			"resignation_letter_date",
			"boarding_status",
			"company",
		],
		order_by="resignation_letter_date desc",
	)
