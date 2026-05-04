import { createResource } from "frappe-ui"

import dayjs from "@/utils/dayjs"

export const myTickets = createResource({
	url: "hrms.api.helpdesk.list_my_tickets",
	auto: true,
	cache: "hrms:my_tickets",
	transform(data) {
		return (data || []).map((t) => {
			t.doctype = "HR Ticket"
			t.sla_countdown = formatSLACountdown(t.sla_due_at, t.status)
			return t
		})
	},
})

export const ticketCategories = createResource({
	url: "frappe.client.get_list",
	params: {
		doctype: "HR Ticket Category",
		fields: ["name", "category_name", "default_team", "sla"],
		limit_page_length: 100,
	},
	auto: true,
	cache: "hrms:ticket_categories",
})

export const ticketDetail = (name) =>
	createResource({
		url: "frappe.client.get",
		params: { doctype: "HR Ticket", name },
		auto: true,
		cache: `hrms:ticket:${name}`,
	})

export const formatSLACountdown = (due, status) => {
	if (!due) return null
	if (status === "Resolved" || status === "Closed") return null
	const now = dayjs()
	const target = dayjs(due)
	if (target.isBefore(now)) {
		return { breached: true, label: `Overdue ${target.from(now, true)}` }
	}
	return { breached: false, label: `Due in ${target.from(now, true)}` }
}

export const priorityTheme = (priority) => {
	switch (priority) {
		case "Critical":
			return "red"
		case "High":
			return "orange"
		case "Medium":
			return "blue"
		case "Low":
		default:
			return "gray"
	}
}

export const statusTheme = (status) => {
	switch (status) {
		case "Open":
			return "orange"
		case "In Progress":
			return "blue"
		case "Awaiting Reply":
			return "yellow"
		case "Resolved":
			return "green"
		case "Closed":
			return "gray"
		default:
			return "gray"
	}
}
