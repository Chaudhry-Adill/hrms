import { createResource } from "frappe-ui"

export const mySeparations = createResource({
	url: "hrms.api.offboarding.list_my_separations",
	auto: true,
	cache: "hrms:my_separations",
})

export const offboardingProgress = createResource({
	url: "hrms.api.offboarding.get_offboarding_progress",
	makeParams: (params) => ({ employee_separation: params.name }),
})

export const statusBadgeColor = (status) => {
	switch (status) {
		case "Completed":
			return "bg-green-100 text-green-800"
		case "In Process":
			return "bg-blue-100 text-blue-800"
		case "Pending":
			return "bg-yellow-100 text-yellow-800"
		default:
			return "bg-gray-100 text-gray-800"
	}
}
