import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { useNavScroll } from "../hooks/useNavScroll";
import type { Theme } from "../hooks/useTheme";
import { useActivity } from "../lib/activity";
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

const HINTS = ["Найти пункт Положения", "Загрузить пример", "Сменить тему", "Спросить про академ"];

interface Props {
  route: Route;
  onRoute: (r: Route) => void;
  health: Health | null;
  theme: Theme;
  onTheme: () => void;
  onThemeSet: (t: Theme) => void;
  onPalette: () => void;
  onHelp: () => void;
}

/** Короткие «факты о системе» для строки под названием: меняются сами, пока сервис ничем не занят. */
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

function useRotating(items: string[], ms: number, paused: boolean): string {
  const [i, setI] = useState(0);
  useEffect(() => {
    if (paused || items.length < 2) return;
    const id = setInterval(() => setI((n) => n + 1), ms);
    return () => clearInterval(id);
  }, [items.length, ms, paused]);
  return items[i % Math.max(1, items.length)] ?? "";
}

function ThemeSwitch({ theme, onSet }: { theme: Theme; onSet: (t: Theme) => void }) {
  const index = Math.max(0, THEMES.findIndex((t) => t.id === theme));
  return (
    <div className="theme-switch" role="radiogroup" aria-label="Тема оформления" style={{ ["--i" as string]: index }}>
      <span className="ts-thumb" aria-hidden="true" />
      {THEMES.map((t) => (
        <button key={t.id} type="button" role="radio" aria-checked={t.id === theme} aria-label={`Тема: ${t.label}`} title={`Тема: ${t.label}`} className={t.id === theme ? "on" : ""} onClick={() => onSet(t.id)}>
          <Icon name={t.icon} size={16} />
        </button>
      ))}
    </div>
  );
}

function StatusChip({ health }: { health: Health | null }) {
  const ok = health?.ocr?.available !== false;
  const rows: [string, string][] = health
    ? [
        ["OCR", ok ? `${String(health.ocr?.version ?? "готов")}` : String(health.ocr?.reason ?? "недоступен")],
        ["Языки", Array.isArray(health.ocr?.languages) ? health.ocr.languages.join(", ") : "—"],
        ["Положение", `${health.regulation?.clauses ?? 0} ${plural(health.regulation?.clauses ?? 0, ["пункт", "пункта", "пунктов"])}`],
        ["Типы документов", String(health.doc_types?.length ?? 0)],
        ["Языковая модель", health.llm?.backend && health.llm.backend !== "none" ? String(health.llm.backend) : "не используется"],
        ["Версия", health.version],
      ]
    : [];
  return (
    <div className={`status-chip ${ok ? "ok" : "bad"} ${health ? "" : "wait"}`}>
      <button type="button" className="status-btn" aria-label={ok ? "Система готова: подробности" : "OCR недоступен: подробности"} aria-describedby="status-pop">
        <i aria-hidden="true" />
        <span>{health ? (ok ? "Готов" : "OCR недоступен") : "…"}</span>
      </button>
      <div className="status-pop" id="status-pop" role="tooltip">
        <p className="eyebrow">Состояние системы</p>
        <dl>
          {rows.map(([k, v]) => (
            <div key={k}>
              <dt>{k}</dt>
              <dd>{v}</dd>
            </div>
          ))}
        </dl>
        <p className="faint">Всё считается на этом компьютере, данные никуда не отправляются.</p>
      </div>
    </div>
  );
}

export function NavBar({ route, onRoute, health, theme, onTheme, onThemeSet, onPalette, onHelp }: Props) {
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
    const t = setTimeout(measure, 300); // шрифты и бейджи могли поменять ширину
    return () => (window.removeEventListener("resize", measure), clearTimeout(t));
  }, [route, health]);

  // подсветка границы и «свет» следуют за курсором
  const onMove = (e: React.PointerEvent) => {
    const el = island.current;
    if (!el || e.pointerType !== "mouse") return;
    const r = el.getBoundingClientRect();
    el.style.setProperty("--mx", `${e.clientX - r.left}px`);
    el.style.setProperty("--my", `${e.clientY - r.top}px`);
  };

  const facts = useMemo(() => systemFacts(health), [health]);
  const fact = useRotating(facts, 4200, activity.busy);
  const hint = useRotating(HINTS, 3400, false);
  const percent = pct(activity.fraction);
  const badges: Partial<Record<Route, number | undefined>> = { rules: health?.regulation?.clauses, types: health?.doc_types?.length };

  return (
    <header className="nav" data-hidden={hidden} data-compact={compact} data-busy={activity.busy}>
      <div className="island" ref={island} onPointerMove={onMove}>
        <a className="brand" href="#/check" onClick={() => onRoute("check")} aria-label="Онлайн-деканат — на стол">
          <Logo size={38} />
          <span className="brand-text">
            <strong>Онлайн-деканат</strong>
            {activity.busy ? (
              <small className="brand-sub busy" key="busy" aria-live="polite">
                <i aria-hidden="true" />
                <span>{activity.label || "Проверяю"}</span>
                <b className="tabnum">{percent}%</b>
              </small>
            ) : (
              <small className="brand-sub" key={fact}>
                {fact}
              </small>
            )}
          </span>
        </a>

        <nav className="tabs" aria-label="Разделы">
          <span className="tab-ind" style={{ transform: `translateX(${ind.x}px)`, width: ind.w, opacity: ind.ready ? 1 : 0 }} aria-hidden="true" />
          {TABS.map((t, i) => {
            const badge = badges[t.id];
            return (
              <a key={t.id} ref={(el) => void (tabs.current[t.id] = el)} href={`#/${t.id}`} aria-current={route === t.id ? "page" : undefined} onClick={() => onRoute(t.id)} style={{ ["--i" as string]: i }}>
                <Icon name={t.icon} size={16} />
                <span className="tab-label">{t.title}</span>
                {badge !== undefined && badge > 0 && <em className="tab-badge tabnum">{badge}</em>}
              </a>
            );
          })}
        </nav>

        <div className="tools">
          <button type="button" className="search-pill" onClick={onPalette} aria-label="Поиск и команды (Ctrl+K)">
            <Icon name="search" size={16} />
            <span className="hint-rot" aria-hidden="true">
              <span key={hint}>{hint}</span>
            </span>
            <kbd>Ctrl K</kbd>
          </button>
          <StatusChip health={health} />
          <ThemeSwitch theme={theme} onSet={onThemeSet} />
          <button type="button" className="theme-cycle round-btn" onClick={onTheme} aria-label="Сменить тему" title="Сменить тему">
            <Icon name={theme === "dark" ? "moon" : theme === "light" ? "sun" : "system"} size={17} />
          </button>
          <button type="button" className="help-btn round-btn" onClick={onHelp} aria-label="Горячие клавиши" title="Горячие клавиши (?)">
            <Icon name="keyboard" size={17} />
          </button>
        </div>

        <div className="nav-progress" data-on={activity.busy} aria-hidden="true">
          <i style={{ ["--p" as string]: activity.fraction }} />
        </div>
        {activity.finishedAt > 0 && <span className="nav-done" key={activity.finishedAt} aria-hidden="true" />}
      </div>
    </header>
  );
}
