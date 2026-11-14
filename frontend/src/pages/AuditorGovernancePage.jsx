import { useState } from 'react';
import AuditorGovernancePanel from '../components/panels/AuditorGovernancePanel';
import PendingRevealVotesPanel from '../components/panels/PendingRevealVotesPanel';
import SectionHeader from '../components/common/SectionHeader';
import Tabs from '../components/common/Tabs';

const TABS = [
  { id: 'auditors', label: 'Auditor Approval' },
  { id: 'reveals', label: 'Contributor Identity Reveals' },
];

export default function AuditorGovernancePage() {
  const [activeTab, setActiveTab] = useState('auditors');

  return (
    <div className="dashboard">
      <SectionHeader title="Governance" subtitle="Vote on new Auditors and contributor identity reveals" />

      <Tabs tabs={TABS} activeTab={activeTab} onChange={setActiveTab} />

      <div className="panel" style={{ display: activeTab === 'auditors' ? 'block' : 'none' }}>
        <p className="panel-eyebrow">Auditor Approval</p>
        <AuditorGovernancePanel />
      </div>
      <div className="panel" style={{ display: activeTab === 'reveals' ? 'block' : 'none' }}>
        <p className="panel-eyebrow">Contributor Identity Reveal Requests</p>
        <PendingRevealVotesPanel />
      </div>
    </div>
  );
}