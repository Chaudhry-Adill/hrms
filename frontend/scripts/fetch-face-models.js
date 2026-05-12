#!/usr/bin/env node
/**
 * fetch-face-models.js — Phase 4.2 Face Detection Check-in
 *
 * Downloads the face-api.js model weights into frontend/public/face-models/.
 * Run manually before the first build (or in CI):
 *
 *     yarn fetch-face-models
 *
 * Total download size: ~10 MB (compressed). The PWA lazy-loads the models
 * only when HR Settings.face_verification_mode != "Off", so users with face
 * mode disabled never pay the download cost.
 *
 * PRIVACY NOTE: face-api.js (MIT-licensed; vincentmuhler/face-api.js)
 * runs entirely in the browser. The descriptor is computed locally and
 * sent over to /api/method/hrms.api.face.verify. No frames are uploaded.
 *
 * Models downloaded (from the upstream weights repo):
 *   - tiny_face_detector_model
 *   - face_landmark_68_model
 *   - face_recognition_model
 *
 * Each model has a manifest (.json) plus one or more shard files (-shard1).
 */
import fs from "node:fs"
import path from "node:path"
import https from "node:https"
import { fileURLToPath } from "node:url"

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

const OUT_DIR = path.resolve(__dirname, "..", "public", "face-models")
// Pinned to a specific commit SHA so builds are reproducible and not
// vulnerable to a compromise of the master branch.
const BASE = "https://raw.githubusercontent.com/vladmandic/face-api/189226d63aabb48cb40776fd1c453ebc0fa722f1/model"

const FILES = [
	"tiny_face_detector_model-weights_manifest.json",
	"tiny_face_detector_model.bin",
	"face_landmark_68_model-weights_manifest.json",
	"face_landmark_68_model.bin",
	"face_recognition_model-weights_manifest.json",
	"face_recognition_model.bin",
]

function download(url, outPath) {
	return new Promise((resolve, reject) => {
		const file = fs.createWriteStream(outPath)
		https
			.get(url, (res) => {
				if (res.statusCode === 302 || res.statusCode === 301) {
					return download(res.headers.location, outPath).then(resolve).catch(reject)
				}
				if (res.statusCode !== 200) {
					reject(new Error(`HTTP ${res.statusCode} for ${url}`))
					return
				}
				res.pipe(file)
				file.on("finish", () => file.close(() => resolve()))
			})
			.on("error", (err) => {
				fs.unlink(outPath, () => reject(err))
			})
	})
}

async function main() {
	if (!fs.existsSync(OUT_DIR)) {
		fs.mkdirSync(OUT_DIR, { recursive: true })
	}
	for (const filename of FILES) {
		const url = `${BASE}/${filename}`
		const outPath = path.join(OUT_DIR, filename)
		if (fs.existsSync(outPath)) {
			console.log(`skip ${filename} (already exists)`)
			continue
		}
		console.log(`fetch ${filename}`)
		await download(url, outPath)
	}
	console.log("done.")
}

main().catch((err) => {
	console.error(err)
	process.exit(1)
})
