import { useState } from 'react';
import CentreForm from '../components/panels/CentreForm';
import ExamEventForm from '../components/panels/ExamEventForm';
import ProposeCompileForm from '../components/panels/ProposeCompileForm';
import ExamEventsStatusPanel from '../components/panels/ExamEventsStatusPanel';
import '../components/common/ConfirmModal.css';
import TopicManagementPanel from '../components/panels/TopicManagementPanel';
import PageHeader from '../components/common/PageHeader';
import Tabs from '../components/common/Tabs';

const SECRET_STORAGE_PREFIX = 'pardarshi_assignment_secret_';

function saveSecretLocally(examEventId, secret) {
  try {
    localStorage.setItem(SECRET_STORAGE_PREFIX + examEventId, secret);
  } catch {
    // Non-fatal — confirm-time entry just falls back to manual paste.
  }
}

const TABS = [
  { id: 'status', label: 'Status' },
  { id: 'setup', label: 'Centres & Topics' },
  { id: 'create', label: 'Create Exam' },
  { id: 'propose', label: 'Propose Compile' },
];

export default function ExamSetupPage() {
  const [activeTab, setActiveTab] = useState('status');
  const [lastCreatedEvent, setLastCreatedEvent] = useState(null);
  const [centreRefreshKey, setCentreRefreshKey] = useState(0);
  const [examListRefreshKey, setExamListRefreshKey] = useState(0);

  function handleEventCreated(result) {
    saveSecretLocally(result.exam_event_id, result.assignment_secret);
    setLastCreatedEvent(result);
    setExamListRefreshKey((k) => k + 1);
  }

  return (
    <div className="dashboard">
      <PageHeader title="Exam Setup" subtitle="Centres, topics, and exam events" />
      <Tabs tabs={TABS} activeTab={activeTab} onChange={setActiveTab} />

      {activeTab === 'status' && <ExamEventsStatusPanel key={examListRefreshKey} />}

      {activeTab === 'setup' && (
        <div className="setup-grid">
          <CentreForm onCreated={() => setCentreRefreshKey((k) => k + 1)} />
          <TopicManagementPanel />
        </div>
      )}

      {activeTab === 'create' && (
        <ExamEventForm key={centreRefreshKey} onCreated={handleEventCreated} />
      )}

      {lastCreatedEvent && (
        <div className="confirm-modal-backdrop">
          <div className="confirm-modal">
            <h3 className="confirm-modal-title">Exam Event Created</h3>
            <p className="ledger-cell-mono" style={{ wordBreak: 'break-all' }}>exam_event_id: {lastCreatedEvent.exam_event_id}</p>
            <p className="ledger-cell-mono" style={{ wordBreak: 'break-all' }}>assignment_secret: {lastCreatedEvent.assignment_secret}</p>
            <p className="login-hint" style={{ marginTop: 10 }}>
              Secret saved in this browser for later. Let another admin propose this exam's compile —
              you'll confirm it yourself from Administration → Compile Queue.
            </p>
            <div className="confirm-modal-actions">
              <button type="button" className="confirm-modal-confirm" onClick={() => setLastCreatedEvent(null)}>
                Got it
              </button>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'propose' && <ProposeCompileForm />}
    </div>
  );
}