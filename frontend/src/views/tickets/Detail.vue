<template>
	<ion-page>
		<BaseLayout :pageTitle="ticket?.subject || __('Ticket')">
			<template #body>
				<div v-if="loading" class="text-center text-gray-500 py-8">
					{{ __("Loading...") }}
				</div>
				<div v-else-if="ticket" class="flex flex-col px-4 py-4 gap-4">
					<!-- Status & priority strip -->
					<div class="bg-white rounded-lg border border-gray-200 p-4 flex flex-col gap-3">
						<div class="flex flex-row flex-wrap items-center gap-2">
							<Badge
								variant="subtle"
								:theme="statusTheme(ticket.status)"
								:label="__(ticket.status, null, 'Ticket Status')"
								size="md"
							/>
							<Badge
								variant="outline"
								:theme="priorityTheme(ticket.priority)"
								:label="__(ticket.priority, null, 'Ticket Priority')"
								size="md"
							/>
							<span class="text-xs text-gray-500 ml-auto">
								{{ ticket.name }}
							</span>
						</div>

						<div v-if="slaInfo" class="text-xs">
							<span :class="slaInfo.breached ? 'text-red-600 font-medium' : 'text-gray-600'">
								{{ slaInfo.label }}
							</span>
						</div>

						<!-- Status transitions -->
						<div class="flex flex-row flex-wrap gap-2">
							<button
								v-for="s in nextStatuses"
								:key="s"
								class="text-xs px-2 py-1 rounded-md border border-gray-300 bg-gray-50 hover:bg-gray-100"
								:disabled="updating"
								@click="changeStatus(s)"
							>
								{{ __(s, null, 'Ticket Status') }}
							</button>
						</div>
					</div>

					<!-- Description -->
					<div class="bg-white rounded-lg border border-gray-200 p-4">
						<div class="text-sm font-medium text-gray-700 mb-2">
							{{ __("Description") }}
						</div>
						<div class="text-sm text-gray-800 whitespace-pre-wrap">
							{{ ticket.description }}
						</div>
					</div>

					<!-- Comments -->
					<div class="bg-white rounded-lg border border-gray-200 p-4">
						<div class="text-sm font-medium text-gray-700 mb-2">
							{{ __("Comments") }}
						</div>
						<div v-if="!ticket.comments?.length" class="text-xs text-gray-500">
							{{ __("No comments yet.") }}
						</div>
						<div
							v-for="(c, idx) in ticket.comments || []"
							:key="idx"
							class="border-t border-gray-100 py-2"
							:class="c.is_internal ? 'bg-yellow-50 -mx-4 px-4' : ''"
						>
							<div class="flex flex-row items-center justify-between">
								<div class="text-xs font-medium text-gray-600">
									{{ c.author }}
									<span v-if="c.is_internal" class="text-yellow-700">
										({{ __("internal") }})
									</span>
								</div>
								<div class="text-xs text-gray-400">
									{{ c.creation }}
								</div>
							</div>
							<div class="text-sm text-gray-800 mt-1 whitespace-pre-wrap">
								{{ c.body }}
							</div>
						</div>

						<div class="mt-3 flex flex-col gap-2">
							<textarea
								v-model="newComment"
								rows="3"
								class="w-full rounded-md border-gray-300 text-sm"
								:placeholder="__('Add a comment')"
							/>
							<button
								class="bg-blue-600 text-white text-sm rounded-md py-2 disabled:opacity-50"
								:disabled="!newComment.trim() || posting"
								@click="postComment"
							>
								{{ posting ? __("Posting...") : __("Post Comment") }}
							</button>
						</div>
					</div>
				</div>
			</template>
		</BaseLayout>
	</ion-page>
</template>

<script setup>
import { computed, inject, ref, watch } from "vue"
import { IonPage } from "@ionic/vue"
import { Badge, createResource } from "frappe-ui"

import BaseLayout from "@/components/BaseLayout.vue"
import {
	formatSLACountdown,
	myTickets,
	priorityTheme,
	statusTheme,
} from "@/data/tickets"

const __ = inject("$translate")

const props = defineProps({
	name: { type: String, required: true },
})

const ticket = ref(null)
const loading = ref(true)
const updating = ref(false)
const posting = ref(false)
const newComment = ref("")

const fetchResource = createResource({
	url: "frappe.client.get",
	makeParams: () => ({ doctype: "HR Ticket", name: props.name }),
	onSuccess(data) {
		ticket.value = data
		loading.value = false
	},
	onError() {
		loading.value = false
	},
})

const reload = () => {
	loading.value = true
	fetchResource.fetch()
}

watch(
	() => props.name,
	() => reload(),
	{ immediate: true },
)

const slaInfo = computed(() => {
	if (!ticket.value) return null
	return formatSLACountdown(ticket.value.sla_due_at, ticket.value.status)
})

const nextStatuses = computed(() => {
	if (!ticket.value) return []
	const all = ["Open", "In Progress", "Awaiting Reply", "Resolved", "Closed"]
	return all.filter((s) => s !== ticket.value.status)
})

const changeStatus = async (status) => {
	if (!ticket.value) return
	updating.value = true
	const r = createResource({
		url: "frappe.client.set_value",
		params: {
			doctype: "HR Ticket",
			name: ticket.value.name,
			fieldname: "status",
			value: status,
		},
		onSuccess() {
			myTickets.reload()
			reload()
		},
	})
	try {
		await r.fetch()
	} finally {
		updating.value = false
	}
}

const postComment = async () => {
	const body = newComment.value.trim()
	if (!body) return
	posting.value = true
	const r = createResource({
		url: "hrms.api.helpdesk.add_comment",
		params: { ticket: props.name, body, is_internal: 0 },
		onSuccess() {
			newComment.value = ""
			reload()
		},
	})
	try {
		await r.fetch()
	} finally {
		posting.value = false
	}
}
</script>
