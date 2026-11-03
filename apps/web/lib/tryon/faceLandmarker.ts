/**
 * Lazy, shared MediaPipe FaceLandmarker (the Face Mesh model, 478 landmarks).
 * The library (~1 MB JS + WASM + 3.8 MB model) loads only when a try-on starts,
 * from /public/mediapipe (self-hosted by scripts/fetch-mediapipe-assets.mjs).
 * All inference runs in the browser; frames never leave the device.
 */

import type { FaceLandmarker } from '@mediapipe/tasks-vision';

const WASM_BASE = '/mediapipe/wasm';
const LOCAL_MODEL = '/mediapipe/face_landmarker.task';
const HOSTED_MODEL = 'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task';

export type RunningMode = 'VIDEO' | 'IMAGE';

let instance: Promise<FaceLandmarker> | null = null;
let currentMode: RunningMode = 'VIDEO';

async function create(): Promise<FaceLandmarker> {
  const { FaceLandmarker, FilesetResolver } = await import('@mediapipe/tasks-vision');
  const fileset = await FilesetResolver.forVisionTasks(WASM_BASE);
  const options = (modelAssetPath: string, delegate: 'GPU' | 'CPU') => ({
    baseOptions: { modelAssetPath, delegate },
    runningMode: currentMode,
    numFaces: 1,
    minFaceDetectionConfidence: 0.5,
    minFacePresenceConfidence: 0.5,
    minTrackingConfidence: 0.5,
    outputFaceBlendshapes: false,
  });
  // GPU first (fast); CPU if WebGL is unavailable. Local model first; hosted if it's missing.
  for (const model of [LOCAL_MODEL, HOSTED_MODEL]) {
    for (const delegate of ['GPU', 'CPU'] as const) {
      try {
        return await FaceLandmarker.createFromOptions(fileset, options(model, delegate));
      } catch (err) {
        console.warn(`[try-on] FaceLandmarker init failed (${delegate}, ${model}):`, err);
      }
    }
  }
  throw new Error('Face tracking could not start on this device.');
}

export async function getFaceLandmarker(mode: RunningMode): Promise<FaceLandmarker> {
  if (!instance) {
    currentMode = mode;
    instance = create().catch((err) => {
      instance = null; // allow a retry
      throw err;
    });
  }
  const landmarker = await instance;
  if (mode !== currentMode) {
    await landmarker.setOptions({ runningMode: mode });
    currentMode = mode;
  }
  return landmarker;
}
