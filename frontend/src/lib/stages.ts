/** Этапы проверки: ровно то, что сервер присылает в поле stage. */
export const STAGES: { id: string; title: string; hint: string }[] = [
  { id: "load", title: "Файл", hint: "открываю и выравниваю снимок" },
  { id: "ocr", title: "Чтение текста", hint: "распознаю слова и строки" },
  { id: "classify", title: "Тип документа", hint: "сверяю с известными типами" },
  { id: "extract", title: "Карточка полей", hint: "раскладываю данные по полям" },
  { id: "answer", title: "Ответ", hint: "ищу основание в Положении" },
];

/** Номер текущего этапа; для завершённой проверки — число этапов. */
export function stageIndex(stage: string): number {
  if (stage === "done") return STAGES.length;
  const i = STAGES.findIndex((s) => s.id === stage);
  return i < 0 ? 0 : i;
}
