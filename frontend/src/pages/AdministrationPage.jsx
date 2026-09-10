import PendingApprovalsPanel from '../components/panels/PendingApprovalsPanel';
import LedgerIntegrityBadge from '../components/panels/LedgerIntegrityBadge';
import FlaggedAttemptsPanel from '../components/panels/FlaggedAttemptsPanel';
import SectionHeader from '../components/common/SectionHeader';

export default function AdministrationPage() {
  return (
    <div className="dashboard">
      <SectionHeader title="Administration" subtitle="System-wide — not tied to a single exam" />
      <div className="dashboard-grid">
        <PendingApprovalsPanel />
        <div className="admin-side-column">
          <LedgerIntegrityBadge />
          <FlaggedAttemptsPanel />
        </div>
      </div>
    </div>
  );
}