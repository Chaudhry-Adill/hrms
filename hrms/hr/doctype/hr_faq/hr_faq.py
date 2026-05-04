# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from frappe.utils.nestedset import NestedSet


class HRFAQ(NestedSet):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		body: DF.TextEditor | None
		category: DF.Link | None
		is_group: DF.Check
		lft: DF.Int
		old_parent: DF.Link | None
		parent_hr_faq: DF.Link | None
		published: DF.Check
		rgt: DF.Int
		title: DF.Data
		views: DF.Int
	# end: auto-generated types

	nsm_parent_field = "parent_hr_faq"
