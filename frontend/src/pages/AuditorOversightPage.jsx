import { useState } from 'react';
import ReadOnlyPendingApprovalsPanel from '../components/panels/ReadOnlyPendingApprovalsPanel';
import LedgerIntegrityBadge from '../components/panels/LedgerIntegrityBadge';
import FlaggedAttemptsPanel from '../components/panels/FlaggedAttemptsPanel';
import ReadOnlyCentreOperatorAssignmentsPanel from '../components/panels/ReadOnlyCentreOperatorAssignmentsPanel';
import ReadOnlyCandidateAssignmentsPanel from '../components/panels/ReadOnlyCandidateAssignmentsPanel';
import ReadOnlyCompileProposalsPanel from '../components/panels/ReadOnlyCompileProposalsPanel';
import SectionHeader from '../components/common/SectionHeader';
import Tabs from '../components/common/Tabs';

const TABS = [
  { id: 'flags', label: 'Flagged Attempts' },
  { id: 'approvals', label: 'Approvals' },
  { id: 'centre-operators', label: 'Centre Operators' },
  { id: 'candidates', label: 'Candidate Allocations' },
  { id: 'compile-proposals', label: 'Compile Proposals' },
];

export default function AuditorOversightPage() {
  const [activeTab, setActiveTab] = useState('flags');

  return (
    <div className="dashboard">
      <SectionHeader title="Oversight" subtitle="Read-only — system-wide, not tied to a single exam" />

      <div className="tabs-with-ledger-row">
        <Tabs tabs={TABS} activeTab={activeTab} onChange={setActiveTab} />
        <LedgerIntegrityBadge />
      </div>

      <div style={{ display: activeTab === 'flags' ? 'block' : 'none' }}>
        <FlaggedAttemptsPanel />
      </div>
      <div style={{ display: activeTab === 'approvals' ? 'block' : 'none' }}>
        <ReadOnlyPendingApprovalsPanel />
      </div>
      <div className="panel" style={{ display: activeTab === 'centre-operators' ? 'block' : 'none' }}>
        <p className="panel-eyebrow">Centre Operator Assignments (read-only)</p>
        <ReadOnlyCentreOperatorAssignmentsPanel />
      </div>
      <div className="panel" style={{ display: activeTab === 'candidates' ? 'block' : 'none' }}>
        <p className="panel-eyebrow">Candidate Allocations (read-only)</p>
        <ReadOnlyCandidateAssignmentsPanel />
      </div>
      <div className="panel" style={{ display: activeTab === 'compile-proposals' ? 'block' : 'none' }}>
        <p className="panel-eyebrow">Pending Compile Proposals (read-only)</p>
        <ReadOnlyCompileProposalsPanel />
      </div>
    </div>
  );
}