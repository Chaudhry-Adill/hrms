# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, getdate, nowdate

from hrms.hr.doctype.shift_schedule.shift_schedule import get_or_insert_shift_schedule


WEEKDAY_CODE_TO_NAME = {
	"Mon": "Monday",
	"Tue": "Tuesday",
	"Wed": "Wednesday",
	"Thu": "Thursday",
	"Fri": "Friday",
	"Sat": "Saturday",
	"Sun": "Sunday",
}


CYCLE_TO_FREQUENCY = {
	1: "Every Week",
	2: "Every 2 Weeks",
	3: "Every 3 Weeks",
	4: "Every 4 Weeks",
}


class ShiftRotation(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from hrms.hr.doctype.shift_rotation_group.shift_rotation_group import ShiftRotationGroup
		from hrms.hr.doctype.shift_rotation_pattern.shift_rotation_pattern import ShiftRotationPattern

		amended_from: DF.Link | None
		cycle_length_weeks: DF.Int
		groups: DF.Table[ShiftRotationGroup]
		holiday_list: DF.Link | None
		patterns: DF.Table[ShiftRotationPattern]
		rotation_name: DF.Data
		start_date: DF.Date
		status: DF.Literal["Draft", "Active", "Inactive"]
	# end: auto-generated types

	def validate(self):
		self.validate_cycle_length()
		self.validate_patterns()
		self.validate_groups()

	def validate_cycle_length(self):
		if not self.cycle_length_weeks or self.cycle_length_weeks <= 0:
			frappe.throw(_("Cycle Length (Weeks) must be greater than 0."))
		if self.cycle_length_weeks > 4:
			frappe.throw(
				_("Cycle Length (Weeks) larger than 4 is not supported (Shift Schedule frequency tops out at Every 4 Weeks).")
			)

	def validate_patterns(self):
		if not self.patterns:
			frappe.throw(_("At least one Pattern row is required."))

		seen = set()
		for row in self.patterns:
			if not row.week_index or row.week_index < 1:
				frappe.throw(_("Pattern row {0}: week_index must be >= 1.").format(row.idx))
			if row.week_index > self.cycle_length_weeks:
				frappe.throw(
					_("Pattern row {0}: week_index {1} exceeds cycle_length_weeks {2}.").format(
						row.idx, row.week_index, self.cycle_length_weeks
					)
				)
			key = (row.week_index, row.shift_type)
			if key in seen:
				frappe.throw(
					_("Duplicate pattern entry for week {0} and shift type {1}.").format(
						row.week_index, row.shift_type or _("(none)")
					)
				)
			seen.add(key)

	def validate_groups(self):
		if not self.groups:
			frappe.throw(_("At least one Group row is required."))
		for grp in self.groups:
			if grp.offset_weeks is None:
				grp.offset_weeks = 0
			if grp.offset_weeks < 0:
				frappe.throw(_("Group {0}: offset_weeks must be >= 0.").format(grp.group_name or grp.idx))

	# -------- Submission lifecycle --------

	def on_submit(self):
		self.generate_shift_schedule_assignments()
		self.db_set("status", "Active")

	def on_cancel(self):
		self.cancel_generated_assignments()
		self.db_set("status", "Inactive")

	def generate_shift_schedule_assignments(self) -> list[str]:
		"""For each (group, member, pattern_row) build one Shift Schedule Assignment.

		The Shift Schedule used is a frequency=Every N Weeks schedule (N = cycle_length_weeks).
		Each pattern row contributes one assignment per member, with start_date offset by
		(group.offset_weeks + (week_index - 1)) weeks from the rotation's start_date.
		The cron job `process_auto_shift_creation` then walks day-by-day producing Shift
		Assignment rows.
		"""
		frequency = CYCLE_TO_FREQUENCY.get(self.cycle_length_weeks)
		if not frequency:
			frappe.throw(_("Unsupported cycle length: {0}.").format(self.cycle_length_weeks))

		created: list[str] = []

		for grp in self.groups:
			for member in grp.members or []:
				if not member.employee:
					continue
				company = frappe.db.get_value("Employee", member.employee, "company")
				if not company:
					frappe.throw(_("Employee {0} has no company set.").format(member.employee))

				for pattern in self.patterns:
					if not pattern.shift_type:
						continue

					weekdays = self._parse_weekdays(pattern.repeat_on_days)
					if not weekdays:
						continue

					schedule_name = get_or_insert_shift_schedule(
						pattern.shift_type, frequency, weekdays
					)

					member_offset_weeks = (grp.offset_weeks or 0) + (pattern.week_index - 1)
					member_start = add_days(getdate(self.start_date), member_offset_weeks * 7)

					assignment = frappe.get_doc(
						{
							"doctype": "Shift Schedule Assignment",
							"employee": member.employee,
							"company": company,
							"shift_schedule": schedule_name,
							"shift_status": "Active",
							"enabled": 1,
							"create_shifts_after": add_days(member_start, -1),
							"shift_rotation": self.name,
						}
					)
					assignment.insert(ignore_permissions=True)
					created.append(assignment.name)

		return created

	def cancel_generated_assignments(self):
		"""Disable + delete Shift Schedule Assignments linked to this rotation."""
		linked = frappe.get_all(
			"Shift Schedule Assignment",
			filters={"shift_rotation": self.name},
			pluck="name",
		)
		for name in linked:
			try:
				doc = frappe.get_doc("Shift Schedule Assignment", name)
				doc.db_set("enabled", 0)
				doc.delete(ignore_permissions=True)
			except Exception:
				frappe.log_error(
					message=frappe.get_traceback(),
					title=f"Failed to cancel Shift Schedule Assignment {name}",
				)

	# -------- Helpers --------

	@staticmethod
	def _parse_weekdays(repeat_on_days: str | None) -> list[str]:
		if not repeat_on_days:
			return []
		out: list[str] = []
		for token in str(repeat_on_days).split(","):
			code = token.strip()[:3].title()
			if code in WEEKDAY_CODE_TO_NAME:
				out.append(WEEKDAY_CODE_TO_NAME[code])
		# de-dup, preserve order
		seen = set()
		ordered: list[str] = []
		for day in out:
			if day not in seen:
				seen.add(day)
				ordered.append(day)
		return ordered


def advance_rotations() -> None:
	"""Daily scheduler hook.

	Idempotent: calls process_auto_shift_creation to walk every active Shift Schedule
	Assignment forward up to (cycle_length_weeks * 7 + 7) days. Since
	`process_auto_shift_creation` filters by `create_shifts_after <= today`, we only
	need to invoke it; the day-by-day walker advances the cursor.
	"""
	from hrms.hr.doctype.shift_schedule_assignment.shift_schedule_assignment import (
		process_auto_shift_creation,
	)

	rotations = frappe.get_all(
		"Shift Rotation",
		filters={"docstatus": 1, "status": "Active"},
		fields=["name", "cycle_length_weeks"],
	)
	if not rotations:
		return

	# Buffer: ensure assignments produce shifts at least N days ahead of today.
	# process_auto_shift_creation already advances 90d by default per call, which is
	# more than the 4-week max cycle + 7d buffer; just invoke it once.
	process_auto_shift_creation()

	frappe.logger().info(
		f"advance_rotations: processed {len(rotations)} active rotations on {nowdate()}"
	)
