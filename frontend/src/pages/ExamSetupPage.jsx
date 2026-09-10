import { useState } from 'react';
import CentreForm from '../components/panels/CentreForm';
import ExamEventForm from '../components/panels/ExamEventForm';
import CompileForm from '../components/panels/CompileForm';
import SectionHeader from '../components/common/SectionHeader';

export default function ExamSetupPage() {
  const [lastCreatedEvent, setLastCreatedEvent] = useState(null);
  const [centreRefreshKey, setCentreRefreshKey] = useState(0);
  const [lastCreatedFormValues, setLastCreatedFormValues] = useState(null);

  function handleEventCreated(result, totalCustodians) {
    setLastCreatedEvent(result);
    setLastCreatedFormValues({ totalCustodians });
  }

  return (
    <div className="dashboard">
      <SectionHeader title="Exam Centres" subtitle="Register centres before creating an exam event" />
      <CentreForm onCreated={() => setCentreRefreshKey((k) => k + 1)} />

      <SectionHeader title="Exam Event" subtitle="Create and compile a new exam event" />
      <ExamEventForm key={centreRefreshKey} onCreated={handleEventCreated} />

      {lastCreatedEvent && !lastCreatedEvent.compiled && (
        <>
          <div className="panel form-success-panel">
            <p className="panel-eyebrow">Exam Event Created</p>
            <p className="ledger-cell-mono">exam_event_id: {lastCreatedEvent.exam_event_id}</p>
          </div>

          <SectionHeader title="Compile" subtitle="Assign custodians and encrypt the paper" />
          <CompileForm
            examEventId={lastCreatedEvent.exam_event_id}
            totalCustodians={lastCreatedFormValues.totalCustodians}
            assignmentSecret={lastCreatedEvent.assignment_secret}
            onCompiled={(result) => setLastCreatedEvent({ ...lastCreatedEvent, compiled: true, compileResult: result })}
          />
        </>
      )}

      {lastCreatedEvent && lastCreatedEvent.compiled && (
        <div className="panel form-success-panel">
          <p className="panel-eyebrow">Exam Event Compiled</p>
          <p style={{ fontSize: 13 }}>
            Head to Overview to monitor share submission, unlock, and print dispatch for this exam.
          </p>
        </div>
      )}
    </div>
  );
}