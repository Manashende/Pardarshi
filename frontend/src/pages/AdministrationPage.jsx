import { useState } from 'react';
import PendingApprovalsPanel from '../components/panels/PendingApprovalsPanel';
import LedgerIntegrityBadge from '../components/panels/LedgerIntegrityBadge';
import FlaggedAttemptsPanel from '../components/panels/FlaggedAttemptsPanel';
import CentreOperatorAssignmentPanel from '../components/panels/CentreOperatorAssignmentPanel';
import CandidateAllocationPanel from '../components/panels/CandidateAllocationPanel';
import PendingCompileProposalsPanel from '../components/panels/PendingCompileProposalsPanel';
import AllQuestionsPanel from '../components/panels/AllQuestionsPanel';
import PageHeader from '../components/common/PageHeader';
import Tabs from '../components/common/Tabs';

const TABS = [
  { id: 'flags', label: 'Flagged Attempts' },
  { id: 'approvals', label: 'Approvals' },
  { id: 'compile', label: 'Compile Queue' },
  { id: 'assignments', label: 'Assignments' },
  { id: 'item-bank', label: 'Item Bank' },
];

export default function AdministrationPage() {
  const [activeTab, setActiveTab] = useState('flags');

  return (
    <div className="dashboard">
      <PageHeader title="Administration" subtitle="System-wide — not tied to a single exam" />

      <div className="tabs-with-ledger-row">
        <Tabs tabs={TABS} activeTab={activeTab} onChange={setActiveTab} />
        <LedgerIntegrityBadge />
      </div>

      <div style={{ display: activeTab === 'flags' ? 'block' : 'none' }}>
        <FlaggedAttemptsPanel />
      </div>
      <div style={{ display: activeTab === 'approvals' ? 'block' : 'none' }}>
        <PendingApprovalsPanel />
      </div>
      <div style={{ display: activeTab === 'compile' ? 'block' : 'none' }}>
        <PendingCompileProposalsPanel />
      </div>
      <div style={{ display: activeTab === 'assignments' ? 'block' : 'none' }}>
        <CentreOperatorAssignmentPanel />
        <CandidateAllocationPanel />
      </div>
      <div style={{ display: activeTab === 'item-bank' ? 'block' : 'none' }}>
        <AllQuestionsPanel />
      </div>
    </div>
  );
}