# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_field
from frappe.utils import add_days, getdate

from erpnext.setup.doctype.employee.test_employee import make_employee

from hrms.hr.doctype.shift_type.test_shift_type import setup_shift_type
from hrms.tests.utils import HRMSTestSuite


def _ensure_custom_field():
	"""Ensure the Shift Schedule Assignment.shift_rotation custom field exists.

	In production this is added in hrms/setup.py; for tests we install it on demand
	so we don't depend on the install order.
	"""
	if not frappe.db.exists(
		"Custom Field", {"dt": "Shift Schedule Assignment", "fieldname": "shift_rotation"}
	):
		create_custom_field(
			"Shift Schedule Assignment",
			{
				"fieldname": "shift_rotation",
				"label": "Shift Rotation",
				"fieldtype": "Link",
				"options": "Shift Rotation",
				"read_only": 1,
				"hidden": 1,
				"insert_after": "shift_schedule",
			},
		)


class TestShiftRotation(HRMSTestSuite):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_ensure_custom_field()

	def setUp(self):
		self.emp_a = make_employee("rot.a@example.com", company="_Test Company")
		self.emp_b = make_employee("rot.b@example.com", company="_Test Company")
		self.emp_c = make_employee("rot.c@example.com", company="_Test Company")
		self.emp_d = make_employee("rot.d@example.com", company="_Test Company")

		self.shift_morning = setup_shift_type(
			shift_type="Test Rotation Morning", start_time="06:00:00", end_time="14:00:00"
		).name
		self.shift_evening = setup_shift_type(
			shift_type="Test Rotation Evening", start_time="14:00:00", end_time="22:00:00"
		).name
		self.shift_night = setup_shift_type(
			shift_type="Test Rotation Night", start_time="22:00:00", end_time="06:00:00"
		).name
		self.shift_off = setup_shift_type(
			shift_type="Test Rotation Day Off", start_time="09:00:00", end_time="17:00:00"
		).name

		# Clear any stale rotations from previous runs
		for name in frappe.get_all("Shift Rotation", pluck="name"):
			doc = frappe.get_doc("Shift Rotation", name)
			if doc.docstatus == 1:
				doc.cancel()
			frappe.delete_doc("Shift Rotation", name, force=True)

	def _build_rotation(
		self,
		rotation_name: str,
		start_date,
		groups: list[dict],
		patterns: list[dict] | None = None,
		cycle_length_weeks: int = 4,
	):
		patterns = patterns or [
			{
				"week_index": 1,
				"shift_type": self.shift_morning,
				"repeat_on_days": "Mon,Tue,Wed,Thu,Fri",
			},
			{
				"week_index": 2,
				"shift_type": self.shift_evening,
				"repeat_on_days": "Mon,Tue,Wed,Thu,Fri",
			},
			{
				"week_index": 3,
				"shift_type": self.shift_night,
				"repeat_on_days": "Mon,Tue,Wed,Thu,Fri",
			},
			{
				"week_index": 4,
				"shift_type": self.shift_off,
				"repeat_on_days": "Mon,Tue,Wed,Thu,Fri",
			},
		]

		doc = frappe.get_doc(
			{
				"doctype": "Shift Rotation",
				"rotation_name": rotation_name,
				"start_date": start_date,
				"cycle_length_weeks": cycle_length_weeks,
				"patterns": patterns,
				"groups": groups,
			}
		).insert()
		doc.submit()
		return doc

	def test_two_group_four_week_rotation_generates_assignments(self):
		"""2 groups * 4 weeks * 1 member each = 8 Shift Schedule Assignments per group."""
		start = getdate("2026-06-01")  # Monday
		rot = self._build_rotation(
			"Test 2x4 Rotation",
			start,
			[
				{
					"group_name": "Group A",
					"offset_weeks": 0,
					"members": [{"employee": self.emp_a}],
				},
				{
					"group_name": "Group B",
					"offset_weeks": 2,
					"members": [{"employee": self.emp_b}],
				},
			],
		)

		assignments = frappe.get_all(
			"Shift Schedule Assignment",
			filters={"shift_rotation": rot.name},
			fields=["name", "employee", "create_shifts_after", "shift_schedule"],
			order_by="employee, create_shifts_after",
		)

		# 4 patterns * 2 members = 8 assignments
		self.assertEqual(len(assignments), 8)

		emp_a_rows = [a for a in assignments if a.employee == self.emp_a]
		emp_b_rows = [a for a in assignments if a.employee == self.emp_b]
		self.assertEqual(len(emp_a_rows), 4)
		self.assertEqual(len(emp_b_rows), 4)

	def test_offset_weeks_shifts_cycle(self):
		"""offset_weeks=2 puts Group B's first assignment 14 days later than Group A."""
		start = getdate("2026-06-01")
		rot = self._build_rotation(
			"Test Offset Rotation",
			start,
			[
				{
					"group_name": "A",
					"offset_weeks": 0,
					"members": [{"employee": self.emp_a}],
				},
				{
					"group_name": "B",
					"offset_weeks": 2,
					"members": [{"employee": self.emp_b}],
				},
			],
			patterns=[
				{
					"week_index": 1,
					"shift_type": self.shift_morning,
					"repeat_on_days": "Mon,Tue,Wed,Thu,Fri",
				}
			],
			cycle_length_weeks=4,
		)

		a_first = frappe.get_all(
			"Shift Schedule Assignment",
			filters={"shift_rotation": rot.name, "employee": self.emp_a},
			fields=["create_shifts_after"],
			order_by="create_shifts_after asc",
		)[0]
		b_first = frappe.get_all(
			"Shift Schedule Assignment",
			filters={"shift_rotation": rot.name, "employee": self.emp_b},
			fields=["create_shifts_after"],
			order_by="create_shifts_after asc",
		)[0]

		delta = (getdate(b_first.create_shifts_after) - getdate(a_first.create_shifts_after)).days
		self.assertEqual(delta, 14)

	def test_swap_employees_rewrites_future_only(self):
		"""swap_employees() must not touch assignments before the effective date."""
		from hrms.api.rotation import swap_employees

		start = getdate("2026-06-01")
		rot = self._build_rotation(
			"Test Swap Rotation",
			start,
			[
				{
					"group_name": "A",
					"offset_weeks": 0,
					"members": [{"employee": self.emp_a}],
				},
				{
					"group_name": "B",
					"offset_weeks": 0,
					"members": [{"employee": self.emp_b}],
				},
			],
		)

		# Only the week-3 and week-4 patterns (start_date + 14d, +21d) are >= effective
		effective = add_days(start, 13)  # halfway through week 2

		before_a = frappe.get_all(
			"Shift Schedule Assignment",
			filters={"shift_rotation": rot.name, "employee": self.emp_a},
			pluck="name",
			order_by="create_shifts_after asc",
		)
		self.assertEqual(len(before_a), 4)

		result = swap_employees(rot.name, self.emp_a, self.emp_b, str(effective))
		# 2 weeks (3,4) per side * 2 sides = 4 rewrites
		self.assertEqual(result["rewritten"], 4)

		# Verify the early ones still belong to original employees
		early_a = frappe.get_all(
			"Shift Schedule Assignment",
			filters={
				"shift_rotation": rot.name,
				"employee": self.emp_a,
				"create_shifts_after": ["<", effective],
			},
			pluck="name",
		)
		self.assertEqual(len(early_a), 2)  # weeks 1 & 2 unchanged

		# Late assignments now belong to B (originally A) and vice versa
		late_a_count = frappe.db.count(
			"Shift Schedule Assignment",
			{
				"shift_rotation": rot.name,
				"employee": self.emp_a,
				"create_shifts_after": [">=", effective],
			},
		)
		late_b_count = frappe.db.count(
			"Shift Schedule Assignment",
			{
				"shift_rotation": rot.name,
				"employee": self.emp_b,
				"create_shifts_after": [">=", effective],
			},
		)
		# After swap: A's 2 late slots went to B; B's 2 late slots went to A
		self.assertEqual(late_a_count, 2)
		self.assertEqual(late_b_count, 2)

	def test_validate_week_index_must_not_exceed_cycle(self):
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				{
					"doctype": "Shift Rotation",
					"rotation_name": "Invalid Week Index",
					"start_date": getdate("2026-06-01"),
					"cycle_length_weeks": 2,
					"patterns": [
						{
							"week_index": 5,
							"shift_type": self.shift_morning,
							"repeat_on_days": "Mon,Tue",
						}
					],
					"groups": [
						{
							"group_name": "A",
							"offset_weeks": 0,
							"members": [{"employee": self.emp_a}],
						}
					],
				}
			).insert()

	def test_validate_duplicate_pattern_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				{
					"doctype": "Shift Rotation",
					"rotation_name": "Duplicate Pattern",
					"start_date": getdate("2026-06-01"),
					"cycle_length_weeks": 2,
					"patterns": [
						{
							"week_index": 1,
							"shift_type": self.shift_morning,
							"repeat_on_days": "Mon",
						},
						{
							"week_index": 1,
							"shift_type": self.shift_morning,
							"repeat_on_days": "Tue",
						},
					],
					"groups": [
						{
							"group_name": "A",
							"offset_weeks": 0,
							"members": [{"employee": self.emp_a}],
						}
					],
				}
			).insert()
