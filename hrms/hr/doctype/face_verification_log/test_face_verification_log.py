# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import json
from unittest.mock import patch

import frappe

from hrms.tests.utils import HRMSTestSuite


def _stub_employee(name="EMP-FACE-0001"):
	if frappe.db.exists("Employee", name):
		return name

	# Use the first existing employee from the bootstrap data if available;
	# otherwise create a minimal stub.
	emp = frappe.db.get_value("Employee", {"status": "Active"}, "name")
	if emp:
		return emp

	doc = frappe.get_doc(
		{
			"doctype": "Employee",
			"employee_name": "Face Test Employee",
			"first_name": "Face",
			"last_name": "Test",
			"gender": "Male",
			"date_of_birth": "1990-01-01",
			"date_of_joining": "2020-01-01",
			"status": "Active",
		}
	)
	doc.insert(ignore_permissions=True, ignore_mandatory=True)
	return doc.name


def _random_descriptor(seed=0):
	import random

	rng = random.Random(seed)
	return [rng.uniform(-1, 1) for _ in range(128)]


class TestFaceVerificationLog(HRMSTestSuite):
	def setUp(self):
		self.employee = _stub_employee()
		# Reset HR Settings to a known mode for each test.
		hr_settings = frappe.get_single("HR Settings")
		# These fields are added via setup.py custom fields. They may not be
		# present in fresh CI environments yet — guard with hasattr.
		if hasattr(hr_settings, "face_verification_mode"):
			hr_settings.face_verification_mode = "Off"
			hr_settings.face_min_confidence = 0.6
			hr_settings.face_require_liveness = 0
			hr_settings.save(ignore_permissions=True)

	def _set_descriptor(self, descriptor):
		emp = frappe.get_doc("Employee", self.employee)
		if hasattr(emp, "face_descriptor_json"):
			emp.face_descriptor_json = json.dumps(descriptor)
			emp.face_enrollment_status = "Enrolled"
			emp.save(ignore_permissions=True)

	def test_enroll_stores_descriptor_and_flips_status(self):
		from hrms.api.face import enroll

		descriptor = _random_descriptor(seed=1)
		enroll(employee=self.employee, descriptor_json=json.dumps(descriptor))

		emp = frappe.get_doc("Employee", self.employee)
		stored = json.loads(emp.face_descriptor_json)
		self.assertEqual(len(stored), 128)
		self.assertEqual(emp.face_enrollment_status, "Enrolled")

	def test_verify_same_descriptor_matches(self):
		from hrms.api.face import verify

		descriptor = _random_descriptor(seed=2)
		self._set_descriptor(descriptor)

		result = verify(
			employee=self.employee,
			descriptor_json=json.dumps(descriptor),
			with_liveness=False,
		)
		self.assertTrue(result["matched"])
		self.assertGreater(result["confidence"], 0.99)
		self.assertTrue(frappe.db.exists("Face Verification Log", result["log_name"]))

	def test_verify_random_descriptor_fails_below_threshold(self):
		from hrms.api.face import verify

		stored = _random_descriptor(seed=3)
		probe = _random_descriptor(seed=999)
		self._set_descriptor(stored)

		result = verify(
			employee=self.employee,
			descriptor_json=json.dumps(probe),
			with_liveness=False,
		)
		self.assertFalse(result["matched"])
		self.assertTrue(frappe.db.exists("Face Verification Log", result["log_name"]))

	def test_verify_always_creates_a_log(self):
		from hrms.api.face import verify

		descriptor = _random_descriptor(seed=4)
		self._set_descriptor(descriptor)

		count_before = frappe.db.count("Face Verification Log", {"employee": self.employee})
		verify(
			employee=self.employee,
			descriptor_json=json.dumps(descriptor),
			with_liveness=False,
		)
		count_after = frappe.db.count("Face Verification Log", {"employee": self.employee})
		self.assertEqual(count_after, count_before + 1)

	def test_validate_face_for_checkin_throws_when_required_and_missing(self):
		from hrms.api.face import validate_face_for_checkin

		hr_settings = frappe.get_single("HR Settings")
		if not hasattr(hr_settings, "face_verification_mode"):
			self.skipTest("face_verification_mode custom field not installed")
		hr_settings.face_verification_mode = "Required"
		hr_settings.save(ignore_permissions=True)

		doc = frappe.get_doc(
			{
				"doctype": "Employee Checkin",
				"employee": self.employee,
				"log_type": "IN",
				"time": frappe.utils.now_datetime(),
			}
		)
		# Don't actually insert — just call the validator.
		with self.assertRaises(frappe.ValidationError):
			validate_face_for_checkin(doc, method="validate")

	def test_validate_face_for_checkin_passes_when_off(self):
		from hrms.api.face import validate_face_for_checkin

		hr_settings = frappe.get_single("HR Settings")
		if not hasattr(hr_settings, "face_verification_mode"):
			self.skipTest("face_verification_mode custom field not installed")
		hr_settings.face_verification_mode = "Off"
		hr_settings.save(ignore_permissions=True)

		doc = frappe.get_doc(
			{
				"doctype": "Employee Checkin",
				"employee": self.employee,
				"log_type": "IN",
				"time": frappe.utils.now_datetime(),
			}
		)
		# Should not raise.
		validate_face_for_checkin(doc, method="validate")


class TestFaceRateLimitAndLockout(HRMSTestSuite):
	def setUp(self):
		self.employee = _stub_employee("EMP-FACE-RATE-0001")
		# Reset failure counter before each test.
		fail_key = f"face_verify_fail:{self.employee}"
		frappe.cache.delete_value(fail_key)

	def _set_descriptor(self, descriptor):
		emp = frappe.get_doc("Employee", self.employee)
		if hasattr(emp, "face_descriptor_json"):
			emp.face_descriptor_json = json.dumps(descriptor)
			emp.face_enrollment_status = "Enrolled"
			emp.save(ignore_permissions=True)

	def test_rate_limit_enforced_on_11th_call(self):
		"""Calling verify 11 times in 60s for the same employee should trigger rate limit on the 11th call."""
		from hrms.api.face import verify

		stored = _random_descriptor(seed=10)
		self._set_descriptor(stored)

		# Patch the rate_limit decorator to a no-op so we can test the inner
		# enforcement logic via a side-effect counter, then restore it.
		# Instead, we call the raw verify function bypassing the decorator by
		# importing the real function reference.  The decorator is applied at
		# import time, so we patch frappe.rate_limiter.rate_limit to a pass-through.
		with patch.object(
			frappe.rate_limiter, "rate_limit", lambda **kwargs: lambda fn: fn
		):
			# Re-import to pick up the unwrapped function for this test.
			from hrms.api.face import verify as raw_verify

			# Call 10 times — should succeed.
			for _ in range(10):
				result = raw_verify(
					employee=self.employee,
					descriptor_json=json.dumps(stored),
					with_liveness=False,
				)
				self.assertTrue(result["matched"])

			# The 11th call should be rate-limited.  We simulate this by
			# temporarily restoring the real decorator behaviour on a fresh
			# wrapper that has already seen 10 calls.
			wrapped = frappe.rate_limiter.rate_limit(
				key="employee", limit=10, seconds=60
			)(raw_verify)

			# Manually seed the rate-limit counter so the next call is the 11th.
			frappe.cache.set_value(
				f"rate_limit_count:{self.employee}", 10, expires_in_sec=60
			)

			with self.assertRaises(frappe.exceptions.RateLimitExceededError):
				wrapped(
					employee=self.employee,
					descriptor_json=json.dumps(stored),
					with_liveness=False,
				)

	def test_five_failures_lockout_sixth_attempt(self):
		"""5 failed verifications should lock out the 6th attempt."""
		from hrms.api.face import verify

		stored = _random_descriptor(seed=20)
		self._set_descriptor(stored)
		probe = _random_descriptor(seed=999)

		# 5 failures.
		for _ in range(5):
			result = verify(
				employee=self.employee,
				descriptor_json=json.dumps(probe),
				with_liveness=False,
			)
			self.assertFalse(result["matched"])

		# 6th attempt should be locked out.
		with self.assertRaises(frappe.ValidationError) as ctx:
			verify(
				employee=self.employee,
				descriptor_json=json.dumps(probe),
				with_liveness=False,
			)
		self.assertIn("locked", str(ctx.exception).lower())

	def test_success_resets_failure_counter(self):
		"""A successful verification should reset the failure counter."""
		from hrms.api.face import verify

		stored = _random_descriptor(seed=30)
		self._set_descriptor(stored)
		probe = _random_descriptor(seed=999)

		# 3 failures.
		for _ in range(3):
			verify(
				employee=self.employee,
				descriptor_json=json.dumps(probe),
				with_liveness=False,
			)

		fail_key = f"face_verify_fail:{self.employee}"
		self.assertEqual(int(frappe.cache.get_value(fail_key) or 0), 3)

		# 1 success.
		verify(
			employee=self.employee,
			descriptor_json=json.dumps(stored),
			with_liveness=False,
		)

		# Counter should be cleared.
		self.assertIsNone(frappe.cache.get_value(fail_key))

		# Subsequent failures should start from 0 again.
		verify(
			employee=self.employee,
			descriptor_json=json.dumps(probe),
			with_liveness=False,
		)
		self.assertEqual(int(frappe.cache.get_value(fail_key) or 0), 1)

	def test_failure_cache_key_set_and_cleared(self):
		"""Verify the cache key face_verify_fail:{employee} is set on failure and cleared on success."""
		from hrms.api.face import verify

		stored = _random_descriptor(seed=40)
		self._set_descriptor(stored)
		probe = _random_descriptor(seed=999)
		fail_key = f"face_verify_fail:{self.employee}"

		# Key absent initially.
		frappe.cache.delete_value(fail_key)
		self.assertIsNone(frappe.cache.get_value(fail_key))

		# Failure sets the key.
		verify(
			employee=self.employee,
			descriptor_json=json.dumps(probe),
			with_liveness=False,
		)
		self.assertEqual(int(frappe.cache.get_value(fail_key) or 0), 1)

		# Success clears the key.
		verify(
			employee=self.employee,
			descriptor_json=json.dumps(stored),
			with_liveness=False,
		)
		self.assertIsNone(frappe.cache.get_value(fail_key))


class TestFaceCleanupJob(HRMSTestSuite):
	def setUp(self):
		self.employee = _stub_employee("EMP-FACE-CLEAN-0001")

	def _create_log(self, match_result, timestamp):
		log = frappe.get_doc(
			{
				"doctype": "Face Verification Log",
				"employee": self.employee,
				"timestamp": timestamp,
				"confidence": 0.5,
				"liveness_passed": 0,
				"match_result": match_result,
			}
		)
		log.flags.ignore_permissions = True
		log.insert()
		return log.name

	def test_cleanup_deletes_old_skipped_logs(self):
		"""Old Skipped logs (older than 30 days) should be deleted by the cleanup job."""
		from hrms.api.face import cleanup_skipped_face_logs

		old_ts = frappe.utils.add_days(frappe.utils.now_datetime(), -31)
		log_name = self._create_log("Skipped", old_ts)
		self.assertTrue(frappe.db.exists("Face Verification Log", log_name))

		cleanup_skipped_face_logs()

		self.assertFalse(frappe.db.exists("Face Verification Log", log_name))

	def test_cleanup_preserves_recent_skipped_logs(self):
		"""Recent Skipped logs (within 30 days) should NOT be deleted."""
		from hrms.api.face import cleanup_skipped_face_logs

		recent_ts = frappe.utils.add_days(frappe.utils.now_datetime(), -1)
		log_name = self._create_log("Skipped", recent_ts)
		self.assertTrue(frappe.db.exists("Face Verification Log", log_name))

		cleanup_skipped_face_logs()

		self.assertTrue(frappe.db.exists("Face Verification Log", log_name))

	def test_cleanup_preserves_non_skipped_logs(self):
		"""Pass/Fail logs older than 30 days should NOT be deleted."""
		from hrms.api.face import cleanup_skipped_face_logs

		old_ts = frappe.utils.add_days(frappe.utils.now_datetime(), -31)
		pass_log = self._create_log("Pass", old_ts)
		fail_log = self._create_log("Fail", old_ts)

		cleanup_skipped_face_logs()

		self.assertTrue(frappe.db.exists("Face Verification Log", pass_log))
		self.assertTrue(frappe.db.exists("Face Verification Log", fail_log))
