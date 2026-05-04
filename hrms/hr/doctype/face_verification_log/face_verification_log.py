# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

# Phase 4.2 Face Detection Check-in.
#
# PRIVACY: Frappe HRMS Face Detection stores 128-d face descriptors only.
# Raw camera frames and images are never uploaded or persisted server-side.
# Each verification attempt — pass, fail, or skipped — is appended here for
# audit. Rows are immutable after insert (see `on_update` guard) so they
# can be relied upon for compliance review.

import frappe
from frappe import _
from frappe.model.document import Document


class FaceVerificationLog(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		confidence: DF.Float
		device_user_agent: DF.SmallText | None
		employee: DF.Link
		employee_name: DF.Data | None
		liveness_passed: DF.Check
		match_result: DF.Literal["Skipped", "Pass", "Fail"]
		notes: DF.SmallText | None
		timestamp: DF.Datetime
	# end: auto-generated types

	def validate(self):
		# Coerce confidence into [0, 1]
		if self.confidence is None:
			self.confidence = 0.0
		if self.confidence < 0:
			self.confidence = 0.0
		if self.confidence > 1:
			self.confidence = 1.0

	def on_update(self):
		# Immutable after insert — only the auto-generated fields may be
		# touched by the framework itself.
		if self.get_doc_before_save() is None:
			return
		mutable_fields = {"_user_tags", "_comments", "_assign", "_liked_by"}
		before = self.get_doc_before_save()
		for field in (
			"employee",
			"timestamp",
			"confidence",
			"liveness_passed",
			"match_result",
			"device_user_agent",
		):
			if (self.get(field) or None) != (before.get(field) or None):
				if field in mutable_fields:
					continue
				frappe.throw(_("Face Verification Log entries are immutable after creation."))
