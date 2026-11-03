'use client';

import Link from 'next/link';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Alert, Button, Spinner, buttonClassName } from '@vysel/ui';
import { getFaceLandmarker } from '@/lib/tryon/faceLandmarker';
import { LandmarkSmoother, faceWidth, toPixels, type Point } from '@/lib/tryon/landmarks';
import { drawLook, type Look } from '@/lib/tryon/render';
import { initialLook, presetsFor, type Preset, type ShadeSet } from '@/lib/tryon/shades';
import { restoreLook, serializeLook, type SavedLookOccasion, type SavedTryOnLook } from '@/lib/tryon/savedLooks';
import { ShadePicker } from './ShadePicker';

type Phase = 'idle' | 'requesting' | 'loading' | 'live' | 'photo' | 'denied' | 'unavailable' | 'error';

const MAX_PHOTO_EDGE = 1600;
const MAX_PHOTO_SIZE = 10 * 1024 * 1024;
const PHOTO_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
const OCCASIONS: { value: SavedLookOccasion; label: string }[] = [
  { value: 'college', label: 'College' },
  { value: 'office', label: 'Office' },
  { value: 'party', label: 'Party' },
  { value: 'wedding', label: 'Wedding' },
];

interface TryOnStudioProps {
  shades: ShadeSet;
  apiRequest?: <T>(path: string, init?: { method?: string; json?: unknown }) => Promise<T>;
}

export function TryOnStudio({ shades, apiRequest }: TryOnStudioProps) {
  const [phase, setPhase] = useState<Phase>('idle');
  const [error, setError] = useState<string | null>(null);
  const [faceFound, setFaceFound] = useState(true);
  const [look, setLook] = useState<Look>(() => initialLook(shades));
  const [savedLooks, setSavedLooks] = useState<SavedTryOnLook[]>([]);
  const [savedLooksError, setSavedLooksError] = useState<string | null>(null);
  const [lookName, setLookName] = useState('');
  const [occasion, setOccasion] = useState<SavedLookOccasion>('college');
  const [savingLook, setSavingLook] = useState(false);
  const [activePreset, setActivePreset] = useState<string | null>(null);
  const [showBefore, setShowBefore] = useState(false);
  const presets = useMemo(() => presetsFor(shades), [shades]);

  const canvasRef = useRef<HTMLCanvasElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const rafRef = useRef<number>(0);
  const videoFrameRef = useRef<number | null>(null);
  const permissionRequestRef = useRef(0);
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
    if (videoFrameRef.current !== null && videoRef.current?.cancelVideoFrameCallback) {
      videoRef.current.cancelVideoFrameCallback(videoFrameRef.current);
      videoFrameRef.current = null;
    }
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    smoother.current.reset();
  }, []);

  // Release the camera when leaving the page or hiding the tab — never keep it on in the background.
  useEffect(() => {
    const onHide = () => {
      if (document.hidden) {
        permissionRequestRef.current += 1;
        if (streamRef.current) {
          stopCamera();
          setPhase('idle');
        }
      }
    };
    document.addEventListener('visibilitychange', onHide);
    return () => {
      document.removeEventListener('visibilitychange', onHide);
      permissionRequestRef.current += 1;
      stopCamera();
    };
  }, [stopCamera]);

  /** Live loop: mirror the frame, track the face, paint the look. */
  const runLoop = useCallback(async () => {
    const video = videoRef.current!;
    const canvas = canvasRef.current!;
    const ctx = canvas.getContext('2d', { willReadFrequently: false })!;
    const landmarker = await getFaceLandmarker('VIDEO');
    if (!streamRef.current) return;
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
      if (typeof video.requestVideoFrameCallback === 'function') {
        videoFrameRef.current = video.requestVideoFrameCallback(frame);
      } else {
        rafRef.current = requestAnimationFrame(frame);
      }
    };
    frame();
  }, []);

  async function startCamera() {
    setError(null);
    photo.current = null;
    const requestId = ++permissionRequestRef.current;
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
      setPhase('unavailable');
      return;
    }
    setPhase('requesting');
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user', width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false });
    } catch (err) {
      if (requestId !== permissionRequestRef.current || document.hidden) return;
      const name = (err as DOMException)?.name;
      setPhase(name === 'NotAllowedError' || name === 'SecurityError' ? 'denied' : name === 'NotFoundError' || name === 'OverconstrainedError' ? 'unavailable' : 'error');
      if (name === 'NotReadableError') setError('Your camera is being used by another app. Close it and try again.');
      return;
    }
    if (document.hidden || requestId !== permissionRequestRef.current) {
      stream.getTracks().forEach((track) => track.stop());
      return;
    }
    streamRef.current = stream;
    setPhase('loading');
    try {
      await getFaceLandmarker('VIDEO'); // first run downloads the model; show progress meanwhile
      if (requestId !== permissionRequestRef.current || document.hidden || !streamRef.current) return;
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
    if (!PHOTO_TYPES.includes(file.type) || file.size > MAX_PHOTO_SIZE) {
      if (fileRef.current) fileRef.current.value = '';
      setError('Choose a JPEG, PNG, or WebP photo smaller than 10 MB.');
      return;
    }
    setPhase('loading');
    let bitmap: ImageBitmap | null = null;
    try {
      bitmap = await createImageBitmap(file);
      const scale = Math.min(1, MAX_PHOTO_EDGE / Math.max(bitmap.width, bitmap.height));
      const width = Math.round(bitmap.width * scale);
      const height = Math.round(bitmap.height * scale);
      const resized = document.createElement('canvas');
      resized.width = width;
      resized.height = height;
      const resizeContext = resized.getContext('2d');
      if (!resizeContext) throw new Error('Photo resizing is not supported in this browser.');
      resizeContext.drawImage(bitmap, 0, 0, width, height);
      bitmap.close();
      bitmap = null;
      const landmarker = await getFaceLandmarker('IMAGE');
      const result = landmarker.detect(resized);
      const face = result.faceLandmarks[0];
      photo.current = { image: resized, width, height, points: face ? toPixels(face, width, height, false) : null };
      setFaceFound(!!face);
      setPhase('photo');
    } catch {
      setError('That image couldn’t be read. Try a JPEG or PNG.');
      setPhase('error');
    } finally {
      bitmap?.close();
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

  useEffect(() => {
    if (!apiRequest) {
      setSavedLooks([]);
      setSavedLooksError(null);
      return;
    }
    let active = true;
    setSavedLooksError(null);
    apiRequest<SavedTryOnLook[]>('/saved-looks')
      .then((items) => {
        if (active) setSavedLooks(items);
      })
      .catch((cause: unknown) => {
        if (active) setSavedLooksError(cause instanceof Error ? cause.message : 'Could not load your saved looks.');
      });
    return () => {
      active = false;
    };
  }, [apiRequest]);

  async function saveCurrentLook(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!apiRequest) return;
    setSavingLook(true);
    setSavedLooksError(null);
    try {
      const saved = await apiRequest<SavedTryOnLook>('/saved-looks', {
        method: 'POST',
        json: { name: lookName.trim(), occasion, look: serializeLook(look) },
      });
      setSavedLooks((current) => [...current, saved]);
      setLookName('');
    } catch (cause) {
      setSavedLooksError(cause instanceof Error ? cause.message : 'Could not save this look.');
    } finally {
      setSavingLook(false);
    }
  }

  function loadSavedLook(saved: SavedTryOnLook) {
    setLook(restoreLook(saved.look));
    setActivePreset(null);
    setShowBefore(false);
  }

  async function removeSavedLook(id: string) {
    if (!apiRequest) return;
    setSavedLooksError(null);
    try {
      await apiRequest(`/saved-looks/${encodeURIComponent(id)}`, { method: 'DELETE' });
      setSavedLooks((current) => current.filter((saved) => saved.id !== id));
    } catch (cause) {
      setSavedLooksError(cause instanceof Error ? cause.message : 'Could not delete the saved look.');
    }
  }

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

      <aside className="to-panel" aria-label="Makeup shades and saved looks">
        <ShadePicker shades={shades} look={look} onChange={changeLook} presets={presets} activePreset={activePreset} onPreset={applyPreset} onReset={reset} />
        {apiRequest ? (
          <section className="to-saved" aria-labelledby="to-saved-title">
            <div>
              <p className="vy-overline">Your collection</p>
              <h2 className="vy-h4" id="to-saved-title">Saved looks</h2>
            </div>
            <form className="to-save-form" onSubmit={saveCurrentLook}>
              <label className="to-save-form__field">
                <span className="vy-label">Look name</span>
                <input className="vy-input" required maxLength={60} value={lookName} onChange={(event) => setLookName(event.target.value)} placeholder="e.g. Soft everyday look" />
              </label>
              <label className="to-save-form__field">
                <span className="vy-label">Occasion</span>
                <select value={occasion} onChange={(event) => setOccasion(event.target.value as SavedLookOccasion)}>
                  {OCCASIONS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                </select>
              </label>
              <Button type="submit" variant="secondary" loading={savingLook} disabled={savingLook}>Save current look</Button>
            </form>
            {savedLooksError && <Alert tone="danger">{savedLooksError}</Alert>}
            {savedLooks.length ? (
              <div className="to-saved__groups">
                {OCCASIONS.map(({ value, label }) => {
                  const group = savedLooks.filter((saved) => saved.occasion === value);
                  if (!group.length) return null;
                  return (
                    <section className="to-saved__group" key={value} aria-labelledby={`saved-${value}`}>
                      <h3 className="vy-overline" id={`saved-${value}`}>{label}</h3>
                      {group.map((saved) => (
                        <article className="to-saved__item" key={saved.id}>
                          <div>
                            <strong>{saved.name}</strong>
                            <span className="vy-caption">{[saved.look.lips.enabled && saved.look.lips.shade_name, saved.look.blush.enabled && saved.look.blush.shade_name, saved.look.liner.enabled && `${saved.look.liner.shade_name}${saved.look.liner.wing ? ' · winged' : ''}`].filter(Boolean).join(' · ') || 'All layers off'}</span>
                          </div>
                          <div className="to-saved__actions">
                            <Button variant="link" size="sm" onClick={() => loadSavedLook(saved)}>Load</Button>
                            <Button variant="ghost" size="sm" onClick={() => removeSavedLook(saved.id)}>Delete</Button>
                          </div>
                        </article>
                      ))}
                    </section>
                  );
                })}
              </div>
            ) : !savedLooksError ? <p className="vy-caption">Save a look to find it here next time.</p> : null}
          </section>
        ) : (
          <div className="to-cta">
            <p className="vy-caption">Sign in to save looks and reload them later.</p>
            <Link href="/login?next=%2Ftry-on" className={buttonClassName({ variant: 'secondary', size: 'sm' })}>
              <span className="vy-btn__label">Sign in to save</span>
            </Link>
          </div>
        )}
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
