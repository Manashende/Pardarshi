export default function ThemeToggle({ theme, onToggle }) {
  return (
    <button onClick={onToggle} className="theme-toggle" aria-label="Toggle light/dark theme">
      {theme === 'dark' ? '☀ Light' : '☾ Dark'}
    </button>
  );
}