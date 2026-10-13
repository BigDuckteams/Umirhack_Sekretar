import { formatSeconds } from "../../lib/format";
import type { AnalysisResult } from "../../types";
import { Icon } from "../../ui/Icon";

function download(name: string, text: string, mime: string) {
  const url = URL.createObjectURL(new Blob([text], { type: mime }));
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function Details({ result, fileName }: { result: AnalysisResult; fileName: string }) {
  const t = result.timings;
  const total = typeof t.total === "number" ? t.total : null;
  return (
    <details className="details">
      <summary>
        <Icon name="chevronRight" size={14} className="chev" /> Технические подробности
      </summary>
      <dl>
        {total !== null && (
          <>
            <dt>Время проверки</dt>
            <dd>
              {formatSeconds(total)}
              {t.ocr_cached === true && <span className="faint"> · текст взят из кэша</span>}
            </dd>
          </>
        )}
        <dt>OCR</dt>
        <dd>{result.ocr.engine ?? "—"}</dd>
        {result.ocr.pages.map((p) => (
          <div key={p.index} className="page-info">
            <dt>Страница {p.index + 1}</dt>
            <dd>
              {p.width}×{p.height}px · слов: {p.words ?? "—"} · качество {p.score != null ? Math.round(p.score) : "—"}
              {p.deskew_angle ? ` · выпрямлено на ${p.deskew_angle.toFixed(1)}°` : ""}
              {p.rotation ? ` · повёрнуто на ${p.rotation}°` : ""}
              {p.variant ? ` · вариант «${p.variant}»` : ""}
            </dd>
          </div>
        ))}
      </dl>
      <div className="row">
        <button type="button" className="btn small" onClick={() => download(`${fileName || "result"}.json`, JSON.stringify(result.export, null, 2), "application/json")}>
          <Icon name="download" size={14} /> Результат (JSON)
        </button>
        <button type="button" className="btn ghost small" onClick={() => navigator.clipboard?.writeText(result.ocr.text)}>
          <Icon name="copy" size={14} /> Текст с документа
        </button>
        <button type="button" className="btn ghost small" onClick={() => window.print()}>
          <Icon name="print" size={14} /> Печать
        </button>
      </div>
      {result.ocr.text && (
        <pre className="ocr-text" tabIndex={0} aria-label="Распознанный текст">
          {result.ocr.text}
        </pre>
      )}
    </details>
  );
}
