# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import add_days, cint, getdate

from hrms.hr.doctype.shift_rotation.shift_rotation import WEEKDAY_CODE_TO_NAME


@frappe.whitelist()
def preview_rotation(rotation: str, weeks_ahead: int = 8) -> list[dict]:
	"""Return a list of {date, employee, employee_name, shift_type, group_name}
	for the editor UI, computed by walking the rotation's patterns/groups directly
	(does NOT require the cron to have run).
	"""
	if not rotation:
		frappe.throw(_("rotation is required"))

	weeks_ahead = max(1, cint(weeks_ahead))

	rot = frappe.get_doc("Shift Rotation", rotation)
	frappe.has_permission(doctype="Shift Rotation", doc=rot, ptype="read", throw=True)

	cycle = rot.cycle_length_weeks or 1
	if cycle <= 0:
		return []

	# Build (week_index_in_cycle, weekday_name) -> shift_type lookup
	pattern_lookup: dict[tuple[int, str], str] = {}
	for p in rot.patterns:
		if not p.shift_type or not p.repeat_on_days:
			continue
		for token in str(p.repeat_on_days).split(","):
			code = token.strip()[:3].title()
			day = WEEKDAY_CODE_TO_NAME.get(code)
			if day:
				pattern_lookup[(p.week_index, day)] = p.shift_type

	rows: list[dict] = []
	start = getdate(rot.start_date)
	total_days = weeks_ahead * 7

	weekday_names = list(WEEKDAY_CODE_TO_NAME.values())

	for grp in rot.groups:
		offset_weeks = grp.offset_weeks or 0
		for member in grp.members or []:
			emp = member.employee
			emp_name = member.employee_name or frappe.db.get_value(
				"Employee", emp, "employee_name"
			)
			for d in range(total_days):
				date = add_days(start, d)
				date_obj = getdate(date)
				# Days since start, accounting for the group offset
				offset_days = d - (offset_weeks * 7)
				if offset_days < 0:
					continue
				week_in_cycle = (offset_days // 7) % cycle + 1
				weekday = weekday_names[date_obj.weekday()]
				shift_type = pattern_lookup.get((week_in_cycle, weekday))
				if not shift_type:
					continue
				rows.append(
					{
						"date": str(date),
						"employee": emp,
						"employee_name": emp_name,
						"shift_type": shift_type,
						"group_name": grp.group_name,
						"week_in_cycle": week_in_cycle,
					}
				)

	return rows


@frappe.whitelist()
def swap_employees(
	rotation: str,
	employee_a: str,
	employee_b: str,
	effective_date: str,
) -> dict:
	"""Rewrite future Shift Schedule Assignments only.

	For every Shift Schedule Assignment linked to this rotation whose
	`create_shifts_after` is on/after `effective_date`:
	  - if its employee is A, switch to B
	  - if its employee is B, switch to A

	Returns a dict with counts of rewritten assignments.
	"""
	if not (rotation and employee_a and employee_b and effective_date):
		frappe.throw(_("rotation, employee_a, employee_b, effective_date are required"))

	rot = frappe.get_doc("Shift Rotation", rotation)
	frappe.has_permission(doctype="Shift Rotation", doc=rot, ptype="write", throw=True)

	eff = getdate(effective_date)
	rewritten = 0

	assignments = frappe.get_all(
		"Shift Schedule Assignment",
		filters={
			"shift_rotation": rotation,
			"employee": ["in", [employee_a, employee_b]],
		},
		fields=["name", "employee", "create_shifts_after"],
	)

	for a in assignments:
		# Only rewrite if assignment's effective window is on/after effective_date.
		if a.create_shifts_after and getdate(a.create_shifts_after) < eff:
			continue
		new_employee = employee_b if a.employee == employee_a else employee_a
		new_company = frappe.db.get_value("Employee", new_employee, "company")
		if not new_company:
			continue
		doc = frappe.get_doc("Shift Schedule Assignment", a.name)
		doc.employee = new_employee
		doc.company = new_company
		doc.save(ignore_permissions=True)
		rewritten += 1

	# Note: the Shift Rotation parent is submittable; group membership on the parent
	# is the historical record of who started where. The Shift Schedule Assignment
	# rows are the live source of truth for "who works which shift from when".
	# We deliberately do NOT mutate the parent doc here.

	return {"rewritten": rewritten, "rotation": rotation, "effective_date": str(eff)}
