# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _

from hrms.api.recruitment import get_candidate_timeline


def get_context(context):
	context.no_cache = 1
	context.parents = [{"name": _("Home"), "route": "/"}]
	context.show_sidebar = False

	token = frappe.form_dict.get("token") or (frappe.form_dict.get("route_options") or {}).get("token")
	if not token:
		context.error = _("No tracking token provided.")
		context.timeline_data = None
		return

	try:
		context.timeline_data = get_candidate_timeline(token=token)
		context.error = None
	except frappe.DoesNotExistError:
		context.timeline_data = None
		context.error = _("Application not found. Please check your tracking link.")
	except Exception:
		frappe.log_error("Track Application page error", "Recruitment")
		context.timeline_data = None
		context.error = _("Unable to load application status.")
