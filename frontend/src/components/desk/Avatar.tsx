/** Аватар цифрового секретаря; пока идёт проверка, вокруг вращается кольцо. */
export function Avatar({ busy = false, size = 34 }: { busy?: boolean; size?: number }) {
  return (
    <span className={`avatar ${busy ? "busy" : ""}`} style={{ width: size, height: size }} aria-hidden="true">
      <svg viewBox="0 0 32 32" width={size - 8} height={size - 8}>
        <path d="M9 8h10l5 5v11H9z" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
        <path className="avatar-check" d="M12 18l3 3 5-6" fill="none" stroke="var(--stamp)" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </span>
  );
}
