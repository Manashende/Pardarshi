import { useEffect, useState } from 'react';
import { getLedger, verifyLedger } from '../api/client';
import { formatTimestamp } from '../utils/formatters';
import SectionHeader from '../components/common/SectionHeader';
import './LedgerPage.css';

export default function LedgerPage() {
  const [entries, setEntries] = useState([]);
  const [verifyResult, setVerifyResult] = useState(null);
  const [error, setError] = useState(null);

  async function refresh() {
    try {
      const [ledgerData, verifyData] = await Promise.all([getLedger(), verifyLedger()]);
      setEntries(ledgerData);
      setVerifyResult(verifyData);
      setError(null);
    } catch (e) {
      setError(e.message);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  return (
    <div className="dashboard">
      <SectionHeader
        title="Audit Ledger"
        subtitle={verifyResult ? `${verifyResult.chain_intact ? 'Chain intact' : 'CHAIN BROKEN'} — ${verifyResult.entries_checked} entries` : ''}
      />

      {error && <p className="panel-error">{error}</p>}

      {verifyResult && !verifyResult.chain_intact && (
        <div className="ledger-tamper-banner">
          Integrity check failed at entry #{verifyResult.first_broken_index}. This indicates the audit
          trail has been altered — investigate immediately.
        </div>
      )}

      <div className="panel ledger-table-wrap">
        <table className="ledger-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Event</th>
              <th>Time</th>
              <th>Details</th>
              <th>Hash</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((e) => (
              <tr key={e.index}>
                <td className="ledger-cell-mono">{e.index}</td>
                <td>{e.event_type}</td>
                <td className="ledger-cell-mono">{formatTimestamp(e.timestamp)}</td>
                <td className="ledger-cell-details">{JSON.stringify(e.details)}</td>
                <td className="ledger-cell-mono ledger-cell-hash" title={e.entry_hash}>
                  {e.entry_hash.slice(0, 10)}…
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {entries.length === 0 && !error && <p className="panel-empty" style={{ padding: 20 }}>No ledger entries yet.</p>}
      </div>
    </div>
  );
}