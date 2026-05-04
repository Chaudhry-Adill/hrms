# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import get_datetime, now_datetime

from hrms.hr.doctype.employee_checkin.employee_checkin import resolve_geofences_for_checkin


@frappe.whitelist()
def resolve_fence_for_employee(employee: str, timestamp: str | None = None) -> dict:
	"""Returns the active fence(s) for an employee at a timestamp.

	Used by the PWA pre-flight check to show live distance/radius UI.

	Response shape:
	{
	    "mode": "Off|Warn|Block",
	    "fences": [
	        {"name": str, "lat": float, "lng": float, "radius_m": float, "label": str}
	    ]
	}
	"""
	if not employee:
		frappe.throw(frappe._("Employee is required."))

	mode = frappe.db.get_single_value("HR Settings", "geofence_enforcement_mode") or "Off"
	ts = get_datetime(timestamp) if timestamp else now_datetime()

	# Resolve current shift for the employee at this timestamp (best effort).
	from hrms.hr.doctype.shift_assignment.shift_assignment import get_actual_start_end_datetime_of_shift

	shift_type = None
	try:
		shift_timings = get_actual_start_end_datetime_of_shift(employee, ts, True)
		if shift_timings:
			shift_type = shift_timings.shift_type.name
	except Exception:
		shift_type = None

	fences = resolve_geofences_for_checkin(employee, shift_type, ts)

	return {
		"mode": mode,
		"fences": [
			{
				"name": f["name"],
				"lat": f["latitude"],
				"lng": f["longitude"],
				"radius_m": f["radius_m"],
				"label": f["label"],
			}
			for f in fences
		],
	}
