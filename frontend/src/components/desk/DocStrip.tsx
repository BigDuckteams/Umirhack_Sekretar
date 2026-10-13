import { useObjectUrl } from "../../hooks/useObjectUrl";
import { Icon } from "../../ui/Icon";
import type { DeskDoc } from "./highlight";

function DocChip({ doc, active, onClick }: { doc: DeskDoc; active: boolean; onClick: () => void }) {
  const url = useObjectUrl(doc.file, doc.name);
  return (
    <button type="button" className={`doc-chip ${active ? "on" : ""}`} aria-pressed={active} title={doc.name} onClick={onClick}>
      {url ? <img src={url} alt="" draggable={false} /> : <span className="pdf-mini">PDF</span>}
      <span>{doc.name}</span>
    </button>
  );
}

interface Props {
  docs: DeskDoc[];
  active: number;
  disabled?: boolean;
  onSelect: (index: number) => void;
  onAnother: () => void;
}

/** Документы на столе и кнопка «Другой документ»: можно держать несколько и переключаться, не теряя ответов. */
export function DocStrip({ docs, active, disabled, onSelect, onAnother }: Props) {
  return (
    <div className="doc-strip" role="group" aria-label="Документы на столе">
      <div className="doc-chips">
        {docs.map((d, i) => (
          <DocChip key={d.key} doc={d} active={i === active} onClick={() => onSelect(i)} />
        ))}
      </div>
      <button type="button" className="another" onClick={onAnother} disabled={disabled} title="Положить на стол другой документ">
        <Icon name="swap" size={15} />
        <span>Другой документ</span>
      </button>
    </div>
  );
}
