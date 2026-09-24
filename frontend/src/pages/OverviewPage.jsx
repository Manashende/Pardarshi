import { useState } from 'react';
import ExamSelector from '../components/panels/ExamSelector';
import ShareStatusPanel from '../components/panels/ShareStatusPanel';
import PrintJobPanel from '../components/panels/PrintJobPanel';
import SectionHeader from '../components/common/SectionHeader';

export default function OverviewPage() {
  const [selection, setSelection] = useState({ examEventId: '', variantId: '' });

  return (
    <div className="dashboard">
      <SectionHeader title="Overview" subtitle="Scoped to the selected exam event and variant" />
      <div className="dashboard-selector-row">
        <ExamSelector onSelectionChange={setSelection} />
      </div>
      <div className="dashboard-grid">
        <ShareStatusPanel variantId={selection.variantId} />
        <PrintJobPanel variantId={selection.variantId} />
      </div>
    </div>
  );
}