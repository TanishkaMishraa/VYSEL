'use client';

import { useEffect, useRef, useState } from 'react';
import { Alert, Button, StateMessage } from '@vysel/ui';
import { AppShell } from '@/components/app/AppShell';
import { RequireAuth } from '@/components/auth/guards';

const MAX_FILE_SIZE = 10 * 1024 * 1024;
const ACCEPTED_TYPES = ['image/jpeg', 'image/png', 'image/webp'];

function ScanSetup() {
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [consented, setConsented] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

  return (
    <div className="scan">
      <header className="scan__heading">
        <p className="vy-overline">Style DNA · Photo setup</p>
        <h1 className="vy-h2">A good scan starts with a clear photo.</h1>
        <p className="vy-body">Choose a recent, front-facing photo in soft natural light. This preview stays in your browser and is not uploaded.</p>
      </header>

      <Alert tone="warning" title="Analysis isn’t available yet">
        The scan and analysis API has not been connected. You can preview a photo here, but it will not be sent to VYSEL or used to create a report.
      </Alert>

      <section className="scan__card vy-card" aria-labelledby="scan-photo-title">
        <div className="scan__photo" aria-live="polite">
          {previewUrl ? (
            // A local object URL is created only for this in-browser preview.
            // eslint-disable-next-line @next/next/no-img-element
            <img src={previewUrl} alt="Selected selfie preview" />
          ) : (
            <div className="scan__placeholder">
              <span className="scan__frame" aria-hidden="true" />
              <p className="vy-caption">Your photo preview appears here</p>
            </div>
          )}
        </div>
        <div className="scan__details">
          <h2 className="vy-h4" id="scan-photo-title">Choose your selfie</h2>
          <ul className="scan__tips">
            <li>Face the camera, with your full face in frame.</li>
            <li>Use even light and remove sunglasses or face coverings.</li>
            <li>JPEG, PNG, or WebP · up to 10 MB.</li>
          </ul>
          <input ref={input} className="vy-visually-hidden" type="file" accept="image/jpeg,image/png,image/webp" capture="user" onChange={chooseFile} aria-label="Choose a selfie" />
          <Button variant="secondary" onClick={() => input.current?.click()}>
            {file ? 'Choose a different photo' : 'Choose photo'}
          </Button>
          {file && <p className="vy-caption">{file.name}</p>}
        </div>
      </section>

      <label className="scan__consent">
        <input type="checkbox" className="scan__checkbox" checked={consented} onChange={(event) => setConsented(event.target.checked)} />
        <span>I understand this photo is only previewed in my browser. VYSEL won’t upload it or run an analysis from this page.</span>
      </label>

      {error && <Alert tone="danger">{error}</Alert>}
      {consented && file && (
        <StateMessage kind="info" title="Your photo is ready to preview" description="When secure upload and analysis are available, you’ll be able to continue here. Nothing has been uploaded." />
      )}
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
