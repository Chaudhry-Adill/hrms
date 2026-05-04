---
name: hrms-testing
description: Use when the user asks about writing, running, or debugging HRMS tests.
---

HRMS testing rules:
- Test base class: `HRMSTestSuite` from `hrms.tests.utils` (extends `ERPNextTestSuite`)
- Test utilities: `hrms.tests.test_utils`
- Bootstrap data: `hrms.tests.utils.BootStrapTestData`
- Run command: `bench --site $FRAPPE_SITE run-tests --module <module_path> --lightmode`
- Parallel tests: `bench --site $FRAPPE_SITE run-parallel-tests --app hrms --total-builds N --build-number M --lightmode`
- Semgrep rules in `semgrep/test-correctness.yml` enforce:
  - No `frappe.db.commit()` in tests
  - No `frappe.db.truncate()` in tests
  - No overriding `tearDown`
- Do not call `frappe.db.commit()` or `frappe.db.truncate()` in tests
- Do not override `tearDown` (HRMSTestSuite handles rollback automatically)
