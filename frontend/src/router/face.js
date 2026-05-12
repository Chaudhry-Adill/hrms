import { faceConfig } from "@/data/face"

const routes = [
	{
		name: "FaceEnrollView",
		path: "/face/enroll",
		component: () => import("@/views/face/Enroll.vue"),
		meta: { requiresAuth: true },
		beforeEnter: (_to, _from, next) => {
			if (faceConfig.data?.mode === "Off") {
				return next({ name: "Home" })
			}
			next()
		},
	},
]

export default routes
