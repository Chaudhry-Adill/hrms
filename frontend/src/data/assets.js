import { createResource } from "frappe-ui"

export const myAssetRequests = createResource({
	url: "hrms.api.assets.list_my_requests",
	auto: true,
	cache: "hrms:my_asset_requests",
})

export const myAllocations = createResource({
	url: "hrms.api.assets.list_my_assets",
	auto: true,
	cache: "hrms:my_asset_allocations",
})

export const assetCategories = createResource({
	url: "hrms.api.assets.list_asset_categories",
	auto: true,
	cache: "hrms:asset_categories",
})

export const requestAsset = createResource({
	url: "hrms.api.assets.request_asset",
})

export const acknowledgeAllocation = createResource({
	url: "hrms.api.assets.acknowledge_allocation",
})

export const requestReturn = createResource({
	url: "hrms.api.assets.request_return",
})

export const statusBadgeColor = (status) => {
	switch (status) {
		case "Open":
			return "bg-yellow-100 text-yellow-800"
		case "Approved":
			return "bg-blue-100 text-blue-800"
		case "Allocated":
			return "bg-green-100 text-green-800"
		case "Returned":
			return "bg-gray-100 text-gray-800"
		case "Rejected":
			return "bg-red-100 text-red-800"
		default:
			return "bg-gray-100 text-gray-800"
	}
}
