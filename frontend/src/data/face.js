// Phase 4.2 Face Detection Check-in — frappe-ui resources.
//
// PRIVACY: We send only descriptors (128-d float arrays). Raw frames stay
// in the browser.
import { createResource } from "frappe-ui"

import { employeeResource } from "./employee"

export const faceConfig = createResource({
	url: "hrms.api.face.get_config",
	cache: "hrms:face_config",
	auto: true,
})

export const enrollmentStatus = createResource({
	url: "hrms.api.face.get_enrollment_status",
	params: {
		employee: employeeResource.data?.name,
	},
	cache: "hrms:face_enrollment_status",
})

export const enrollFace = createResource({
	url: "hrms.api.face.enroll",
})

export const verifyFace = createResource({
	url: "hrms.api.face.verify",
})
