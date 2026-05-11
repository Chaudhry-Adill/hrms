const routes = [
	{
		name: "TicketListView",
		path: "/tickets",
		component: () => import("@/views/tickets/List.vue"),
		meta: { requiresAuth: true },
	},
	{
		name: "TicketFormView",
		path: "/tickets/new",
		component: () => import("@/views/tickets/Form.vue"),
		meta: { requiresAuth: true },
	},
	{
		name: "TicketDetailView",
		path: "/tickets/:name",
		props: true,
		component: () => import("@/views/tickets/Detail.vue"),
		meta: { requiresAuth: true },
	},
]

export default routes
