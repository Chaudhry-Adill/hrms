import { createRouter, createWebHistory } from "vue-router";

const routes = [
	{
		path: "/",
		name: "Home",
		component: () => import("./views/Home.vue"),
	},
	{
		path: "/rotations",
		name: "RotationEditor",
		component: () => import("./views/RotationEditor.vue"),
	},
];

const router = createRouter({
	history: createWebHistory("/hr"),
	routes,
});

export default router;
