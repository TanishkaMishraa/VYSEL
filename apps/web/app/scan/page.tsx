'use client';

import { useEffect, useRef, useState, type FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import { Alert, Button } from '@vysel/ui';
import { AppShell } from '@/components/app/AppShell';
import { RequireAuth } from '@/components/auth/guards';
import { useAuth } from '@/components/auth/AuthProvider';
import { GuidedCapture } from '@/components/scan/GuidedCapture';
import { ApiError } from '@/lib/api';
import type { FaceShape, FeatureContrast, Report, RecommendationFeatures, SkinDepth, Undertone } from '@/lib/reports';

const MAX_FILE_SIZE = 5 * 1024 * 1024;
const ACCEPTED_TYPES = ['image/jpeg', 'image/png'];
const OPTIONS = {
  face_shape: ['oval', 'round', 'square', 'heart', 'oblong', 'diamond'],
  undertone: ['warm', 'cool', 'neutral', 'olive'],
  skin_depth: ['fair', 'light', 'medium', 'tan', 'deep'],
  contrast: ['low', 'medium', 'high'],
} as const;
const CONFIDENCE = { tentative: 0.35, fairly_sure: 0.65, very_sure: 0.9 } as const;

interface UploadedImage { image: { id: string } }
interface ScanResult {
  id: string;
  status: 'queued' | 'running' | 'succeeded' | 'failed';
  face_count?: number;
  error?: { code: string; message: string };
  recommendation_features?: RecommendationFeatures | null;
  warnings?: { code: string; message: string }[];
  head_pose?: { pitch: number; yaw: number; roll: number };
  validation?: Record<string, { passed: boolean; value: string | number; threshold: string | number; message: string }>;
  skin?: { status?: string; color_correction?: { method?: string; applied?: boolean; clamped?: boolean } };
  attributes?: { face_shape?: { status?: string }; eye_color?: { status?: string }; hair_color?: { status?: string } };
}

function ScanSetup() {
  const { apiRequest } = useAuth();
  const router = useRouter();
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [confidence, setConfidence] = useState<keyof typeof CONFIDENCE>('fairly_sure');
  const [consent, setConsent] = useState(false);
  const [faceShape, setFaceShape] = useState<FaceShape | ''>('');
  const [undertone, setUndertone] = useState<Undertone | ''>('');
  const [skinDepth, setSkinDepth] = useState<SkinDepth | ''>('');
  const [contrast, setContrast] = useState<FeatureContrast | ''>('');
  const [scan, setScan] = useState<ScanResult | null>(null);
  const [scanId, setScanId] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [cameraOpen, setCameraOpen] = useState(false);
  const pollTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => () => { if (pollTimer.current) clearTimeout(pollTimer.current); }, []);

  useEffect(() => {
    if (!file) {
      setPreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  function chooseFile(event: React.ChangeEvent<HTMLInputElement>) {
    const selected = event.target.files?.[0] ?? null;
    setError(null);
    if (!selected) return;
    setFile(null);
    setConsent(false);
    if (pollTimer.current) clearTimeout(pollTimer.current);
    if (input.current) input.current.value = '';
    if (!ACCEPTED_TYPES.includes(selected.type)) {
      setError('Choose a JPEG or PNG image.');
      return;
    }
    if (selected.size > MAX_FILE_SIZE) {
      setError('Choose an image no larger than 5 MB.');
      return;
    }
    setFile(selected);
    setScan(null);
    setScanId(null);
    setFaceShape(''); setUndertone(''); setSkinDepth(''); setContrast('');
  }

  async function pollScan(id: string) {
    try {
      const result = await apiRequest<ScanResult>(`/scans/${id}`);
      setScan(result);
      if (result.status === 'queued' || result.status === 'running') {
        pollTimer.current = setTimeout(() => void pollScan(id), 1000);
      } else {
        setAnalyzing(false);
        if (result.status === 'succeeded' && result.recommendation_features) {
          const features = result.recommendation_features;
          setFaceShape(features.face_shape.value);
          setUndertone(features.undertone.value);
          setSkinDepth(features.skin_depth.value);
          setContrast(features.contrast.value);
        }
      }
    } catch (cause) {
      setAnalyzing(false);
      setError(cause instanceof ApiError ? cause.message : 'Could not check scan status. Please try again.');
    }
  }

  async function analyzePhoto() {
    if (!file || !consent) return;
    setError(null); setAnalyzing(true); setScan(null); setScanId(null);
    try {
      const form = new FormData();
      form.append('file', file);
      form.append('consent', 'true');
      form.append('policy_version', '2026-11-01');
      const uploaded = await apiRequest<UploadedImage>('/images', { method: 'POST', body: form });
      const created = await apiRequest<ScanResult>('/scans', { method: 'POST', json: { image_id: uploaded.image.id } });
      setScanId(created.id);
      setScan(created);
      if (created.status === 'queued' || created.status === 'running') {
        pollTimer.current = setTimeout(() => void pollScan(created.id), 500);
      } else {
        await pollScan(created.id);
      }
    } catch (cause) {
      setAnalyzing(false);
      setError(cause instanceof ApiError ? cause.message : 'We could not start the scan. Please try again.');
    }
  }

  async function createReport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    const formData = new FormData(event.currentTarget);
    const confidenceValue = CONFIDENCE[confidence];
    const scannedFeatures = scan?.status === 'succeeded' ? scan.recommendation_features : null;
    const useScanFeatures = Boolean(scannedFeatures
      && scannedFeatures.face_shape.value === faceShape
      && scannedFeatures.undertone.value === undertone
      && scannedFeatures.skin_depth.value === skinDepth
      && scannedFeatures.contrast.value === contrast);
    const features: RecommendationFeatures = useScanFeatures && scannedFeatures
      ? scannedFeatures
      : {
          face_shape: { value: formData.get('face_shape') as FaceShape, confidence: confidenceValue },
          undertone: { value: formData.get('undertone') as Undertone, confidence: confidenceValue },
          skin_depth: { value: formData.get('skin_depth') as SkinDepth, confidence: confidenceValue },
          contrast: { value: formData.get('contrast') as FeatureContrast, confidence: confidenceValue },
        };

    setSaving(true);
    try {
      const report = await apiRequest<Report>('/reports', { method: 'POST', json: { features, ...(useScanFeatures && scanId ? { scan_id: scanId } : {}) } });
      router.push(`/reports/${report.id}`);
    } catch (cause) {
      setError(cause instanceof ApiError ? cause.message : 'We couldn’t create your report. Please try again.');
      setSaving(false);
    }
  }

  return (
    <div className="scan">
      <header className="scan__heading">
        <p className="vy-overline">Style DNA · Personal estimates</p>
        <h1 className="vy-h2">Build your Style DNA report.</h1>
        <p className="vy-body">Get estimates from a selfie or enter them yourself. Your estimates power your personalised style suggestions.</p>
      </header>

      <Alert tone="info" title="You choose how to provide estimates">
        Selfie analysis is optional and requires your consent. If you skip it, recommendations use the estimates you enter below and your saved style preferences.
      </Alert>

      <form className="scan__form" onSubmit={createReport}>
        <fieldset className="scan__estimates vy-card">
          <legend className="vy-h4">Your estimates</legend>
          <p className="vy-caption">These are estimates, not a definitive assessment. You can adjust automated estimates or enter them yourself.</p>
          <div className="scan__fields">
            <label className="scan__field">
              <span className="vy-label">Face shape</span>
              <select name="face_shape" required value={faceShape} onChange={(event) => setFaceShape(event.target.value as FaceShape)}>
                <option value="" disabled>Select an estimate</option>
                {OPTIONS.face_shape.map((value) => <option key={value} value={value}>{value}</option>)}
              </select>
            </label>
            <label className="scan__field">
              <span className="vy-label">Undertone</span>
              <select name="undertone" required value={undertone} onChange={(event) => setUndertone(event.target.value as Undertone)}>
                <option value="" disabled>Select an estimate</option>
                {OPTIONS.undertone.map((value) => <option key={value} value={value}>{value}</option>)}
              </select>
            </label>
            <label className="scan__field">
              <span className="vy-label">Skin depth</span>
              <select name="skin_depth" required value={skinDepth} onChange={(event) => setSkinDepth(event.target.value as SkinDepth)}>
                <option value="" disabled>Select an estimate</option>
                {OPTIONS.skin_depth.map((value) => <option key={value} value={value}>{value}</option>)}
              </select>
            </label>
            <label className="scan__field">
              <span className="vy-label">Feature contrast</span>
              <select name="contrast" required value={contrast} onChange={(event) => setContrast(event.target.value as FeatureContrast)}>
                <option value="" disabled>Select an estimate</option>
                {OPTIONS.contrast.map((value) => <option key={value} value={value}>{value}</option>)}
              </select>
            </label>
            <label className="scan__field">
              <span className="vy-label">Confidence in these estimates</span>
              <select value={confidence} onChange={(event) => setConfidence(event.target.value as keyof typeof CONFIDENCE)}>
                <option value="tentative">Not very sure</option>
                <option value="fairly_sure">Fairly sure</option>
                <option value="very_sure">Very sure</option>
              </select>
            </label>
          </div>
        </fieldset>

        <details className="scan__photo-details">
          <summary className="vy-label">Optional: get estimates from a selfie</summary>
          <section className="scan__card vy-card" aria-labelledby="scan-photo-title">
            <div className="scan__photo" aria-live="polite">
              {previewUrl ? (
                // A local object URL is created only for this in-browser preview.
                // eslint-disable-next-line @next/next/no-img-element
                <img src={previewUrl} alt="Selected photo preview" />
              ) : (
                <p className="vy-caption">Your photo preview appears here</p>
              )}
            </div>
            <div className="scan__details">
              <h2 className="vy-h4" id="scan-photo-title">Selfie analysis</h2>
              <p className="vy-caption">JPEG or PNG, up to 5 MB. Your upload and scan are stored for up to 24 hours, then removed.</p>
              <input ref={input} className="vy-visually-hidden" type="file" accept="image/jpeg,image/png" capture="user" onChange={chooseFile} aria-label="Choose a selfie to analyze" />
              <Button variant="secondary" onClick={() => input.current?.click()} type="button">
                {file ? 'Choose a different photo' : 'Choose photo'}
              </Button>
              <Button variant="secondary" type="button" onClick={() => { setError(null); setCameraOpen(true); }}>Use guided camera</Button>
              {file && <p className="vy-caption">{file.name}</p>}
              {file && <label className="vy-caption"><input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} /> I consent to VYSEL processing this selfie to estimate facial attributes.</label>}
              {file && <Button type="button" onClick={() => void analyzePhoto()} disabled={!consent || analyzing}>
                {analyzing ? 'Analyzing selfie…' : 'Analyze selfie'}
              </Button>}
              {scan && <p className="vy-caption" role="status" aria-live="polite">
                {scan.status === 'queued' && 'Your scan is queued…'}
                {scan.status === 'running' && 'Analyzing your selfie…'}
                {scan.status === 'succeeded' && 'Estimates are ready and have filled in the fields above.'}
                {scan.status === 'failed' && (scan.error?.message ?? 'The scan could not be completed. You can still enter estimates manually.')}
              </p>}
            </div>
          </section>
        </details>

        {cameraOpen && <div className="capture__modal" role="dialog" aria-modal="true" aria-labelledby="capture-title">
          <div className="capture__dialog">
            <h2 className="vy-h3" id="capture-title">Guided selfie capture</h2>
            <GuidedCapture onCancel={() => setCameraOpen(false)} onCapture={(captured) => {
              setFile(captured); setConsent(false); setScan(null); setScanId(null); setCameraOpen(false);
              setFaceShape(''); setUndertone(''); setSkinDepth(''); setContrast('');
            }} />
          </div>
        </div>}

        {scan?.status === 'succeeded' && <section className="scan__assessments vy-card" aria-labelledby="scan-assessments-title">
          <h2 className="vy-h4" id="scan-assessments-title">Scan assessments</h2>
          <p className="vy-caption">Separate checks from the available image and face analysis. Unknown indicators are shown as inconclusive.</p>
          <div className="scan__assessment-grid">
            <Assessment title="Face alignment" status={scan.face_count !== 1 ? 'Inconclusive' : scan.warnings?.some((warning) => ['FACE_PARTIALLY_OUT_OF_FRAME', 'HIGH_HEAD_ROTATION', 'FACE_LOW_RESOLUTION'].includes(warning.code)) ? 'Warning' : 'Passed'} detail={scan.warnings?.filter((warning) => ['FACE_PARTIALLY_OUT_OF_FRAME', 'HIGH_HEAD_ROTATION', 'FACE_LOW_RESOLUTION'].includes(warning.code)).map((warning) => warning.message).join(' ') || (scan.face_count === 1 ? 'One face was detected and passed the scan alignment checks.' : 'Face count or alignment results are unavailable.')} />
            <Assessment title="Image quality" status={!scan.validation ? 'Inconclusive' : Object.values(scan.validation).every((check) => check.passed) ? 'Passed' : 'Warning'} detail={Object.values(scan.validation ?? {}).map((check) => check.message).join(' ') || 'No image quality details were returned.'} />
            <Assessment title="Lighting quality" status={!scan.validation?.brightness || !scan.validation.exposure ? 'Inconclusive' : scan.validation.brightness.passed && scan.validation.exposure.passed ? 'Passed' : 'Warning'} detail={[scan.validation?.brightness?.message, scan.validation?.exposure?.message].filter(Boolean).join(' ') || 'Lighting could not be assessed.'} />
            <Assessment title="Colour consistency" status="Inconclusive" detail={scan.skin?.color_correction?.method ? `Skin analysis used ${scan.skin.color_correction.method} white-balance correction${scan.skin.color_correction.applied ? '' : ' (not applied)'}. This does not distinguish camera processing from filters.` : 'Camera colour profile and intentional colour edits are not reliably distinguishable with the available analysis.'} />
            <Assessment title="Possible filters or manipulation" status="Inconclusive" detail="No validated forensic manipulation or face-swap detector is configured. Colour or texture differences alone are not treated as proof of editing." />
            <Assessment title="Liveness" status="Inconclusive" detail="The guided movement challenge is a capture aid, not a validated presentation-attack detector. Printed or replayed faces may pass." />
            <Assessment title="Face identity similarity" status="Inconclusive" detail="Reference-image identity verification is not available in this scan flow." />
          </div>
        </section>}

        {error && <Alert tone="danger">{error}</Alert>}
        <div className="scan__submit">
          <Button type="submit" disabled={saving}>{saving ? 'Creating report…' : 'Generate my Style DNA report'}</Button>
          <p className="vy-caption">Your report is saved privately to your account. You can opt in to sharing later.</p>
        </div>
      </form>
    </div>
  );
}

function Assessment({ title, status, detail }: { title: string; status: 'Passed' | 'Warning' | 'Failed' | 'Inconclusive'; detail: string }) {
  return <article className="scan__assessment"><div><h3 className="vy-label">{title}</h3><span className={`scan__assessment-status scan__assessment-status--${status.toLowerCase()}`}>{status}</span></div><p className="vy-caption">{detail}</p></article>;
}

export default function ScanPage() {
  return (
    <RequireAuth>
      <AppShell narrow>
        <ScanSetup />
      </AppShell>
    </RequireAuth>
  );
}
