import { useEffect, useState } from 'react';
import LoginForm from './components/auth/LoginForm';
import RegisterForm from './components/auth/RegisterForm';
import TopBar from './components/common/TopBar';
import Sidebar from './components/common/Sidebar';
import Tabs from './components/common/Tabs';
import OverviewPage from './pages/OverviewPage';
import AdministrationPage from './pages/AdministrationPage';
import LedgerPage from './pages/LedgerPage';
import ExamSetupPage from './pages/ExamSetupPage';
import ItemBankPage from './pages/ItemBankPage';
import CustodianPage from './pages/CustodianPage';
import CentreOperatorPage from './pages/CentreOperatorPage';
import { useTheme } from './hooks/useTheme';
import { clearAuthToken, setAuthToken, setSessionExpiredHandler } from './api/client';
import StudentPage from './pages/StudentPage';
import MyExamsPage from './pages/MyExamsPage';
import AuditorGovernancePage from './pages/AuditorGovernancePage';
import AuditorOversightPage from './pages/AuditorOversightPage';

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
    items.push({ id: 'oversight', label: 'Oversight', hint: 'Read-only approvals & flags' });
    items.push({ id: 'ledger', label: 'Audit Ledger', hint: 'Full event trail' });
    items.push({ id: 'auditor-governance', label: 'Auditor Approvals', hint: 'Vote on new auditors' });
  }
  if (role === 'CONTRIBUTOR') {
    items.push({ id: 'item-bank', label: 'Item Bank', hint: 'Submit questions' });
  }
  if (role === 'CUSTODIAN') {
    items.push({ id: 'custodian', label: 'Custodian', hint: 'Share submission' });
  }
  if (role === 'CENTRE_OPERATOR') {
    items.push({ id: 'centre-operator', label: 'Centre Operator', hint: 'Unlock & print' });
  }
  if (role === 'STUDENT') {
    items.push({ id: 'student', label: 'Apply', hint: 'Submit exam application' });
    items.push({ id: 'my-exams', label: 'My Exams', hint: 'Allocation status' });
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
  'centre-operator': CentreOperatorPage,
  'student': StudentPage,
  'my-exams': MyExamsPage,
  'auditor-governance': AuditorGovernancePage,
  'oversight': AuditorOversightPage,
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
  const [sessionExpiredMessage, setSessionExpiredMessage] = useState(null);

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

  // Registered once so any 401 from an expired/revoked token — surfacing
  // from any API call, anywhere in the app — routes straight back to
  // login instead of leaving the user stuck looking at a raw error message.
  useEffect(() => {
    setSessionExpiredHandler(() => handleLogout('Your session expired — please log in again.'));
    // eslint-disable-next-line react-hooks/exhaustive-deps
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

  function handleLogout(sessionExpiredMessage) {
    clearAuthToken();
    setUser(null);
    setView('login');
    setActiveNavView(null);
    localStorage.removeItem(SESSION_STORAGE_KEY);
    // Only set on an actual session-expiry logout (see below) — a normal
    // manual "Log out" click calls this with no argument, so the message
    // stays cleared for that case.
    setSessionExpiredMessage(sessionExpiredMessage ?? null);
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
        sessionExpiredMessage={sessionExpiredMessage}
      />
    );
  }

  const navItems = navItemsForRole(user.role);
  const ActivePage = activeNavView ? PAGE_COMPONENTS[activeNavView] : null;
  // A sidebar only earns its place when there's enough content that
  // persistent visibility matters (Admin, Auditor today). A 2-3 item nav
  // (Student today) is really "a few views of one subject" — tabs say
  // that better than a sidebar implying separate destinations. A single
  // item (Custodian, Centre Operator, Contributor) needs no nav chrome
  // at all, since it's always already active.
  const navStyle = navItems.length <= 1 ? 'none' : navItems.length <= 3 ? 'tabs' : 'sidebar';

  return (
    <div className={navStyle === 'sidebar' ? 'app-shell-with-sidebar' : 'app-shell-no-sidebar'}>
      {navStyle === 'sidebar' && (
        <Sidebar items={navItems} activeView={activeNavView} onSelectView={setActiveNavView} />
      )}
      <div className="app-main-column">
        <TopBar user={user} theme={theme} onToggleTheme={toggleTheme} onLogout={handleLogout} />
        {navStyle === 'tabs' && (
          <div className="app-top-tabs-wrap">
            <Tabs
              tabs={navItems.map((item) => ({ id: item.id, label: item.label }))}
              activeTab={activeNavView}
              onChange={setActiveNavView}
            />
          </div>
        )}
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