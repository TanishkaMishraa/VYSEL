#!/usr/bin/env node
/**
 * Self-hosts MediaPipe assets for the virtual try-on (runs before `next dev` / `next build`):
 *   public/mediapipe/wasm/*              ← copied from node_modules/@mediapipe/tasks-vision/wasm
 *   public/mediapipe/face_landmarker.task ← downloaded once from Google's model bucket
 *
 * Self-hosting means the browser never contacts Google during a try-on. If the download
 * fails (offline), we warn and continue: the app falls back to the hosted model URL.
 */
import { createWriteStream, existsSync, mkdirSync, readdirSync, copyFileSync, statSync, renameSync, unlinkSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, join } from 'node:path';
import { Readable } from 'node:stream';
import { pipeline } from 'node:stream/promises';
import { fileURLToPath } from 'node:url';

const webDir = join(dirname(fileURLToPath(import.meta.url)), '..');
const outDir = join(webDir, 'public', 'mediapipe');
const MODEL_URL = 'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task';
const modelPath = join(outDir, 'face_landmarker.task');

const require = createRequire(import.meta.url);
// The package doesn't export package.json; its main bundle sits beside wasm/.
const wasmSrc = join(dirname(require.resolve('@mediapipe/tasks-vision')), 'wasm');
const wasmOut = join(outDir, 'wasm');
mkdirSync(wasmOut, { recursive: true });
for (const file of readdirSync(wasmSrc)) copyFileSync(join(wasmSrc, file), join(wasmOut, file));
console.log(`[mediapipe] wasm runtime → public/mediapipe/wasm (${readdirSync(wasmOut).length} files)`);

if (existsSync(modelPath) && statSync(modelPath).size > 1_000_000) {
  console.log('[mediapipe] face_landmarker.task already present');
} else {
  const tmp = `${modelPath}.part`;
  try {
    const res = await fetch(MODEL_URL);
    if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);
    await pipeline(Readable.fromWeb(res.body), createWriteStream(tmp));
    renameSync(tmp, modelPath);
    console.log(`[mediapipe] face_landmarker.task downloaded (${(statSync(modelPath).size / 1e6).toFixed(1)} MB)`);
  } catch (err) {
    if (existsSync(tmp)) unlinkSync(tmp);
    console.warn(`[mediapipe] model download failed (${err.message}); try-on will load it from Google at runtime.`);
  }
}
