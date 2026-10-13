import type { Verdict } from "../types";

const TEXT: Record<Verdict, string> = { ok: "В порядке", missing: "Не хватает", no_answer: "Ответа нет" };

export function stampDate(d = new Date()): string {
  return d.toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit", year: "numeric" });
}

/** Круглая-прямоугольная печать деканата. Появляется «ударом»: анимация и шероховатость краски — в CSS. */
export function Stamp({ verdict, date = stampDate() }: { verdict: Verdict; date?: string }) {
  return (
    <div className={`stamp stamp-${verdict}`} role="img" aria-label={`Штамп: ${TEXT[verdict]}`}>
      <span className="stamp-ripple" aria-hidden="true" />
      <div className="stamp-body" aria-hidden="true">
        <small>Деканат · проверка</small>
        <strong>{TEXT[verdict]}</strong>
        <small>{date}</small>
      </div>
    </div>
  );
}
