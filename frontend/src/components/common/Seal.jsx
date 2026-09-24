export default function Seal({ size = 56, active = true }) {
  const color = active ? 'var(--verdigris)' : 'var(--text-dim)';
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" fill="none">
      <circle cx="32" cy="32" r="30" stroke={color} strokeWidth="1.5" />
      <circle cx="32" cy="32" r="25.5" stroke={color} strokeWidth="0.75" opacity="0.6" />
      <circle cx="32" cy="32" r="21" stroke={color} strokeWidth="1" opacity="0.35" />
      <path d="M22 33 L28 39 L42 25" stroke={color} strokeWidth="2.5"
        strokeLinecap="round" strokeLinejoin="round" fill="none" />
    </svg>
  );
}