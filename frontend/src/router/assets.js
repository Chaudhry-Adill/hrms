const routes = [
	{
		name: "AssetListView",
		path: "/assets",
		component: () => import("@/views/assets/List.vue"),
		meta: { requiresAuth: true },
	},
	{
		name: "AssetRequestFormView",
		path: "/assets/new",
		component: () => import("@/views/assets/RequestForm.vue"),
		meta: { requiresAuth: true },
	},
	{
		name: "AssetDetailView",
		path: "/assets/:name",
		props: true,
		component: () => import("@/views/assets/Detail.vue"),
		meta: { requiresAuth: true },
	},
]

export default routes
