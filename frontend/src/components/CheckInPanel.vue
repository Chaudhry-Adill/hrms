<template>
	<div class="flex flex-col bg-white rounded w-full py-6 px-4 border-none">
		<h2 class="text-lg font-bold text-gray-900">
			{{ __("Hey, {0} 👋", [employee?.data?.first_name]) }}
		</h2>

		<template v-if="settings.data?.allow_employee_checkin_from_mobile_app">
			<div class="font-medium text-sm text-gray-500 mt-1.5" v-if="lastLog">
				<span>{{ __("Last {0} was at {1}", [__(lastLogType), formatTimestamp(lastLog.time)]) }}</span>
				<span class="whitespace-pre"> &middot; </span>
				<router-link :to="{ name: 'EmployeeCheckinListView' }" v-slot="{ navigate }">
					<span @click="navigate" class="underline">View List</span>
				</router-link>
			</div>
			<Button
				class="mt-4 mb-1 drop-shadow-sm py-5 text-base"
				id="open-checkin-modal"
				@click="handleEmployeeCheckin"
			>
				<template #prefix>
					<FeatherIcon
						:name="nextAction.action === 'IN' ? 'arrow-right-circle' : 'arrow-left-circle'"
						class="w-4"
					/>
				</template>
				{{ nextAction.label }}
			</Button>
		</template>

		<div v-else class="font-medium text-sm text-gray-500 mt-1.5">
			{{ dayjs().format("ddd, D MMMM, YYYY") }}
		</div>
	</div>

	<ion-modal
		v-if="settings.data?.allow_employee_checkin_from_mobile_app"
		ref="modal"
		trigger="open-checkin-modal"
		:initial-breakpoint="1"
		:breakpoints="[0, 1]"
	>
		<div class="h-120 w-full flex flex-col items-center justify-center gap-5 p-4 mb-5">
			<div class="flex flex-col gap-1.5 mt-2 items-center justify-center">
				<div class="font-bold text-xl">
					{{ dayjs(checkinTimestamp).format("hh:mm:ss a") }}
				</div>
				<div class="font-medium text-gray-500 text-sm">
					{{ dayjs().format("D MMM, YYYY") }}
				</div>
			</div>

			<template v-if="settings.data?.allow_geolocation_tracking">
				<span v-if="locationStatus" class="font-medium text-gray-500 text-sm">
					{{ locationStatus }}
				</span>

				<GeofenceStatusPill
					v-if="geofenceMode !== 'Off' && primaryFence"
					:distance-m="distanceM"
					:radius-m="primaryFence.radius_m"
					:mode="geofenceMode"
				/>

				<span
					v-if="geofenceMode === 'Block' && distanceM !== null && !inRange"
					class="text-xs font-medium text-red-600"
				>
					{{ __("You must be within the fence to check in") }}
				</span>
				<span
					v-else-if="geofenceMode === 'Warn' && distanceM !== null && !inRange"
					class="text-xs font-medium text-yellow-700"
				>
					{{ __("You are outside the geofence — check-in will be flagged") }}
				</span>

				<div class="rounded border-4 translate-z-0 block overflow-hidden w-full h-170">
					<iframe
						width="100%"
						height="170"
						frameborder="0"
						scrolling="no"
						marginheight="0"
						marginwidth="0"
						style="border: 0"
						:src="`https://maps.google.com/maps?q=${latitude},${longitude}&hl=en&z=15&amp;output=embed`"
					>
					</iframe>
				</div>
			</template>

			<template v-if="faceMode === 'Required'">
				<FaceCapture
					:auto-start="true"
					:require-liveness="faceRequireLiveness"
					@captured="onFaceCaptured"
				/>
				<span
					v-if="faceMatched"
					class="text-xs font-medium text-green-700"
				>
					{{ __("Face verified") }}
				</span>
				<span
					v-else-if="faceError"
					class="text-xs font-medium text-red-600"
				>
					{{ faceError }}
				</span>
				<span v-else class="text-xs font-medium text-gray-500">
					{{ __("Face verification required to continue") }}
				</span>
			</template>

			<Button
				:loading="checkins.insert.loading"
				:disabled="submitDisabled"
				variant="solid"
				class="w-full py-5 text-sm disabled:bg-gray-700"
				@click="submitLog(nextAction.action)"
			>
				{{ __("Confirm {0}", [nextAction.label]) }}
			</Button>
		</div>
	</ion-modal>
</template>

<script setup>
import { createListResource, toast, FeatherIcon } from "frappe-ui"
import { computed, inject, ref, onMounted, onBeforeUnmount } from "vue"
import { IonModal, modalController } from "@ionic/vue"

import { formatTimestamp } from "@/utils/formatters"
import { settings } from "@/data/settings"
import { resolveFence } from "@/data/attendance"
import { faceConfig, verifyFace } from "@/data/face"
import GeofenceStatusPill from "@/components/GeofenceStatusPill.vue"
import FaceCapture from "@/components/FaceCapture.vue"

const DOCTYPE = "Employee Checkin"

const socket = inject("$socket")
const employee = inject("$employee")
const dayjs = inject("$dayjs")
const __ = inject("$translate")
const checkinTimestamp = ref(null)
const latitude = ref(0)
const longitude = ref(0)
const locationStatus = ref("")
const distanceM = ref(null)

const checkins = createListResource({
	doctype: DOCTYPE,
	fields: ["name", "employee", "employee_name", "log_type", "time", "device_id"],
	filters: {
		employee: employee.data.name,
	},
	orderBy: "time desc",
})
checkins.reload()

const lastLog = computed(() => {
	if (checkins.list.loading || !checkins.data) return {}
	return checkins.data[0]
})

const lastLogType = computed(() => {
	return lastLog?.value?.log_type === "IN" ? "check-in" : "check-out"
})

const nextAction = computed(() => {
	return lastLog?.value?.log_type === "IN"
		? { action: "OUT", label: __("Check Out") }
		: { action: "IN", label: __("Check In") }
})

function handleLocationSuccess(position) {
	latitude.value = position.coords.latitude
	longitude.value = position.coords.longitude

	locationStatus.value = [
		__("Latitude: {0}°", [Number(latitude.value).toFixed(5)]),
		__("Longitude: {0}°", [Number(longitude.value).toFixed(5)]),
	].join(", ")

	if (primaryFence.value) {
		distanceM.value = haversineMeters(
			latitude.value,
			longitude.value,
			primaryFence.value.lat,
			primaryFence.value.lng,
		)
	}
}

function handleLocationError(error) {
	locationStatus.value = "Unable to retrieve your location"
	if (error) locationStatus.value += `: ERROR(${error.code}): ${error.message}`
}

const fetchLocation = () => {
	if (!navigator.geolocation) {
		locationStatus.value = __("Geolocation is not supported by your current browser")
	} else {
		locationStatus.value = __("Locating...")
		navigator.geolocation.getCurrentPosition(handleLocationSuccess, handleLocationError)
	}
}

function haversineMeters(lat1, lng1, lat2, lng2) {
	const r = 6371
	const p = Math.PI / 180
	const a =
		0.5 -
		Math.cos((lat2 - lat1) * p) / 2 +
		(Math.cos(lat1 * p) *
			Math.cos(lat2 * p) *
			(1 - Math.cos((lng2 - lng1) * p))) /
			2
	return 2 * r * Math.asin(Math.sqrt(a)) * 1000
}

const geofenceMode = computed(() => resolveFence.data?.mode || "Off")
const primaryFence = computed(() => {
	const fences = resolveFence.data?.fences || []
	return fences.length ? fences[0] : null
})
const inRange = computed(() => {
	if (distanceM.value == null || !primaryFence.value) return false
	return distanceM.value <= (primaryFence.value.radius_m || 0)
})

// ---------- Phase 4.2: face verification ---------------------------------
const faceMode = computed(() => faceConfig.data?.mode || "Off")
const faceRequireLiveness = computed(() => !!faceConfig.data?.require_liveness)
const faceVerificationLog = ref(null)
const faceMatched = ref(false)
const faceError = ref("")

const faceBlocksSubmit = computed(() => {
	if (faceMode.value !== "Required") return false
	return !faceMatched.value
})

const submitDisabled = computed(() => {
	if (geofenceMode.value !== "Block") {
		// Geofence does not block, but face mode might.
		return faceBlocksSubmit.value
	}
	if (!primaryFence.value) return faceBlocksSubmit.value
	if (distanceM.value == null) return true
	return !inRange.value || faceBlocksSubmit.value
})

const onFaceCaptured = ({ descriptor, livenessPassed }) => {
	faceError.value = ""
	verifyFace.submit(
		{
			employee: employee.data.name,
			descriptor_json: JSON.stringify(descriptor),
			with_liveness: livenessPassed ? 1 : 0,
		},
		{
			onSuccess(result) {
				if (result?.matched) {
					faceMatched.value = true
					faceVerificationLog.value = result.log_name
				} else {
					faceMatched.value = false
					faceError.value = __("Face did not match — please retry")
				}
			},
			onError(err) {
				faceError.value =
					err?.messages?.[0] || err?.message || __("Face verification failed")
			},
		},
	)
}

const handleEmployeeCheckin = () => {
	checkinTimestamp.value = dayjs().format("YYYY-MM-DD HH:mm:ss")

	// Reset face state per modal-open.
	faceMatched.value = false
	faceVerificationLog.value = null
	faceError.value = ""
	faceConfig.reload?.()

	if (settings.data?.allow_geolocation_tracking) {
		distanceM.value = null
		resolveFence.fetch({
			employee: employee.data.name,
			timestamp: checkinTimestamp.value,
		})
		fetchLocation()
	}
}

const submitLog = (logType) => {
	const actionLabel = logType === "IN" ? __("Check-in") : __("Check-out")

	const payload = {
		employee: employee.data.name,
		log_type: logType,
		time: checkinTimestamp.value,
		latitude: latitude.value,
		longitude: longitude.value,
	}
	if (faceVerificationLog.value) {
		payload.face_verification_log = faceVerificationLog.value
	}

	checkins.insert.submit(
		payload,
		{
			onSuccess() {
				modalController.dismiss()
				toast({
					title: __("Success"),
					text: __("{0} successful!", [actionLabel]),
					icon: "check-circle",
					position: "bottom-center",
					iconClasses: "text-green-500",
				})
			},
			onError(error) {
				let messages = error.messages || []

				for (const message of messages) {
					toast({
						title: __("Error"),
						text: message || __("{0} failed!", [actionLabel]),
						icon: "alert-circle",
						position: "bottom-center",
						iconClasses: "text-red-500",
					})
				}
			},
		}
	)
}

onMounted(() => {
	socket.emit("doctype_subscribe", DOCTYPE)
	socket.on("list_update", (data) => {
		if (data.doctype == DOCTYPE) {
			checkins.reload()
		}
	})
})

onBeforeUnmount(() => {
	socket.emit("doctype_unsubscribe", DOCTYPE)
	socket.off("list_update")
})
</script>
