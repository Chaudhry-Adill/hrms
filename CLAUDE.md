# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Frappe HRMS is an open-source HR and Payroll application built on the [Frappe Framework](https://github.com/frappe/frappe) and [ERPNext](https://github.com/frappe/erpnext). It provides modules for Employee Lifecycle, Leave & Attendance, Expense Claims, Performance Management, and Payroll & Taxation.

**Dependencies**: `frappe` (>=17.0.0-dev, <18.0.0) and `erpnext` (>=17.0.0-dev, <18.0.0) must be installed.

## Development Commands

### Setup
Local development requires a Frappe bench environment:
```bash
bench start
bench new-site hrms.localhost
bench get-app erpnext
bench get-app hrms
bench --site hrms.localhost install-app hrms
bench --site hrms.localhost add-to-hosts
```
The site will be available at `http://hrms.localhost:8080`.

### Python Tests
Tests extend `HRMSTestSuite` (from `hrms.tests.utils`) which wraps `ERPNextTestSuite`. Tests are located alongside their doctypes in `test_<doctype>.py` files.

Run a single test module:
```bash
bench --site <site> run-tests --module hrms.hr.doctype.leave_application.test_leave_application --lightmode
```

Run all tests for the app:
```bash
bench --site <site> run-parallel-tests --app hrms --total-builds <N> --build-number <M> --lightmode
```

Test utilities and bootstrap data live in `hrms/tests/test_utils.py` and `hrms/tests/utils.py`.

### Frontend
The repository has two Vue 3 + Vite frontends using Frappe UI and Tailwind CSS:
- `frontend/` — PWA/mobile app (uses Ionic Vue and Firebase)
- `roster/` — Roster management UI

Install dependencies:
```bash
yarn install
```

Run development servers:
```bash
yarn dev-pwa   # cd frontend && vite
yarn dev-roster # cd roster && vite
```

Build for production:
```bash
yarn build-pwa
yarn build-roster
```

### Linting and Formatting
- **Python**: Ruff (config in `pyproject.toml`). Run `ruff check --fix` and `ruff format`.
- **JS/Vue/CSS**: Prettier (excludes `frontend/` from the root pre-commit config; `frontend/` and `roster/` have their own configs).
- **Pre-commit**: `pre-commit run --all-files`
- **Semgrep**: Security rules from `frappe/semgrep-rules` and test-correctness rules from `semgrep/test-correctness.yml`.

### Commit Conventions
Commits must follow [Conventional Commits](https://www.conventionalcommits.org/). Allowed types: `build`, `chore`, `ci`, `docs`, `feat`, `fix`, `perf`, `refactor`, `revert`, `style`, `test`, `patch`. Config is in `commitlint.config.js`.

## High-Level Architecture

### Module Structure
The app is organized into two main modules under `hrms/`:
- **`hr/`** — Employee lifecycle, recruitment, leaves, attendance, expense claims, performance, training, shifts, and travel.
- **`payroll/`** — Salary structures, salary slips, payroll entries, tax declarations, gratuity, and benefits.

### DocType-Centric Model
Frappe uses DocTypes as the core abstraction. Each DocType lives in `hrms/<module>/doctype/<doctype_name>/` and typically contains:
- `<doctype>.py` — server-side controller (extends `Document`)
- `<doctype>.json` — schema and field definitions
- `test_<doctype>.py` — unit tests
- `.js` files — client-side scripts for forms, lists, or trees

### Key Architectural Patterns
- **Controllers** (`hrms/controllers/`): Shared logic for cross-cutting concerns. `employee_boarding_controller.py` handles onboarding/separation workflows by creating Projects and Tasks. `employee_reminders.py` sends scheduled birthday and work-anniversary emails.
- **Overrides** (`hrms/overrides/`): HRMS extends core ERPNext DocType classes (e.g., `Employee`, `Timesheet`, `Payment Entry`, `Project`) via `override_doctype_class` in `hooks.py`. It also hooks into ERPNext document events (`doc_events` in `hooks.py`) for validations and status updates.
- **Regional Overrides** (`hrms/regional/`): Country-specific logic (e.g., India HRA exemption and tax calculations) is dispatched via `regional_overrides` in `hooks.py`.
- **Setup & Fixtures** (`hrms/setup.py`): The app installs custom fields into ERPNext masters (e.g., `Company`) and creates default records during `after_install`.
- **Hooks** (`hrms/hooks.py`): Central registry for app metadata, scheduler events, document hooks, dashboard overrides, website routes (`/hrms/`, `/hr/`), and global search configuration.

### Frontend Architecture
- **`frontend/`** builds the PWA (`/assets/hrms/frontend/`) and copies its `index.html` to `hrms/www/hrms.html`. It uses Ionic Vue for mobile-native UI patterns and Firebase for push notifications.
- **`roster/`** builds the roster view (`/assets/hrms/roster/`) and copies its `index.html` to `hrms/www/roster.html`.
- Both are served through Frappe’s asset pipeline and routed via `website_route_rules` in `hooks.py`.

### Testing Rules
- Do not call `frappe.db.commit()` in tests (breaks idempotency).
- Do not override `tearDown` in tests (`HRMSTestSuite` handles rollback automatically).
- Do not call `frappe.db.truncate()` in tests (implies an implicit commit).
These are enforced by Semgrep rules in `semgrep/test-correctness.yml`.
