import { useLayoutEffect, useRef, useState } from "react";
import type { Theme } from "../hooks/useTheme";
import type { Health } from "../types";
import { Icon, type IconName } from "../ui/Icon";

export type Route = "check" | "rules" | "types";

const TABS: { id: Route; title: string; icon: IconName }[] = [
  { id: "check", title: "Стол", icon: "doc" },
  { id: "rules", title: "Положение", icon: "book" },
  { id: "types", title: "Типы документов", icon: "layers" },
];

const THEME_LABEL: Record<Theme, string> = { system: "Тема: как в системе", light: "Тема: светлая", dark: "Тема: тёмная" };

interface Props {
  route: Route;
  onRoute: (r: Route) => void;
  health: Health | null;
  theme: Theme;
  onTheme: () => void;
  onPalette: () => void;
  onHelp: () => void;
}

export function NavBar({ route, onRoute, health, theme, onTheme, onPalette, onHelp }: Props) {
  const ocrOk = health?.ocr?.available !== false;
  const tabs = useRef<Partial<Record<Route, HTMLAnchorElement | null>>>({});
  const strip = useRef<HTMLElement>(null);
  const [ind, setInd] = useState({ x: 0, w: 0, ready: false });

  // «таблетка» под активной вкладкой плавно переезжает на новое место
  useLayoutEffect(() => {
    const measure = () => {
      const el = tabs.current[route];
      if (el) setInd((i) => ({ x: el.offsetLeft, w: el.offsetWidth, ready: i.ready || true }));
    };
    measure();
    window.addEventListener("resize", measure);
    return () => window.removeEventListener("resize", measure);
  }, [route]);

  return (
    <header className="nav">
      <div className="nav-inner">
        <a className="brand" href="#/check" onClick={() => onRoute("check")} aria-label="Онлайн-деканат — на главную">
          <svg viewBox="0 0 32 32" width="30" height="30" aria-hidden="true">
            <rect width="32" height="32" rx="9" fill="var(--ink)" />
            <path d="M9 8h10l5 5v11H9z" fill="none" stroke="var(--btn-ink)" strokeWidth="2" strokeLinejoin="round" />
            <path className="logo-check" d="M12 18l3 3 5-6" fill="none" stroke="var(--stamp)" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <span className="brand-text">
            <strong>Онлайн-деканат</strong>
            <small>цифровой секретарь</small>
          </span>
        </a>

        <nav className="tabs" aria-label="Разделы" ref={strip}>
          <span className="tab-ind" style={{ transform: `translateX(${ind.x}px)`, width: ind.w, opacity: ind.ready ? 1 : 0 }} aria-hidden="true" />
          {TABS.map((t) => (
            <a key={t.id} ref={(el) => void (tabs.current[t.id] = el)} href={`#/${t.id}`} aria-current={route === t.id ? "page" : undefined} onClick={() => onRoute(t.id)}>
              <Icon name={t.icon} size={16} />
              <span>{t.title}</span>
            </a>
          ))}
        </nav>

        <div className="nav-tools">
          <button type="button" className="palette-btn" onClick={onPalette} aria-label="Поиск и команды (Ctrl+K)">
            <Icon name="search" size={15} />
            <span>Поиск и команды</span>
            <kbd>Ctrl K</kbd>
          </button>
          {health && (
            <span className={`ocr-dot ${ocrOk ? "ok" : "bad"}`} role="status" title={ocrOk ? String(health.ocr.version ?? "OCR готов") : String(health.ocr.reason ?? "OCR недоступен")}>
              <i aria-hidden="true" />
              <span className="sr-only">{ocrOk ? "OCR готов" : "OCR недоступен"}</span>
            </span>
          )}
          <button type="button" className={`round-btn theme theme-${theme}`} onClick={onTheme} aria-label={THEME_LABEL[theme]} title={THEME_LABEL[theme]}>
            <Icon name="system" size={17} className="ti ti-system" />
            <Icon name="sun" size={17} className="ti ti-light" />
            <Icon name="moon" size={17} className="ti ti-dark" />
          </button>
          <button type="button" className="round-btn" onClick={onHelp} aria-label="Горячие клавиши" title="Горячие клавиши (?)">
            <Icon name="keyboard" size={17} />
          </button>
        </div>
      </div>
    </header>
  );
}
