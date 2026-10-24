export function LogoMark({ size = 34 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" aria-hidden focusable="false">
      <defs>
        <linearGradient id="vf-g" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#8f7cff" />
          <stop offset="1" stopColor="#5b3df5" />
        </linearGradient>
      </defs>
      <path d="M5 8h8.2L20 24.5 26.8 8H35L23.6 34a3.8 3.8 0 0 1-7.2 0z" fill="url(#vf-g)" />
      <path d="M15.5 17.5l3.6 3.6 6.4-7" fill="none" stroke="#fff" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function Wordmark() {
  return (
    <span className="brand-text">
      <strong>VERIFAI</strong>
      <small>Trust. Verify. Move Forward.</small>
    </span>
  );
}
