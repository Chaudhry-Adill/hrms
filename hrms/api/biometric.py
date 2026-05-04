# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Whitelisted endpoints for the Biometric Device Desk form buttons."""

import frappe


@frappe.whitelist()
def test_connection(device: str) -> dict:
	"""Open + close a connection to the device. Returns {success, message}."""
	doc = frappe.get_doc("Biometric Device", device)
	doc.check_permission("read")
	return doc.test_connection()


@frappe.whitelist()
def manual_sync(device: str) -> str:
	"""Trigger a one-shot sync for this device. Returns the sync log name."""
	doc = frappe.get_doc("Biometric Device", device)
	doc.check_permission("write")
	return doc.sync()


@frappe.whitelist()
def import_device_users(device: str) -> list[dict]:
	"""Pull user list from device. Does NOT auto-create mappings."""
	doc = frappe.get_doc("Biometric Device", device)
	doc.check_permission("read")
	return doc.import_users()
