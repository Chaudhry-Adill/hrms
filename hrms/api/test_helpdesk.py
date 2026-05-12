# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# See license.txt

import frappe
from frappe import _

from hrms.api.helpdesk import create_ticket, search_faq
from hrms.tests.utils import HRMSTestSuite


class TestHelpdeskAPI(HRMSTestSuite):
	def setUp(self):
		self.employee = frappe.db.get_value(
			"Employee", {"status": "Active"}, "name"
		) or frappe.get_doc(
			{
				"doctype": "Employee",
				"employee_name": "Helpdesk Test Employee",
				"first_name": "Helpdesk",
				"last_name": "Test",
				"gender": "Male",
				"date_of_birth": "1990-01-01",
				"date_of_joining": "2020-01-01",
				"status": "Active",
			}
		).insert(ignore_permissions=True, ignore_mandatory=True)

		# Ensure the employee is linked to the current user so _get_session_employee works
		emp_doc = frappe.get_doc("Employee", self.employee)
		if not emp_doc.user_id:
			emp_doc.user_id = frappe.session.user
			emp_doc.save(ignore_permissions=True)

		# Seed FAQs
		for title in ["Password Reset", "VPN Setup"]:
			if not frappe.db.exists("HR FAQ", {"title": title}):
				frappe.get_doc(
					{
						"doctype": "HR FAQ",
						"title": title,
						"body": f"How to {title.lower()}",
						"published": 1,
						"views": 10,
					}
				).insert(ignore_permissions=True)

	def test_search_faq_with_sql_metacharacters(self):
		# Should not throw — query builder escapes values safely
		result = search_faq(query="' OR 1=1 --")
		self.assertIsInstance(result, list)

	def test_search_faq_with_percent_wildcard(self):
		result = search_faq(query="%")
		self.assertIsInstance(result, list)

	def test_search_faq_filters_by_category(self):
		cat = frappe.get_doc(
			{
				"doctype": "HR FAQ Category",
				"category_name": "_Test FAQ Cat",
			}
		).insert(ignore_permissions=True)
		faq = frappe.get_doc(
			{
				"doctype": "HR FAQ",
				"title": "Category Specific",
				"body": "Body text",
				"published": 1,
				"category": cat.name,
				"views": 99,
			}
		).insert(ignore_permissions=True)
		result = search_faq(query="Category Specific", category=cat.name)
		self.assertEqual(len(result), 1)
		self.assertEqual(result[0]["name"], faq.name)

	def test_create_ticket_rejects_foreign_attachment(self):
		# Create a file owned by Administrator
		file_doc = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "admin_doc.txt",
				"content": "admin content",
			}
		).insert(ignore_permissions=True)
		file_doc.owner = "Administrator"
		file_doc.save(ignore_permissions=True)

		with self.assertRaises(frappe.ValidationError) as ctx:
			create_ticket(
				subject="Test attachment",
				description="desc",
				attachments=[file_doc.file_url],
			)
		self.assertIn("only attach files you uploaded", str(ctx.exception).lower())

	def test_create_ticket_enforces_attachment_cap(self):
		urls = []
		for i in range(11):
			file_doc = frappe.get_doc(
				{
					"doctype": "File",
					"file_name": f"doc_{i}.txt",
					"content": f"content {i}",
				}
			).insert(ignore_permissions=True)
			file_doc.owner = frappe.session.user
			file_doc.save(ignore_permissions=True)
			urls.append(file_doc.file_url)

		with self.assertRaises(frappe.ValidationError) as ctx:
			create_ticket(
				subject="Too many attachments",
				description="desc",
				attachments=urls,
			)
		self.assertIn("up to 10 files", str(ctx.exception))
