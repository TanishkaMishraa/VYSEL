'use client';

import { useEffect, useRef, useState, type FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import { Alert, Button } from '@vysel/ui';
import { AppShell } from '@/components/app/AppShell';
import { RequireAuth } from '@/components/auth/guards';
import { useAuth } from '@/components/auth/AuthProvider';
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
  error?: { code: string; message: string };
  recommendation_features?: RecommendationFeatures | null;
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

        {error && <Alert tone="danger">{error}</Alert>}
        <div className="scan__submit">
          <Button type="submit" disabled={saving}>{saving ? 'Creating report…' : 'Generate my Style DNA report'}</Button>
          <p className="vy-caption">Your report is saved privately to your account. You can opt in to sharing later.</p>
        </div>
      </form>
    </div>
  );
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
