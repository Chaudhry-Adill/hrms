# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class HRTicketSLA(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		business_hours_only: DF.Check
		first_response_hours: DF.Float
		holiday_list: DF.Link | None
		resolution_hours: DF.Float
		sla_name: DF.Data
	# end: auto-generated types

	pass
