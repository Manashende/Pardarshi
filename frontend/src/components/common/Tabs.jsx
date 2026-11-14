import './Tabs.css';

export default function Tabs({ tabs, activeTab, onChange }) {
  return (
    <div className="tabs-bar" role="tablist">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          role="tab"
          type="button"
          aria-selected={activeTab === tab.id}
          className={`tabs-item ${activeTab === tab.id ? 'tabs-item-active' : ''}`}
          onClick={() => onChange(tab.id)}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}