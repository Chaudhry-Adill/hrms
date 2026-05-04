<template>
	<ListItem>
		<template #left>
			<div class="flex flex-col items-start gap-1.5 grow">
				<div class="text-base font-medium text-gray-800 line-clamp-1">
					{{ props.doc.subject }}
				</div>
				<div class="flex flex-row flex-wrap items-center gap-1 text-xs text-gray-500">
					<span v-if="props.doc.category">{{ props.doc.category }}</span>
					<span v-if="props.doc.category && props.doc.sla_countdown" class="whitespace-pre"> &middot; </span>
					<span
						v-if="props.doc.sla_countdown"
						:class="props.doc.sla_countdown.breached ? 'text-red-600 font-medium' : ''"
					>
						{{ props.doc.sla_countdown.label }}
					</span>
				</div>
			</div>
		</template>
		<template #right>
			<Badge
				variant="outline"
				:theme="priorityTheme(props.doc.priority)"
				:label="__(props.doc.priority, null, 'Ticket Priority')"
				size="sm"
			/>
			<Badge
				variant="subtle"
				:theme="statusTheme(props.doc.status)"
				:label="__(props.doc.status, null, 'Ticket Status')"
				size="md"
			/>
			<FeatherIcon name="chevron-right" class="h-5 w-5 text-gray-500" />
		</template>
	</ListItem>
</template>

<script setup>
import { FeatherIcon, Badge } from "frappe-ui"

import ListItem from "@/components/ListItem.vue"
import { priorityTheme, statusTheme } from "@/data/tickets"

const props = defineProps({
	doc: {
		type: Object,
		required: true,
	},
})
</script>
