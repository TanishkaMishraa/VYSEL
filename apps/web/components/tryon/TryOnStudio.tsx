'use client';

import Link from 'next/link';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Alert, Button, Spinner, buttonClassName } from '@vysel/ui';
import { getFaceLandmarker } from '@/lib/tryon/faceLandmarker';
import { LandmarkSmoother, faceWidth, toPixels, type Point } from '@/lib/tryon/landmarks';
import { drawLook, type Look } from '@/lib/tryon/render';
import { initialLook, presetsFor, type Preset, type ShadeSet } from '@/lib/tryon/shades';
import { ShadePicker } from './ShadePicker';

type Phase = 'idle' | 'requesting' | 'loading' | 'live' | 'photo' | 'denied' | 'unavailable' | 'error';

const MAX_PHOTO_EDGE = 1600;

export function TryOnStudio({ shades }: { shades: ShadeSet }) {
  const [phase, setPhase] = useState<Phase>('idle');
  const [error, setError] = useState<string | null>(null);
  const [faceFound, setFaceFound] = useState(true);
  const [look, setLook] = useState<Look>(() => initialLook(shades));
  const [activePreset, setActivePreset] = useState<string | null>(null);
  const [showBefore, setShowBefore] = useState(false);
  const presets = useMemo(() => presetsFor(shades), [shades]);

  const canvasRef = useRef<HTMLCanvasElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const rafRef = useRef<number>(0);
  const smoother = useRef(new LandmarkSmoother());
  const photo = useRef<{ image: CanvasImageSource; width: number; height: number; points: Point[] | null } | null>(null);
  // The render loop reads the latest look without restarting.
  const lookRef = useRef(look);
  const beforeRef = useRef(showBefore);
  lookRef.current = look;
  beforeRef.current = showBefore;

  // Shade set changed (e.g. Style DNA loaded after first paint): start from its recommendations.
  useEffect(() => {
    setLook(initialLook(shades));
    setActivePreset(null);
  }, [shades]);

  const stopCamera = useCallback(() => {
    cancelAnimationFrame(rafRef.current);
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    smoother.current.reset();
  }, []);

  // Release the camera when leaving the page or hiding the tab — never keep it on in the background.
  useEffect(() => {
    const onHide = () => {
      if (document.hidden && streamRef.current) {
        stopCamera();
        setPhase('idle');
      }
    };
    document.addEventListener('visibilitychange', onHide);
    return () => {
      document.removeEventListener('visibilitychange', onHide);
      stopCamera();
    };
  }, [stopCamera]);

  /** Live loop: mirror the frame, track the face, paint the look. */
  const runLoop = useCallback(async () => {
    const video = videoRef.current!;
    const canvas = canvasRef.current!;
    const ctx = canvas.getContext('2d', { willReadFrequently: false })!;
    const landmarker = await getFaceLandmarker('VIDEO');
    let lastTime = -1;
    let found = true;

    const frame = () => {
      if (!streamRef.current) return;
      if (video.readyState >= 2 && video.currentTime !== lastTime) {
        lastTime = video.currentTime;
        const w = video.videoWidth;
        const h = video.videoHeight;
        if (canvas.width !== w || canvas.height !== h) Object.assign(canvas, { width: w, height: h });

        const result = landmarker.detectForVideo(video, performance.now());
        ctx.save();
        ctx.translate(w, 0);
        ctx.scale(-1, 1); // selfie mirror
        ctx.drawImage(video, 0, 0, w, h);
        ctx.restore();

        const face = result.faceLandmarks[0];
        if (face) {
          const raw = toPixels(face, w, h, true);
          const pts = smoother.current.smooth(raw, faceWidth(raw));
          if (!beforeRef.current) drawLook(ctx, pts, lookRef.current);
        } else {
          smoother.current.reset();
        }
        if (!!face !== found) setFaceFound((found = !!face)); // re-render only on change
      }
      rafRef.current = requestAnimationFrame(frame);
    };
    frame();
  }, []);

  async function startCamera() {
    setError(null);
    photo.current = null;
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
      setPhase('unavailable');
      return;
    }
    setPhase('requesting');
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user', width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false });
    } catch (err) {
      const name = (err as DOMException)?.name;
      setPhase(name === 'NotAllowedError' || name === 'SecurityError' ? 'denied' : name === 'NotFoundError' || name === 'OverconstrainedError' ? 'unavailable' : 'error');
      if (name === 'NotReadableError') setError('Your camera is being used by another app. Close it and try again.');
      return;
    }
    streamRef.current = stream;
    setPhase('loading');
    try {
      await getFaceLandmarker('VIDEO'); // first run downloads the model; show progress meanwhile
      const video = videoRef.current!;
      video.srcObject = stream;
      await video.play();
      setPhase('live');
      runLoop();
    } catch (err) {
      stopCamera();
      setError(err instanceof Error ? err.message : 'Face tracking could not start.');
      setPhase('error');
    }
  }

  /** Photo mode: analyse a local image once, then repaint on every look change. */
  async function loadPhoto(file: File) {
    stopCamera();
    setError(null);
    setPhase('loading');
    try {
      const bitmap = await createImageBitmap(file);
      const scale = Math.min(1, MAX_PHOTO_EDGE / Math.max(bitmap.width, bitmap.height));
      const width = Math.round(bitmap.width * scale);
      const height = Math.round(bitmap.height * scale);
      const landmarker = await getFaceLandmarker('IMAGE');
      const result = landmarker.detect(bitmap);
      const face = result.faceLandmarks[0];
      photo.current = { image: bitmap, width, height, points: face ? toPixels(face, width, height, false) : null };
      setFaceFound(!!face);
      setPhase('photo');
    } catch {
      setError('That image couldn’t be read. Try a JPEG or PNG.');
      setPhase('error');
    } finally {
      if (fileRef.current) fileRef.current.value = '';
    }
  }

  // Photo mode has no loop: repaint whenever the look or the before/after toggle changes.
  useEffect(() => {
    const p = photo.current;
    const canvas = canvasRef.current;
    if (phase !== 'photo' || !p || !canvas) return;
    Object.assign(canvas, { width: p.width, height: p.height });
    const ctx = canvas.getContext('2d')!;
    ctx.drawImage(p.image, 0, 0, p.width, p.height);
    if (p.points && !showBefore) drawLook(ctx, p.points, look);
  }, [phase, look, showBefore]);

  function snapshot() {
    canvasRef.current?.toBlob((blob) => {
      if (!blob) return;
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = 'vysel-try-on.png';
      a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 1000);
    }, 'image/png');
  }

  const changeLook = (next: Look) => {
    setLook(next);
    setActivePreset(null);
  };
  const applyPreset = (p: Preset) => {
    setLook(p.look);
    setActivePreset(p.id);
  };
  const reset = () => {
    setLook(initialLook(shades));
    setActivePreset(null);
    setShowBefore(false);
  };

  const active = phase === 'live' || phase === 'photo';

  return (
    <div className="to-studio">
      <div className="to-stage">
        <div className="to-frame" data-active={active}>
          {/* The video element is a hidden frame source; the canvas shows video + makeup. */}
          <video ref={videoRef} className="to-video" playsInline muted aria-hidden="true" />
          <canvas
            ref={canvasRef}
            className="to-canvas"
            hidden={!active}
            role="img"
            aria-label={phase === 'photo' ? 'Your photo with makeup preview' : 'Live camera preview with makeup'}
          />

          {!active && (
            <div className="to-placeholder">
              {(phase === 'idle' || phase === 'error' || phase === 'denied' || phase === 'unavailable') && (
                <>
                  <span className="to-placeholder__guide" aria-hidden="true" />
                  <p className="vy-h4">See shades on your own face</p>
                  <p className="vy-caption">
                    Everything runs in your browser. Your camera feed is never uploaded or recorded.
                  </p>
                </>
              )}
              {(phase === 'requesting' || phase === 'loading') && (
                <>
                  <Spinner size="lg" label={phase === 'requesting' ? 'Waiting for camera permission' : 'Loading face tracking'} />
                  <p className="vy-caption">{phase === 'requesting' ? 'Allow camera access in your browser’s prompt.' : 'Preparing face tracking (first time only takes a few seconds)…'}</p>
                </>
              )}
            </div>
          )}

          {active && !faceFound && (
            <p className="to-hint" role="status">
              {phase === 'photo' ? 'No face found in this photo. Try a clear, front-facing one.' : 'Centre your face in good light'}
            </p>
          )}
        </div>

        <div aria-live="polite">
          {phase === 'denied' && (
            <Alert tone="warning" title="Camera access is blocked">
              Allow the camera from the icon in your browser’s address bar, then try again — or use a photo instead.
            </Alert>
          )}
          {phase === 'unavailable' && (
            <Alert tone="info" title="No camera available">
              We couldn’t find a usable camera on this device. You can still try shades on a photo.
            </Alert>
          )}
          {phase === 'error' && <Alert tone="danger">{error ?? 'Something went wrong starting the try-on. Please try again.'}</Alert>}
        </div>

        <div className="to-actions">
          {phase === 'live' ? (
            <Button
              variant="secondary"
              onClick={() => {
                stopCamera();
                setPhase('idle');
              }}
            >
              Stop camera
            </Button>
          ) : (
            <Button onClick={startCamera} loading={phase === 'requesting' || phase === 'loading'}>
              {phase === 'photo' ? 'Switch to camera' : phase === 'denied' || phase === 'error' ? 'Try again' : 'Start camera'}
            </Button>
          )}
          <Button variant="ghost" onClick={() => fileRef.current?.click()}>
            Use a photo
          </Button>
          <input
            ref={fileRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            className="vy-visually-hidden"
            tabIndex={-1}
            aria-hidden="true"
            onChange={(e) => e.target.files?.[0] && loadPhoto(e.target.files[0])}
          />
          {active && (
            <>
              <Button variant="ghost" aria-pressed={showBefore} onClick={() => setShowBefore((v) => !v)}>
                {showBefore ? 'Show makeup' : 'Before / after'}
              </Button>
              <Button variant="ghost" onClick={snapshot}>
                Save snapshot
              </Button>
            </>
          )}
        </div>
        <p className="vy-caption">Previews are approximate: lighting, camera and screen all change how colour looks.</p>
      </div>

      <aside className="to-panel" aria-label="Makeup shades">
        <ShadePicker shades={shades} look={look} onChange={changeLook} presets={presets} activePreset={activePreset} onPreset={applyPreset} onReset={reset} />
        {shades.source === 'starter' && (
          <div className="to-cta">
            <p className="vy-caption">Get shades matched to your undertone.</p>
            <Link href="/scan" className={buttonClassName({ variant: 'secondary', size: 'sm' })}>
              <span className="vy-btn__label">Build your Style DNA</span>
            </Link>
          </div>
        )}
      </aside>
    </div>
  );
}
