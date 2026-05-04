<template>
	<div class="bg-white rounded-lg border border-gray-200 p-4 w-full">
		<div class="flex flex-row items-center justify-between mb-2">
			<div class="text-sm font-medium text-gray-700">
				{{ __("Help & FAQs") }}
			</div>
			<router-link
				:to="{ name: 'TicketFormView' }"
				class="text-xs text-blue-600 hover:underline"
			>
				{{ __("File a ticket") }}
			</router-link>
		</div>

		<input
			v-model="query"
			type="text"
			class="w-full rounded-md border-gray-300 text-sm mb-3"
			:placeholder="__('Search FAQs...')"
		/>

		<div v-if="searchResource.loading" class="text-xs text-gray-500 py-2">
			{{ __("Searching...") }}
		</div>
		<div v-else-if="!results.length && query" class="text-xs text-gray-500 py-2">
			{{ __("No matching FAQs.") }}
		</div>
		<div v-else class="flex flex-col gap-2">
			<div
				v-for="r in results"
				:key="r.name"
				class="border-t border-gray-100 pt-2 cursor-pointer"
				@click="open(r)"
			>
				<div class="text-sm font-medium text-gray-800">{{ r.title }}</div>
				<div v-if="r.category" class="text-xs text-gray-500">
					{{ r.category }}
				</div>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, inject, ref, watch } from "vue"
import { createResource } from "frappe-ui"

const __ = inject("$translate")

const query = ref("")
const debounced = ref("")
let timer = null

watch(query, (val) => {
	clearTimeout(timer)
	timer = setTimeout(() => {
		debounced.value = val
	}, 300)
})

const searchResource = createResource({
	url: "hrms.api.helpdesk.search_faq",
	makeParams: () => ({ query: debounced.value }),
	auto: true,
})

watch(debounced, () => {
	searchResource.fetch()
})

const results = computed(() => (searchResource.data || []).slice(0, 3))

const open = (faq) => {
	// Could route to a dedicated FAQ viewer; for now no-op placeholder.
	console.log("Open FAQ", faq.name)
}
</script>
