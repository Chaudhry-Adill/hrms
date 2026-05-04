# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import add_to_date, now_datetime


PRIORITY_LADDER = ("Low", "Medium", "High", "Critical")


class HRTicket(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		amended_from: DF.Link | None
		assigned_team: DF.Link | None
		assigned_to: DF.Link | None
		category: DF.Link | None
		comments: DF.Table
		description: DF.LongText
		first_response_at: DF.Datetime | None
		priority: DF.Literal["Low", "Medium", "High", "Critical"]
		raised_by: DF.Link
		resolution: DF.TextEditor | None
		resolved_at: DF.Datetime | None
		sla_due_at: DF.Datetime | None
		status: DF.Literal["Open", "In Progress", "Awaiting Reply", "Resolved", "Closed"]
		subject: DF.Data
	# end: auto-generated types

	def before_insert(self):
		self._apply_category_defaults()

	def _apply_category_defaults(self):
		"""Resolve category → SLA → due date, auto-fill team/assignee."""
		if not self.category:
			return

		category = frappe.db.get_value(
			"HR Ticket Category",
			self.category,
			["default_team", "sla"],
			as_dict=True,
		)
		if not category:
			return

		# Auto-assign team from category default
		if not self.assigned_team and category.default_team:
			self.assigned_team = category.default_team

		# Compute SLA due
		if category.sla and not self.sla_due_at:
			resolution_hours = frappe.db.get_value(
				"HR Ticket SLA", category.sla, "resolution_hours"
			)
			if resolution_hours:
				base = self.creation or now_datetime()
				self.sla_due_at = add_to_date(base, hours=float(resolution_hours))

		# If assigned_to empty, look up department head via Department.leader → user_id
		if not self.assigned_to and self.assigned_team:
			leader = frappe.get_value("Department", self.assigned_team, "leader")
			if leader:
				leader_user = frappe.db.get_value("Employee", leader, "user_id")
				if leader_user:
					self.assigned_to = leader_user

	def on_update(self):
		"""Track first response & resolution timestamps based on status transitions."""
		previous = self.get_doc_before_save()
		old_status = previous.status if previous else None
		new_status = self.status

		if old_status == new_status:
			return

		# First response: status moved away from Open and last comment is from someone other than raised_by user
		if (
			new_status != "Open"
			and not self.first_response_at
			and self._has_external_comment()
		):
			self.db_set("first_response_at", now_datetime(), update_modified=False)

		# Resolution timestamp
		if new_status == "Resolved" and not self.resolved_at:
			self.db_set("resolved_at", now_datetime(), update_modified=False)

	def _has_external_comment(self) -> bool:
		"""True if the most recent comment was authored by someone other than the raised_by employee's user."""
		if not self.comments:
			return False

		raised_by_user = (
			frappe.db.get_value("Employee", self.raised_by, "user_id")
			if self.raised_by
			else None
		)
		last = self.comments[-1]
		return bool(last.author) and last.author != raised_by_user
