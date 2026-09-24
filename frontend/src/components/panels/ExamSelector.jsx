import { useEffect, useState } from 'react';
import { listExamEvents, listVariantsForExamEvent } from '../../api/client';
import { formatTimestamp } from '../../utils/formatters';
import './ExamSelector.css';

export default function ExamSelector({ onSelectionChange }) {
  const [examEvents, setExamEvents] = useState([]);
  const [variants, setVariants] = useState([]);
  const [selectedExamId, setSelectedExamId] = useState('');
  const [selectedVariantId, setSelectedVariantId] = useState('');
  const [error, setError] = useState(null);

  useEffect(() => {
    listExamEvents()
      .then((events) => {
        setExamEvents(events);
        if (events.length > 0) setSelectedExamId(events[0].exam_event_id);
      })
      .catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    if (!selectedExamId) {
      setVariants([]);
      return;
    }
    listVariantsForExamEvent(selectedExamId)
      .then((v) => {
        setVariants(v);
        setSelectedVariantId(v.length > 0 ? v[0].variant_id : '');
      })
      .catch((e) => setError(e.message));
  }, [selectedExamId]);

  useEffect(() => {
    onSelectionChange({ examEventId: selectedExamId, variantId: selectedVariantId });
  }, [selectedExamId, selectedVariantId]);

  if (error) {
    return <div className="panel"><p className="panel-error">{error}</p></div>;
  }

  return (
    <div className="exam-selector">
      <div className="selector-field">
        <label>Exam Event</label>
        <select value={selectedExamId} onChange={(e) => setSelectedExamId(e.target.value)}>
          {examEvents.length === 0 && <option value="">No exam events yet</option>}
          {examEvents.map((ev) => (
            <option key={ev.exam_event_id} value={ev.exam_event_id}>
              {ev.exam_name} — {ev.status} — {formatTimestamp(ev.exam_start_epoch)}
            </option>
          ))}
        </select>
      </div>
      <div className="selector-field">
        <label>Paper Variant</label>
        <select value={selectedVariantId} onChange={(e) => setSelectedVariantId(e.target.value)}
                disabled={variants.length === 0}>
          {variants.length === 0 && <option value="">No variants compiled yet</option>}
          {variants.map((v) => (
            <option key={v.variant_id} value={v.variant_id}>Variant {v.variant_index}</option>
          ))}
        </select>
      </div>
    </div>
  );
}