# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


from datetime import date, datetime, timedelta

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, get_datetime

from hrms.hr.doctype.shift_assignment.shift_assignment import get_actual_start_end_datetime_of_shift
from hrms.hr.utils import (
	get_distance_between_coordinates,
	set_geolocation_from_coordinates,
	validate_active_employee,
)


class CheckinRadiusExceededError(frappe.ValidationError):
	pass


class EmployeeCheckin(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		attendance: DF.Link | None
		device_id: DF.Data | None
		employee: DF.Link
		employee_name: DF.Data | None
		latitude: DF.Float
		log_type: DF.Literal["", "IN", "OUT"]
		longitude: DF.Float
		offshift: DF.Check
		overtime_type: DF.Link | None
		shift: DF.Link | None
		shift_actual_end: DF.Datetime | None
		shift_actual_start: DF.Datetime | None
		shift_end: DF.Datetime | None
		shift_start: DF.Datetime | None
		skip_auto_attendance: DF.Check
		time: DF.Datetime
	# end: auto-generated types

	def before_validate(self):
		self.time = get_datetime(self.time).replace(microsecond=0)

	def validate(self):
		validate_active_employee(self.employee)
		self.validate_duplicate_log()
		self.validate_time_change()
		self.fetch_shift()
		self.set_geolocation()
		self.validate_distance_from_shift_location()

	def validate_duplicate_log(self):
		doc = frappe.db.exists(
			"Employee Checkin",
			{
				"employee": self.employee,
				"time": self.time,
				"name": ("!=", self.name),
				"log_type": self.log_type,
			},
		)
		if doc:
			doc_link = frappe.get_desk_link("Employee Checkin", doc)
			frappe.throw(
				_("This employee already has a log with the same timestamp.{0}").format("<Br>" + doc_link)
			)

	def validate_time_change(self):
		if self.attendance and self.has_value_changed("time"):
			frappe.throw(
				title=_("Cannot Modify Time"),
				msg=_(
					"An attendance record is linked to this checkin. Please cancel the attendance before modifying time."
				),
			)

	@frappe.whitelist()
	def set_geolocation(self):
		set_geolocation_from_coordinates(self)

	@frappe.whitelist()
	def fetch_shift(self):
		if not (
			shift_actual_timings := get_actual_start_end_datetime_of_shift(
				self.employee, get_datetime(self.time), True
			)
		):
			self.shift = None
			self.offshift = 1
			return

		if (
			shift_actual_timings.shift_type.determine_check_in_and_check_out
			== "Strictly based on Log Type in Employee Checkin"
			and not self.log_type
			and not self.skip_auto_attendance
		):
			frappe.throw(
				_("Log Type is required for check-ins falling in the shift: {0}.").format(
					shift_actual_timings.shift_type.name
				)
			)
		if not self.attendance:
			self.offshift = 0
			self.shift = shift_actual_timings.shift_type.name
			self.shift_actual_start = shift_actual_timings.actual_start
			self.shift_actual_end = shift_actual_timings.actual_end
			self.shift_start = shift_actual_timings.start_datetime
			self.shift_end = shift_actual_timings.end_datetime
			self.overtime_type = shift_actual_timings.overtime_type or None

	def validate_distance_from_shift_location(self):
		mode = frappe.db.get_single_value("HR Settings", "geofence_enforcement_mode") or "Off"

		if mode == "Off" and not frappe.db.get_single_value("HR Settings", "allow_geolocation_tracking"):
			return

		if not (self.latitude or self.longitude):
			if mode == "Off":
				return
			frappe.throw(_("Latitude and longitude values are required for checking in."))

		fences = resolve_geofences_for_checkin(self.employee, self.shift, self.time)

		if not fences and mode == "Off":
			# preserve legacy single-shift-location behavior when new mode unset
			fences = _legacy_assignment_fences(self.employee, self.shift, self.time)

		if not fences:
			return

		min_distance = None
		nearest_radius = None
		for fence in fences:
			fence_lat, fence_lng, radius = fence["latitude"], fence["longitude"], fence["radius_m"]
			if radius is None or radius <= 0:
				continue
			if not (self.latitude or self.longitude):
				continue
			distance = get_distance_between_coordinates(
				fence_lat, fence_lng, self.latitude, self.longitude
			)
			if min_distance is None or distance < min_distance:
				min_distance = distance
				nearest_radius = radius

		if min_distance is None:
			return

		if hasattr(self, "geofence_distance_m"):
			self.geofence_distance_m = min_distance

		if min_distance <= nearest_radius:
			return

		message = _("You must be within {0} meters of your shift location to check in.").format(
			nearest_radius
		)

		# Audit log every rejection (security & compliance).
		frappe.get_doc(
			{
				"doctype": "Error Log",
				"method": "hrms.hr.doctype.employee_checkin.employee_checkin.validate_distance_from_shift_location",
				"error": frappe.as_json(
					{
						"employee": self.employee,
						"checkin_time": str(self.time),
						"latitude": self.latitude,
						"longitude": self.longitude,
						"min_distance_m": min_distance,
						"allowed_radius_m": nearest_radius,
						"mode": mode,
						"message": message,
					}
				),
			}
		).insert(ignore_permissions=True)

		if mode == "Warn":
			frappe.msgprint(message, indicator="orange", title=_("Out of Geofence"))
			return

		if mode == "Block":
			frappe.throw(message, exc=CheckinRadiusExceededError)

		# mode == "Off" but legacy allow_geolocation_tracking is enabled — preserve old throw
		frappe.throw(message, exc=CheckinRadiusExceededError)


def resolve_geofences_for_checkin(
	employee: str,
	shift_assignment: str | None,
	timestamp: str | datetime | None,
) -> list[dict]:
	"""Returns a list of fence dicts following the override resolution chain:

	Employee.geofence_overrides → Department.geofence_overrides → Shift Assignment's
	shift_location → Shift Type's default. Higher-priority enforcing overrides win.

	Each item is a dict: {"name", "latitude", "longitude", "radius_m", "label",
	"enforce", "priority"}.
	"""
	timestamp = get_datetime(timestamp) if timestamp else None

	def _fence_row(shift_location, enforce=1, priority=1):
		if not shift_location:
			return None
		row = frappe.db.get_value(
			"Shift Location",
			shift_location,
			["name", "location_name", "checkin_radius", "latitude", "longitude"],
			as_dict=True,
		)
		if not row:
			return None
		return {
			"name": row.name,
			"label": row.location_name or row.name,
			"latitude": row.latitude,
			"longitude": row.longitude,
			"radius_m": row.checkin_radius,
			"enforce": int(enforce or 0),
			"priority": int(priority or 0),
		}

	def _from_overrides(parenttype, parent):
		if not parent:
			return []
		try:
			rows = frappe.get_all(
				"Geofence Override",
				filters={"parenttype": parenttype, "parent": parent},
				fields=["shift_location", "priority", "enforce"],
				order_by="priority desc",
			)
		except Exception:
			return []
		fences = []
		for r in rows:
			fence = _fence_row(r.shift_location, enforce=r.enforce, priority=r.priority)
			if fence:
				fences.append(fence)
		return fences

	# 1) Employee overrides
	emp_fences = _from_overrides("Employee", employee)
	enforcing = [f for f in emp_fences if f["enforce"]]
	if enforcing:
		return enforcing

	# 2) Department overrides
	department = frappe.db.get_value("Employee", employee, "department") if employee else None
	dept_fences = _from_overrides("Department", department)
	enforcing = [f for f in dept_fences if f["enforce"]]
	if enforcing:
		return enforcing

	# 3) Shift Assignment's shift_location for this employee at this time
	assignment_fences = _legacy_assignment_fences(employee, shift_assignment, timestamp)
	if assignment_fences:
		return assignment_fences

	# 4) Shift Type's default location (best effort — Shift Type may not have one)
	if shift_assignment:
		default_location = frappe.db.get_value("Shift Type", shift_assignment, "shift_location")
		fence = _fence_row(default_location)
		if fence:
			return [fence]

	# Fallback: any non-enforcing employee/department fence still gives us pill data
	return emp_fences or dept_fences


def _legacy_assignment_fences(
	employee: str,
	shift: str | None,
	timestamp: str | datetime | None,
) -> list[dict]:
	if not employee:
		return []

	filters = {
		"employee": employee,
		"shift_location": ["is", "set"],
		"docstatus": 1,
		"status": "Active",
	}
	if shift:
		filters["shift_type"] = shift
	if timestamp:
		filters["start_date"] = ["<=", timestamp]

	or_filters = None
	if timestamp:
		or_filters = [["end_date", ">=", timestamp], ["end_date", "is", "not set"]]

	assignment_locations = frappe.get_all(
		"Shift Assignment",
		filters=filters,
		or_filters=or_filters,
		pluck="shift_location",
	)
	if not assignment_locations:
		return []

	row = frappe.db.get_value(
		"Shift Location",
		assignment_locations[0],
		["name", "location_name", "checkin_radius", "latitude", "longitude"],
		as_dict=True,
	)
	if not row:
		return []
	return [
		{
			"name": row.name,
			"label": row.location_name or row.name,
			"latitude": row.latitude,
			"longitude": row.longitude,
			"radius_m": row.checkin_radius,
			"enforce": 1,
			"priority": 0,
		}
	]


@frappe.whitelist()
def add_log_based_on_employee_field(
	employee_field_value: str | int,
	timestamp: str | datetime,
	device_id: str | int | None = None,
	log_type: str | None = None,
	skip_auto_attendance: str | bool | int = 0,
	employee_fieldname: str = "attendance_device_id",
	latitude: str | float | None = None,
	longitude: str | float | None = None,
) -> Document:
	"""Finds the relevant Employee using the employee field value and creates a Employee Checkin.

	:param employee_field_value: The value to look for in employee field.
	:param timestamp: The timestamp of the Log. Currently expected in the following format as string: '2019-05-08 10:48:08.000000'
	:param device_id: (optional)Location / Device ID. A short string is expected.
	:param log_type: (optional)Direction of the Punch if available (IN/OUT).
	:param skip_auto_attendance: (optional)Skip auto attendance field will be set for this log(0/1).
	:param employee_fieldname: (Default: attendance_device_id)Name of the field in Employee DocType based on which employee lookup will happen.
	:latitude: (optional) Latitude of the shift location.
	:longitude: (optional) Longitude of the shift location.
	"""

	if not frappe.has_permission("Employee Checkin", ptype="create"):
		frappe.throw(_("Not permitted to create Employee Checkin logs."), frappe.PermissionError)

	if not employee_field_value or not timestamp:
		frappe.throw(_("'employee_field_value' and 'timestamp' are required."))

	employee = frappe.db.get_values(
		"Employee",
		{employee_fieldname: employee_field_value},
		["name", "employee_name", employee_fieldname],
		as_dict=True,
	)
	if employee:
		employee = employee[0]
	else:
		frappe.throw(
			_("No Employee found for the given employee field value. '{}': {}").format(
				employee_fieldname, employee_field_value
			)
		)

	doc = frappe.new_doc("Employee Checkin")
	doc.employee = employee.name
	doc.employee_name = employee.employee_name
	doc.time = timestamp
	doc.device_id = device_id
	doc.log_type = log_type
	doc.latitude = latitude
	doc.longitude = longitude
	if cint(skip_auto_attendance) == 1:
		doc.skip_auto_attendance = "1"
	doc.insert()

	return doc


@frappe.whitelist()
def bulk_fetch_shift(checkins: list[str] | str) -> None:
	if isinstance(checkins, str):
		checkins = frappe.json.loads(checkins)
	for d in checkins:
		doc = frappe.get_doc("Employee Checkin", d)
		doc.fetch_shift()
		doc.flags.ignore_validate = True
		doc.save()


def mark_attendance_and_link_log(
	logs: list[Document],
	attendance_status: str,
	attendance_date: str | date,
	working_hours: float | None = None,
	late_entry: int | bool = False,
	early_exit: int | bool = False,
	in_time: datetime | None = None,
	out_time: datetime | None = None,
	shift: str | None = None,
	overtime_type: str | None = None,
) -> Document | None:
	"""Creates an attendance and links the attendance to the Employee Checkin.
	Note: If attendance is already present for the given date, the logs are marked as skipped and no exception is thrown.

	:param logs: The List of 'Employee Checkin'.
	:param attendance_status: Attendance status to be marked. One of: (Present, Absent, Half Day, Skip). Note: 'On Leave' is not supported by this function.
	:param attendance_date: Date of the attendance to be created.
	:param working_hours: (optional)Number of working hours for the given date.
	"""
	log_names = [x.name for x in logs]
	employee = logs[0].employee

	if attendance_status == "Skip":
		skip_attendance_in_checkins(log_names)
		return None

	if attendance_status not in ("Present", "Absent", "Half Day"):
		frappe.throw(_("{0} is an invalid Attendance Status.").format(attendance_status))

	try:
		frappe.db.savepoint("attendance_creation")

		attendance = create_or_update_attendance(
			employee=employee,
			attendance_date=attendance_date,
			attendance_status=attendance_status,
			working_hours=working_hours,
			shift=shift,
			late_entry=late_entry,
			early_exit=early_exit,
			in_time=in_time,
			out_time=out_time,
			overtime_type=overtime_type,
		)

		if attendance_status == "Absent":
			attendance.add_comment(
				text=_("Employee was marked Absent for not meeting the working hours threshold.")
			)

		update_attendance_in_checkins(log_names, attendance.name)
		return attendance

	except frappe.ValidationError as e:
		handle_attendance_exception(log_names, e)
		return None


def create_or_update_attendance(
	employee,
	attendance_date,
	attendance_status,
	working_hours=None,
	shift=None,
	late_entry=False,
	early_exit=False,
	in_time=None,
	out_time=None,
	overtime_type=None,
):
	"""Creates a new attendance or updates an existing half-day attendance."""
	if attendance := get_existing_half_day_attendance(employee, attendance_date):
		frappe.db.set_value(
			"Attendance",
			attendance.name,
			{
				"working_hours": working_hours,
				"shift": shift,
				"late_entry": late_entry,
				"early_exit": early_exit,
				"in_time": in_time,
				"out_time": out_time,
				"half_day_status": "Absent" if attendance_status == "Absent" else "Present",
				"modify_half_day_status": 0,
			},
		)
		return frappe.get_doc("Attendance", attendance.name)
	else:
		attendance = frappe.new_doc("Attendance")
		attendance.update(
			{
				"doctype": "Attendance",
				"employee": employee,
				"attendance_date": attendance_date,
				"status": attendance_status,
				"working_hours": working_hours,
				"shift": shift,
				"late_entry": late_entry,
				"early_exit": early_exit,
				"in_time": in_time,
				"out_time": out_time,
			}
		)

		# Set overtime data if applicable
		if overtime_type and attendance_status == "Present":
			overtime_data = get_overtime_data(shift, working_hours)
			if overtime_data:
				attendance.update(
					{
						"overtime_type": overtime_type,
						"standard_working_hours": overtime_data.get("standard_working_hours"),
						"actual_overtime_duration": overtime_data.get("actual_overtime_duration"),
					}
				)
		attendance.save()
		attendance.submit()

	return attendance


def get_overtime_data(shift_name, working_hours):
	overtime_data = {}

	shift_type_details = frappe.db.get_value(
		doctype="Shift Type",
		filters={"name": shift_name},
		fieldname=["allow_overtime", "start_time", "end_time"],
		as_dict=True,
	)

	if not shift_type_details or not shift_type_details.allow_overtime:
		return overtime_data

	standard_working_hours = calculate_time_difference(
		shift_type_details.start_time, shift_type_details.end_time
	)

	if working_hours > standard_working_hours:
		actual_overtime_duration = working_hours - standard_working_hours
		overtime_data = {
			"standard_working_hours": standard_working_hours,
			"actual_overtime_duration": actual_overtime_duration,
		}

	return overtime_data


def get_existing_half_day_attendance(employee, attendance_date):
	attendance_name = frappe.db.exists(
		"Attendance",
		{
			"employee": employee,
			"attendance_date": attendance_date,
			"status": "Half Day",
			"modify_half_day_status": 1,
			"leave_type": ("is", "set"),
		},
	)

	if attendance_name:
		attendance_doc = frappe.get_doc("Attendance", attendance_name)
		return attendance_doc
	return None


def calculate_working_hours(logs, check_in_out_type, working_hours_calc_type):
	"""Given a set of logs in chronological order calculates the total working hours based on the parameters.
	Zero is returned for all invalid cases.

	:param logs: The List of 'Employee Checkin'.
	:param check_in_out_type: One of: 'Alternating entries as IN and OUT during the same shift', 'Strictly based on Log Type in Employee Checkin'
	:param working_hours_calc_type: One of: 'First Check-in and Last Check-out', 'Every Valid Check-in and Check-out'
	"""
	total_hours = 0
	in_time = out_time = None
	if check_in_out_type == "Alternating entries as IN and OUT during the same shift":
		in_time = logs[0].time
		if len(logs) >= 2:
			out_time = logs[-1].time
		if working_hours_calc_type == "First Check-in and Last Check-out":
			# assumption in this case: First log always taken as IN, Last log always taken as OUT
			total_hours = time_diff_in_hours(in_time, logs[-1].time)
		elif working_hours_calc_type == "Every Valid Check-in and Check-out":
			logs = logs[:]
			while len(logs) >= 2:
				total_hours += time_diff_in_hours(logs[0].time, logs[1].time)
				del logs[:2]

	elif check_in_out_type == "Strictly based on Log Type in Employee Checkin":
		if working_hours_calc_type == "First Check-in and Last Check-out":
			first_in_log_index = find_index_in_dict(logs, "log_type", "IN")
			first_in_log = logs[first_in_log_index] if first_in_log_index or first_in_log_index == 0 else None
			last_out_log_index = find_index_in_dict(reversed(logs), "log_type", "OUT")
			last_out_log = (
				logs[len(logs) - 1 - last_out_log_index]
				if last_out_log_index or last_out_log_index == 0
				else None
			)
			in_time = getattr(first_in_log, "time", None)
			out_time = getattr(last_out_log, "time", None)
			if first_in_log and last_out_log:
				total_hours = time_diff_in_hours(in_time, out_time)
		elif working_hours_calc_type == "Every Valid Check-in and Check-out":
			in_log = out_log = None
			for log in logs:
				if in_log and out_log:
					if not in_time:
						in_time = in_log.time
					out_time = out_log.time
					total_hours += time_diff_in_hours(in_log.time, out_log.time)
					in_log = out_log = None
				if not in_log:
					in_log = log if log.log_type == "IN" else None
					if in_log and not in_time:
						in_time = in_log.time
				elif not out_log:
					out_log = log if log.log_type == "OUT" else None

			if in_log and out_log:
				out_time = out_log.time
				total_hours += time_diff_in_hours(in_log.time, out_log.time)

	return total_hours, in_time, out_time


def time_diff_in_hours(start, end):
	return round(float((end - start).total_seconds()) / 3600, 2)


def find_index_in_dict(dict_list, key, value):
	return next((index for (index, d) in enumerate(dict_list) if d[key] == value), None)


def handle_attendance_exception(log_names: list, error_message: str):
	frappe.db.rollback(save_point="attendance_creation")
	frappe.clear_messages()
	skip_attendance_in_checkins(log_names)
	add_comment_in_checkins(log_names, error_message)


def add_comment_in_checkins(log_names: list, error_message: str):
	text = "{prefix}<br>{error_message}".format(
		prefix=frappe.bold(_("Reason for skipping auto attendance:")), error_message=error_message
	)

	for name in log_names:
		frappe.get_doc(
			{
				"doctype": "Comment",
				"comment_type": "Comment",
				"reference_doctype": "Employee Checkin",
				"reference_name": name,
				"content": text,
			}
		).insert(ignore_permissions=True)


def skip_attendance_in_checkins(log_names: list):
	EmployeeCheckin = frappe.qb.DocType("Employee Checkin")
	(
		frappe.qb.update(EmployeeCheckin)
		.set("skip_auto_attendance", 1)
		.where(EmployeeCheckin.name.isin(log_names))
	).run()


def update_attendance_in_checkins(log_names: list, attendance_id: str):
	EmployeeCheckin = frappe.qb.DocType("Employee Checkin")
	(
		frappe.qb.update(EmployeeCheckin)
		.set("attendance", attendance_id)
		.where(EmployeeCheckin.name.isin(log_names))
	).run()


def calculate_time_difference(start_time, end_time):
	if end_time < start_time:
		end_time += timedelta(days=1)
	time_difference = abs(start_time - end_time)

	return round(time_difference.total_seconds() / 3600, 2)
