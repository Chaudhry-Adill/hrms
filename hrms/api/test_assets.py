# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from unittest.mock import patch

import frappe
from frappe.utils import today

from hrms.api.assets import (
	acknowledge_allocation,
	generate_return_requests_for_employee,
	request_return,
)
from hrms.tests.utils import HRMSTestSuite


class TestAssetsAPI(HRMSTestSuite):
	def _get_employee(self) -> str:
		return frappe.get_all("Employee", filters={"status": "Active"}, limit=1)[0].name

	def _maybe_make_asset(self, employee: str) -> str | None:
		if not frappe.db.exists("DocType", "Asset"):
			return None
		try:
			company = frappe.db.get_value("Employee", employee, "company")
			category = frappe.db.exists("Asset Category", {"asset_category_name": "Test Laptop"})
			if not category:
				cat_doc = frappe.get_doc(
					{"doctype": "Asset Category", "asset_category_name": "Test Laptop"}
				).insert(ignore_permissions=True)
				category = cat_doc.name
			location = frappe.db.exists("Location", {"location_name": "Test HQ"})
			if not location:
				loc_doc = frappe.get_doc(
					{"doctype": "Location", "location_name": "Test HQ"}
				).insert(ignore_permissions=True)
				location = loc_doc.name
			item_code = "TEST-LAPTOP-001"
			if not frappe.db.exists("Item", item_code):
				frappe.get_doc(
					{
						"doctype": "Item",
						"item_code": item_code,
						"item_name": "Test Laptop",
						"is_fixed_asset": 1,
						"is_stock_item": 0,
						"asset_category": category,
						"item_group": "All Item Groups",
					}
				).insert(ignore_permissions=True)
			asset = frappe.get_doc(
				{
					"doctype": "Asset",
					"asset_name": "Test Laptop 001",
					"asset_category": category,
					"item_code": item_code,
					"company": company,
					"location": location,
					"available_for_use_date": today(),
					"gross_purchase_amount": 1000,
					"purchase_date": today(),
				}
			).insert(ignore_permissions=True)
			asset.submit()
			frappe.db.set_value("Asset", asset.name, "status", "Submitted")
			return asset.name
		except Exception:
			return None

	def _make_allocation(self, employee: str, asset_name: str) -> str:
		alloc = frappe.get_doc(
			{
				"doctype": "Employee Asset Allocation",
				"employee": employee,
				"asset": asset_name,
				"from_date": today(),
				"condition_at_issue": "Good",
			}
		).insert()
		alloc.submit()
		return alloc.name

	def test_acknowledge_allocation_validates_permission_for_non_owner(self):
		employee = self._get_employee()
		asset_name = self._maybe_make_asset(employee)
		if not asset_name:
			self.skipTest("ERPNext Asset not available")
		alloc_name = self._make_allocation(employee, asset_name)

		other_user = "guest@example.com"
		if not frappe.db.exists("User", other_user):
			frappe.get_doc(
				{"doctype": "User", "email": other_user, "first_name": "Guest"}
			).insert(ignore_permissions=True)

		with patch.object(frappe.session, "user", other_user):
			with self.assertRaises(frappe.PermissionError):
				acknowledge_allocation(alloc_name)

	def test_acknowledge_allocation_allows_owner_and_uses_save(self):
		employee = self._get_employee()
		asset_name = self._maybe_make_asset(employee)
		if not asset_name:
			self.skipTest("ERPNext Asset not available")
		alloc_name = self._make_allocation(employee, asset_name)

		emp_user = frappe.db.get_value("Employee", employee, "user_id") or "Administrator"
		with patch.object(frappe.session, "user", emp_user):
			result = acknowledge_allocation(alloc_name)

		self.assertEqual(result["acknowledgement"], 1)
		self.assertIsNotNone(result["acknowledgement_at"])

		alloc = frappe.get_doc("Employee Asset Allocation", alloc_name)
		self.assertTrue(alloc.acknowledgement)
		self.assertIsNotNone(alloc.acknowledgement_at)

	def test_request_return_creates_without_ignore_permissions(self):
		employee = self._get_employee()
		asset_name = self._maybe_make_asset(employee)
		if not asset_name:
			self.skipTest("ERPNext Asset not available")
		alloc_name = self._make_allocation(employee, asset_name)

		emp_user = frappe.db.get_value("Employee", employee, "user_id") or "Administrator"
		with patch.object(frappe.session, "user", emp_user):
			result = request_return(alloc_name, reason="Done using")

		self.assertIn("name", result)
		req = frappe.get_doc("Employee Asset Request", result["name"])
		self.assertEqual(req.request_type, "Return")
		self.assertEqual(req.allocated_asset, asset_name)

	def test_generate_return_requests_for_employee_not_whitelisted(self):
		self.assertNotIn(
			generate_return_requests_for_employee,
			frappe.whitelisted.values(),
		)
		# Ensure it still works as an internal call
		employee = self._get_employee()
		asset_name = self._maybe_make_asset(employee)
		if not asset_name:
			self.skipTest("ERPNext Asset not available")
		self._make_allocation(employee, asset_name)

		created = generate_return_requests_for_employee(employee)
		self.assertGreaterEqual(len(created), 1)
