<template>
	<!--
	  FaceCapture.vue (Phase 4.2)

	  Streams the front-facing camera, detects a face on each frame using
	  face-api.js, and emits a 128-d descriptor once detection is stable.
	  No frames are uploaded — only the descriptor returned by tinyFaceDetector
	  + faceLandmarkNet + faceRecognitionNet.

	  Liveness (optional) is a coarse blink-detection on the eye-aspect-ratio
	  (EAR) computed from the 68-point landmarks. This is NOT anti-spoofing
	  grade — see the discovery-spike open question on liveness vendors.
	-->
	<div class="flex flex-col items-center gap-3 w-full">
		<div class="relative w-full max-w-xs aspect-[3/4] rounded-lg overflow-hidden bg-gray-200">
			<video
				ref="videoEl"
				class="w-full h-full object-cover"
				autoplay
				playsinline
				muted
			/>
			<canvas
				ref="overlayEl"
				class="absolute inset-0 w-full h-full pointer-events-none"
			/>
			<div
				v-if="status"
				class="absolute bottom-0 inset-x-0 bg-black/50 text-white text-xs font-medium text-center py-1"
			>
				{{ status }}
			</div>
		</div>

		<div v-if="requireLiveness" class="text-xs font-medium text-gray-600">
			{{ __("Please blink to confirm liveness") }}
		</div>

		<div v-if="errorMessage" class="text-xs font-medium text-red-600">
			{{ errorMessage }}
		</div>
	</div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, inject } from "vue"

const __ = inject("$translate") || ((s) => s)

const props = defineProps({
	requireLiveness: { type: Boolean, default: false },
	autoStart: { type: Boolean, default: true },
	stableFrames: { type: Number, default: 8 },
})

const emit = defineEmits(["captured", "error"])

const videoEl = ref(null)
const overlayEl = ref(null)
const status = ref("")
const errorMessage = ref("")

let stream = null
let rafId = null
let faceapi = null
let modelsLoaded = false
let stableCount = 0
let earHistory = []
let blinkSeen = false
let captured = false

const MODELS_URL = "/assets/hrms/frontend/face-models"
const EAR_BLINK_THRESHOLD = 0.21
const EAR_HISTORY = 30

async function loadModels() {
	// Lazy-import face-api.js so the bundle doesn't pay for it on screens
	// that don't need face detection.
	faceapi = await import("face-api.js")
	await Promise.all([
		faceapi.nets.tinyFaceDetector.loadFromUri(MODELS_URL),
		faceapi.nets.faceLandmark68Net.loadFromUri(MODELS_URL),
		faceapi.nets.faceRecognitionNet.loadFromUri(MODELS_URL),
	])
	modelsLoaded = true
}

async function startCamera() {
	try {
		stream = await navigator.mediaDevices.getUserMedia({
			video: { facingMode: "user", width: 480, height: 640 },
			audio: false,
		})
		if (videoEl.value) {
			videoEl.value.srcObject = stream
			await videoEl.value.play()
		}
	} catch (err) {
		errorMessage.value = __("Unable to access camera: ") + (err?.message || err)
		emit("error", err)
		throw err
	}
}

function eyeAspectRatio(eye) {
	// 6-point eye: indices [0..5]. EAR = (||p2-p6|| + ||p3-p5||) / (2 * ||p1-p4||)
	const dist = (a, b) => Math.hypot(a.x - b.x, a.y - b.y)
	return (
		(dist(eye[1], eye[5]) + dist(eye[2], eye[4])) /
		(2 * dist(eye[0], eye[3]) + 1e-6)
	)
}

async function loop() {
	if (captured || !videoEl.value || !modelsLoaded) {
		rafId = requestAnimationFrame(loop)
		return
	}

	try {
		const detection = await faceapi
			.detectSingleFace(
				videoEl.value,
				new faceapi.TinyFaceDetectorOptions({ inputSize: 224, scoreThreshold: 0.5 }),
			)
			.withFaceLandmarks()
			.withFaceDescriptor()

		if (!detection) {
			status.value = __("No face detected — center your face")
			stableCount = 0
		} else {
			stableCount += 1
			status.value = __("Hold still…") + ` (${stableCount}/${props.stableFrames})`

			if (props.requireLiveness) {
				const left = detection.landmarks.getLeftEye()
				const right = detection.landmarks.getRightEye()
				const ear = (eyeAspectRatio(left) + eyeAspectRatio(right)) / 2
				earHistory.push(ear)
				if (earHistory.length > EAR_HISTORY) earHistory.shift()
				// Look for at least two consecutive frames below the threshold.
				let belowRun = 0
				for (const e of earHistory) {
					if (e < EAR_BLINK_THRESHOLD) {
						belowRun += 1
						if (belowRun >= 2) {
							blinkSeen = true
							break
						}
					} else {
						belowRun = 0
					}
				}
			}

			const ready = stableCount >= props.stableFrames
			const livenessOk = !props.requireLiveness || blinkSeen
			if (ready && livenessOk) {
				captured = true
				const descriptor = Array.from(detection.descriptor)
				emit("captured", { descriptor, livenessPassed: blinkSeen })
				status.value = __("Captured")
			} else if (ready && !livenessOk) {
				status.value = __("Please blink")
			}
		}
	} catch (err) {
		// Detection errors are common on first frames — keep looping.
		// eslint-disable-next-line no-console
		console.warn("face-api detect error", err)
	}

	rafId = requestAnimationFrame(loop)
}

function stopCamera() {
	if (rafId) cancelAnimationFrame(rafId)
	rafId = null
	if (stream) {
		stream.getTracks().forEach((t) => t.stop())
		stream = null
	}
}

async function start() {
	captured = false
	stableCount = 0
	earHistory = []
	blinkSeen = false
	status.value = __("Loading models…")
	try {
		if (!modelsLoaded) await loadModels()
		await startCamera()
		status.value = __("Detecting…")
		loop()
	} catch (err) {
		// Already surfaced via errorMessage.
	}
}

defineExpose({ start, stop: stopCamera })

onMounted(() => {
	if (props.autoStart) start()
})

onBeforeUnmount(() => {
	stopCamera()
})
</script>
