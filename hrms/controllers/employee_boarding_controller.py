# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

import frappe
from frappe import _
from frappe.desk.form import assign_to
from frappe.model.document import Document
from frappe.utils import add_days, flt, unique

from erpnext.setup.doctype.employee.employee import get_holiday_list_for_employee
from erpnext.setup.doctype.holiday_list.holiday_list import is_holiday


class EmployeeBoardingController(Document):
	"""
	Create the project and the task for the boarding process
	Assign to the concerned person and roles as per the onboarding/separation template
	"""

	def validate(self):
		# remove the task if linked before submitting the form
		if self.amended_from:
			for activity in self.activities:
				activity.task = ""

	def on_submit(self):
		# create the project for the given employee onboarding
		project_name = _(self.doctype) + " : "
		if self.doctype == "Employee Onboarding":
			project_name += self.job_applicant
		else:
			project_name += self.employee

		project = frappe.get_doc(
			{
				"doctype": "Project",
				"project_name": project_name,
				"expected_start_date": self.date_of_joining
				if self.doctype == "Employee Onboarding"
				else self.resignation_letter_date,
				"department": self.department,
				"company": self.company,
			}
		).insert(ignore_permissions=True, ignore_mandatory=True)

		self.db_set("project", project.name)
		self.db_set("boarding_status", "Pending")
		self.reload()
		self.create_task_and_notify_user()

	def create_task_and_notify_user(self):
		# create the task for the given project and assign to the concerned person
		holiday_list = self.get_holiday_list()

		for activity in self.activities:
			if activity.task:
				continue

			dates = self.get_task_dates(activity, holiday_list)

			task = frappe.get_doc(
				{
					"doctype": "Task",
					"project": self.project,
					"subject": activity.activity_name + " : " + self.employee_name,
					"description": activity.description,
					"department": self.department,
					"company": self.company,
					"task_weight": activity.task_weight,
					"exp_start_date": dates[0],
					"exp_end_date": dates[1],
				}
			).insert(ignore_permissions=True)
			activity.db_set("task", task.name)

			users = [activity.user] if activity.user else []
			if activity.role:
				user_list = frappe.db.sql_list(
					"""
					SELECT
						DISTINCT(has_role.parent)
					FROM
						`tabHas Role` has_role
							LEFT JOIN `tabUser` user
								ON has_role.parent = user.name
					WHERE
						has_role.parenttype = 'User'
							AND user.enabled = 1
							AND has_role.role = %s
				""",
					activity.role,
				)
				users = unique(users + user_list)

				if "Administrator" in users:
					users.remove("Administrator")

			# Offboarding extensions: route to clearance department, auto-create exit interview.
			if self.doctype == "Employee Separation":
				if activity.get("clearance_department"):
					users = unique(users + self._get_department_head_users(activity.clearance_department))

				if activity.get("is_exit_interview"):
					self._create_exit_interview_for_activity(activity, task)

				if activity.get("requires_asset_return"):
					self._generate_asset_return_requests(activity)

			# assign the task the users
			if users:
				self.assign_task_to_users(task, users)

	def _get_department_head_users(self, department: str) -> list[str]:
		"""Return enabled users responsible for the clearance department.

		Resolution order:
		1. Department's leader (Employee link) → User via Employee.user_id.
		2. Users belonging to Employees with this department who hold a Department Head role.
		3. Fall back to global Department Head role-holders so the task isn't dropped.
		"""
		users: list[str] = []

		leader = frappe.db.get_value("Department", department, "leader") if department else None
		if leader:
			leader_user = frappe.db.get_value("Employee", leader, "user_id")
			if leader_user:
				users.append(leader_user)

		dept_users = frappe.db.sql_list(
			"""
			SELECT DISTINCT e.user_id
			FROM `tabEmployee` e
			JOIN `tabHas Role` hr ON hr.parent = e.user_id
			JOIN `tabUser` u ON u.name = e.user_id
			WHERE e.department = %s
				AND e.status = 'Active'
				AND u.enabled = 1
				AND hr.parenttype = 'User'
				AND hr.role IN ('Department Head', 'HR Manager')
			""",
			department,
		) if department else []
		users = unique(users + dept_users)

		if not users:
			users = frappe.db.sql_list(
				"""
				SELECT DISTINCT has_role.parent
				FROM `tabHas Role` has_role
				JOIN `tabUser` u ON u.name = has_role.parent
				WHERE has_role.parenttype = 'User'
					AND u.enabled = 1
					AND has_role.role = 'Department Head'
				"""
			)

		if "Administrator" in users:
			users.remove("Administrator")
		return [u for u in users if u]

	def _create_exit_interview_for_activity(self, _activity, _task):
		"""Auto-create a draft Exit Interview tied to the separating employee."""
		if not self.employee:
			return

		existing = frappe.db.exists(
			"Exit Interview", {"employee": self.employee, "docstatus": ["<", 2]}
		)
		if existing:
			return

		ei = frappe.get_doc(
			{
				"doctype": "Exit Interview",
				"employee": self.employee,
				"company": self.company,
				"status": "Pending",
			}
		)
		ei.insert(ignore_permissions=True, ignore_mandatory=True)

	def _generate_asset_return_requests(self, activity):
		"""Generate asset-return requests for all current allocations.

		Phase 3 integration: queries every active `Employee Asset Allocation` for
		the separating employee and creates one return-type `Employee Asset Request`
		per row. Skips if `Employee Asset Request` doctype isn't installed (soft
		fallback for installs that pre-date Phase 3).
		"""
		if not frappe.db.exists("DocType", "Employee Asset Request"):
			return

		if not self.employee:
			return

		due_date = None
		# Prefer the activity's task due date if set; else fall back to today + 7 in the API.
		if activity.get("task"):
			due_date = frappe.db.get_value("Task", activity.task, "exp_end_date")

		try:
			from hrms.api.assets import generate_return_requests_for_employee

			created = generate_return_requests_for_employee(
				self.employee,
				due_date=due_date,
				separation=self.name,
			) or []

			if created:
				activity.db_set(
					"description",
					(activity.description or "")
					+ "\n\n"
					+ _("Generated {0} asset return request(s): {1}").format(
						len(created), ", ".join(created)
					),
				)
		except ImportError:
			# Phase 3 module not yet wired up — leave the breadcrumb on the activity.
			activity.db_set(
				"description",
				(activity.description or "") + "\n\n[Asset return pending Phase 3]",
			)

	def get_holiday_list(self):
		if self.doctype == "Employee Separation":
			return get_holiday_list_for_employee(self.employee)
		else:
			if self.employee:
				return get_holiday_list_for_employee(self.employee)
			else:
				if not self.holiday_list:
					frappe.throw(_("Please set the Holiday List."), frappe.MandatoryError)
				else:
					return self.holiday_list

	def get_task_dates(self, activity, holiday_list):
		start_date = end_date = None

		if activity.begin_on is not None:
			start_date = add_days(self.boarding_begins_on, activity.begin_on)
			start_date = self.update_if_holiday(start_date, holiday_list)

			if activity.duration is not None:
				end_date = add_days(self.boarding_begins_on, activity.begin_on + activity.duration)
				end_date = self.update_if_holiday(end_date, holiday_list)

		return [start_date, end_date]

	def update_if_holiday(self, date, holiday_list):
		while is_holiday(holiday_list, date):
			date = add_days(date, 1)
		return date

	def assign_task_to_users(self, task, users):
		for user in users:
			args = {
				"assign_to": [user],
				"doctype": task.doctype,
				"name": task.name,
				"description": task.description or task.subject,
				"notify": self.notify_users_by_email,
			}
			assign_to.add(args)

	def on_cancel(self):
		# delete task project
		project = self.project
		for task in frappe.get_all("Task", filters={"project": project}):
			frappe.delete_doc("Task", task.name, force=1)
		frappe.delete_doc("Project", project, force=1)
		self.db_set("project", "")
		for activity in self.activities:
			activity.db_set("task", "")

		frappe.msgprint(
			_("Linked Project {} and Tasks deleted.").format(project), alert=True, indicator="blue"
		)


@frappe.whitelist()
def get_onboarding_details(parent: str, parenttype: str):
	return frappe.get_all(
		"Employee Boarding Activity",
		fields=[
			"activity_name",
			"role",
			"user",
			"required_for_employee_creation",
			"description",
			"task_weight",
			"begin_on",
			"duration",
		],
		filters={"parent": parent, "parenttype": parenttype},
		order_by="idx",
	)


def update_employee_boarding_status(project, event=None):
	employee_onboarding = frappe.db.exists("Employee Onboarding", {"project": project.name})
	employee_separation = frappe.db.exists("Employee Separation", {"project": project.name})

	if not (employee_onboarding or employee_separation):
		return

	status = "Pending"
	if flt(project.percent_complete) > 0.0 and flt(project.percent_complete) < 100.0:
		status = "In Process"
	elif flt(project.percent_complete) == 100.0:
		status = "Completed"

	if employee_onboarding:
		frappe.db.set_value("Employee Onboarding", employee_onboarding, "boarding_status", status)
	elif employee_separation:
		frappe.db.set_value("Employee Separation", employee_separation, "boarding_status", status)


def update_task(task, event=None):
	if task.project and not task.flags.from_project:
		update_employee_boarding_status(frappe.get_cached_doc("Project", task.project))
