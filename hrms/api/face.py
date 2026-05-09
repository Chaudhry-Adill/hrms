# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Phase 4.2 Face Detection — server-side surface.

PRIVACY POSTURE
---------------
This module deliberately accepts only 128-d face descriptors (floating-point
vectors produced by face-api.js running in the user's browser). Raw camera
frames are NEVER sent to the server. Stored data:
  * Employee.face_descriptor_json — JSON-encoded list[float] of length 128.
  * Face Verification Log — append-only audit row per attempt.

Operators wanting encryption-at-rest should turn on Frappe's encrypted-field
storage at the database/host level — descriptors are stored in a Long Text
custom field on Employee (see hrms/setup.py).
"""

from __future__ import annotations

import json
import math
from typing import TYPE_CHECKING

import frappe
from frappe import _
from frappe.utils.data import cint

if TYPE_CHECKING:
	from hrms.hr.doctype.employee_checkin.employee_checkin import EmployeeCheckin

DESCRIPTOR_DIM = 128


def _cosine_similarity(a: list[float], b: list[float]) -> float:
	"""Cosine similarity in pure Python — no NumPy dependency.

	face-api.js uses Euclidean distance natively, but for normalized 128-d
	descriptors cosine similarity is monotonic with -L2 and easier to bound
	in [0, 1] for a confidence reading.
	"""
	if len(a) != len(b):
		return 0.0
	dot = sum(x * y for x, y in zip(a, b, strict=False))
	na = math.sqrt(sum(x * x for x in a))
	nb = math.sqrt(sum(x * x for x in b))
	if not na or not nb:
		return 0.0
	# Map cosine in [-1, 1] to [0, 1].
	return max(0.0, min(1.0, (dot / (na * nb) + 1.0) / 2.0))


def _parse_descriptor(descriptor_json: str | list) -> list[float]:
	if isinstance(descriptor_json, list):
		raw = descriptor_json
	else:
		try:
			raw = json.loads(descriptor_json)
		except (TypeError, ValueError):
			frappe.throw(_("Face descriptor must be a valid JSON array."))

	if not isinstance(raw, list) or len(raw) != DESCRIPTOR_DIM:
		frappe.throw(_("Face descriptor must be a 128-element array."))

	try:
		return [float(x) for x in raw]
	except (TypeError, ValueError):
		frappe.throw(_("Face descriptor must contain only numeric values."))


def _check_self_or_hr(employee: str) -> None:
	"""Permission gate: subject employee, HR Manager, or System Manager."""
	user = frappe.session.user
	if user == "Administrator":
		return

	roles = set(frappe.get_roles(user))
	if roles & {"HR Manager", "System Manager"}:
		return

	user_employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
	if user_employee and user_employee == employee:
		return

	frappe.throw(_("You are not permitted to perform face operations for this employee."), frappe.PermissionError)


@frappe.whitelist()
def enroll(employee: str, descriptor_json: str) -> dict:
	"""Store a 128-d face descriptor for the employee.

	The PWA enrollment flow captures three poses (front, left, right),
	averages them client-side, and posts the single resulting vector here.
	"""
	if not employee:
		frappe.throw(_("Employee is required."))

	_check_self_or_hr(employee)

	descriptor = _parse_descriptor(descriptor_json)

	emp = frappe.get_doc("Employee", employee)
	# Custom fields (added in setup.py). Defensive in case install hasn't run.
	if not hasattr(emp, "face_descriptor_json"):
		frappe.throw(_("Face Detection custom fields are not installed on Employee."))

	emp.face_descriptor_json = json.dumps(descriptor)
	emp.face_enrollment_status = "Enrolled"
	emp.flags.ignore_permissions = True
	emp.save()

	return {"enrolled": True, "employee": employee}


@frappe.whitelist()
@frappe.rate_limiter.rate_limit(key="employee", limit=10, seconds=60)
def verify(employee: str, descriptor_json: str, with_liveness: bool | int = False) -> dict:
	"""Compare a probe descriptor against the stored enrollment.

	Always inserts a Face Verification Log row, regardless of outcome —
	the row is the audit trail Employee Checkin.validate consults.
	"""
	if not employee:
		frappe.throw(_("Employee is required."))

	_check_self_or_hr(employee)

	# Check consecutive failure lockout BEFORE expensive matching logic.
	fail_key = f"face_verify_fail:{employee}"
	fail_count = cint(frappe.cache.get_value(fail_key) or 0)
	if fail_count >= 5:
		frappe.throw(
			_("Face verification locked after 5 consecutive failures. Contact HR to unlock."),
			frappe.ValidationError,
		)

	probe = _parse_descriptor(descriptor_json)

	stored_json = frappe.db.get_value("Employee", employee, "face_descriptor_json")
	min_confidence = frappe.db.get_single_value("HR Settings", "face_min_confidence") or 0.7
	require_liveness = frappe.db.get_single_value("HR Settings", "face_require_liveness") or 0

	# Coerce flag: frappe sometimes passes "0"/"1"/"true" strings via REST.
	liveness_passed = bool(int(with_liveness)) if str(with_liveness).isdigit() else bool(with_liveness)

	matched = False
	confidence = 0.0
	if stored_json:
		try:
			stored = _parse_descriptor(stored_json)
			confidence = _cosine_similarity(probe, stored)
			matched = confidence >= float(min_confidence)
			if require_liveness and not liveness_passed:
				matched = False
		except frappe.ValidationError:
			matched = False

	# Update lockout counter on failure; clear on success.
	if matched:
		frappe.cache.delete_value(fail_key)
	else:
		new_count = fail_count + 1
		frappe.cache.set_value(fail_key, new_count, expires_in_sec=3600)

	log = frappe.get_doc(
		{
			"doctype": "Face Verification Log",
			"employee": employee,
			"timestamp": frappe.utils.now_datetime(),
			"confidence": round(confidence, 4),
			"liveness_passed": 1 if liveness_passed else 0,
			"match_result": "Pass" if matched else ("Skipped" if not stored_json else "Fail"),
			"device_user_agent": (frappe.local.request.headers.get("User-Agent") if frappe.local.request else None),
		}
	)
	log.flags.ignore_permissions = True
	log.insert()

	return {
		"matched": bool(matched),
		"confidence": round(confidence, 4),
		"log_name": log.name,
	}


@frappe.whitelist()
def get_enrollment_status(employee: str) -> dict:
	"""Return the enrollment state for the employee."""
	if not employee:
		frappe.throw(_("Employee is required."))

	_check_self_or_hr(employee)

	status = frappe.db.get_value("Employee", employee, "face_enrollment_status") or "Not Enrolled"
	mode = frappe.db.get_single_value("HR Settings", "face_verification_mode") or "Off"
	return {"employee": employee, "status": status, "mode": mode}


@frappe.whitelist()
def get_config() -> dict:
	"""Lightweight unauthenticated-style endpoint — exposes only mode/threshold.

	Consumed by the PWA CheckInPanel to decide whether to render the face
	capture step. No PII leaves the server.
	"""
	return {
		"mode": frappe.db.get_single_value("HR Settings", "face_verification_mode") or "Off",
		"min_confidence": float(frappe.db.get_single_value("HR Settings", "face_min_confidence") or 0.7),
		"require_liveness": bool(frappe.db.get_single_value("HR Settings", "face_require_liveness") or 0),
	}


# ---------------------------------------------------------------------------
# Document hook — registered on Employee Checkin.validate via hooks.py
# ---------------------------------------------------------------------------


def validate_face_for_checkin(doc: "EmployeeCheckin", method: str | None = None) -> None:
	"""When face mode is Required, refuse check-ins without a passing log.

	This is appended to the existing Employee Checkin validation chain — it
	never replaces it. Phase 1's geofence pre-flight (CheckInPanel.vue) and
	server-side `validate_distance_from_shift_location` continue to run.
	"""
	mode = frappe.db.get_single_value("HR Settings", "face_verification_mode") or "Off"
	if mode != "Required":
		return

	log_name = doc.get("face_verification_log")
	if not log_name:
		frappe.throw(_("Face verification required for check-in."), title=_("Face Verification Required"))

	log = frappe.db.get_value(
		"Face Verification Log",
		log_name,
		["match_result", "employee"],
		as_dict=True,
	)
	if not log:
		frappe.throw(_("Linked Face Verification Log {0} not found.").format(log_name))

	if log.employee != doc.employee:
		frappe.throw(_("Face Verification Log {0} does not belong to this employee.").format(log_name))

	if log.match_result != "Pass":
		frappe.throw(_("Face verification did not pass — please retry."))


# ---------------------------------------------------------------------------
# Scheduled job — registered in hooks.py under scheduler_events.daily
# ---------------------------------------------------------------------------


def cleanup_skipped_face_logs() -> None:
	"""Daily scheduled job: purge Face Verification Log rows with
	match_result == 'Skipped' older than 30 days.
	"""
	threshold = frappe.utils.add_days(frappe.utils.today(), -30)
	rows = frappe.db.get_all(
		"Face Verification Log",
		filters={
			"match_result": "Skipped",
			"timestamp": ("<", threshold),
		},
		pluck="name",
	)
	for name in rows:
		frappe.delete_doc("Face Verification Log", name, ignore_permissions=True, force=True)
