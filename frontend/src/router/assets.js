const routes = [
	{
		name: "AssetListView",
		path: "/assets",
		component: () => import("@/views/assets/List.vue"),
	},
	{
		name: "AssetRequestFormView",
		path: "/assets/new",
		component: () => import("@/views/assets/RequestForm.vue"),
	},
	{
		name: "AssetDetailView",
		path: "/assets/:name",
		props: true,
		component: () => import("@/views/assets/Detail.vue"),
	},
]

export default routes
