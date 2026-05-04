# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import json

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
