<template>
	<BaseLayout :pageTitle="__('My Assets')">
		<template #right-header>
			<Button
				variant="solid"
				:label="__('Request Asset')"
				@click="goToNewRequest"
			>
				<template #prefix>
					<FeatherIcon name="plus" class="h-4 w-4" />
				</template>
			</Button>
		</template>
		<template #body>
			<div class="flex flex-col gap-4 px-4 mt-5 mb-7">
				<TabButtons
					:buttons="tabs"
					v-model="activeTab"
				/>

				<!-- Active Allocations tab -->
				<div v-if="activeTab === 'allocations'" class="flex flex-col gap-3">
					<div
						v-if="myAllocations.loading"
						class="text-center text-gray-500 mt-10"
					>
						{{ __("Loading...") }}
					</div>
					<EmptyState
						v-else-if="!(myAllocations.data || []).length"
						:message="__('No active asset allocations.')"
					/>
					<router-link
						v-for="alloc in myAllocations.data || []"
						:key="alloc.name"
						:to="{ name: 'AssetDetailView', params: { name: alloc.name } }"
					>
						<AssetItem :doc="alloc" />
					</router-link>
				</div>

				<!-- My Requests tab -->
				<div v-else class="flex flex-col gap-3">
					<div
						v-if="myAssetRequests.loading"
						class="text-center text-gray-500 mt-10"
					>
						{{ __("Loading...") }}
					</div>
					<EmptyState
						v-else-if="!(myAssetRequests.data || []).length"
						:message="__('No asset requests yet.')"
					/>
					<router-link
						v-for="req in myAssetRequests.data || []"
						:key="req.name"
						:to="{ name: 'AssetDetailView', params: { name: req.name } }"
					>
						<AssetItem :doc="req" />
					</router-link>
				</div>
			</div>
		</template>
	</BaseLayout>
</template>

<script setup>
import { ref } from "vue"
import { useRouter } from "vue-router"
import { Button, FeatherIcon } from "frappe-ui"

import BaseLayout from "@/components/BaseLayout.vue"
import EmptyState from "@/components/EmptyState.vue"
import TabButtons from "@/components/TabButtons.vue"
import AssetItem from "@/components/AssetItem.vue"
import { myAssetRequests, myAllocations } from "@/data/assets"

const router = useRouter()
const activeTab = ref("allocations")

const tabs = [
	{ label: __("Active Assets"), value: "allocations" },
	{ label: __("My Requests"), value: "requests" },
]

const goToNewRequest = () => {
	router.push({ name: "AssetRequestFormView" })
}
</script>
