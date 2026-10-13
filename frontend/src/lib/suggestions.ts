import { AUTO_TYPE, type DocTypeSummary, GENERIC_TYPE, type Suggestion } from "../types";

const GENERIC_SUGGESTIONS: Suggestion[] = [
  { kind: "field", text: "О чём документ?" },
  { kind: "field", text: "Какая дата документа?" },
  { kind: "field", text: "Что указано в п. 1?" },
];

const AUTO_SUGGESTIONS: Suggestion[] = [
  { kind: "check", text: "Достаточно ли этого документа?" },
  { kind: "check", text: "Чего не хватает в документе?" },
  { kind: "rules", text: "Сколько дней рассматривается заявление?" },
];

export const SUGGESTION_TITLES: Record<Suggestion["kind"], string> = {
  check: "Проверка документа",
  field: "Значение из документа",
  rules: "По Положению",
};

/** Подсказки вопросов для выбранного (или уже определённого) типа: проверка, значение поля, правила. */
export function suggestionsFor(types: DocTypeSummary[], docType: string, detectedId: string | null | undefined, rules: Suggestion[]): Suggestion[] {
  if (docType === GENERIC_TYPE) return GENERIC_SUGGESTIONS;
  const id = docType !== AUTO_TYPE ? docType : detectedId;
  const t = types.find((x) => x.id === id);
  if (t?.suggestions?.length) return t.suggestions;
  return [...AUTO_SUGGESTIONS.slice(0, 2), ...(rules.length ? rules.slice(0, 2) : AUTO_SUGGESTIONS.slice(2))];
}
