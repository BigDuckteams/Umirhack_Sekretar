import { useEffect, useState } from "react";
import { formatSeconds, pct } from "../../lib/format";
import { STAGES, stageIndex } from "../../lib/stages";
import type { Turn } from "../../hooks/useDesk";
import { Icon } from "../../ui/Icon";
import { Avatar } from "./Avatar";

function useElapsed(since: number, active: boolean): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) return;
    const id = setInterval(() => setNow(Date.now()), 100);
    return () => clearInterval(id);
  }, [active]);
  return Math.max(0, (now - since) / 1000);
}

/** Разбор документа в реальном времени: пять этапов, живая подпись от сервера, время и отмена. */
export function ProcessTurn({ turn, onCancel }: { turn: Turn; onCancel: () => void }) {
  const snap = turn.progress;
  const current = snap ? stageIndex(snap.stage) : 0;
  const fraction = snap?.fraction ?? 0;
  const elapsed = useElapsed(turn.at, true);

  return (
    <article className="turn turn-bot process" aria-live="polite" aria-busy="true">
      <Avatar busy />
      <div className="bubble bot-bubble">
        <header className="process-head">
          <div>
            <p className="eyebrow">Разбираю документ</p>
            <h3>{snap?.label ?? "Начинаю"}</h3>
          </div>
          <span className="tabnum faint elapsed">{formatSeconds(elapsed)}</span>
        </header>

        <ol className="timeline" aria-label="Этапы проверки">
          {STAGES.map((s, i) => {
            const state = i < current ? "done" : i === current ? "now" : "next";
            return (
              <li key={s.id} className={state} aria-current={state === "now" ? "step" : undefined}>
                <span className="node" aria-hidden="true">
                  {state === "done" ? <Icon name="check" size={13} /> : i + 1}
                </span>
                <span className="tl-text">
                  <strong>{s.title}</strong>
                  <small>{state === "now" ? s.hint : state === "done" ? "готово" : ""}</small>
                </span>
              </li>
            );
          })}
        </ol>

        <div className="bar" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct(fraction)} aria-label="Ход проверки">
          <i style={{ width: `${pct(fraction)}%` }} />
        </div>

        <footer className="process-foot">
          <small className="faint">Мелкий шрифт читается дольше: пробую несколько вариантов обработки.</small>
          <button type="button" className="btn ghost small" onClick={onCancel}>
            Отменить <kbd>Esc</kbd>
          </button>
        </footer>
      </div>
    </article>
  );
}
