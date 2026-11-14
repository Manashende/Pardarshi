import { useState } from 'react';
import Tabs from '../common/Tabs';
import ReadOnlyCentreOperatorAssignmentsPanel from './ReadOnlyCentreOperatorAssignmentsPanel';
import ReadOnlyCandidateAssignmentsPanel from './ReadOnlyCandidateAssignmentsPanel';
import ReadOnlyCompileProposalsPanel from './ReadOnlyCompileProposalsPanel';

const TABS = [
  { id: 'centre-operators', label: 'Centre Operators' },
  { id: 'candidates', label: 'Candidate Allocations' },
  { id: 'compile-proposals', label: 'Compile Proposals' },
];

export default function OversightTablesPanel() {
  const [activeTab, setActiveTab] = useState('centre-operators');

  return (
    <div className="panel">
      <Tabs tabs={TABS} activeTab={activeTab} onChange={setActiveTab} />
      <div style={{ display: activeTab === 'centre-operators' ? 'block' : 'none' }}>
        <ReadOnlyCentreOperatorAssignmentsPanel />
      </div>
      <div style={{ display: activeTab === 'candidates' ? 'block' : 'none' }}>
        <ReadOnlyCandidateAssignmentsPanel />
      </div>
      <div style={{ display: activeTab === 'compile-proposals' ? 'block' : 'none' }}>
        <ReadOnlyCompileProposalsPanel />
      </div>
    </div>
  );
}