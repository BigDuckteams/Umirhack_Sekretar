import { useCallback, useState } from "react";
import { type HistoryEntry, loadHistory, pushEntry, saveHistory } from "../lib/history";

export function useHistory() {
  const [entries, setEntries] = useState<HistoryEntry[]>(() => loadHistory());

  const add = useCallback((entry: HistoryEntry) => {
    setEntries((list) => {
      const next = pushEntry(list, entry);
      saveHistory(next);
      return next;
    });
  }, []);

  const clear = useCallback(() => {
    setEntries([]);
    saveHistory([]);
  }, []);

  const remove = useCallback((id: string) => {
    setEntries((list) => {
      const next = list.filter((e) => e.id !== id);
      saveHistory(next);
      return next;
    });
  }, []);

  return { entries, add, clear, remove };
}
