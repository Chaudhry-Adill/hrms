<template>
	<BaseLayout :pageTitle="__('Asset Detail')">
		<template #body>
			<div
				v-if="loading"
				class="text-center text-gray-500 mt-10"
			>
				{{ __("Loading...") }}
			</div>
			<div
				v-else-if="!doc"
				class="text-center text-gray-500 mt-10"
			>
				{{ __("Not found.") }}
			</div>
			<div v-else class="flex flex-col gap-4 px-4 mt-5 mb-7">
				<!-- Summary card -->
				<div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
					<div class="flex items-center justify-between mb-2">
						<div class="font-bold text-base">
							{{ doc.asset_name || doc.allocated_asset || doc.name }}
						</div>
						<span
							class="text-xs font-medium px-2 py-1 rounded-full"
							:class="statusBadgeColor(displayStatus)"
						>
							{{ __(displayStatus) }}
						</span>
					</div>

					<div class="text-sm text-gray-600 space-y-1">
						<div v-if="doc.employee_name">
							<span class="text-gray-400">{{ __("Employee") }}:</span>
							{{ doc.employee_name }}
						</div>
						<div v-if="doc.from_date">
							<span class="text-gray-400">{{ __("From") }}:</span>
							{{ doc.from_date }}
						</div>
						<div v-if="doc.expected_return_date">
							<span class="text-gray-400">{{ __("Expected Return") }}:</span>
							{{ doc.expected_return_date }}
						</div>
						<div v-if="doc.allocation_date">
							<span class="text-gray-400">{{ __("Allocated On") }}:</span>
							{{ doc.allocation_date }}
						</div>
						<div v-if="doc.actual_return_date">
							<span class="text-gray-400">{{ __("Returned On") }}:</span>
							{{ doc.actual_return_date }}
						</div>
						<div v-if="doc.condition_at_issue">
							<span class="text-gray-400">{{ __("Condition") }}:</span>
							{{ doc.condition_at_issue }}
						</div>
					</div>
				</div>

				<!-- Status timeline (request flow) -->
				<div
					v-if="!isAllocation"
					class="bg-white rounded-lg shadow-sm border border-gray-200 p-4"
				>
					<div class="font-bold text-sm mb-3">{{ __("Status Timeline") }}</div>
					<div
						v-for="(step, idx) in timelineSteps"
						:key="idx"
						class="flex items-center gap-2 text-sm py-1"
					>
						<span
							class="inline-block w-2 h-2 rounded-full"
							:class="step.done ? 'bg-blue-500' : 'bg-gray-300'"
						/>
						<span :class="step.done ? 'text-gray-800' : 'text-gray-400'">
							{{ __(step.label) }}
						</span>
					</div>
				</div>

				<!-- Acknowledge button (allocation only, if not yet acknowledged) -->
				<div
					v-if="isAllocation && !doc.acknowledgement"
					class="bg-white rounded-lg shadow-sm border border-gray-200 p-4"
				>
					<div class="text-sm text-gray-600 mb-3">
						{{ __("Please review and acknowledge receipt of this asset.") }}
					</div>
					<Button
						variant="solid"
						:label="__('Acknowledge')"
						:loading="acknowledgeAllocation.loading"
						@click="acknowledge"
					/>
				</div>

				<div
					v-if="isAllocation && doc.acknowledgement"
					class="bg-green-50 rounded-lg border border-green-200 p-3 text-sm text-green-800"
				>
					{{ __("Acknowledged on") }} {{ doc.acknowledgement_at }}
				</div>

				<!-- Request return button -->
				<div
					v-if="isAllocation && !doc.actual_return_date"
					class="bg-white rounded-lg shadow-sm border border-gray-200 p-4"
				>
					<Button
						:label="__('Request Return')"
						:loading="requestReturn.loading"
						@click="onRequestReturn"
					/>
				</div>

				<div v-if="errorMessage" class="text-sm text-red-600">
					{{ errorMessage }}
				</div>
			</div>
		</template>
	</BaseLayout>
</template>

<script setup>
import { computed, ref } from "vue"
import { useRouter } from "vue-router"
import { Button } from "frappe-ui"

import BaseLayout from "@/components/BaseLayout.vue"
import {
	myAssetRequests,
	myAllocations,
	acknowledgeAllocation,
	requestReturn,
	statusBadgeColor,
} from "@/data/assets"

const props = defineProps({
	name: {
		type: String,
		required: true,
	},
})

const router = useRouter()
const errorMessage = ref("")

const doc = computed(() => {
	const allocations = myAllocations.data || []
	const requests = myAssetRequests.data || []
	return (
		allocations.find((a) => a.name === props.name) ||
		requests.find((r) => r.name === props.name)
	)
})

const isAllocation = computed(() => {
	if (!doc.value) return false
	// Allocations have an `asset` field; requests have request_type
	return !!doc.value.asset && !doc.value.request_type
})

const loading = computed(() => myAllocations.loading || myAssetRequests.loading)

const displayStatus = computed(() => {
	if (!doc.value) return ""
	if (isAllocation.value) {
		if (doc.value.actual_return_date) return "Returned"
		if (doc.value.acknowledgement) return "Acknowledged"
		return "Active"
	}
	return doc.value.status || "Open"
})

const timelineSteps = computed(() => {
	if (!doc.value) return []
	const status = doc.value.status
	const order = ["Open", "Approved", "Allocated", "Returned"]
	const idx = order.indexOf(status)
	return order.map((label, i) => ({
		label,
		done: status === "Rejected" ? false : i <= idx,
	}))
})

const acknowledge = async () => {
	errorMessage.value = ""
	try {
		await acknowledgeAllocation.submit({ allocation: props.name })
		myAllocations.reload()
	} catch (err) {
		errorMessage.value = err?.messages?.join(", ") || err?.message
	}
}

const onRequestReturn = async () => {
	errorMessage.value = ""
	try {
		await requestReturn.submit({ allocation: props.name, reason: "" })
		myAssetRequests.reload()
		router.push({ name: "AssetListView" })
	} catch (err) {
		errorMessage.value = err?.messages?.join(", ") || err?.message
	}
}
</script>
