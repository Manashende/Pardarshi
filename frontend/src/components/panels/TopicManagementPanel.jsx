import { useEffect, useState } from 'react';
import { listTopics, createTopic } from '../../api/client';

export default function TopicManagementPanel() {
  const [topics, setTopics] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [newName, setNewName] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    load();
  }, []);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const data = await listTopics();
      setTopics(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleAdd(e) {
    e.preventDefault();
    if (!newName.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      await createTopic(newName.trim());
      setNewName('');
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="panel">
      <p className="panel-eyebrow">Topics</p>
      <span className="login-hint">
        Subjects available when submitting questions. Can't be renamed or deleted once added.
      </span>

      {error && <p className="login-error">{error}</p>}

      <form onSubmit={handleAdd} style={{ marginTop: 12 }}>
        <div className="form-field">
          <label>New Topic Name</label>
          <input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="e.g. Thermodynamics" />
        </div>
        <button type="submit" disabled={submitting} className="login-submit">
          {submitting ? 'Adding…' : 'Add Topic'}
        </button>
      </form>

      {loading ? (
        <p className="empty-state" style={{ marginTop: 16 }}>Loading…</p>
      ) : topics.length === 0 ? (
        <p className="empty-state" style={{ marginTop: 16 }}>
          No topics added yet — Contributors can't submit questions until at least one exists.
        </p>
      ) : (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 16 }}>
          {topics.map((t) => (
            <span
              key={t.id}
              className="login-hint"
              style={{
                border: '1px solid var(--verdigris, #4E9B87)',
                borderRadius: 999,
                padding: '4px 14px',
                margin: 0,
              }}
            >
              {t.name}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}