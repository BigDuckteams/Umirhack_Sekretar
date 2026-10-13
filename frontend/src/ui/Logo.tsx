/**
 * Знак «Онлайн-деканата»: печать декана с зубчатым краем, на ней лист документа и красная галочка-штамп.
 * Градиенты определены один раз в <LogoDefs/> (кладётся в корень приложения), поэтому знак можно ставить где угодно.
 */
export function LogoDefs() {
  return (
    <svg width="0" height="0" aria-hidden="true" focusable="false" style={{ position: "absolute" }}>
      <defs>
        <linearGradient id="dk-logo-bg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#27467a" />
          <stop offset="1" stopColor="#0c1629" />
        </linearGradient>
        <radialGradient id="dk-logo-glow" cx=".28" cy=".18" r=".95">
          <stop offset="0" stopColor="#f6b24c" stopOpacity=".42" />
          <stop offset="1" stopColor="#f6b24c" stopOpacity="0" />
        </radialGradient>
      </defs>
    </svg>
  );
}

interface Props {
  size?: number;
  /** без плитки-подложки: знак ложится на любой тёмный фон (аватар секретаря) */
  bare?: boolean;
  className?: string;
}

export function Logo({ size = 36, bare = false, className = "" }: Props) {
  return (
    <svg className={`logo ${className}`} viewBox="0 0 40 40" width={size} height={size} aria-hidden="true" focusable="false">
      {!bare && (
        <>
          <rect width="40" height="40" rx="12" fill="url(#dk-logo-bg)" />
          <rect width="40" height="40" rx="12" fill="url(#dk-logo-glow)" />
          <rect x=".5" y=".5" width="39" height="39" rx="11.5" fill="none" stroke="#fff" strokeOpacity=".16" />
        </>
      )}
      <g className="logo-teeth-wrap">
        <circle className="logo-teeth" cx="20" cy="20" r="16.4" fill="none" stroke="#f6b24c" strokeOpacity={bare ? 0.7 : 0.6} strokeWidth="1.3" strokeDasharray="1.5 2.5" strokeLinecap="round" />
      </g>
      <g className="logo-sheet">
        <g transform="rotate(-7 20 20)">
          <path d="M12.8 10.2h9.6l5.2 5.2v15.2H12.8z" fill="#fffdf8" />
          <path d="M22.4 10.2v5.2h5.2z" fill="#e4d9bd" />
          <path d="M15.8 19.2h7.8M15.8 22.8h5.2" stroke="#b3a889" strokeWidth="1.5" strokeLinecap="round" />
        </g>
      </g>
      <path className="logo-check" d="M16.6 26.6l4 4 8-9.6" fill="none" stroke="#ec4a31" strokeWidth="3.3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
