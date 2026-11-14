import { useEffect, useRef, useState } from 'react';
import './SearchableSelect.css';

export default function SearchableSelect({
  options,
  value,
  onChange,
  placeholder = 'Select…',
  getLabel = (o) => o.label,
  getValue = (o) => o.value,
  disabled = false,
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const containerRef = useRef(null);

  useEffect(() => {
    function handleClickOutside(e) {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setOpen(false);
        setQuery('');
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const selected = options.find((o) => getValue(o) === value);
  const filtered = options.filter((o) => getLabel(o).toLowerCase().includes(query.toLowerCase()));

  return (
    <div className="searchable-select" ref={containerRef}>
      <button
        type="button"
        className="searchable-select-trigger"
        disabled={disabled}
        onClick={() => setOpen((o) => !o)}
      >
        <span className={selected ? '' : 'searchable-select-placeholder'}>
          {selected ? getLabel(selected) : placeholder}
        </span>
        <span className="searchable-select-caret">▾</span>
      </button>
      {open && !disabled && (
        <div className="searchable-select-panel">
          <input
            type="text"
            className="searchable-select-search"
            placeholder="Search…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            autoFocus
          />
          <div className="searchable-select-list">
            {filtered.length === 0 && <div className="searchable-select-empty">No matches</div>}
            {filtered.map((o) => (
              <button
                type="button"
                key={getValue(o)}
                className={`searchable-select-option ${getValue(o) === value ? 'searchable-select-option-active' : ''}`}
                onClick={() => { onChange(getValue(o)); setOpen(false); setQuery(''); }}
              >
                {getLabel(o)}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}