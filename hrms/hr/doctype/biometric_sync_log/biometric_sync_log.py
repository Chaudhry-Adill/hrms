# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class BiometricSyncLog(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		device: DF.Link
		ended_at: DF.Datetime | None
		error_log: DF.LongText | None
		logs_fetched: DF.Int
		logs_inserted: DF.Int
		logs_skipped: DF.Int
		naming_series: DF.Literal["BIO-SYNC-.YYYY.-.#####"]
		started_at: DF.Datetime | None
		status: DF.Literal["Running", "Success", "Partial", "Failed"]
	# end: auto-generated types

	pass
