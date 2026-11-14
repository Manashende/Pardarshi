import { useState } from 'react';
import MyExamsPanel from '../components/panels/MyExamsPanel';
import ExamTakingView from '../components/panels/ExamTakingView';
import SectionHeader from '../components/common/SectionHeader';

export default function MyExamsPage() {
  const [activeVariantId, setActiveVariantId] = useState(null);

  if (activeVariantId) {
    return (
      <ExamTakingView
        variantId={activeVariantId}
        onExit={() => setActiveVariantId(null)}
      />
    );
  }

  return (
    <div className="dashboard">
      <SectionHeader title="My Exams" subtitle="Applications awaiting allocation, and allocated exams" />
      <MyExamsPanel onEnterExam={setActiveVariantId} />
    </div>
  );
}