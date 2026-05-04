---
name: frappe-frontend
description: Use when the user asks about the frontend PWA, roster UI, Vue 3, Ionic, Frappe UI, or Tailwind CSS in this project.
---

Frontend architecture:
- `frontend/` — PWA/mobile app (Vue 3 + Vite + Ionic Vue + Firebase)
- `roster/` — Roster management UI (Vue 3 + Vite + Frappe UI + Tailwind CSS)
- Both are served through Frappe's asset pipeline
- Route rules in `hrms/hooks.py` under `website_route_rules`
- Development:
  - `yarn dev-pwa` (cd frontend && vite)
  - `yarn dev-roster` (cd roster && vite)
- Build:
  - `yarn build-pwa`
  - `yarn build-roster`
- Linting:
  - `frontend/` has its own eslint and prettier configs
  - Root prettier excludes `frontend/` from formatting
- Frappe UI components are used for consistency with the Frappe desk UI
