<template>
	<ion-page>
		<BaseLayout :pageTitle="__('My Tickets')">
			<template #actions>
				<ion-button @click="goNew">
					<FeatherIcon name="plus" class="h-5 w-5" />
				</ion-button>
			</template>
			<template #body>
				<div class="flex flex-col px-4 py-3 gap-2">
					<div v-if="myTickets.loading" class="text-center text-gray-500 py-8">
						{{ __("Loading...") }}
					</div>
					<EmptyState
						v-else-if="!tickets.length"
						:title="__('No tickets yet')"
						:description="__('File a ticket and the helpdesk team will get back to you.')"
					/>
					<router-link
						v-for="t in tickets"
						:key="t.name"
						:to="{ name: 'TicketDetailView', params: { name: t.name } }"
						class="bg-white rounded-lg border border-gray-200 p-3 hover:border-gray-300"
					>
						<TicketItem :doc="t" />
					</router-link>
				</div>
			</template>
		</BaseLayout>
	</ion-page>
</template>

<script setup>
import { computed, inject } from "vue"
import { IonPage, IonButton } from "@ionic/vue"
import { FeatherIcon } from "frappe-ui"
import { useRouter } from "vue-router"

import BaseLayout from "@/components/BaseLayout.vue"
import EmptyState from "@/components/EmptyState.vue"
import TicketItem from "@/components/TicketItem.vue"
import { myTickets } from "@/data/tickets"

const __ = inject("$translate")
const router = useRouter()

const tickets = computed(() => myTickets.data || [])

const goNew = () => router.push({ name: "TicketFormView" })
</script>
