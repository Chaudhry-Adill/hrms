# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from typing import TYPE_CHECKING

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime, today

if TYPE_CHECKING:
	from frappe.types import DF


class EmployeeAssetAllocation(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		acknowledgement: DF.Check
		acknowledgement_at: DF.Datetime | None
		actual_return_date: DF.Date | None
		amended_from: DF.Link | None
		asset: DF.Link
		asset_name: DF.Data | None
		condition_at_issue: DF.Literal["New", "Good", "Fair", "Poor"]
		employee: DF.Link
		employee_name: DF.Data | None
		expected_return_date: DF.Date | None
		from_date: DF.Date
		issue_movement: DF.Link | None
		naming_series: DF.Literal["EAA-.YYYY.-.#####"] | None
		request: DF.Link | None
		return_movement: DF.Link | None
	# end: auto-generated types

	def validate(self):
		if not self.from_date:
			self.from_date = today()

	def on_submit(self):
		"""Create ERPNext Asset Movement (Issue) and update parent request."""
		movement_name = self._create_asset_movement(purpose="Issue")
		if movement_name:
			self.db_set("issue_movement", movement_name)

		# Update parent request status if linked
		if self.request:
			try:
				request = frappe.get_doc("Employee Asset Request", self.request)
				if request.docstatus == 1 and request.status != "Allocated":
					request.db_set("allocated_asset", self.asset)
					request.db_set("allocation_date", self.from_date)
					request.db_set("allocated_movement", movement_name)
					request.db_set("status", "Allocated")
			except frappe.DoesNotExistError:
				pass

	def on_cancel(self):
		"""Create ERPNext Asset Movement (Receipt) and flip parent request to Returned."""
		movement_name = self._create_asset_movement(purpose="Receipt")
		if movement_name:
			self.db_set("return_movement", movement_name)
		self.db_set("actual_return_date", today())

		if self.request:
			try:
				request = frappe.get_doc("Employee Asset Request", self.request)
				if request.docstatus == 1 and request.status != "Returned":
					request.db_set("status", "Returned")
					request.db_set("actual_return_date", today())
			except frappe.DoesNotExistError:
				pass

	def _create_asset_movement(self, purpose: str) -> str | None:
		"""Create an ERPNext Asset Movement document for this allocation.

		purpose: "Issue" or "Receipt".
		Coded defensively — if ERPNext is not installed, return None.
		"""
		try:
			# Pull current location from the Asset (movement requires source location).
			asset = frappe.get_doc("Asset", self.asset)

			company = getattr(asset, "company", None)
			source_location = getattr(asset, "location", None)

			# For Issue: from current location → employee.
			# For Receipt: from employee → original/asset location.
			row: dict = {
				"asset": self.asset,
			}

			if purpose == "Issue":
				row["source_location"] = source_location
				row["to_employee"] = self.employee
			else:
				row["from_employee"] = self.employee
				row["target_location"] = source_location

			movement = frappe.get_doc(
				{
					"doctype": "Asset Movement",
					"company": company,
					"purpose": purpose,
					"transaction_date": now_datetime(),
					"reference_doctype": self.doctype,
					"reference_name": self.name,
					"assets": [row],
				}
			)
			movement.insert(ignore_permissions=True)
			movement.submit()
			return movement.name

		except Exception as exc:
			frappe.log_error(
				title=f"Asset Movement {purpose} failed for allocation {self.name}",
				message=frappe.get_traceback() + f"\n\n{exc}",
			)
			frappe.msgprint(
				_("Could not create Asset Movement ({0}): {1}").format(purpose, exc),
				indicator="orange",
				alert=True,
			)
			return None

	@frappe.whitelist()
	def acknowledge(self):
		"""Mark this allocation as acknowledged by the assigned employee."""
		current_user_emp = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
		if current_user_emp != self.employee:
			frappe.has_permission("Employee Asset Allocation", doc=self, ptype="write", throw=True)

		self.acknowledgement = 1
		self.acknowledgement_at = frappe.utils.now_datetime()
		self.save()
