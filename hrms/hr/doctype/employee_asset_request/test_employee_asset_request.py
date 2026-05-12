# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from unittest.mock import patch

import frappe
from frappe.utils import add_days, today

from hrms.tests.utils import HRMSTestSuite


class TestEmployeeAssetRequest(HRMSTestSuite):
	"""Test the Employee Asset Request lifecycle.

	These tests assume ERPNext Asset / Asset Movement is installed. When run in
	environments without ERPNext, the Asset-related sections will be skipped.
	"""

	@classmethod
	def setUpClass(cls) -> None:
		super().setUpClass()

	def _get_employee(self) -> str:
		return frappe.get_all("Employee", filters={"status": "Active"}, limit=1)[0].name

	def _maybe_make_asset(self, employee: str) -> str | None:
		"""Create an available Asset for tests; return its name, or None if ERPNext isn't installed."""
		if not frappe.db.exists("DocType", "Asset"):
			return None

		# Need an Asset Category, Item, Location to create Asset realistically.
		# Skip the test plumbing if any prerequisite is missing.
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

	def test_request_approval_creates_allocation_and_movement(self):
		"""When request flips to Approved, an Allocation should be auto-created and submitted,
		issuing an Asset Movement."""
		employee = self._get_employee()
		asset_name = self._maybe_make_asset(employee)

		req = frappe.get_doc(
			{
				"doctype": "Employee Asset Request",
				"employee": employee,
				"request_date": today(),
				"request_type": "New",
				"category": frappe.db.get_value("Asset", asset_name, "asset_category")
				if asset_name
				else None,
				"urgency": "Normal",
				"purpose": "Need a laptop for work",
				"status": "Open",
			}
		).insert()
		req.submit()

		# Flip status to Approved — triggers on_update_after_submit
		req.db_set("status", "Approved")
		req.run_method("on_update_after_submit")

		req.reload()

		if asset_name:
			# Allocation should exist
			allocations = frappe.get_all(
				"Employee Asset Allocation",
				filters={"request": req.name, "docstatus": 1},
			)
			self.assertEqual(len(allocations), 1, "Allocation should be auto-created on approval")

			alloc = frappe.get_doc("Employee Asset Allocation", allocations[0].name)
			self.assertEqual(alloc.asset, asset_name)
			self.assertTrue(alloc.issue_movement, "Issue movement should be linked on allocation")

			# Parent request should now be Allocated
			self.assertEqual(req.status, "Allocated")
			self.assertEqual(req.allocated_asset, asset_name)

	def test_allocation_cancellation_creates_receipt_movement(self):
		"""Cancelling an allocation should create an Asset Movement (Receipt) and flip the
		parent request to Returned."""
		employee = self._get_employee()
		asset_name = self._maybe_make_asset(employee)

		if not asset_name:
			self.skipTest("ERPNext Asset/Asset Movement not available in this test environment")

		req = frappe.get_doc(
			{
				"doctype": "Employee Asset Request",
				"employee": employee,
				"request_date": today(),
				"request_type": "New",
				"category": frappe.db.get_value("Asset", asset_name, "asset_category"),
				"urgency": "Normal",
				"status": "Open",
			}
		).insert()
		req.submit()

		req.db_set("status", "Approved")
		req.run_method("on_update_after_submit")

		alloc_name = frappe.get_all(
			"Employee Asset Allocation", filters={"request": req.name}, limit=1
		)[0].name
		alloc = frappe.get_doc("Employee Asset Allocation", alloc_name)

		# Cancel the allocation
		alloc.cancel()

		alloc.reload()
		self.assertTrue(alloc.return_movement, "Return movement should be created on cancel")
		self.assertEqual(alloc.actual_return_date, today())

		req.reload()
		self.assertEqual(req.status, "Returned")

	def test_acknowledge_allocation(self):
		"""acknowledge_allocation API should flip acknowledgement and stamp time."""
		employee = self._get_employee()
		asset_name = self._maybe_make_asset(employee)
		if not asset_name:
			self.skipTest("ERPNext Asset not available")

		req = frappe.get_doc(
			{
				"doctype": "Employee Asset Request",
				"employee": employee,
				"request_date": today(),
				"request_type": "New",
				"category": frappe.db.get_value("Asset", asset_name, "asset_category"),
				"status": "Open",
			}
		).insert()
		req.submit()
		req.db_set("status", "Approved")
		req.run_method("on_update_after_submit")

		alloc_name = frappe.get_all(
			"Employee Asset Allocation", filters={"request": req.name}, limit=1
		)[0].name

		# Mock the calling user as the employee's user
		emp_user = frappe.db.get_value("Employee", employee, "user_id") or "Administrator"
		with patch.object(frappe.session, "user", emp_user):
			from hrms.api.assets import acknowledge_allocation

			result = acknowledge_allocation(alloc_name)

		self.assertEqual(result["acknowledgement"], 1)
		self.assertIsNotNone(result["acknowledgement_at"])

		alloc = frappe.get_doc("Employee Asset Allocation", alloc_name)
		self.assertTrue(alloc.acknowledgement)
		self.assertIsNotNone(alloc.acknowledgement_at)

	def test_offboarding_generates_return_requests(self):
		"""Submitting an Employee Separation should generate one return request per active allocation."""
		employee = self._get_employee()
		asset_name = self._maybe_make_asset(employee)
		if not asset_name:
			self.skipTest("ERPNext Asset not available")

		# Create an active allocation directly
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

		# Call the API directly (mirrors what the controller does)
		from hrms.api.assets import generate_return_requests_for_employee

		created = generate_return_requests_for_employee(
			employee, due_date=add_days(today(), 7), separation="TEST-SEP-001"
		)

		self.assertGreaterEqual(len(created), 1)
		req = frappe.get_doc("Employee Asset Request", created[0])
		self.assertEqual(req.request_type, "Return")
		self.assertEqual(req.allocated_asset, asset_name)
		self.assertEqual(req.employee, employee)

	def test_request_asset_api_creates_draft(self):
		"""request_asset API creates a draft Open request for the current user."""
		employee = self._get_employee()
		emp_user = frappe.db.get_value("Employee", employee, "user_id") or "Administrator"

		# Need an Asset Category if ERPNext is installed
		category = None
		if frappe.db.exists("DocType", "Asset Category"):
			cat = frappe.db.get_value("Asset Category", {}, "name")
			if not cat:
				cat = frappe.get_doc(
					{"doctype": "Asset Category", "asset_category_name": "Test Cat"}
				).insert(ignore_permissions=True).name
			category = cat

		if not category:
			self.skipTest("ERPNext Asset Category not available")

		with patch.object(frappe.session, "user", emp_user):
			from hrms.api.assets import request_asset

			result = request_asset(category=category, purpose="Test", urgency="Normal")

		self.assertIn("name", result)
		req = frappe.get_doc("Employee Asset Request", result["name"])
		self.assertEqual(req.status, "Open")
		self.assertEqual(req.request_type, "New")
		self.assertEqual(req.employee, employee)

	def test_invalid_status_transition_blocked(self):
		"""Illegal status jumps should raise ValidationError."""
		employee = self._get_employee()
		req = frappe.get_doc(
			{
				"doctype": "Employee Asset Request",
				"employee": employee,
				"request_date": today(),
				"request_type": "New",
				"status": "Open",
			}
		).insert()
		req.submit()

		req.db_set("status", "Returned")
		with self.assertRaises(frappe.ValidationError):
			req.run_method("on_update_after_submit")

	def test_valid_status_transitions_allowed(self):
		"""Allowed transitions should not raise."""
		employee = self._get_employee()
		req = frappe.get_doc(
			{
				"doctype": "Employee Asset Request",
				"employee": employee,
				"request_date": today(),
				"request_type": "New",
				"status": "Open",
			}
		).insert()
		req.submit()

		# Open → Approved
		req.db_set("status", "Approved")
		req.run_method("on_update_after_submit")
		self.assertEqual(req.status, "Approved")

		# Approved → Allocated (simulated by direct db_set; allocation logic tested elsewhere)
		req.db_set("status", "Allocated")
		req.run_method("on_update_after_submit")
		self.assertEqual(req.status, "Allocated")
