<template>
	<BaseLayout :pageTitle="__('Offboarding')">
		<template #body>
			<div class="flex flex-col gap-5 px-4 mt-5 mb-7">
				<div v-if="loading" class="text-center text-gray-500 mt-10">
					{{ __("Loading...") }}
				</div>

				<div
					v-else-if="!separations.length"
					class="text-center text-gray-500 mt-10"
				>
					{{ __("No active offboarding process.") }}
				</div>

				<div v-else>
					<div
						v-for="sep in separations"
						:key="sep.name"
						class="bg-white rounded-lg shadow-sm border border-gray-200 mb-5 p-4"
					>
						<div class="flex items-center justify-between mb-2">
							<div class="font-bold text-base">{{ sep.employee_name }}</div>
							<span
								class="text-xs font-medium px-2 py-1 rounded-full"
								:class="statusBadgeColor(sep.boarding_status)"
							>
								{{ __(sep.boarding_status || "Pending") }}
							</span>
						</div>

						<div
							v-if="progressMap[sep.name]"
							class="text-xs text-gray-600 mb-3"
						>
							{{ progressMap[sep.name].completed }} /
							{{ progressMap[sep.name].total }}
							{{ __("activities completed") }}
							·
							{{ progressMap[sep.name].pct }}%
						</div>

						<div class="w-full bg-gray-100 rounded-full h-2 mb-4">
							<div
								class="bg-blue-500 h-2 rounded-full transition-all"
								:style="{
									width: (progressMap[sep.name]?.pct || 0) + '%',
								}"
							/>
						</div>

						<div class="space-y-2">
							<div
								v-for="(task, idx) in progressMap[sep.name]?.tasks || []"
								:key="idx"
								class="flex items-start gap-2 text-sm"
							>
								<span
									class="inline-block w-2 h-2 rounded-full mt-1.5 flex-shrink-0"
									:class="
										task.status === 'Completed'
											? 'bg-green-500'
											: 'bg-gray-300'
									"
								/>
								<div class="flex-1">
									<div class="font-medium text-gray-800">
										{{ task.activity_name }}
									</div>
									<div
										v-if="task.clearance_department"
										class="text-xs text-gray-500"
									>
										{{ __("Clearance") }}:
										{{ task.clearance_department }}
									</div>
									<div
										v-if="task.is_exit_interview"
										class="text-xs text-blue-600"
									>
										{{ __("Exit interview") }}
									</div>
								</div>
								<div class="text-xs text-gray-500">
									{{ task.status || "—" }}
								</div>
							</div>
						</div>
					</div>
				</div>
			</div>
		</template>
	</BaseLayout>
</template>

<script setup>
import { computed, reactive, watch } from "vue"
import { createResource } from "frappe-ui"

import BaseLayout from "@/components/BaseLayout.vue"
import { mySeparations, statusBadgeColor } from "@/data/offboarding"

const separations = computed(() => mySeparations.data || [])
const loading = computed(() => mySeparations.loading)

const progressMap = reactive({})

const fetchProgress = (name) => {
	if (progressMap[name]) return
	const resource = createResource({
		url: "hrms.api.offboarding.get_offboarding_progress",
		params: { employee_separation: name },
		auto: true,
		onSuccess(data) {
			progressMap[name] = data
		},
	})
	resource.fetch()
}

watch(
	separations,
	(rows) => {
		for (const r of rows) fetchProgress(r.name)
	},
	{ immediate: true },
)
</script>
