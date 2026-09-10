import './SectionHeader.css';

export default function SectionHeader({ title, subtitle }) {
  return (
    <div className="section-header">
      <h3 className="section-header-title">{title}</h3>
      {subtitle && <span className="section-header-subtitle">{subtitle}</span>}
    </div>
  );
}