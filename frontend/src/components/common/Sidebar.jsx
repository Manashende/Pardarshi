import './Sidebar.css';

export default function Sidebar({ items, activeView, onSelectView }) {
  return (
    <nav className="sidebar">
      {items.map((item) => (
        <button
          key={item.id}
          className={`sidebar-item ${activeView === item.id ? 'sidebar-item-active' : ''}`}
          onClick={() => onSelectView(item.id)}
        >
          <span className="sidebar-item-label">{item.label}</span>
          <span className="sidebar-item-hint">{item.hint}</span>
        </button>
      ))}
    </nav>
  );
}