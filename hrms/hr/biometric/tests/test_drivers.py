# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# See license.txt

"""Tests for the biometric driver layer.

`pyzk` is not assumed to be installed in CI; tests inject a fake driver via
monkey-patching so the protocol layer is never exercised. Goals:
  - sync() calls add_log_based_on_employee_field with the right kwargs
  - Sync log records correct fetched/inserted/skipped counts
  - A failing driver leaves status=Failed and inserted=0
  - Lookup via attendance_device_id resolves through to Employee Checkin
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import frappe
from frappe.utils import now_datetime

from erpnext.setup.doctype.employee.test_employee import make_employee

from hrms.hr.biometric.base import BiometricSyncError, Driver
from hrms.tests.utils import HRMSTestSuite


class FakeDriver(Driver):
	"""In-memory driver used by tests. No network, no pyzk."""

	def __init__(self, device, logs=None, users=None, fail_on_connect=False, fail_on_fetch=False):
		super().__init__(device)
		self._logs = logs or []
		self._users = users or []
		self._fail_on_connect = fail_on_connect
		self._fail_on_fetch = fail_on_fetch
		self.connected = False

	def connect(self):
		if self._fail_on_connect:
			raise BiometricSyncError("connect failed", vendor="ZKTeco", host="127.0.0.1")
		self.connected = True

	def disconnect(self):
		self.connected = False

	def fetch_logs(self, since_id=None):
		if self._fail_on_fetch:
			raise BiometricSyncError("fetch failed", vendor="ZKTeco", host="127.0.0.1")
		if since_id is None:
			return list(self._logs)
		return [log for log in self._logs if int(log.get("log_id") or 0) > int(since_id)]

	def get_users(self):
		return list(self._users)


def _patch_driver(fake: FakeDriver):
	"""Returns a context manager that overrides BiometricDevice._get_driver."""
	from hrms.hr.doctype.biometric_device.biometric_device import BiometricDevice

	return patch.object(BiometricDevice, "_get_driver", return_value=fake)


class TestBiometricDrivers(HRMSTestSuite):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		# Ensure a clean slate for our doctypes
		frappe.db.delete("Biometric Sync Log")
		frappe.db.delete("Biometric Device")

	def setUp(self):
		# Test employee with a known attendance_device_id
		self.employee = make_employee(
			"biotest@example.com",
			company="_Test Company",
			attendance_device_id="BIO-001",
		)

	def _make_device(self, name="Test Device", **kwargs):
		device = frappe.new_doc("Biometric Device")
		device.device_name = name
		device.vendor = kwargs.get("vendor", "ZKTeco")
		device.host = kwargs.get("host", "127.0.0.1")
		device.port = kwargs.get("port", 4370)
		device.enabled = 1
		device.employee_field_for_lookup = "attendance_device_id"
		device.default_log_type = kwargs.get("default_log_type", "Auto")
		device.auto_attendance_skip = 1
		device.insert(ignore_permissions=True)
		return device

	def test_sync_creates_employee_checkin_via_attendance_device_id(self):
		device = self._make_device(name="Test Device A")
		ts = now_datetime()
		fake = FakeDriver(
			device,
			logs=[
				{"log_id": 1, "user_id": "BIO-001", "timestamp": ts, "punch_type": 0},
			],
		)

		with _patch_driver(fake), patch(
			"hrms.hr.doctype.employee_checkin.employee_checkin.add_log_based_on_employee_field"
		) as add_log:
			# Returns a fake doc-like object with .name
			class _Stub:
				name = "EMP-CHKIN-001"

			add_log.return_value = _Stub()
			sync_log_name = device.sync()

			add_log.assert_called_once()
			kwargs = add_log.call_args.kwargs
			self.assertEqual(kwargs["employee_field_value"], "BIO-001")
			self.assertEqual(kwargs["device_id"], "Test Device A")
			self.assertEqual(kwargs["log_type"], "IN")
			self.assertEqual(kwargs["employee_fieldname"], "attendance_device_id")
			self.assertEqual(int(kwargs["skip_auto_attendance"]), 1)

		log = frappe.get_doc("Biometric Sync Log", sync_log_name)
		self.assertEqual(log.status, "Success")
		self.assertEqual(log.logs_fetched, 1)
		self.assertEqual(log.logs_inserted, 1)
		self.assertEqual(log.logs_skipped, 0)

	def test_sync_writes_real_employee_checkin(self):
		device = self._make_device(name="Test Device B")
		ts = now_datetime()
		fake = FakeDriver(
			device,
			logs=[{"log_id": 1, "user_id": "BIO-001", "timestamp": ts, "punch_type": 0}],
		)

		with _patch_driver(fake):
			device.sync()

		# Verify Employee Checkin row landed
		exists = frappe.db.exists(
			"Employee Checkin",
			{"employee": self.employee, "device_id": "Test Device B"},
		)
		self.assertTrue(exists)

	def test_failed_connection_marks_status_failed(self):
		device = self._make_device(name="Test Device C")
		fake = FakeDriver(device, fail_on_connect=True)

		with _patch_driver(fake):
			sync_log_name = device.sync()

		log = frappe.get_doc("Biometric Sync Log", sync_log_name)
		self.assertEqual(log.status, "Failed")
		self.assertEqual(log.logs_inserted, 0)
		self.assertTrue(log.error_log)

	def test_unknown_user_is_skipped(self):
		device = self._make_device(name="Test Device D")
		ts = now_datetime()
		fake = FakeDriver(
			device,
			logs=[
				{"log_id": 1, "user_id": "BIO-001", "timestamp": ts, "punch_type": 0},
				{"log_id": 2, "user_id": "UNKNOWN-XYZ", "timestamp": ts, "punch_type": 1},
			],
		)

		# Patch add_log so the unknown lookup doesn't raise from frappe
		with _patch_driver(fake), patch(
			"hrms.hr.doctype.employee_checkin.employee_checkin.add_log_based_on_employee_field"
		) as add_log:
			class _Stub:
				name = "EMP-CHKIN-X"

			# Raise for unknown employee, succeed for known one
			def _side(**kwargs):
				if kwargs["employee_field_value"] == "BIO-001":
					return _Stub()
				raise frappe.ValidationError("No employee")

			add_log.side_effect = _side
			sync_log_name = device.sync()

		log = frappe.get_doc("Biometric Sync Log", sync_log_name)
		self.assertEqual(log.logs_fetched, 2)
		self.assertEqual(log.logs_inserted, 1)
		self.assertEqual(log.logs_skipped, 1)
		# Partial because at least one error occurred but one succeeded
		self.assertEqual(log.status, "Partial")

	def test_log_type_auto_maps_punch_codes(self):
		device = self._make_device(name="Test Device E")

		# punch 0 → IN, punch 1 → OUT
		self.assertEqual(device._resolve_log_type(0), "IN")
		self.assertEqual(device._resolve_log_type(1), "OUT")
		# Unknown punch
		self.assertIsNone(device._resolve_log_type(99))

		device.default_log_type = "IN"
		self.assertEqual(device._resolve_log_type(1), "IN")

	def test_cursor_advances_after_successful_sync(self):
		device = self._make_device(name="Test Device F")
		ts = now_datetime()
		fake = FakeDriver(
			device,
			logs=[
				{"log_id": 5, "user_id": "BIO-001", "timestamp": ts, "punch_type": 0},
				{"log_id": 7, "user_id": "BIO-001", "timestamp": ts, "punch_type": 1},
			],
		)

		with _patch_driver(fake), patch(
			"hrms.hr.doctype.employee_checkin.employee_checkin.add_log_based_on_employee_field"
		) as add_log:
			class _Stub:
				name = "EMP-CHKIN-CURSOR"

			add_log.return_value = _Stub()
			device.sync()

		device.reload()
		self.assertEqual(int(device.last_log_id), 7)
		self.assertIsNotNone(device.last_sync_at)
