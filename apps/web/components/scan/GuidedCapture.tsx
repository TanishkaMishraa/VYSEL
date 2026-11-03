'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { Button } from '@vysel/ui';
import { getFaceLandmarker } from '@/lib/tryon/faceLandmarker';

type Pose = { yaw: number; pitch: number; roll: number; size: number; centered: boolean };
type Step = 'straight' | 'left' | 'right' | 'up' | 'down';
const STEPS: Step[] = ['straight', 'left', 'right', 'up', 'down'];
function configuredAngle(name: string, fallback: number): number {
  const value = Number(process.env[`NEXT_PUBLIC_FACE_GUIDE_${name}_DEGREES`]);
  return Number.isFinite(value) && value > 0 && value <= 45 ? value : fallback;
}
const THRESHOLDS = { yaw: configuredAngle('YAW', 9), pitch: configuredAngle('PITCH', 4), roll: configuredAngle('ROLL', 12), minFaceWidth: 0.22, maxFaceWidth: 0.72, centerTolerance: 0.2, minBrightness: 35, maxBrightness: 225, minSharpness: 18 };
const LABELS: Record<Step, string> = { straight: 'Look straight at the camera', left: 'Turn your head to your left', right: 'Turn your head to your right', up: 'Tilt your chin upward', down: 'Tilt your chin downward' };

function shuffleSteps(): Step[] {
  const movements = STEPS.slice(1);
  for (let i = movements.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [movements[i], movements[j]] = [movements[j], movements[i]];
  }
  return ['straight', ...movements, 'straight'];
}

function measure(landmarks: { x: number; y: number }[]): Pose {
  const leftEye = landmarks[33], rightEye = landmarks[263], nose = landmarks[1];
  const left = landmarks[234], right = landmarks[454];
  const eyeDistance = Math.hypot(rightEye.x - leftEye.x, rightEye.y - leftEye.y) || 1;
  const faceWidth = Math.abs(right.x - left.x);
  const eyeMidX = (leftEye.x + rightEye.x) / 2;
  const eyeMidY = (leftEye.y + rightEye.y) / 2;
  const faceHeight = Math.abs(landmarks[152].y - landmarks[10].y) || 1;
  return {
    // Landmark ratios provide normalized pose angles without assuming a phone or camera model.
    yaw: Math.atan((nose.x - eyeMidX) / eyeDistance) * 180 / Math.PI,
    pitch: Math.atan((nose.y - eyeMidY) / faceHeight) * 180 / Math.PI,
    roll: Math.atan2(rightEye.y - leftEye.y, rightEye.x - leftEye.x) * 180 / Math.PI,
    size: faceWidth,
    centered: Math.abs((left.x + right.x) / 2 - 0.5) <= THRESHOLDS.centerTolerance && Math.abs((landmarks[10].y + landmarks[152].y) / 2 - 0.5) <= THRESHOLDS.centerTolerance,
  };
}

function movementReached(step: Step, current: Pose, baseline: Pose): boolean {
  if (step === 'straight') return Math.abs(current.yaw - baseline.yaw) < THRESHOLDS.yaw * 0.6 && Math.abs(current.pitch - baseline.pitch) < THRESHOLDS.pitch;
  if (step === 'left') return current.yaw - baseline.yaw > THRESHOLDS.yaw;
  if (step === 'right') return baseline.yaw - current.yaw > THRESHOLDS.yaw;
  if (step === 'up') return current.pitch - baseline.pitch < -THRESHOLDS.pitch;
  return current.pitch - baseline.pitch > THRESHOLDS.pitch;
}

export function GuidedCapture({ onCapture, onCancel }: { onCapture: (file: File) => void; onCancel: () => void }) {
  const video = useRef<HTMLVideoElement>(null);
  const stream = useRef<MediaStream | null>(null);
  const baseline = useRef<Pose | null>(null);
  const neutral = useRef<Pose | null>(null);
  const completedFrames = useRef(0);
  const lastFrame = useRef(0);
  const sequenceComplete = useRef(false);
  const qualityBlocked = useRef(true);
  const qualityText = useRef('Checking lighting and focus…');
  const canvas = useRef<HTMLCanvasElement>(null);
  const [steps, setSteps] = useState<Step[]>(shuffleSteps);
  const [stepIndex, setStepIndex] = useState(0);
  const [pose, setPose] = useState<Pose | null>(null);
  const [message, setMessage] = useState('Starting camera…');
  const [qualityMessage, setQualityMessage] = useState('Checking lighting and focus…');
  const [error, setError] = useState('');
  const [ready, setReady] = useState(false);
  const [screenLight, setScreenLight] = useState(false);
  const step = steps[stepIndex];
  const stepRef = useRef(step); stepRef.current = step;
  const indexRef = useRef(stepIndex); indexRef.current = stepIndex;
  const stepsRef = useRef(steps); stepsRef.current = steps;

  const stop = useCallback(() => {
    stream.current?.getTracks().forEach((track) => track.stop());
    stream.current = null;
  }, []);
  useEffect(() => stop, [stop]);

  useEffect(() => {
    let active = true;
    let raf = 0;
    async function start() {
      try {
        if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) throw new Error('Camera access requires HTTPS or localhost.');
        const camera = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user', width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false });
        if (!active) { camera.getTracks().forEach((track) => track.stop()); return; }
        stream.current = camera;
        if (!video.current) return;
        video.current.srcObject = camera;
        await video.current.play();
        setMessage('Loading on-device face tracking…');
        const landmarker = await getFaceLandmarker('VIDEO');
        if (!active) return;
        setMessage('Center your face in the guide.');
        const tick = (time: number) => {
          if (!active) return;
          raf = requestAnimationFrame(tick);
          const element = video.current;
          if (!element || element.readyState < 2 || time - lastFrame.current < 120) return;
          lastFrame.current = time;
          const result = landmarker.detectForVideo(element, time);
          const faces = result.faceLandmarks;
          const qc = canvas.current;
          const qctx = qc?.getContext('2d', { willReadFrequently: true });
          if (qc && qctx) {
            qc.width = 80; qc.height = 60;
            qctx.drawImage(element, 0, 0, 80, 60);
            const pixels = qctx.getImageData(0, 0, 80, 60).data;
            const gray = new Float32Array(80 * 60);
            let mean = 0;
            for (let i = 0, p = 0; i < pixels.length; i += 4, p++) { gray[p] = (pixels[i] * 0.299 + pixels[i + 1] * 0.587 + pixels[i + 2] * 0.114); mean += gray[p]; }
            mean /= gray.length;
            let sharpness = 0;
            for (let y = 1; y < 59; y++) for (let x = 1; x < 79; x++) { const i = y * 80 + x; const lap = 4 * gray[i] - gray[i - 1] - gray[i + 1] - gray[i - 80] - gray[i + 80]; sharpness += lap * lap; }
            sharpness /= 78 * 58;
            const quality = mean < THRESHOLDS.minBrightness ? 'Too dark to capture. Move toward a light source or increase your screen brightness.'
              : mean > THRESHOLDS.maxBrightness ? 'Too bright. Turn away from direct light or reduce exposure.'
              : sharpness < THRESHOLDS.minSharpness ? 'The preview looks soft. Hold the phone steady and improve focus.'
              : 'Lighting and focus look suitable.';
            qualityBlocked.current = quality !== 'Lighting and focus look suitable.';
            qualityText.current = quality;
            setQualityMessage(quality);
          }
          if (faces.length !== 1) {
            setReady(false); setMessage(faces.length > 1 ? 'Only one face can be in the frame.' : 'Move into view of the camera.');
            baseline.current = null; completedFrames.current = 0; return;
          }
          const current = measure(faces[0]);
          if (qualityBlocked.current) { setReady(false); setMessage(qualityText.current); return; }
          setPose(current);
          if (sequenceComplete.current) {
            const origin = neutral.current;
            const aligned = origin && !qualityBlocked.current && current.size >= THRESHOLDS.minFaceWidth && current.size <= THRESHOLDS.maxFaceWidth && current.centered && Math.abs(current.yaw - origin.yaw) < THRESHOLDS.yaw * 0.6 && Math.abs(current.pitch - origin.pitch) < THRESHOLDS.pitch && Math.abs(current.roll) <= THRESHOLDS.roll;
            setReady(Boolean(aligned));
            setMessage(aligned ? 'All movements complete. Hold still to capture.' : 'Face the camera straight again to capture.');
            return;
          }
          if (current.size < THRESHOLDS.minFaceWidth) { setReady(false); setMessage('Move a little closer.'); return; }
          if (current.size > THRESHOLDS.maxFaceWidth) { setReady(false); setMessage('Move a little farther away.'); return; }
          if (!current.centered) { setReady(false); setMessage('Center your whole face in the frame.'); return; }
          if (Math.abs(current.roll) > THRESHOLDS.roll) { setReady(false); setMessage('Keep your head level; roll is sideways tilt.'); return; }
          if (!baseline.current) { baseline.current = current; neutral.current = current; }
          const origin = baseline.current;
          const activeStep = stepRef.current;
          if (movementReached(activeStep, current, activeStep === 'straight' ? (neutral.current ?? origin) : origin)) {
            completedFrames.current += 1;
            setReady(false); setMessage('Movement detected — hold still…');
            if (completedFrames.current >= 4) {
              const last = indexRef.current === stepsRef.current.length - 1;
              if (last) { sequenceComplete.current = true; setReady(true); setMessage('All movements complete. Hold still to capture.'); return; }
              setStepIndex((index) => Math.min(index + 1, stepsRef.current.length - 1));
              completedFrames.current = 0;
              baseline.current = current;
              setMessage(`Movement confirmed. Continue to the next prompt.`);
            }
          } else {
            completedFrames.current = 0;
            setReady(false);
            setMessage(LABELS[activeStep]);
          }
        };
        raf = requestAnimationFrame(tick);
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : 'Camera or face tracking could not start.');
      }
    }
    void start();
    return () => { active = false; cancelAnimationFrame(raf); stop(); };
  }, [stop]);

  // Take only a current camera frame after all movement prompts pass.
  async function capture() {
    const element = video.current;
    if (!element || !ready) return;
    const target = canvas.current;
    if (!target) return;
    target.width = element.videoWidth; target.height = element.videoHeight;
    const context = target.getContext('2d');
    if (!context) return;
    context.translate(target.width, 0); context.scale(-1, 1); context.drawImage(element, 0, 0);
    const blob = await new Promise<Blob | null>((resolve) => target.toBlob(resolve, 'image/jpeg', 0.92));
    if (!blob) { setError('The camera frame could not be captured. Please retry.'); return; }
    onCapture(new File([blob], `vysel-selfie-${Date.now()}.jpg`, { type: 'image/jpeg' }));
  }

  function retry() { baseline.current = null; neutral.current = null; sequenceComplete.current = false; completedFrames.current = 0; setSteps(shuffleSteps()); setStepIndex(0); setReady(false); setError(''); setMessage('Center your face in the guide.'); }

  return <section className="capture" aria-label="Guided face capture">
    <div className={`capture__viewport ${screenLight ? 'capture__viewport--screen-light' : ''}`}>
      <video ref={video} className="capture__video" playsInline muted aria-label="Live front camera preview" />
      <svg className={`capture__guide ${pose?.centered ? 'capture__guide--aligned' : ''}`} viewBox="0 0 280 360" aria-hidden="true">
        <path d="M140 27 C74 27 49 77 53 154 C56 235 87 320 140 337 C193 320 224 235 227 154 C231 77 206 27 140 27Z" />
        <path d="M83 148 Q108 130 131 148 M149 148 Q172 130 197 148 M112 219 Q140 229 168 219 M140 160 L130 204 L145 208" />
        <path className={`capture__arrow ${step === 'left' ? 'is-active' : ''}`} d="M25 175 H61 M25 175 L38 162 M25 175 L38 188" />
        <path className={`capture__arrow ${step === 'right' ? 'is-active' : ''}`} d="M255 175 H219 M255 175 L242 162 M255 175 L242 188" />
        <path className={`capture__arrow ${step === 'up' ? 'is-active' : ''}`} d="M140 4 V23 M140 4 L132 13 M140 4 L148 13" />
        <path className={`capture__arrow ${step === 'down' ? 'is-active' : ''}`} d="M140 355 V335 M140 355 L132 346 M140 355 L148 346" />
      </svg>
    <span className="capture__status">{message}</span>
    </div>
    <p className="vy-caption" aria-live="polite">{qualityMessage} Face tracking runs on this device. This guided movement check is not proof of liveness and cannot reliably detect replay attacks.</p>
    {error && <p role="alert" className="vy-caption">{error}</p>}
    <div className="capture__actions">
      <Button variant="secondary" type="button" aria-pressed={screenLight} onClick={() => setScreenLight((value) => !value)}>{screenLight ? 'Turn off screen illumination' : 'Screen illumination'}</Button>
      <Button variant="secondary" type="button" onClick={retry}>Retry movement check</Button>
      <Button type="button" disabled={!ready} onClick={() => void capture()}>Capture selfie</Button>
      <Button variant="secondary" type="button" onClick={onCancel}>Cancel</Button>
    </div>
    <canvas ref={canvas} className="vy-visually-hidden" />
  </section>;
}
