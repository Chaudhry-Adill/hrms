---
description: Run bench tests for a specific module
argument-hint: <module_path>
---

Run the HRMS test suite for module "$1".

```bash
bench --site $FRAPPE_SITE run-tests --module $1 --lightmode
```

Example module paths:
- `hrms.hr.doctype.leave_application.test_leave_application`
- `hrms.payroll.doctype.salary_slip.test_salary_slip`
