import { useEffect, useState } from 'react';
import { getPrintJobsSummaryForVariant } from '../../api/client';
import { makespanToHuman } from '../../utils/formatters';
import './PrintJobPanel.css';

const CBSE_BASELINE_SECONDS = 90 * 60;

export default function PrintJobPanel({ variantId }) {
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState(null);

  async function refresh() {
    try {
      const data = await getPrintJobsSummaryForVariant(variantId);
      setSummary(data);
      setError(null);
    } catch (e) {
      setError(e.message);
    }
  }

  useEffect(() => {
    if (!variantId) return;
    refresh();
    const interval = setInterval(refresh, 5000);
    return () => clearInterval(interval);
  }, [variantId]);

  if (!variantId) {
    return <div className="panel"><p className="panel-empty">No variant selected.</p></div>;
  }
  if (error) {
    return <div className="panel"><p className="panel-error">{error}</p></div>;
  }
  if (!summary || summary.jobs.length === 0) {
    return (
      <div className="panel">
        <p className="panel-eyebrow">Print Dispatch</p>
        <p className="panel-empty">No print jobs yet — dispatched automatically on successful unlock.</p>
      </div>
    );
  }

  const speedup = summary.makespan_seconds ? (CBSE_BASELINE_SECONDS / summary.makespan_seconds).toFixed(1) : null;

  return (
    <div className="panel">
      <p className="panel-eyebrow">Print Dispatch — {summary.num_printers_used} parallel printers</p>

      <div className="print-stats-row">
        <div className="print-stat">
          <span className="print-stat-value">{summary.total_copies}</span>
          <span className="print-stat-label">copies</span>
        </div>
        <div className="print-stat">
          <span className="print-stat-value">{makespanToHuman(summary.makespan_seconds)}</span>
          <span className="print-stat-label">makespan</span>
        </div>
        {speedup && (
          <div className="print-stat print-stat-highlight">
            <span className="print-stat-value">{speedup}×</span>
            <span className="print-stat-label">vs CBSE baseline</span>
          </div>
        )}
      </div>

      <div className="print-jobs-grid">
        {summary.jobs.map((job) => (
          <div key={job.printer_id} className="print-job-chip">
            <span className="print-job-chip-id">Printer {job.printer_id}</span>
            <span className="print-job-chip-copies">{job.copies} copies</span>
          </div>
        ))}
      </div>
    </div>
  );
}