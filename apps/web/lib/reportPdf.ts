import { jsPDF } from 'jspdf';
import type { Recommendations, RecommendationCategory } from '@/lib/reports';

const PAGE_WIDTH = 210;
const PAGE_HEIGHT = 297;
const MARGIN = 18;
const CONTENT_WIDTH = PAGE_WIDTH - MARGIN * 2;
const BOTTOM = PAGE_HEIGHT - MARGIN - 12;

const CATEGORY_LABELS: Record<RecommendationCategory, string> = {
  hair: 'Hair',
  eyewear: 'Eyewear',
  makeup: 'Makeup',
  outfit_color: 'Outfit colours',
  outfit_cut: 'Outfit cuts',
};

function printable(value: string): string {
  return value.replace(/[^\x20-\x7E]/g, ' ');
}

function safeColor(value: string | null | undefined): [number, number, number] | null {
  if (!value || !/^#[0-9a-f]{6}$/i.test(value)) return null;
  return [1, 3, 5].map((start) => Number.parseInt(value.slice(start, start + 2), 16)) as [number, number, number];
}

export function downloadReportPdf(report: Recommendations, reportId: string, createdAt: string): void {
  const pdf = new jsPDF({ format: 'a4', unit: 'mm', compress: true });
  let y = MARGIN;

  const page = () => {
    pdf.addPage();
    y = MARGIN;
  };
  const ensure = (height: number) => {
    if (y + height > BOTTOM) page();
  };
  const wrapped = (value: string, width: number, size: number) => {
    pdf.setFontSize(size);
    return pdf.splitTextToSize(printable(value), width) as string[];
  };
  const writeParagraph = (value: string, options: { size?: number; color?: [number, number, number]; width?: number; lineGap?: number } = {}) => {
    const { size = 9, color = [65, 58, 55], width = CONTENT_WIDTH, lineGap = 4.5 } = options;
    const lines = wrapped(value, width, size);
    ensure(lines.length * lineGap + 2);
    pdf.setFont('helvetica', 'normal');
    pdf.setFontSize(size);
    pdf.setTextColor(...color);
    pdf.text(lines, MARGIN, y);
    y += lines.length * lineGap + 2;
  };
  const section = (title: string) => {
    ensure(13);
    y += 3;
    pdf.setFont('helvetica', 'bold');
    pdf.setFontSize(13);
    pdf.setTextColor(72, 49, 48);
    pdf.text(printable(title), MARGIN, y);
    y += 7;
  };

  pdf.setFont('helvetica', 'bold');
  pdf.setFontSize(9);
  pdf.setTextColor(153, 102, 91);
  pdf.text('VYSEL  /  STYLE DNA', MARGIN, y);
  y += 10;

  pdf.setFont('helvetica', 'bold');
  pdf.setFontSize(22);
  pdf.setTextColor(35, 29, 28);
  pdf.text('Your personal style report', MARGIN, y);
  y += 8;
  pdf.setFont('helvetica', 'normal');
  pdf.setFontSize(10);
  pdf.setTextColor(95, 85, 82);
  pdf.text(`${printable(report.season.value.toUpperCase())} season - provisional`, MARGIN, y);
  y += 6;
  pdf.text(`Created ${new Date(createdAt).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric', timeZone: 'UTC' })}`, MARGIN, y);
  y += 5;
  writeParagraph(report.season.rationale, { size: 9 });

  section('Your estimates');
  const estimates = [
    ['Face shape', report.features.face_shape],
    ['Undertone', report.features.undertone],
    ['Skin depth', report.features.skin_depth],
    ['Feature contrast', report.features.contrast],
  ] as const;
  estimates.forEach(([label, estimate], index) => {
    const x = MARGIN + (index % 2) * (CONTENT_WIDTH / 2);
    const rowY = y + Math.floor(index / 2) * 11;
    pdf.setFont('helvetica', 'bold');
    pdf.setFontSize(9);
    pdf.setTextColor(45, 39, 38);
    pdf.text(`${label}: ${printable(estimate.value)}`, x, rowY);
    pdf.setFont('helvetica', 'normal');
    pdf.setFontSize(8);
    pdf.setTextColor(105, 94, 90);
    pdf.text(`${Math.round(estimate.confidence * 100)}% confidence`, x, rowY + 4);
  });
  y += 25;

  section(`${report.season.value} colour palette`);
  report.palette.forEach((color) => {
    const wearLines = wrapped(color.wear, CONTENT_WIDTH - 27, 8);
    const rowHeight = Math.max(12, wearLines.length * 4 + 8);
    ensure(rowHeight);
    const rgb = safeColor(color.hex);
    if (rgb) {
      pdf.setFillColor(...rgb);
      pdf.roundedRect(MARGIN, y - 3, 12, 9, 1, 1, 'F');
    }
    pdf.setFont('helvetica', 'bold');
    pdf.setFontSize(9);
    pdf.setTextColor(45, 39, 38);
    pdf.text(`${printable(color.name)}  ${printable(color.hex)}  (${printable(color.role)})`, MARGIN + 17, y);
    pdf.setFont('helvetica', 'normal');
    pdf.setFontSize(8);
    pdf.setTextColor(95, 85, 82);
    pdf.text(wearLines, MARGIN + 17, y + 4.5);
    y += rowHeight;
  });

  section('Recommendations');
  report.recommendations.forEach((group) => {
    ensure(10);
    pdf.setFont('helvetica', 'bold');
    pdf.setFontSize(11);
    pdf.setTextColor(72, 49, 48);
    pdf.text(CATEGORY_LABELS[group.category], MARGIN, y);
    y += 6;

    group.items.forEach((item) => {
      const reasonLines = wrapped(item.reason, CONTENT_WIDTH - 8, 8.5);
      const cardHeight = 16 + reasonLines.length * 4.2;
      ensure(cardHeight + 3);
      pdf.setDrawColor(224, 214, 208);
      pdf.setLineWidth(0.25);
      pdf.roundedRect(MARGIN, y - 3, CONTENT_WIDTH, cardHeight, 1.5, 1.5, 'S');

      const rgb = safeColor(item.color_hex);
      if (rgb) {
        pdf.setFillColor(...rgb);
        pdf.circle(MARGIN + 4, y + 1, 1.8, 'F');
      }
      pdf.setFont('helvetica', 'bold');
      pdf.setFontSize(9);
      pdf.setTextColor(45, 39, 38);
      pdf.text(wrapped(item.label, CONTENT_WIDTH - 45, 9), MARGIN + 9, y + 1);
      pdf.setFont('helvetica', 'normal');
      pdf.setFontSize(8);
      pdf.setTextColor(105, 94, 90);
      pdf.text(`${Math.round(item.score * 100)}% match  |  Budget: ${item.budget}`, PAGE_WIDTH - MARGIN - 2, y + 1, { align: 'right' });
      pdf.setFontSize(8.5);
      pdf.setTextColor(65, 58, 55);
      pdf.text(reasonLines, MARGIN + 4, y + 7);
      y += cardHeight + 3;
    });
    y += 2;
  });

  section('About this report');
  writeParagraph(report.disclaimer, { size: 8 });
  writeParagraph('This report uses self-selected estimates and profile preferences. It is not automated facial analysis or professional advice.', { size: 8 });

  const totalPages = pdf.getNumberOfPages();
  for (let number = 1; number <= totalPages; number += 1) {
    pdf.setPage(number);
    pdf.setFont('helvetica', 'normal');
    pdf.setFontSize(7);
    pdf.setTextColor(130, 120, 115);
    pdf.text(`Private report ${printable(reportId)}`, MARGIN, PAGE_HEIGHT - 8);
    pdf.text(`${number} / ${totalPages}`, PAGE_WIDTH - MARGIN, PAGE_HEIGHT - 8, { align: 'right' });
  }

  pdf.save(`vysel-style-dna-${reportId}.pdf`);
}
