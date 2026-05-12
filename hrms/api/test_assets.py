# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from unittest.mock import patch

import frappe
from frappe.utils import add_days, today

from hrms.tests.utils import HRMSTestSuite


class TestAssetsAPI(HRMSTestSuite):
	def _get_employee(self) -> str:
		return frappe.get_all("Employee", filters={"status": "Active"}, limit=1)[0].name

	def test_acknowledge_allocation_validates_permission_for_non_owner(self):
		employee = self._get_employee()
		alloc = frappe.get_doc(
			{
				"doctype": "Employee Asset Allocation",
				"employee": employee,
				"asset": "_Test Asset",
				"from_date": today(),
			}
		).insert(ignore_permissions=True)

		with self.assertRaises(frappe.PermissionError):
			from hrms.api.assets import acknowledge_allocation

			acknowledge_allocation(alloc.name)

	def test_acknowledge_allocation_allows_owner_and_uses_save(self):
		employee = self._get_employee()
		emp_user = frappe.db.get_value("Employee", employee, "user_id") or "Administrator"
		alloc = frappe.get_doc(
			{
				"doctype": "Employee Asset Allocation",
				"employee": employee,
				"asset": "_Test Asset",
				"from_date": today(),
			}
		).insert(ignore_permissions=True)

		with patch.object(frappe.session, "user", emp_user):
			from hrms.api.assets import acknowledge_allocation

			result = acknowledge_allocation(alloc.name)

		self.assertEqual(result["acknowledgement"], 1)
		self.assertIsNotNone(result["acknowledgement_at"])
		alloc.reload()
		self.assertTrue(alloc.acknowledgement)
		self.assertIsNotNone(alloc.acknowledgement_at)

	def test_request_return_creates_without_ignore_permissions(self):
		employee = self._get_employee()
		emp_user = frappe.db.get_value("Employee", employee, "user_id") or "Administrator"
		alloc = frappe.get_doc(
			{
				"doctype": "Employee Asset Allocation",
				"employee": employee,
				"asset": "_Test Asset",
				"from_date": today(),
			}
		).insert(ignore_permissions=True)
		alloc.submit()

		with patch.object(frappe.session, "user", emp_user):
			from hrms.api.assets import request_return

			result = request_return(alloc.name, reason="No longer needed")

		self.assertIn("name", result)
		req = frappe.get_doc("Employee Asset Request", result["name"])
		self.assertEqual(req.request_type, "Return")
		self.assertEqual(req.status, "Open")

	def test_generate_return_requests_for_employee_not_whitelisted(self):
		from hrms.api.assets import generate_return_requests_for_employee

		self.assertNotIn(
			generate_return_requests_for_employee,
			frappe.whitelisted,
		)

		employee = self._get_employee()
		created = generate_return_requests_for_employee(
			employee, due_date=add_days(today(), 7), separation="TEST-SEP-001"
		)
		self.assertIsInstance(created, list)
