<template>
	<ion-page>
		<BaseLayout :pageTitle="__('New Ticket')">
			<template #body>
				<div class="flex flex-col px-4 py-4 gap-4">
					<div>
						<label class="block text-sm font-medium text-gray-700 mb-1">
							{{ __("Subject") }} *
						</label>
						<input
							v-model="form.subject"
							type="text"
							class="w-full rounded-md border-gray-300 text-sm"
							:placeholder="__('Brief summary')"
						/>
					</div>

					<div>
						<label class="block text-sm font-medium text-gray-700 mb-1">
							{{ __("Category") }}
						</label>
						<select
							v-model="form.category"
							class="w-full rounded-md border-gray-300 text-sm"
						>
							<option value="">{{ __("Select category") }}</option>
							<option
								v-for="c in categories"
								:key="c.name"
								:value="c.name"
							>
								{{ c.category_name }}
							</option>
						</select>
					</div>

					<div>
						<label class="block text-sm font-medium text-gray-700 mb-1">
							{{ __("Priority") }}
						</label>
						<select
							v-model="form.priority"
							class="w-full rounded-md border-gray-300 text-sm"
						>
							<option value="Low">{{ __("Low") }}</option>
							<option value="Medium">{{ __("Medium") }}</option>
							<option value="High">{{ __("High") }}</option>
							<option value="Critical">{{ __("Critical") }}</option>
						</select>
					</div>

					<div>
						<label class="block text-sm font-medium text-gray-700 mb-1">
							{{ __("Description") }} *
						</label>
						<textarea
							v-model="form.description"
							rows="6"
							class="w-full rounded-md border-gray-300 text-sm"
							:placeholder="__('Describe the issue in detail')"
						/>
					</div>

					<div v-if="error" class="text-sm text-red-600">
						{{ error }}
					</div>

					<button
						class="bg-blue-600 text-white rounded-md py-2 text-sm font-medium disabled:opacity-50"
						:disabled="submitting || !form.subject || !form.description"
						@click="submit"
					>
						{{ submitting ? __("Submitting...") : __("Submit Ticket") }}
					</button>
				</div>
			</template>
		</BaseLayout>
	</ion-page>
</template>

<script setup>
import { computed, inject, reactive, ref } from "vue"
import { IonPage } from "@ionic/vue"
import { createResource } from "frappe-ui"
import { useRouter } from "vue-router"

import BaseLayout from "@/components/BaseLayout.vue"
import { ticketCategories, myTickets } from "@/data/tickets"

const __ = inject("$translate")
const router = useRouter()

const form = reactive({
	subject: "",
	category: "",
	priority: "Medium",
	description: "",
})
const error = ref("")
const submitting = ref(false)

const categories = computed(() => ticketCategories.data || [])

const submit = async () => {
	error.value = ""
	submitting.value = true
	const resource = createResource({
		url: "hrms.api.helpdesk.create_ticket",
		params: {
			subject: form.subject,
			category: form.category || null,
			priority: form.priority,
			description: form.description,
		},
		onSuccess(data) {
			myTickets.reload()
			router.replace({ name: "TicketDetailView", params: { name: data.name } })
		},
		onError(err) {
			error.value = err?.messages?.[0] || err?.message || __("Failed to submit ticket")
		},
	})
	try {
		await resource.fetch()
	} finally {
		submitting.value = false
	}
}
</script>
