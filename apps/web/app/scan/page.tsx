'use client';

import { useEffect, useRef, useState, type FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import { Alert, Button } from '@vysel/ui';
import { AppShell } from '@/components/app/AppShell';
import { RequireAuth } from '@/components/auth/guards';
import { useAuth } from '@/components/auth/AuthProvider';
import { ApiError } from '@/lib/api';
import type { FaceShape, FeatureContrast, Report, RecommendationFeatures, SkinDepth, Undertone } from '@/lib/reports';

const MAX_FILE_SIZE = 10 * 1024 * 1024;
const ACCEPTED_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
const OPTIONS = {
  face_shape: ['oval', 'round', 'square', 'heart', 'oblong', 'diamond'],
  undertone: ['warm', 'cool', 'neutral', 'olive'],
  skin_depth: ['fair', 'light', 'medium', 'tan', 'deep'],
  contrast: ['low', 'medium', 'high'],
} as const;
const CONFIDENCE = { tentative: 0.35, fairly_sure: 0.65, very_sure: 0.9 } as const;

function ScanSetup() {
  const { apiRequest } = useAuth();
  const router = useRouter();
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [confidence, setConfidence] = useState<keyof typeof CONFIDENCE>('fairly_sure');
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

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
    if (input.current) input.current.value = '';
    if (!ACCEPTED_TYPES.includes(selected.type)) {
      setError('Choose a JPEG, PNG, or WebP image.');
      return;
    }
    if (selected.size > MAX_FILE_SIZE) {
      setError('Choose an image smaller than 10 MB.');
      return;
    }
    setFile(selected);
  }

  async function createReport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    const formData = new FormData(event.currentTarget);
    const confidenceValue = CONFIDENCE[confidence];
    const features: RecommendationFeatures = {
      face_shape: { value: formData.get('face_shape') as FaceShape, confidence: confidenceValue },
      undertone: { value: formData.get('undertone') as Undertone, confidence: confidenceValue },
      skin_depth: { value: formData.get('skin_depth') as SkinDepth, confidence: confidenceValue },
      contrast: { value: formData.get('contrast') as FeatureContrast, confidence: confidenceValue },
    };

    setSaving(true);
    try {
      const report = await apiRequest<Report>('/reports', { method: 'POST', json: { features } });
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
        <p className="vy-body">Choose the features that best describe you. Your answers—not your photo—power your personalised style suggestions.</p>
      </header>

      <Alert tone="info" title="No facial analysis is performed">
        VYSEL does not upload or analyse your photo. Recommendations use only the estimates you select below and your saved style preferences.
      </Alert>

      <form className="scan__form" onSubmit={createReport}>
        <fieldset className="scan__estimates vy-card">
          <legend className="vy-h4">Your estimates</legend>
          <p className="vy-caption">These are personal estimates, not an automated assessment. You can create a report without selecting a photo.</p>
          <div className="scan__fields">
            <label className="scan__field">
              <span className="vy-label">Face shape</span>
              <select name="face_shape" required defaultValue="">
                <option value="" disabled>Select an estimate</option>
                {OPTIONS.face_shape.map((value) => <option key={value} value={value}>{value}</option>)}
              </select>
            </label>
            <label className="scan__field">
              <span className="vy-label">Undertone</span>
              <select name="undertone" required defaultValue="">
                <option value="" disabled>Select an estimate</option>
                {OPTIONS.undertone.map((value) => <option key={value} value={value}>{value}</option>)}
              </select>
            </label>
            <label className="scan__field">
              <span className="vy-label">Skin depth</span>
              <select name="skin_depth" required defaultValue="">
                <option value="" disabled>Select an estimate</option>
                {OPTIONS.skin_depth.map((value) => <option key={value} value={value}>{value}</option>)}
              </select>
            </label>
            <label className="scan__field">
              <span className="vy-label">Feature contrast</span>
              <select name="contrast" required defaultValue="">
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
          <summary className="vy-label">Optional: preview a photo locally</summary>
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
              <h2 className="vy-h4" id="scan-photo-title">Photo preview only</h2>
              <p className="vy-caption">This optional preview stays in your browser and does not affect the report.</p>
              <input ref={input} className="vy-visually-hidden" type="file" accept="image/jpeg,image/png,image/webp" capture="user" onChange={chooseFile} aria-label="Choose a photo for local preview" />
              <Button variant="secondary" onClick={() => input.current?.click()} type="button">
                {file ? 'Choose a different photo' : 'Choose photo'}
              </Button>
              {file && <p className="vy-caption">{file.name}</p>}
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
