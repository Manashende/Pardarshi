import Seal from './Seal';
import ThemeToggle from './ThemeToggle';
import './TopBar.css';

export default function TopBar({ user, theme, onToggleTheme, onLogout }) {
  return (
    <header className="topbar">
      <div className="topbar-brand">
        <Seal size={28} />
        <span className="topbar-wordmark">Pardarshi</span>
        <span className="topbar-divider">/</span>
        <span className="topbar-section">Console</span>
      </div>
      <div className="topbar-actions">
        <div className="topbar-user">
          <span className="topbar-user-name">{user.full_name}</span>
          <span className="topbar-user-role">{user.role}</span>
        </div>
        <ThemeToggle theme={theme} onToggle={onToggleTheme} />
        <button className="topbar-logout" onClick={onLogout}>Log out</button>
      </div>
    </header>
  );
}