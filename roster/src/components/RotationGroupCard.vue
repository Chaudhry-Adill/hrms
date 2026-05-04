<template>
	<div
		class="rounded-lg border p-4 bg-white shadow-sm"
		:class="{ 'ring-2 ring-blue-300': isDropTarget }"
		@dragover.prevent="$emit('dragover', $event)"
		@dragenter.prevent="$emit('dragenter', $event)"
		@dragleave="$emit('dragleave', $event)"
		@drop="$emit('drop', $event)"
	>
		<div class="flex items-center justify-between mb-2">
			<div class="text-base font-medium">{{ group.group_name }}</div>
			<div class="text-xs text-gray-500">offset: {{ group.offset_weeks }}w</div>
		</div>

		<div class="flex flex-wrap gap-2">
			<div
				v-for="member in group.members"
				:key="member.employee"
				class="px-2 py-1 bg-gray-100 rounded-full text-sm cursor-grab flex items-center gap-2"
				:draggable="true"
				@dragstart="
					(e) => {
						if (e.dataTransfer) {
							e.dataTransfer.effectAllowed = 'move';
							e.dataTransfer.setData(
								'application/json',
								JSON.stringify({
									employee: member.employee,
									group: group.group_name,
								}),
							);
						}
						$emit('member-dragstart', member, group);
					}
				"
				@dragend="$emit('member-dragend')"
			>
				<Avatar
					v-if="member.image"
					:label="member.employee_name || member.employee"
					:image="member.image"
					size="sm"
				/>
				<span>{{ member.employee_name || member.employee }}</span>
			</div>

			<div
				v-if="!group.members?.length"
				class="text-xs text-gray-400 italic"
			>
				No members
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { Avatar } from "frappe-ui";

interface Member {
	employee: string;
	employee_name?: string;
	image?: string;
}

interface Group {
	group_name: string;
	offset_weeks: number;
	members: Member[];
}

defineProps<{
	group: Group;
	isDropTarget?: boolean;
}>();

defineEmits<{
	(e: "member-dragstart", member: Member, group: Group): void;
	(e: "member-dragend"): void;
	(e: "dragover", event: DragEvent): void;
	(e: "dragenter", event: DragEvent): void;
	(e: "dragleave", event: DragEvent): void;
	(e: "drop", event: DragEvent): void;
}>();
</script>
