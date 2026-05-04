# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from typing import TYPE_CHECKING

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today

if TYPE_CHECKING:
	from frappe.types import DF


class EmployeeAssetRequest(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		allocated_asset: DF.Link | None
		allocated_movement: DF.Link | None
		allocation_date: DF.Date | None
		amended_from: DF.Link | None
		approver: DF.Link | None
		actual_return_date: DF.Date | None
		category: DF.Link | None
		company: DF.Link | None
		department: DF.Link | None
		employee: DF.Link
		employee_name: DF.Data | None
		expected_return_date: DF.Date | None
		notes: DF.Text | None
		purpose: DF.Text | None
		request_date: DF.Date
		request_type: DF.Literal["New", "Return"]
		status: DF.Literal["Open", "Approved", "Rejected", "Allocated", "Returned"]
		urgency: DF.Literal["Low", "Normal", "High"]
	# end: auto-generated types

	def validate(self):
		if not self.request_date:
			self.request_date = today()

		if self.request_type == "New" and not self.category and self.status not in ("Open", "Rejected"):
			frappe.throw(_("Asset Category is required for new asset requests."))

		if self.request_type == "Return" and not self.allocated_asset:
			# Allowed at draft, but warn — return requests are normally created with the asset link
			pass

	def on_update_after_submit(self):
		"""Drive lifecycle: Approved → create allocation, Allocated → set links, Returned → stamp date."""
		# Capture previous values from DB to detect transitions
		previous = self.get_doc_before_save()
		previous_status = previous.status if previous else None

		if previous_status == self.status:
			return

		if self.status == "Approved" and self.request_type == "New":
			self._create_allocation_for_approved_request()

		elif self.status == "Allocated":
			# Defensive: ensure allocation_date stamped
			if not self.allocation_date:
				self.db_set("allocation_date", today())

		elif self.status == "Returned":
			if not self.actual_return_date:
				self.db_set("actual_return_date", today())

	def _create_allocation_for_approved_request(self):
		"""Pick best matching Asset and create + submit an Employee Asset Allocation."""
		if self.allocated_asset:
			# Already allocated upstream
			asset_to_use = self.allocated_asset
		else:
			asset_to_use = self._pick_available_asset()
			if not asset_to_use:
				frappe.msgprint(
					_("No available Asset found for category {0}. Please allocate manually.").format(
						self.category
					),
					indicator="orange",
					alert=True,
				)
				return

		allocation = frappe.get_doc(
			{
				"doctype": "Employee Asset Allocation",
				"employee": self.employee,
				"asset": asset_to_use,
				"from_date": today(),
				"request": self.name,
				"expected_return_date": self.expected_return_date,
			}
		)
		allocation.insert(ignore_permissions=True)
		allocation.submit()

	def _pick_available_asset(self) -> str | None:
		"""Return the asset_name (PK) of the best matching available Asset.

		ERPNext Asset uses `status` field; "Submitted" indicates available unassigned assets.
		Sort by asset_name ascending so we pick deterministically.
		"""
		if not self.category:
			return None

		try:
			candidates = frappe.get_all(
				"Asset",
				filters={
					"asset_category": self.category,
					"status": "Submitted",
					"docstatus": 1,
				},
				fields=["name"],
				order_by="name asc",
				limit=1,
			)
		except Exception:
			# ERPNext not installed in sandbox; fail gracefully
			return None

		return candidates[0].name if candidates else None
