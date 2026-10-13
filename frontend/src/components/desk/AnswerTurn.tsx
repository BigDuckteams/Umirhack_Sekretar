import { useMemo } from "react";
import type { Turn } from "../../hooks/useDesk";
import { fieldBoxes, VERDICT_META } from "../../lib/format";
import type { Box, DocTypeSummary, FieldResult, PartResult, Source } from "../../types";
import { Icon } from "../../ui/Icon";
import { Avatar } from "./Avatar";
import { Details } from "./Details";
import { FieldsCard } from "./FieldsCard";
import type { Highlight } from "./highlight";
import { TypeRail } from "./TypeRail";
import { VerdictCard } from "./VerdictCard";

interface Props {
  turn: Turn;
  active: boolean;
  types: DocTypeSummary[];
  busy: boolean;
  activeField: string | null;
  onActivate: () => void;
  onFocusSource: (s: Source, boxes: Box[]) => void;
  onClause: (s: Source) => void;
  onFieldHover: (h: Highlight | null) => void;
  onFieldSelect: (f: FieldResult, p?: PartResult) => void;
  onChooseType: (id: string) => void;
}

/** Ответ секретаря. Активный — раскрыт целиком, прежние — свёрнуты в строку (плавно, без прыжков). */
export function AnswerTurn(p: Props) {
  const { turn } = p;
  const result = turn.result!;
  const meta = VERDICT_META[result.answer.verdict];

  const resolveBoxes = useMemo(
    () => (s: Source): Box[] => {
      if (s.boxes.length) return s.boxes;
      const f = result.fields.find((x) => x.id === s.ref);
      return f ? fieldBoxes(f) : [];
    },
    [result.fields],
  );

  return (
    <article className={`turn turn-bot answer ${p.active ? "is-active" : "is-folded"}`}>
      <Avatar />
      <div className="bubble bot-bubble">
        <button type="button" className={`fold-summary tone-${meta.tone}`} onClick={p.onActivate} aria-expanded={p.active} tabIndex={p.active ? -1 : 0}>
          <span className="fold-dot" aria-hidden="true" />
          <strong>{meta.title}</strong>
          <span className="fold-text">{result.answer.text}</span>
          <Icon name="chevronDown" size={14} />
        </button>
        <div className="fold" aria-hidden={!p.active} inert={!p.active}>
          <div className="fold-inner">
            <VerdictCard
              answer={result.answer}
              warnings={result.warnings}
              images={result.images}
              resolveBoxes={resolveBoxes}
              onFocusSource={(s) => p.onFocusSource(s, resolveBoxes(s))}
              onClause={p.onClause}
            />
            <TypeRail info={result.doc_type} types={p.types} busy={p.busy} hasFile={!!turn.file} onChoose={p.onChooseType} />
            <FieldsCard fields={result.fields} activeId={p.activeField} onHover={p.onFieldHover} onSelect={p.onFieldSelect} />
            <Details result={result} fileName={turn.fileName.replace(/\.[^.]+$/, "")} />
          </div>
        </div>
      </div>
    </article>
  );
}
