import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Photo setup',
  robots: { index: false, follow: false },
};

export default function ScanLayout({ children }: { children: React.ReactNode }) {
  return children;
}
