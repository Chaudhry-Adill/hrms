const routes = [
	{
		name: "OffboardingStatusView",
		path: "/offboarding",
		component: () => import("@/views/offboarding/Status.vue"),
		meta: { requiresAuth: true },
	},
]

export default routes
