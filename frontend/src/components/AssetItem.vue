<template>
	<ListItem
		:isTeamRequest="false"
		:employee="props.doc.employee"
		:employeeName="props.doc.employee_name"
	>
		<template #left>
			<FeatherIcon name="package" class="h-5 w-5 text-gray-500" />
			<div class="flex flex-col items-start gap-1.5">
				<div class="text-base font-normal text-gray-800">
					{{ title }}
				</div>
				<div class="text-xs font-normal text-gray-500">
					<span v-if="props.doc.request_type">{{ __(props.doc.request_type, null, "Asset Request Type") }}</span>
					<span v-if="dateLabel" class="whitespace-pre"> &middot; </span>
					<span v-if="dateLabel" class="whitespace-nowrap">{{ dateLabel }}</span>
				</div>
			</div>
		</template>
		<template #right>
			<Badge
				variant="outline"
				:theme="colorMap[status] || 'gray'"
				:label="__(status, null, 'Asset Status')"
				size="md"
			/>
			<FeatherIcon name="chevron-right" class="h-5 w-5 text-gray-500" />
		</template>
	</ListItem>
</template>

<script setup>
import { computed } from "vue"
import { FeatherIcon, Badge } from "frappe-ui"

import ListItem from "@/components/ListItem.vue"

const props = defineProps({
	doc: {
		type: Object,
		required: true,
	},
})

const title = computed(() => {
	return (
		props.doc.allocated_asset ||
		props.doc.asset_name ||
		props.doc.asset ||
		props.doc.category ||
		props.doc.name
	)
})

const dateLabel = computed(() => {
	return props.doc.request_date || props.doc.from_date || ""
})

const status = computed(() => {
	if (props.doc.status) return props.doc.status
	if (props.doc.acknowledgement) return "Acknowledged"
	return "Active"
})

const colorMap = {
	Open: "orange",
	Approved: "blue",
	Rejected: "red",
	Allocated: "green",
	Returned: "gray",
	Acknowledged: "green",
	Active: "blue",
}
</script>
