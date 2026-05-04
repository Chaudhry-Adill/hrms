<template>
	<div class="p-4 space-y-4">
		<div class="flex items-center justify-between">
			<div>
				<h1 class="text-xl font-semibold">Rotation Editor</h1>
				<p class="text-sm text-gray-500" v-if="rotation.data">
					{{ rotation.data.rotation_name }} — cycle of
					{{ rotation.data.cycle_length_weeks }} weeks, starts
					{{ rotation.data.start_date }}
				</p>
			</div>
			<Autocomplete
				:options="rotationOptions"
				v-model="selectedRotation"
				placeholder="Select rotation"
				class="w-72"
			/>
		</div>

		<!-- Groups -->
		<div
			v-if="rotation.data"
			class="grid gap-3"
			:style="{
				gridTemplateColumns: `repeat(${Math.min(rotation.data.groups.length, 3)}, minmax(0, 1fr))`,
			}"
		>
			<RotationGroupCard
				v-for="grp in rotation.data.groups"
				:key="grp.group_name"
				:group="grp"
				:is-drop-target="dropTargetGroup === grp.group_name"
				@member-dragstart="onMemberDragStart"
				@member-dragend="onMemberDragEnd"
				@dragenter="dropTargetGroup = grp.group_name"
				@dragleave="dropTargetGroup = ''"
				@drop="onGroupDrop(grp)"
			/>
		</div>

		<!-- Calendar grid: rows = groups, cols = weeks-in-cycle -->
		<div
			v-if="rotation.data && preview.data"
			class="rounded-lg border overflow-auto"
		>
			<table class="border-separate border-spacing-0 w-full">
				<thead>
					<tr class="bg-gray-50">
						<th class="text-left p-2 border-b text-sm font-medium">
							Group / Week
						</th>
						<th
							v-for="w in cycleWeeks"
							:key="w"
							class="p-2 border-b border-l text-sm font-medium"
						>
							Week {{ w }}
						</th>
					</tr>
				</thead>
				<tbody>
					<tr v-for="(grp, gIdx) in rotation.data.groups" :key="grp.group_name">
						<td class="p-2 border-t text-sm font-medium">
							{{ grp.group_name }}
						</td>
						<td
							v-for="w in cycleWeeks"
							:key="`${grp.group_name}-${w}`"
							class="p-2 border-t border-l align-top text-sm"
							:class="gIdx === 0 ? '' : ''"
						>
							<div
								v-for="entry in cellEntries(grp.group_name, w)"
								:key="`${entry.shift_type}-${entry.employee}`"
								class="rounded px-2 py-1 mb-1 text-xs"
								:style="{
									backgroundColor: shiftColor(entry.shift_type, 50),
									borderLeft: `3px solid ${shiftColor(entry.shift_type, 400)}`,
								}"
							>
								<div class="font-medium">{{ entry.shift_type }}</div>
								<div class="text-gray-600 truncate">
									{{ entry.employee_name || entry.employee }}
								</div>
							</div>
						</td>
					</tr>
				</tbody>
			</table>
		</div>

		<div v-else-if="rotation.loading" class="text-gray-500">Loading…</div>
	</div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from "vue";
import { Autocomplete, createResource } from "frappe-ui";
import colors from "tailwindcss/colors";

import RotationGroupCard from "../components/RotationGroupCard.vue";

interface Member {
	employee: string;
	employee_name?: string;
}

interface Group {
	group_name: string;
	offset_weeks: number;
	members: Member[];
}

interface Pattern {
	week_index: number;
	shift_type: string;
	repeat_on_days: string;
}

interface RotationDoc {
	name: string;
	rotation_name: string;
	start_date: string;
	cycle_length_weeks: number;
	patterns: Pattern[];
	groups: Group[];
}

interface PreviewRow {
	date: string;
	employee: string;
	employee_name?: string;
	shift_type: string;
	group_name: string;
	week_in_cycle: number;
}

const selectedRotation = ref<{ value: string; label: string } | null>(null);

const draggedMember = ref<Member | null>(null);
const draggedFromGroup = ref<string | null>(null);
const dropTargetGroup = ref("");

const palette: Array<keyof typeof colors> = [
	"blue",
	"green",
	"orange",
	"pink",
	"violet",
	"cyan",
	"red",
	"lime",
	"yellow",
	"fuchsia",
];

function shiftColor(shiftType: string, shade: 50 | 200 | 300 | 400 = 50) {
	let hash = 0;
	for (let i = 0; i < shiftType.length; i++) hash = (hash << 5) - hash + shiftType.charCodeAt(i);
	const idx = Math.abs(hash) % palette.length;
	const family = colors[palette[idx]] as Record<string, string>;
	return family[String(shade)] || family["100"];
}

const rotationList = createResource({
	url: "frappe.client.get_list",
	auto: true,
	makeParams() {
		return {
			doctype: "Shift Rotation",
			fields: ["name", "rotation_name"],
			filters: { docstatus: 1 },
			limit_page_length: 200,
		};
	},
});

const rotationOptions = computed(() =>
	(rotationList.data || []).map((r: { name: string; rotation_name: string }) => ({
		value: r.name,
		label: `${r.rotation_name} (${r.name})`,
	})),
);

const rotation = createResource({
	url: "frappe.client.get",
	makeParams() {
		return { doctype: "Shift Rotation", name: selectedRotation.value?.value };
	},
	transform: (data: RotationDoc) => data,
});

const preview = createResource({
	url: "hrms.api.rotation.preview_rotation",
	makeParams() {
		return {
			rotation: selectedRotation.value?.value,
			weeks_ahead: rotation.data ? rotation.data.cycle_length_weeks : 4,
		};
	},
	transform: (data: PreviewRow[]) => data,
});

const swap = createResource({
	url: "hrms.api.rotation.swap_employees",
	onSuccess() {
		rotation.fetch();
		preview.fetch();
	},
});

watch(selectedRotation, (val) => {
	if (val?.value) {
		rotation.fetch();
		preview.fetch();
	}
});

const cycleWeeks = computed(() => {
	if (!rotation.data) return [];
	return Array.from({ length: rotation.data.cycle_length_weeks }, (_, i) => i + 1);
});

function cellEntries(groupName: string, weekIdx: number): PreviewRow[] {
	if (!preview.data) return [];
	const seen = new Set<string>();
	const out: PreviewRow[] = [];
	for (const row of preview.data) {
		if (row.group_name !== groupName || row.week_in_cycle !== weekIdx) continue;
		const key = `${row.shift_type}::${row.employee}`;
		if (seen.has(key)) continue;
		seen.add(key);
		out.push(row);
	}
	return out;
}

function onMemberDragStart(member: Member, group: Group) {
	draggedMember.value = member;
	draggedFromGroup.value = group.group_name;
}

function onMemberDragEnd() {
	draggedMember.value = null;
	draggedFromGroup.value = null;
	dropTargetGroup.value = "";
}

function onGroupDrop(targetGroup: Group) {
	if (
		!draggedMember.value ||
		!draggedFromGroup.value ||
		draggedFromGroup.value === targetGroup.group_name ||
		!rotation.data
	)
		return;

	const targetMember = targetGroup.members?.[0];
	if (!targetMember) return;

	const today = new Date().toISOString().slice(0, 10);
	swap.submit({
		rotation: rotation.data.name,
		employee_a: draggedMember.value.employee,
		employee_b: targetMember.employee,
		effective_date: today,
	});

	onMemberDragEnd();
}
</script>
