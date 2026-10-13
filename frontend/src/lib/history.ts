import type { Verdict } from "../types";

/** Запись истории: только текст — картинки в localStorage не кладём. */
export interface HistoryEntry {
  id: string;
  at: number;
  question: string;
  fileName: string;
  docType: string;
  typeTitle: string;
  verdict: Verdict;
  answer: string;
}

const KEY = "dekanat.history.v1";
export const HISTORY_LIMIT = 30;

export function loadHistory(storage: Pick<Storage, "getItem"> = localStorage): HistoryEntry[] {
  try {
    const raw = storage.getItem(KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((e): e is HistoryEntry => !!e && typeof e.id === "string" && typeof e.question === "string" && typeof e.answer === "string").slice(0, HISTORY_LIMIT);
  } catch {
    return [];
  }
}

export function saveHistory(entries: HistoryEntry[], storage: Pick<Storage, "setItem"> = localStorage): void {
  try {
    storage.setItem(KEY, JSON.stringify(entries.slice(0, HISTORY_LIMIT)));
  } catch {
    /* приватный режим или переполнение — история просто не сохранится */
  }
}

/** Добавляет запись в начало; повтор того же вопроса по тому же файлу заменяет старую запись. */
export function pushEntry(list: HistoryEntry[], entry: HistoryEntry): HistoryEntry[] {
  const rest = list.filter((e) => !(e.question === entry.question && e.fileName === entry.fileName && e.docType === entry.docType));
  return [entry, ...rest].slice(0, HISTORY_LIMIT);
}
