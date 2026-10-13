import { fieldBoxes, pct } from "../../lib/format";
import type { FieldResult, FieldStatus, PartResult } from "../../types";
import { Icon } from "../../ui/Icon";
import type { Highlight } from "./highlight";

const LABEL: Record<FieldStatus, string> = { found: "найдено", partial: "найдено частично", missing: "не найдено" };

function Glyph({ status }: { status: FieldStatus }) {
  return (
    <span className={`glyph ${status}`} role="img" aria-label={LABEL[status]}>
      {status === "found" && (
        <svg viewBox="0 0 24 24" width="13" height="13" aria-hidden="true">
          <path className="draw" d="M5 12.5l4.5 4.5L19 7.5" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      )}
      {status === "partial" && <span aria-hidden="true">!</span>}
      {status === "missing" && <span aria-hidden="true">–</span>}
    </span>
  );
}

interface Props {
  fields: FieldResult[];
  activeId: string | null;
  onHover: (h: Highlight | null) => void;
  onSelect: (field: FieldResult, part?: PartResult) => void;
}

/** Карточка документа из ТЗ: все поля выбранного типа; чего нет — «не найдено». Наведение показывает место на снимке. */
export function FieldsCard({ fields, activeId, onHover, onSelect }: Props) {
  if (!fields.length) return null;
  const found = fields.filter((f) => f.status === "found").length;
  const share = found / fields.length;
  let n = 0;

  return (
    <section className="fields" aria-labelledby="fields-title">
      <header className="fields-head">
        <div>
          <p className="eyebrow">Карточка документа</p>
          <h3 id="fields-title">Что найдено в документе</h3>
        </div>
        <div className="fields-count tabnum" title="Найдено полей">
          <strong>{found}</strong>
          <span> из {fields.length}</span>
        </div>
      </header>
      <div className="fields-meter" aria-hidden="true">
        <i style={{ transform: `scaleX(${share})` }} />
      </div>

      <ul className="field-rows" role="list">
        {fields.map((f) => {
          const boxes = fieldBoxes(f);
          const clickable = boxes.length > 0;
          const showParts = f.parts.length > 0 && (f.kind !== "marks" || f.parts.length > 1);
          const hl: Highlight = { id: `field:${f.id}`, label: f.title, boxes };
          return (
            <li key={f.id} style={{ ["--i" as string]: n++ }} className={`frow ${f.status} ${activeId === f.id ? "active" : ""}`}>
              <div
                className={`frow-main ${clickable ? "clickable" : ""}`}
                role={clickable ? "button" : undefined}
                tabIndex={clickable ? 0 : undefined}
                aria-label={clickable ? `${f.title}: показать на снимке` : undefined}
                onMouseEnter={() => clickable && onHover(hl)}
                onMouseLeave={() => onHover(null)}
                onFocus={() => clickable && onHover(hl)}
                onBlur={() => onHover(null)}
                onClick={() => clickable && onSelect(f)}
                onKeyDown={(e) => {
                  if (clickable && (e.key === "Enter" || e.key === " ")) {
                    e.preventDefault();
                    onSelect(f);
                  }
                }}
              >
                <Glyph status={f.status} />
                <span className="f-title">{f.title}</span>
                <span className={`f-value ${f.status === "missing" ? "none" : ""}`}>
                  {f.status === "missing" ? "не найдено" : f.value}
                  {f.status !== "missing" && f.kind !== "marks" && f.confidence > 0 && (
                    <i className={`f-conf ${pct(f.confidence) < 55 ? "low" : ""}`} title={`Уверенность распознавания: ${pct(f.confidence)}%`}>
                      <b style={{ width: `${pct(f.confidence)}%` }} />
                    </i>
                  )}
                </span>
                {clickable && <Icon name="eye" size={14} className="f-eye" />}
              </div>
              {showParts && (
                <ul className="parts" role="list">
                  {f.parts.map((p) => {
                    const phl: Highlight = { id: `field:${f.id}.${p.id}`, label: `${f.title}: ${p.title}`, boxes: p.boxes };
                    const pc = p.boxes.length > 0;
                    return (
                      <li
                        key={p.id}
                        className={`part ${p.found ? "found" : "missing"} ${activeId === `${f.id}.${p.id}` ? "active" : ""} ${pc ? "clickable" : ""}`}
                        role={pc ? "button" : undefined}
                        tabIndex={pc ? 0 : undefined}
                        onMouseEnter={() => pc && onHover(phl)}
                        onMouseLeave={() => onHover(null)}
                        onClick={() => pc && onSelect(f, p)}
                        onKeyDown={(e) => {
                          if (pc && (e.key === "Enter" || e.key === " ")) {
                            e.preventDefault();
                            onSelect(f, p);
                          }
                        }}
                      >
                        <Glyph status={p.found ? "found" : "missing"} />
                        <span className="f-title">{p.title}</span>
                        <span className={`f-value ${p.found ? "" : "none"}`}>{p.found ? p.value : f.kind === "marks" ? "нет" : "не найдено"}</span>
                      </li>
                    );
                  })}
                </ul>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
