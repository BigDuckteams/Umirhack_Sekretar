import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { useNavScroll } from "../hooks/useNavScroll";
import type { Theme } from "../hooks/useTheme";
import { useActivity } from "../lib/activity";
import { emit } from "../lib/bus";
import { pct, plural } from "../lib/format";
import type { Health } from "../types";
import { Icon, type IconName } from "../ui/Icon";
import { Logo } from "../ui/Logo";

export type Route = "check" | "rules" | "types";

const TABS: { id: Route; title: string; icon: IconName }[] = [
  { id: "check", title: "Стол", icon: "doc" },
  { id: "rules", title: "Положение", icon: "book" },
  { id: "types", title: "Типы документов", icon: "layers" },
];

const THEMES: { id: Theme; label: string; icon: IconName }[] = [
  { id: "system", label: "Как в системе", icon: "system" },
  { id: "light", label: "Светлая", icon: "sun" },
  { id: "dark", label: "Тёмная", icon: "moon" },
];

interface Props {
  route: Route;
  onRoute: (r: Route) => void;
  health: Health | null;
  theme: Theme;
  onThemeSet: (t: Theme) => void;
  onPalette: () => void;
  onHelp: () => void;
}

/** Короткие факты о системе для меню: распознавание, Положение, типы документов. */
export function systemFacts(health: Health | null): string[] {
  const facts: string[] = [];
  if (health) {
    const ocr = health.ocr;
    if (ocr?.available === false) facts.push("OCR недоступен");
    else {
      const v = String(ocr?.version ?? "").match(/\d+(?:\.\d+){0,2}/)?.[0];
      facts.push(`Tesseract${v ? ` ${v}` : ""} · ${Array.isArray(ocr?.languages) ? ocr.languages.filter((l: string) => l !== "osd").join("+") : "rus"}`);
    }
    const n = health.regulation?.clauses ?? 0;
    facts.push(`Положение: ${n} ${plural(n, ["пункт", "пункта", "пунктов"])}`);
    const t = health.doc_types?.length ?? 0;
    facts.push(`${t} ${plural(t, ["тип документа", "типа документов", "типов документов"])}`);
  }
  facts.push("Без внешних API");
  return facts;
}

function ThemeSwitch({ theme, onSet }: { theme: Theme; onSet: (t: Theme) => void }) {
  const index = Math.max(0, THEMES.findIndex((t) => t.id === theme));
  return (
    <div className="theme-switch" role="radiogroup" aria-label="Тема оформления" style={{ ["--i" as string]: index }}>
      <span className="ts-thumb" aria-hidden="true" />
      {THEMES.map((t) => (
        <button key={t.id} type="button" role="radio" aria-checked={t.id === theme} aria-label={`Тема: ${t.label}`} title={t.label} className={t.id === theme ? "on" : ""} onClick={() => onSet(t.id)}>
          <Icon name={t.icon} size={15} />
          <span>{t.label === "Как в системе" ? "Авто" : t.label}</span>
        </button>
      ))}
    </div>
  );
}

/**
 * Одно меню вместо россыпи кнопок: тема, состояние системы, горячие клавиши, удаление данных и вход для сотрудников.
 * Точка на кнопке меню показывает состояние системы с первого взгляда.
 */
function Menu({ health, theme, onThemeSet, onHelp, onForget }: { health: Health | null; theme: Theme; onThemeSet: (t: Theme) => void; onHelp: () => void; onForget: () => void }) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const panelId = useId();
  const ok = health?.ocr?.available !== false;
  const state = !health ? "wait" : ok ? "ok" : "bad";
  const llm = health?.llm?.backend && health.llm.backend !== "none" ? String(health.llm.backend) : "не используется";

  useEffect(() => {
    if (!open) return;
    const onDown = (e: PointerEvent) => !root.current?.contains(e.target as Node) && setOpen(false);
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("pointerdown", onDown);
    document.addEventListener("keydown", onKey);
    return () => (document.removeEventListener("pointerdown", onDown), document.removeEventListener("keydown", onKey));
  }, [open]);

  const act = (fn: () => void) => () => (setOpen(false), fn());

  return (
    <div className={`nav-menu ${state}`} ref={root}>
      <button
        type="button"
        className="menu-btn"
        aria-expanded={open}
        aria-controls={panelId}
        aria-label={`Меню: ${state === "wait" ? "проверяю систему" : ok ? "система готова" : "OCR недоступен"}`}
        title="Меню"
        onClick={() => setOpen((o) => !o)}
      >
        <span className="menu-lines" aria-hidden="true">
          <i />
          <i />
          <i />
        </span>
        <i className="menu-dot" aria-hidden="true" />
      </button>
      <div className="menu-panel" id={panelId} role="group" aria-label="Меню" data-open={open} inert={!open}>
        <section className="menu-sec">
          <p className="eyebrow">Оформление</p>
          <ThemeSwitch theme={theme} onSet={onThemeSet} />
        </section>
        <section className="menu-sec">
          <p className="eyebrow">Состояние системы</p>
          <p className={`menu-state ${state}`}>
            <i aria-hidden="true" />
            {state === "wait" ? "Проверяю…" : ok ? "Готов к работе" : `OCR недоступен${health?.ocr?.reason ? `: ${String(health.ocr.reason)}` : ""}`}
          </p>
          <ul className="menu-facts" role="list">
            {systemFacts(health).map((f) => (
              <li key={f}>{f}</li>
            ))}
            <li>Языковая модель: {llm}</li>
            {health?.version && <li>Версия {health.version}</li>}
          </ul>
        </section>
        <section className="menu-sec menu-actions">
          <button type="button" onClick={act(onHelp)}>
            <Icon name="keyboard" size={16} />
            <span>Горячие клавиши</span>
            <kbd>?</kbd>
          </button>
          <button type="button" className="danger" onClick={act(onForget)}>
            <Icon name="trash" size={16} />
            <span>Удалить мои данные</span>
          </button>
          <a href="/admin" onClick={() => setOpen(false)}>
            <Icon name="key" size={16} />
            <span>Вход для сотрудников</span>
            <Icon name="arrowRight" size={14} className="menu-go" />
          </a>
        </section>
      </div>
    </div>
  );
}

export function NavBar({ route, onRoute, health, theme, onThemeSet, onPalette, onHelp }: Props) {
  const { hidden, compact } = useNavScroll();
  const activity = useActivity();
  const island = useRef<HTMLDivElement>(null);
  const tabs = useRef<Partial<Record<Route, HTMLAnchorElement | null>>>({});
  const [ind, setInd] = useState({ x: 0, w: 0, ready: false });

  // «таблетка» под активной вкладкой плавно переезжает на новое место
  useLayoutEffect(() => {
    const measure = () => {
      const el = tabs.current[route];
      if (el) setInd({ x: el.offsetLeft, w: el.offsetWidth, ready: true });
    };
    measure();
    window.addEventListener("resize", measure);
    const t = setTimeout(measure, 300); // шрифты могли поменять ширину
    return () => (window.removeEventListener("resize", measure), clearTimeout(t));
  }, [route]);

  // удаление данных подтверждает стол: переходим на него и просим показать подтверждение
  const forget = () => {
    location.hash = "#/check";
    setTimeout(() => emit("forget"), 80);
  };

  // подсветка границы и «свет» следуют за курсором
  const onMove = (e: React.PointerEvent) => {
    const el = island.current;
    if (!el || e.pointerType !== "mouse") return;
    const r = el.getBoundingClientRect();
    el.style.setProperty("--mx", `${e.clientX - r.left}px`);
    el.style.setProperty("--my", `${e.clientY - r.top}px`);
  };

  return (
    <header className="nav" data-hidden={hidden} data-compact={compact} data-busy={activity.busy}>
      <div className="island" ref={island} onPointerMove={onMove}>
        <a className="brand" href="#/check" onClick={() => onRoute("check")} aria-label="Онлайн-деканат — на стол">
          <Logo size={36} />
          <span className="brand-text">
            <strong>Онлайн-деканат</strong>
            {activity.busy ? (
              <small className="brand-sub busy" key="busy" aria-live="polite">
                <i aria-hidden="true" />
                <span>{activity.label || "Проверяю"}</span>
                <b className="tabnum">{pct(activity.fraction)}%</b>
              </small>
            ) : (
              <small className="brand-sub" key="idle">
                цифровой секретарь
              </small>
            )}
          </span>
        </a>

        <nav className="tabs" aria-label="Разделы">
          <span className="tab-ind" style={{ transform: `translateX(${ind.x}px)`, width: ind.w, opacity: ind.ready ? 1 : 0 }} aria-hidden="true" />
          {TABS.map((t, i) => (
            <a key={t.id} ref={(el) => void (tabs.current[t.id] = el)} href={`#/${t.id}`} aria-current={route === t.id ? "page" : undefined} onClick={() => onRoute(t.id)} style={{ ["--i" as string]: i }} title={t.title}>
              <Icon name={t.icon} size={16} />
              <span className="tab-label">{t.title}</span>
            </a>
          ))}
        </nav>

        <div className="tools">
          <button type="button" className="search-pill" onClick={onPalette} aria-label="Поиск и команды (Ctrl+K)">
            <Icon name="search" size={16} />
            <span className="search-label">Поиск</span>
            <kbd>Ctrl K</kbd>
          </button>
          <Menu health={health} theme={theme} onThemeSet={onThemeSet} onHelp={onHelp} onForget={forget} />
        </div>

        <div className="nav-progress" data-on={activity.busy} aria-hidden="true">
          <i style={{ ["--p" as string]: activity.fraction }} />
        </div>
        {activity.finishedAt > 0 && <span className="nav-done" key={activity.finishedAt} aria-hidden="true" />}
      </div>
    </header>
  );
}
