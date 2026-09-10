import { useEffect, useState } from 'react';
import LoginForm from './components/auth/LoginForm';
import RegisterForm from './components/auth/RegisterForm';
import TopBar from './components/common/TopBar';
import Sidebar from './components/common/Sidebar';
import OverviewPage from './pages/OverviewPage';
import AdministrationPage from './pages/AdministrationPage';
import LedgerPage from './pages/LedgerPage';
import ExamSetupPage from './pages/ExamSetupPage';
import ItemBankPage from './pages/ItemBankPage';
import CustodianPage from './pages/CustodianPage';
import { useTheme } from './hooks/useTheme';
import { clearAuthToken, setAuthToken } from './api/client';

const SESSION_STORAGE_KEY = 'pardarshi_session_user';

// Every role's available pages, in one place. Extend this as
// centre-operator pages get built — nothing else in this file needs to
// change when that happens.
function navItemsForRole(role) {
  const items = [];
  if (role === 'ADMIN') {
    items.push({ id: 'overview', label: 'Overview', hint: 'Exam operations' });
    items.push({ id: 'exam-setup', label: 'Exam Setup', hint: 'Centres & exam events' });
    items.push({ id: 'administration', label: 'Administration', hint: 'Approvals & flags' });
    items.push({ id: 'ledger', label: 'Audit Ledger', hint: 'Full event trail' });
  }
  if (role === 'AUDITOR') {
    items.push({ id: 'overview', label: 'Overview', hint: 'Exam operations' });
    items.push({ id: 'administration', label: 'Administration', hint: 'Approvals & flags' });
    items.push({ id: 'ledger', label: 'Audit Ledger', hint: 'Full event trail' });
  }
  if (role === 'CONTRIBUTOR') {
    items.push({ id: 'item-bank', label: 'Item Bank', hint: 'Submit questions' });
  }
  if (role === 'CUSTODIAN') {
    items.push({ id: 'custodian', label: 'Custodian', hint: 'Share submission' });
  }
  return items;
}

const PAGE_COMPONENTS = {
  'overview': OverviewPage,
  'exam-setup': ExamSetupPage,
  'administration': AdministrationPage,
  'ledger': LedgerPage,
  'item-bank': ItemBankPage,
  'custodian': CustodianPage,
};

function loadStoredSession() {
  try {
    const raw = localStorage.getItem(SESSION_STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function App() {
  const [user, setUser] = useState(null);
  const [view, setView] = useState('login');
  const { theme, toggleTheme } = useTheme();
  const [activeNavView, setActiveNavView] = useState(null);
  const [restoring, setRestoring] = useState(true);

  // On first load, restore a previous session from localStorage so a
  // page refresh doesn't force a re-login. There's no "who am I"
  // endpoint yet, so we persist the user object we already got back
  // from login() alongside the token, rather than re-fetching it.
  useEffect(() => {
    const stored = loadStoredSession();
    if (stored && stored.token && stored.user) {
      setAuthToken(stored.token);
      setUser(stored.user);
      const items = navItemsForRole(stored.user.role);
      setActiveNavView(items.length > 0 ? items[0].id : null);
    }
    setRestoring(false);
  }, []);

  function handleLoginSuccess(loggedInUser, token) {
    setUser(loggedInUser);
    const items = navItemsForRole(loggedInUser.role);
    setActiveNavView(items.length > 0 ? items[0].id : null);
    try {
      localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify({ token, user: loggedInUser }));
    } catch {
      // Non-fatal — the session just won't survive a refresh this time.
    }
  }

  function handleLogout() {
    clearAuthToken();
    setUser(null);
    setView('login');
    setActiveNavView(null);
    localStorage.removeItem(SESSION_STORAGE_KEY);
  }

  // Briefly render nothing while we check for a stored session, so we
  // don't flash the login screen before immediately replacing it.
  if (restoring) {
    return null;
  }

  if (!user) {
    if (view === 'register') {
      return <RegisterForm onBackToLogin={() => setView('login')} />;
    }
    return (
      <LoginForm
        onLoginSuccess={handleLoginSuccess}
        theme={theme}
        onToggleTheme={toggleTheme}
        onGoToRegister={() => setView('register')}
      />
    );
  }

  const navItems = navItemsForRole(user.role);
  const ActivePage = activeNavView ? PAGE_COMPONENTS[activeNavView] : null;

  return (
    <div className="app-shell-with-sidebar">
      <Sidebar items={navItems} activeView={activeNavView} onSelectView={setActiveNavView} />
      <div className="app-main-column">
        <TopBar user={user} theme={theme} onToggleTheme={toggleTheme} onLogout={handleLogout} />
        {!ActivePage && (
          <div className="dashboard">
            <p className="panel-empty">
              Your role ({user.role}) has no pages in this app yet.
            </p>
          </div>
        )}
        {ActivePage && <ActivePage />}
      </div>
    </div>
  );
}

export default App;