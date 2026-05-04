# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors and Contributors
# See license.txt

import frappe
from frappe.utils import nowdate

from erpnext.setup.doctype.employee.test_employee import make_employee

from hrms.hr.doctype.job_offer.test_job_offer import create_job_offer
from hrms.tests.test_utils import create_job_applicant
from hrms.tests.utils import HRMSTestSuite


class TestJobApplicant(HRMSTestSuite):
	def test_job_applicant_naming(self):
		applicant = frappe.get_doc(
			{
				"doctype": "Job Applicant",
				"status": "Open",
				"applicant_name": "_Test Applicant",
				"email_id": "job_applicant_naming@example.com",
			}
		).insert()
		self.assertEqual(applicant.name, "job_applicant_naming@example.com")

		applicant = frappe.get_doc(
			{
				"doctype": "Job Applicant",
				"status": "Open",
				"applicant_name": "_Test Applicant",
				"email_id": "job_applicant_naming@example.com",
			}
		).insert()
		self.assertEqual(applicant.name, "job_applicant_naming@example.com-1")

	def test_update_applicant_to_employee(self):
		applicant = create_job_applicant()
		job_offer = create_job_offer(
			job_applicant=applicant.name, status="Awaiting Response", company="_Test Company"
		)
		job_offer.save()

		# before creating employee
		self.assertEqual(applicant.status, "Open")
		self.assertEqual(job_offer.status, "Awaiting Response")

		# create employee
		make_employee(user=applicant.name, job_applicant=applicant.name, company="_Test Company")

		# after creating employee
		applicant.reload()
		self.assertEqual(applicant.status, "Accepted")
		job_offer.reload()
		self.assertEqual(job_offer.status, "Accepted")

	def test_tracking_token_generated_on_insert(self):
		applicant = frappe.get_doc(
			{
				"doctype": "Job Applicant",
				"status": "Open",
				"applicant_name": "_Tracking Token Applicant",
				"email_id": "tracking_token@example.com",
			}
		).insert()
		self.assertTrue(applicant.tracking_token)
		self.assertGreaterEqual(len(applicant.tracking_token), 32)

		# token must remain stable across saves
		original = applicant.tracking_token
		applicant.applicant_rating = 4
		applicant.save()
		applicant.reload()
		self.assertEqual(applicant.tracking_token, original)

	def test_stage_log_appended_on_status_change(self):
		applicant = frappe.get_doc(
			{
				"doctype": "Job Applicant",
				"status": "Open",
				"applicant_name": "_Stage Log Applicant",
				"email_id": "stage_log@example.com",
			}
		).insert()
		# after_insert seeds the initial Open log
		self.assertEqual(len(applicant.stage_log), 1)
		self.assertEqual(applicant.stage_log[0].stage, "Open")

		applicant.status = "Shortlisted"
		applicant.save()
		applicant.reload()
		self.assertEqual(len(applicant.stage_log), 2)
		self.assertEqual(applicant.stage_log[-1].stage, "Shortlisted")

		# saving without status change should not append
		applicant.applicant_rating = 5
		applicant.save()
		applicant.reload()
		self.assertEqual(len(applicant.stage_log), 2)

	def test_bulk_update_status(self):
		from hrms.api.recruitment import bulk_update_status

		names = []
		for i in range(3):
			doc = frappe.get_doc(
				{
					"doctype": "Job Applicant",
					"status": "Open",
					"applicant_name": f"_Bulk Applicant {i}",
					"email_id": f"bulk_applicant_{i}@example.com",
				}
			).insert()
			names.append(doc.name)

		result = bulk_update_status(applicants=names, status="Shortlisted", note="Moved in bulk")
		self.assertEqual(set(result["updated"]), set(names))
		self.assertEqual(result["skipped"], [])

		for n in names:
			doc = frappe.get_doc("Job Applicant", n)
			self.assertEqual(doc.status, "Shortlisted")
			# note should be on the most recent log row
			self.assertEqual(doc.stage_log[-1].note, "Moved in bulk")

	def test_get_candidate_timeline_by_token(self):
		from hrms.api.recruitment import get_candidate_timeline

		applicant = frappe.get_doc(
			{
				"doctype": "Job Applicant",
				"status": "Open",
				"applicant_name": "_Timeline Applicant",
				"email_id": "timeline_applicant@example.com",
			}
		).insert()
		applicant.status = "Replied"
		applicant.save()

		timeline = get_candidate_timeline(token=applicant.tracking_token)
		self.assertEqual(timeline["current_status"], "Replied")
		self.assertEqual(timeline["applicant_name"], "_Timeline Applicant")
		# never leak email
		self.assertNotIn("email_id", timeline)
		self.assertGreaterEqual(len(timeline["timeline"]), 2)

		with self.assertRaises(frappe.DoesNotExistError):
			get_candidate_timeline(token="nonexistent-token-value")
