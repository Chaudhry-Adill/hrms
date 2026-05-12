# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import frappe
from frappe.utils import getdate

from hrms.tests.utils import HRMSTestSuite


class TestEmployeeSeparation(HRMSTestSuite):
	def test_employee_separation(self):
		separation = create_employee_separation()

		self.assertEqual(separation.docstatus, 1)
		self.assertEqual(separation.boarding_status, "Pending")

		project = frappe.get_doc("Project", separation.project)
		project.percent_complete_method = "Manual"
		project.status = "Completed"
		project.save()

		separation.reload()
		self.assertEqual(separation.boarding_status, "Completed")

		separation.cancel()
		self.assertEqual(separation.project, "")

	def test_clearance_department_routes_dept_head(self):
		"""Activity with clearance_department should fan task assignment to Department Head users."""
		dept_head_user = "test_dept_head@example.com"
		if not frappe.db.exists("User", dept_head_user):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": dept_head_user,
					"first_name": "Dept",
					"last_name": "Head",
					"send_welcome_email": 0,
					"roles": [{"role": "Department Head"}, {"role": "HR User"}],
				}
			).insert(ignore_permissions=True)

		employee = frappe.db.get_value("Employee", {"status": "Active", "company": "_Test Company"})
		dept = frappe.db.get_value("Employee", employee, "department") or frappe.db.get_value(
			"Department", {"company": "_Test Company"}, "name"
		)

		separation = frappe.new_doc("Employee Separation")
		separation.employee = employee
		separation.boarding_begins_on = getdate()
		separation.company = "_Test Company"
		separation.append(
			"activities",
			{
				"activity_name": "IT Clearance",
				"clearance_department": dept,
			},
		)
		separation.insert()
		separation.submit()

		task = separation.activities[0].task
		self.assertTrue(task)
		# At least one ToDo should exist for the task — routing engaged.
		todos = frappe.get_all("ToDo", filters={"reference_type": "Task", "reference_name": task})
		self.assertGreater(len(todos), 0)
		self.assertTrue(todos[0].owner)

	def test_is_exit_interview_creates_draft(self):
		employee = frappe.db.get_value("Employee", {"status": "Active", "company": "_Test Company"})
		# Clear any pre-existing exit interview for this employee to make the test deterministic.
		for ei in frappe.get_all(
			"Exit Interview", filters={"employee": employee, "docstatus": ["<", 2]}
		):
			frappe.delete_doc("Exit Interview", ei.name, force=1)

		separation = frappe.new_doc("Employee Separation")
		separation.employee = employee
		separation.boarding_begins_on = getdate()
		separation.company = "_Test Company"
		separation.append(
			"activities",
			{"activity_name": "Exit Interview", "is_exit_interview": 1, "role": "HR User"},
		)
		separation.insert()
		separation.submit()

		exists = frappe.db.exists(
			"Exit Interview", {"employee": employee, "docstatus": ["<", 2]}
		)
		self.assertTrue(exists)

	def test_requires_asset_return_no_op_without_phase3(self):
		# When Phase 3 is not installed, requires_asset_return must not raise.
		if frappe.db.exists("DocType", "Employee Asset Request"):
			self.skipTest("Phase 3 module installed; skipping no-op assertion")

		employee = frappe.db.get_value("Employee", {"status": "Active", "company": "_Test Company"})
		separation = frappe.new_doc("Employee Separation")
		separation.employee = employee
		separation.boarding_begins_on = getdate()
		separation.company = "_Test Company"
		separation.append(
			"activities",
			{"activity_name": "Return Assets", "requires_asset_return": 1, "role": "HR User"},
		)
		separation.insert()
		# Must complete without raising
		separation.submit()
		self.assertEqual(separation.docstatus, 1)

	def test_get_offboarding_progress(self):
		from hrms.api.offboarding import get_offboarding_progress

		separation = create_employee_separation()
		progress = get_offboarding_progress(separation.name)
		self.assertIn("tasks", progress)
		self.assertIn("pct", progress)
		self.assertIn("blockers", progress)
		self.assertEqual(progress["employee"], separation.employee)


def create_employee_separation():
	employee = frappe.db.get_value("Employee", {"status": "Active", "company": "_Test Company"})
	separation = frappe.new_doc("Employee Separation")
	separation.employee = employee
	separation.boarding_begins_on = getdate()
	separation.company = "_Test Company"
	separation.append("activities", {"activity_name": "Deactivate Employee", "role": "HR User"})
	separation.boarding_status = "Pending"
	separation.insert()
	separation.submit()
	return separation
