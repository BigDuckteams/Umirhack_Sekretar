import { useEffect, useRef } from "react";
import type { Turn } from "../../hooks/useDesk";
import { relativeTime, VERDICT_META } from "../../lib/format";
import type { HistoryEntry } from "../../lib/history";
import type { Box, DocTypeSummary, FieldResult, PartResult, Source } from "../../types";
import { Icon } from "../../ui/Icon";
import { AnswerTurn } from "./AnswerTurn";
import { Avatar } from "./Avatar";
import { DemoLoop } from "./DemoLoop";
import type { Highlight } from "./highlight";
import { ProcessTurn } from "./ProcessTurn";
import { UserTurn } from "./UserTurn";

interface Props {
  turns: Turn[];
  activeId: string | null;
  types: DocTypeSummary[];
  busy: boolean;
  activeField: string | null;
  history: HistoryEntry[];
  onActivate: (id: string) => void;
  onCancel: () => void;
  onRetry: (turn: Turn) => void;
  onFocusSource: (turn: Turn, s: Source, boxes: Box[]) => void;
  onClause: (s: Source) => void;
  onFieldHover: (h: Highlight | null) => void;
  onFieldSelect: (turn: Turn, f: FieldResult, p?: PartResult) => void;
  onChooseType: (turn: Turn, typeId: string) => void;
  onPickHistory: (e: HistoryEntry) => void;
  onClearHistory: () => void;
}

const CAPS: { icon: "doc" | "layers" | "book"; title: string; text: string }[] = [
  { icon: "doc", title: "Читаю снимок", text: "Фото, скан или PDF: наклон, тень и блики не помеха." },
  { icon: "layers", title: "Заполняю карточку", text: "ФИО, вуз, период, номер, печать — чего нет, помечаю «не найдено»." },
  { icon: "book", title: "Отвечаю по Положению", text: "Со ссылкой на пункт и подсветкой места на снимке." },
];

export function Thread(p: Props) {
  const end = useRef<HTMLDivElement>(null);
  const lastId = p.turns[p.turns.length - 1]?.id;
  const lastPhase = p.turns[p.turns.length - 1]?.phase;

  // новая реплика или готовый ответ — плавно прокручиваем диалог вниз
  useEffect(() => {
    if (!lastId) return;
    const t = setTimeout(() => end.current?.scrollIntoView({ behavior: "smooth", block: "end" }), 80);
    return () => clearTimeout(t);
  }, [lastId, lastPhase]);

  const typeTitle = (id: string) => p.types.find((t) => t.id === id)?.title ?? id;

  if (!p.turns.length) {
    return (
      <div className="thread-empty">
        <p className="eyebrow">Онлайн-деканат · цифровой секретарь</p>
        <h1>
          Покажите документ — получите <em>ответ со ссылкой на пункт</em>
        </h1>
        <p className="lead">Секретарь прочитает фото справки или заявления, заполнит карточку полей и честно скажет, чего не хватает — или что ответа нет.</p>
        <DemoLoop />
        <ul className="caps" role="list">
          {CAPS.map((c, i) => (
            <li key={c.title} style={{ ["--i" as string]: i }}>
              <span className="cap-icon">
                <Icon name={c.icon} size={20} />
              </span>
              <strong>{c.title}</strong>
              <span className="muted">{c.text}</span>
            </li>
          ))}
        </ul>
        {p.history.length > 0 && (
          <section className="hist" aria-labelledby="hist-title">
            <div className="hist-head">
              <h2 id="hist-title">
                <Icon name="history" size={16} /> Недавние вопросы
              </h2>
              <button type="button" className="link" onClick={p.onClearHistory}>
                Очистить
              </button>
            </div>
            <ul role="list">
              {p.history.slice(0, 4).map((e, i) => (
                <li key={e.id} style={{ ["--i" as string]: i }}>
                  <button type="button" className="hist-card" onClick={() => p.onPickHistory(e)}>
                    <span className={`dot tone-${VERDICT_META[e.verdict].tone}`} aria-label={VERDICT_META[e.verdict].title} />
                    <span className="hist-main">
                      <strong>{e.question || (e.fileName ? `Файл «${e.fileName}»` : "Без вопроса")}</strong>
                      <small>{e.answer}</small>
                    </span>
                    <small className="faint nowrap">{relativeTime(e.at)}</small>
                  </button>
                </li>
              ))}
            </ul>
            <p className="hint">История хранится только в этом браузере, снимки в неё не попадают.</p>
          </section>
        )}
      </div>
    );
  }

  return (
    <div className="thread" role="log" aria-label="Диалог с секретарём">
      {p.turns.map((t) => (
        <div className="exchange" key={t.id}>
          <UserTurn turn={t} typeTitle={typeTitle} />
          {t.phase === "running" && <ProcessTurn turn={t} onCancel={p.onCancel} />}
          {t.phase === "done" && t.result && (
            <AnswerTurn
              turn={t}
              active={t.id === p.activeId}
              types={p.types}
              busy={p.busy}
              activeField={t.id === p.activeId ? p.activeField : null}
              onActivate={() => p.onActivate(t.id)}
              onFocusSource={(s, boxes) => p.onFocusSource(t, s, boxes)}
              onClause={p.onClause}
              onFieldHover={p.onFieldHover}
              onFieldSelect={(f, part) => p.onFieldSelect(t, f, part)}
              onChooseType={(id) => p.onChooseType(t, id)}
            />
          )}
          {t.phase === "error" && (
            <article className="turn turn-bot error-turn" role="alert">
              <Avatar />
              <div className="bubble bot-bubble err">
                <p className="eyebrow">Не получилось</p>
                <h3>Проверка не завершилась</h3>
                <p>{t.error}</p>
                <button type="button" className="btn small" onClick={() => p.onRetry(t)}>
                  <Icon name="refresh" size={14} /> Попробовать ещё раз
                </button>
              </div>
            </article>
          )}
          {t.phase === "cancelled" && (
            <article className="turn turn-bot cancelled">
              <Avatar />
              <div className="bubble bot-bubble muted-bubble">
                <p>Проверка отменена.</p>
                <button type="button" className="link" onClick={() => p.onRetry(t)}>
                  Запустить снова
                </button>
              </div>
            </article>
          )}
        </div>
      ))}
      <div ref={end} className="thread-end" />
    </div>
  );
}
