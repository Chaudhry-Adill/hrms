<template>
	<BaseLayout :pageTitle="__('Request Asset')">
		<template #body>
			<div class="flex flex-col gap-4 px-4 mt-5 mb-7">
				<div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
					<FormControl
						v-model="form.category"
						type="select"
						:label="__('Asset Category')"
						:options="categoryOptions"
						required
					/>

					<FormControl
						v-model="form.urgency"
						type="select"
						:label="__('Urgency')"
						:options="['Low', 'Normal', 'High']"
						class="mt-3"
					/>

					<FormControl
						v-model="form.expected_return_date"
						type="date"
						:label="__('Expected Return Date')"
						class="mt-3"
					/>

					<FormControl
						v-model="form.purpose"
						type="textarea"
						:label="__('Purpose / Justification')"
						class="mt-3"
						:placeholder="__('Why do you need this asset?')"
					/>

					<div
						v-if="errorMessage"
						class="text-sm text-red-600 mt-3"
					>
						{{ errorMessage }}
					</div>

					<div class="flex justify-end gap-2 mt-5">
						<Button :label="__('Cancel')" @click="goBack" />
						<Button
							variant="solid"
							:label="__('Submit Request')"
							:loading="requestAsset.loading"
							@click="submit"
						/>
					</div>
				</div>
			</div>
		</template>
	</BaseLayout>
</template>

<script setup>
import { computed, reactive, ref } from "vue"
import { useRouter } from "vue-router"
import { Button, FormControl } from "frappe-ui"

import BaseLayout from "@/components/BaseLayout.vue"
import {
	assetCategories,
	requestAsset,
	myAssetRequests,
} from "@/data/assets"

const router = useRouter()
const errorMessage = ref("")

const form = reactive({
	category: "",
	urgency: "Normal",
	purpose: "",
	expected_return_date: null,
})

const categoryOptions = computed(() => {
	return (assetCategories.data || []).map((c) => ({
		label: c.asset_category_name || c.name,
		value: c.name,
	}))
})

const goBack = () => {
	router.push({ name: "AssetListView" })
}

const submit = async () => {
	errorMessage.value = ""
	if (!form.category) {
		errorMessage.value = __("Please choose an asset category.")
		return
	}
	try {
		await requestAsset.submit({
			category: form.category,
			urgency: form.urgency,
			purpose: form.purpose,
			expected_return_date: form.expected_return_date,
		})
		myAssetRequests.reload()
		router.push({ name: "AssetListView" })
	} catch (err) {
		errorMessage.value = err?.messages?.join(", ") || err?.message || __("Submission failed.")
	}
}
</script>
