# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.utils import add_to_date, now_datetime

from erpnext.setup.doctype.employee.test_employee import make_employee

from hrms.scheduler.ticket_sla import escalate_breached_slas
from hrms.tests.utils import HRMSTestSuite


def _ensure_sla(name="_Test Helpdesk SLA", first=4, resolution=48):
	if not frappe.db.exists("HR Ticket SLA", name):
		return frappe.get_doc(
			{
				"doctype": "HR Ticket SLA",
				"sla_name": name,
				"first_response_hours": first,
				"resolution_hours": resolution,
			}
		).insert(ignore_permissions=True)
	return frappe.get_doc("HR Ticket SLA", name)


def _ensure_department(name="_Test Helpdesk Dept", leader=None):
	if not frappe.db.exists("Department", name):
		dept = frappe.get_doc(
			{
				"doctype": "Department",
				"department_name": name,
				"company": "_Test Company",
			}
		).insert(ignore_permissions=True)
	else:
		dept = frappe.get_doc("Department", name)
	if leader and dept.get("leader") != leader:
		dept.db_set("leader", leader)
	return dept


def _ensure_category(name="_Test IT Category", department=None, sla=None):
	if frappe.db.exists("HR Ticket Category", name):
		return frappe.get_doc("HR Ticket Category", name)
	return frappe.get_doc(
		{
			"doctype": "HR Ticket Category",
			"category_name": name,
			"default_team": department,
			"sla": sla,
		}
	).insert(ignore_permissions=True)


class TestHRTicket(HRMSTestSuite):
	def setUp(self):
		self.employee = make_employee("ticket_user_@example.com", company="_Test Company")
		self.sla = _ensure_sla()
		self.department = _ensure_department()
		self.category = _ensure_category(
			department=self.department.name, sla=self.sla.name
		)

	def _new_ticket(self, **overrides):
		payload = {
			"doctype": "HR Ticket",
			"subject": "Cannot login to ERPNext",
			"raised_by": self.employee,
			"description": "Locked out after VPN switch.",
			"category": self.category.name,
			"status": "Open",
			"priority": "Low",
		}
		payload.update(overrides)
		return frappe.get_doc(payload).insert(ignore_permissions=True)

	def test_sla_due_at_computed_on_insert(self):
		ticket = self._new_ticket()
		self.assertIsNotNone(ticket.sla_due_at)
		# Should be roughly 48 hours after creation
		expected = add_to_date(ticket.creation, hours=48)
		# Allow 60s skew
		self.assertAlmostEqual(
			frappe.utils.get_datetime(ticket.sla_due_at).timestamp(),
			frappe.utils.get_datetime(expected).timestamp(),
			delta=60,
		)

	def test_no_sla_no_due_at(self):
		category = _ensure_category(name="_Test No SLA Category", department=self.department.name)
		# Make sure it has no sla
		category.db_set("sla", None)
		ticket = self._new_ticket(category=category.name)
		self.assertIsNone(ticket.sla_due_at)

	def test_dept_head_auto_assignment(self):
		# Create an employee whose user becomes the department head
		head = make_employee("ticket_head_@example.com", company="_Test Company")
		head_user = frappe.db.get_value("Employee", head, "user_id")
		dept = _ensure_department("_Test Helpdesk Dept Head", leader=head)
		category = _ensure_category(
			name="_Test Cat With Head", department=dept.name, sla=self.sla.name
		)
		ticket = self._new_ticket(category=category.name)
		self.assertEqual(ticket.assigned_team, dept.name)
		self.assertEqual(ticket.assigned_to, head_user)

	def test_first_response_set_on_status_change(self):
		ticket = self._new_ticket()
		# Add a comment from someone other than raised_by user
		ticket.append(
			"comments",
			{"body": "Looking into it", "author": "Administrator"},
		)
		ticket.status = "In Progress"
		ticket.save()
		ticket.reload()
		self.assertIsNotNone(ticket.first_response_at)

	def test_resolved_at_set_on_resolution(self):
		ticket = self._new_ticket()
		ticket.status = "Resolved"
		ticket.save()
		ticket.reload()
		self.assertIsNotNone(ticket.resolved_at)

	def test_escalate_breached_slas_bumps_priority(self):
		ticket = self._new_ticket(priority="Low")
		# Simulate breach
		past = add_to_date(now_datetime(), hours=-1)
		frappe.db.set_value("HR Ticket", ticket.name, "sla_due_at", past)

		with patch("hrms.scheduler.ticket_sla._notify_department_head") as mock_notify:
			count = escalate_breached_slas()

		self.assertGreaterEqual(count, 1)
		mock_notify.assert_called()
		ticket.reload()
		self.assertEqual(ticket.priority, "Medium")

	def test_escalation_critical_stays_critical(self):
		ticket = self._new_ticket(priority="Critical")
		past = add_to_date(now_datetime(), hours=-1)
		frappe.db.set_value("HR Ticket", ticket.name, "sla_due_at", past)

		with patch("hrms.scheduler.ticket_sla._notify_department_head"):
			escalate_breached_slas()

		ticket.reload()
		self.assertEqual(ticket.priority, "Critical")

	def test_escalation_skips_resolved(self):
		ticket = self._new_ticket(priority="Low")
		past = add_to_date(now_datetime(), hours=-1)
		frappe.db.set_value("HR Ticket", ticket.name, "sla_due_at", past)
		frappe.db.set_value("HR Ticket", ticket.name, "status", "Resolved")

		with patch("hrms.scheduler.ticket_sla._notify_department_head") as mock_notify:
			escalate_breached_slas()

		ticket.reload()
		self.assertEqual(ticket.priority, "Low")
		# Notify should not have been called for this ticket
		# (other tickets may exist, but at least this one is excluded)
		called_for_self = any(
			call.args and call.args[0].get("name") == ticket.name
			for call in mock_notify.call_args_list
		)
		self.assertFalse(called_for_self)
