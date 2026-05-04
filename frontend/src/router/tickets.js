const routes = [
	{
		name: "TicketListView",
		path: "/tickets",
		component: () => import("@/views/tickets/List.vue"),
	},
	{
		name: "TicketFormView",
		path: "/tickets/new",
		component: () => import("@/views/tickets/Form.vue"),
	},
	{
		name: "TicketDetailView",
		path: "/tickets/:name",
		props: true,
		component: () => import("@/views/tickets/Detail.vue"),
	},
]

export default routes
