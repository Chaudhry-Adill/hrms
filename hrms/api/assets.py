# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import add_days, getdate, now_datetime, today


def _get_current_employee() -> str:
	"""Return employee record for the logged-in user; throw if not linked."""
	employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
	if not employee:
		frappe.throw(_("No Employee record linked to your user."))
	return employee


@frappe.whitelist()
def request_asset(
	category: str,
	purpose: str | None = None,
	urgency: str = "Normal",
	expected_return_date: str | None = None,
) -> dict:
	"""Create a draft Employee Asset Request for the current user."""
	if not category:
		frappe.throw(_("Asset Category is required."))

	employee = _get_current_employee()

	doc = frappe.get_doc(
		{
			"doctype": "Employee Asset Request",
			"employee": employee,
			"request_date": today(),
			"request_type": "New",
			"category": category,
			"urgency": urgency,
			"purpose": purpose,
			"expected_return_date": expected_return_date,
			"status": "Open",
		}
	)
	doc.insert()
	return {"name": doc.name, "status": doc.status}


@frappe.whitelist()
def acknowledge_allocation(allocation: str) -> dict:
	"""Mark allocation as acknowledged by the assigned employee."""
	if not allocation:
		frappe.throw(_("Allocation is required."))

	doc = frappe.get_doc("Employee Asset Allocation", allocation)

	current_emp = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
	if current_emp != doc.employee:
		frappe.has_permission("Employee Asset Allocation", doc=doc, ptype="write", throw=True)

	doc.acknowledgement = 1
	doc.acknowledgement_at = now_datetime()
	doc.save()

	return {
		"name": doc.name,
		"acknowledgement": 1,
		"acknowledgement_at": doc.acknowledgement_at,
	}


@frappe.whitelist()
def request_return(allocation: str, reason: str | None = None) -> dict:
	"""Create a return-type Employee Asset Request for an existing allocation."""
	if not allocation:
		frappe.throw(_("Allocation is required."))

	alloc = frappe.get_doc("Employee Asset Allocation", allocation)

	if alloc.docstatus != 1:
		frappe.throw(_("Allocation must be submitted to request a return."))

	current_emp = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
	if current_emp != alloc.employee and not (
		"HR Manager" in frappe.get_roles() or "HR User" in frappe.get_roles()
	):
		frappe.throw(_("You can only request returns for your own allocations."))

	doc = frappe.get_doc(
		{
			"doctype": "Employee Asset Request",
			"employee": alloc.employee,
			"request_date": today(),
			"request_type": "Return",
			"allocated_asset": alloc.asset,
			"purpose": reason,
			"status": "Open",
		}
	)
	doc.insert()
	return {"name": doc.name, "status": doc.status}


@frappe.whitelist()
def list_my_assets() -> list[dict]:
	"""Return active Asset Allocations for the current user."""
	employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
	if not employee:
		return []

	return frappe.get_all(
		"Employee Asset Allocation",
		filters={
			"employee": employee,
			"docstatus": 1,
			"actual_return_date": ["is", "not set"],
		},
		fields=[
			"name",
			"employee",
			"employee_name",
			"asset",
			"asset_name",
			"from_date",
			"expected_return_date",
			"acknowledgement",
			"acknowledgement_at",
			"condition_at_issue",
			"request",
		],
		order_by="from_date desc",
	)


@frappe.whitelist()
def list_my_requests(status: str | None = None) -> list[dict]:
	"""Return Employee Asset Requests for the current user."""
	employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
	if not employee:
		return []

	filters: dict = {"employee": employee}
	if status:
		filters["status"] = status

	return frappe.get_all(
		"Employee Asset Request",
		filters=filters,
		fields=[
			"name",
			"employee",
			"employee_name",
			"request_date",
			"request_type",
			"category",
			"urgency",
			"status",
			"allocated_asset",
			"allocation_date",
			"expected_return_date",
			"actual_return_date",
		],
		order_by="request_date desc",
	)


def generate_return_requests_for_employee(
	employee: str,
	due_date: str | None = None,
	separation: str | None = None,
) -> list[str]:
	"""Create return-type Employee Asset Requests for every active allocation.

	Called by the offboarding controller when an Employee Separation activity has
	`requires_asset_return` checked.
	"""
	if not employee:
		return []

	# Default expected return = activity due date, or today + 7
	expected_return = getdate(due_date) if due_date else add_days(getdate(today()), 7)

	allocations = frappe.get_all(
		"Employee Asset Allocation",
		filters={
			"employee": employee,
			"docstatus": 1,
			"actual_return_date": ["is", "not set"],
		},
		fields=["name", "asset"],
	)

	created: list[str] = []
	for alloc in allocations:
		# Skip if there's already an open Return request for this asset+employee
		existing = frappe.db.exists(
			"Employee Asset Request",
			{
				"employee": employee,
				"request_type": "Return",
				"allocated_asset": alloc.asset,
				"status": ["in", ["Open", "Approved"]],
				"docstatus": ["<", 2],
			},
		)
		if existing:
			continue

		doc = frappe.get_doc(
			{
				"doctype": "Employee Asset Request",
				"employee": employee,
				"request_date": today(),
				"request_type": "Return",
				"allocated_asset": alloc.asset,
				"expected_return_date": expected_return,
				"status": "Open",
				"purpose": (
					_("Auto-generated return request from Employee Separation {0}").format(separation)
					if separation
					else _("Auto-generated return request from offboarding workflow.")
				),
			}
		)
		doc.insert(ignore_permissions=True)
		created.append(doc.name)

	return created


@frappe.whitelist()
def list_asset_categories() -> list[dict]:
	"""Return ERPNext Asset Categories (for the request form select)."""
	try:
		return frappe.get_all(
			"Asset Category", fields=["name", "asset_category_name"], order_by="asset_category_name asc"
		)
	except Exception:
		return []
