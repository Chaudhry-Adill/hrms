<template>
	<!--
	  Enroll.vue (Phase 4.2)

	  Three-pose enrollment flow:
	    1. Front
	    2. Left turn ~30°
	    3. Right turn ~30°
	  Each pose captures one 128-d descriptor; the three are averaged
	  client-side before posting to /api/method/hrms.api.face.enroll.

	  PRIVACY: only the averaged descriptor leaves the device. No frames.
	-->
	<ion-page>
		<ion-header>
			<ion-toolbar>
				<ion-buttons slot="start">
					<ion-back-button default-href="/home" />
				</ion-buttons>
				<ion-title>{{ __("Face Enrollment") }}</ion-title>
			</ion-toolbar>
		</ion-header>

		<ion-content class="ion-padding">
			<div class="flex flex-col items-center gap-4 py-4">
				<div class="text-center">
					<div class="text-base font-bold">
						{{ __("Pose {0} of 3", [poseIndex + 1]) }}
					</div>
					<div class="text-sm text-gray-600 mt-1">
						{{ poseInstructions[poseIndex] }}
					</div>
				</div>

				<FaceCapture
					ref="captureRef"
					:auto-start="true"
					:require-liveness="false"
					:stable-frames="6"
					@captured="onCaptured"
					@error="onError"
				/>

				<div class="flex gap-2 mt-2">
					<div
						v-for="i in 3"
						:key="i"
						class="w-3 h-3 rounded-full"
						:class="i - 1 < descriptors.length ? 'bg-green-500' : 'bg-gray-300'"
					/>
				</div>

				<div v-if="errorMessage" class="text-xs text-red-600">
					{{ errorMessage }}
				</div>

				<Button
					v-if="descriptors.length === 3"
					:loading="enrollFace.loading"
					variant="solid"
					class="w-full max-w-xs py-4"
					@click="submit"
				>
					{{ __("Save Enrollment") }}
				</Button>
			</div>
		</ion-content>
	</ion-page>
</template>

<script setup>
import { ref, inject } from "vue"
import {
	IonPage,
	IonHeader,
	IonToolbar,
	IonTitle,
	IonContent,
	IonButtons,
	IonBackButton,
} from "@ionic/vue"
import { Button, toast } from "frappe-ui"

import FaceCapture from "@/components/FaceCapture.vue"
import { enrollFace } from "@/data/face"

const __ = inject("$translate") || ((s) => s)
const employee = inject("$employee")

const poseInstructions = [
	__("Look straight at the camera"),
	__("Slowly turn your head 30° to the left"),
	__("Slowly turn your head 30° to the right"),
]

const poseIndex = ref(0)
const descriptors = ref([])
const errorMessage = ref("")
const captureRef = ref(null)

function onCaptured({ descriptor }) {
	descriptors.value.push(descriptor)
	if (poseIndex.value < 2) {
		poseIndex.value += 1
		// Re-arm capture for the next pose after a short pause.
		setTimeout(() => {
			captureRef.value?.start()
		}, 600)
	} else {
		captureRef.value?.stop()
	}
}

function onError(err) {
	errorMessage.value = err?.message || String(err)
}

function averageDescriptors(list) {
	if (!list.length) return []
	const dim = list[0].length
	const out = new Array(dim).fill(0)
	for (const d of list) for (let i = 0; i < dim; i++) out[i] += d[i]
	for (let i = 0; i < dim; i++) out[i] /= list.length
	return out
}

function submit() {
	const avg = averageDescriptors(descriptors.value)
	enrollFace.submit(
		{
			employee: employee?.data?.name,
			descriptor_json: JSON.stringify(avg),
		},
		{
			onSuccess() {
				toast({
					title: __("Enrolled"),
					text: __("Face enrolled successfully"),
					icon: "check-circle",
					iconClasses: "text-green-500",
					position: "bottom-center",
				})
			},
			onError(err) {
				errorMessage.value = err?.messages?.[0] || err?.message || __("Enrollment failed")
			},
		},
	)
}
</script>
