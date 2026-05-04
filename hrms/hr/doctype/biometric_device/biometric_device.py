# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, now_datetime

from hrms.hr.biometric.base import BiometricSyncError


class BiometricDevice(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from hrms.hr.doctype.biometric_user_mapping.biometric_user_mapping import BiometricUserMapping

		auto_attendance_skip: DF.Check
		default_log_type: DF.Literal["Auto", "IN", "OUT"]
		device_name: DF.Data
		employee_field_for_lookup: DF.Literal["attendance_device_id", "employee"]
		enabled: DF.Check
		host: DF.Data
		last_log_id: DF.Int
		last_sync_at: DF.Datetime | None
		password: DF.Password | None
		port: DF.Int
		user_mappings: DF.Table[BiometricUserMapping]
		vendor: DF.Literal["ZKTeco", "ESSL"]
	# end: auto-generated types

	# ---------------- Driver dispatch ----------------

	def _get_driver(self):
		"""Return the correct driver instance for this device's vendor.

		ZKTeco/ESSL share the same protocol family so both go through ZKTecoDriver.
		"""
		from hrms.hr.biometric.zkteco import ZKTecoDriver

		if self.vendor in ("ZKTeco", "ESSL"):
			return ZKTecoDriver(self)

		frappe.throw(_("Unsupported biometric vendor: {0}").format(self.vendor))

	# ---------------- Public actions ----------------

	@frappe.whitelist()
	def test_connection(self) -> dict:
		"""Open + close a connection to the device. Returns {success, message}."""
		driver = self._get_driver()
		try:
			driver.connect()
			driver.disconnect()
			return {"success": True, "message": _("Connected to {0}:{1}").format(self.host, self.port)}
		except BiometricSyncError as e:
			return {"success": False, "message": str(e)}
		except Exception as e:
			return {"success": False, "message": _("Connection failed: {0}").format(str(e))}

	@frappe.whitelist()
	def import_users(self) -> list[dict]:
		"""Pull users from the device. Does NOT auto-create mappings."""
		driver = self._get_driver()
		driver.connect()
		try:
			return driver.get_users()
		finally:
			try:
				driver.disconnect()
			except Exception:
				pass

	@frappe.whitelist()
	def sync(self) -> str:
		"""Pull new attendance logs and create Employee Checkin rows.

		Creates a Biometric Sync Log row recording the run. Returns its name.
		"""
		from hrms.hr.doctype.employee_checkin.employee_checkin import add_log_based_on_employee_field

		sync_log = frappe.new_doc("Biometric Sync Log")
		sync_log.device = self.name
		sync_log.started_at = now_datetime()
		sync_log.status = "Running"
		sync_log.logs_fetched = 0
		sync_log.logs_inserted = 0
		sync_log.logs_skipped = 0
		sync_log.insert(ignore_permissions=True)

		errors: list[str] = []
		fetched = 0
		inserted = 0
		skipped = 0
		max_log_id = cint(self.last_log_id)

		driver = None
		try:
			driver = self._get_driver()
			driver.connect()
			logs = driver.fetch_logs(since_id=cint(self.last_log_id) or None) or []
			fetched = len(logs)

			for log in logs:
				try:
					user_id = log.get("user_id")
					ts = log.get("timestamp")
					punch_type = log.get("punch_type")
					log_id = cint(log.get("log_id") or 0)

					if not user_id or not ts:
						skipped += 1
						continue

					employee_field_value = self._resolve_employee_field_value(user_id)
					if not employee_field_value:
						skipped += 1
						continue

					log_type = self._resolve_log_type(punch_type)

					add_log_based_on_employee_field(
						employee_field_value=employee_field_value,
						timestamp=ts,
						device_id=self.device_name,
						log_type=log_type,
						skip_auto_attendance=cint(self.auto_attendance_skip),
						employee_fieldname=self.employee_field_for_lookup or "attendance_device_id",
					)
					inserted += 1
					if log_id and log_id > max_log_id:
						max_log_id = log_id
				except Exception as inner:
					skipped += 1
					errors.append(f"log={log!r}: {inner}")

		except BiometricSyncError as e:
			errors.append(str(e))
		except Exception as e:
			errors.append(f"Unexpected: {e}")
		finally:
			if driver is not None:
				try:
					driver.disconnect()
				except Exception:
					pass

		# Determine status
		if errors and inserted == 0:
			status = "Failed"
		elif errors:
			status = "Partial"
		else:
			status = "Success"

		# Update cursor + timestamp on the device only on partial/full success
		if status in ("Success", "Partial") and inserted > 0:
			self.db_set("last_log_id", max_log_id, update_modified=False)
			self.db_set("last_sync_at", now_datetime(), update_modified=False)

		sync_log.reload()
		sync_log.ended_at = now_datetime()
		sync_log.logs_fetched = fetched
		sync_log.logs_inserted = inserted
		sync_log.logs_skipped = skipped
		sync_log.error_log = "\n".join(errors) if errors else None
		sync_log.status = status
		sync_log.save(ignore_permissions=True)

		return sync_log.name

	# ---------------- Helpers ----------------

	def _resolve_employee_field_value(self, device_user_id: str) -> str | None:
		"""Map a device user_id to the lookup value used by add_log_based_on_employee_field.

		Strategy:
		  1) If a Biometric User Mapping row matches device_user_id, return its
		     `employee` value (when employee_field_for_lookup == 'employee') or
		     the value of `attendance_device_id` on that Employee.
		  2) Otherwise return device_user_id unchanged — caller's lookup field
		     (default attendance_device_id) is expected to match it directly.
		"""
		mapping = None
		for row in self.user_mappings or []:
			if str(row.device_user_id) == str(device_user_id):
				mapping = row
				break

		if mapping:
			if (self.employee_field_for_lookup or "attendance_device_id") == "employee":
				return mapping.employee
			# Need attendance_device_id on the mapped employee; fall back to mapping.employee
			# so that lookup by 'attendance_device_id' finds it (or skip if employee has none).
			return frappe.db.get_value("Employee", mapping.employee, "attendance_device_id") or mapping.employee

		return str(device_user_id)

	def _resolve_log_type(self, punch_type) -> str | None:
		"""Map device punch type → IN/OUT or honor configured default."""
		if (self.default_log_type or "Auto") != "Auto":
			return self.default_log_type

		# pyzk attendance.punch values: 0=Check-in, 1=Check-out, 2=Break-out, 3=Break-in,
		# 4=Overtime-in, 5=Overtime-out. We collapse to IN/OUT.
		try:
			p = cint(punch_type)
		except Exception:
			return None
		if p in (0, 3, 4):
			return "IN"
		if p in (1, 2, 5):
			return "OUT"
		return None
