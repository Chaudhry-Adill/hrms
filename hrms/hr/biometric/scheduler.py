# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Scheduler hook for periodic biometric polling.

Wired up via `scheduler_events` in hrms/hooks.py with a `*/15 * * * *` cron.
Each device runs in its own try/except so a single bad device cannot break
the whole tick.
"""

from __future__ import annotations

import frappe


def poll_all_devices() -> None:
	"""Iterate enabled Biometric Devices and call .sync() on each."""
	devices = frappe.get_all(
		"Biometric Device",
		filters={"enabled": 1},
		pluck="name",
	)
	for name in devices:
		try:
			device = frappe.get_doc("Biometric Device", name)
			device.sync()
		except Exception:
			frappe.log_error(
				title=f"Biometric poll failed for {name}",
				message=frappe.get_traceback(with_context=True),
			)
