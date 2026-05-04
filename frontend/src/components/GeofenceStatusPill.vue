<template>
  <div
    class="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium"
    :class="pillClasses"
  >
    <span
      class="inline-block h-2 w-2 rounded-full"
      :class="dotClasses"
    />
    <span>{{ label }}</span>
  </div>
</template>

<script setup>
import { computed, inject } from "vue"

const __ = inject("$translate")

const props = defineProps({
  distanceM: {
    type: Number,
    default: null,
  },
  radiusM: {
    type: Number,
    default: 0,
  },
  mode: {
    type: String,
    default: "Off",
  },
})

const inRange = computed(() => {
  if (props.distanceM == null || !props.radiusM) return false
  return props.distanceM <= props.radiusM
})

const distanceLabel = computed(() => {
  if (props.distanceM == null) return __("Locating...")
  const d = Math.round(props.distanceM)
  return __("{0}m / {1}m", [d, Math.round(props.radiusM || 0)])
})

const label = computed(() => {
  if (props.distanceM == null) return __("Locating...")
  if (inRange.value) return __("In range") + " (" + distanceLabel.value + ")"
  if (props.mode === "Block")
    return __("Out of range") + " (" + distanceLabel.value + ")"
  return __("Out of range") + " (" + distanceLabel.value + ")"
})

const pillClasses = computed(() => {
  if (props.distanceM == null) return "bg-gray-100 text-gray-700"
  if (inRange.value) return "bg-green-100 text-green-800"
  if (props.mode === "Block") return "bg-red-100 text-red-800"
  return "bg-yellow-100 text-yellow-800"
})

const dotClasses = computed(() => {
  if (props.distanceM == null) return "bg-gray-400"
  if (inRange.value) return "bg-green-500"
  if (props.mode === "Block") return "bg-red-500"
  return "bg-yellow-500"
})
</script>
