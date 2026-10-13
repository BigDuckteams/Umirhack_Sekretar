import { useSyncExternalStore } from "react";

/** Что сейчас делает сервис — общая «лампочка» для панели навигации, заголовка вкладки и всего остального. */
export interface Activity {
  busy: boolean;
  fraction: number;
  label: string;
  /** момент завершения последней проверки: по нему панель вспыхивает «готово» */
  finishedAt: number;
}

const IDLE: Activity = { busy: false, fraction: 0, label: "", finishedAt: 0 };
let state: Activity = IDLE;
const listeners = new Set<() => void>();

export function getActivity(): Activity {
  return state;
}

export function setActivity(next: Partial<Activity>): void {
  const merged = { ...state, ...next };
  if (merged.busy === state.busy && merged.fraction === state.fraction && merged.label === state.label && merged.finishedAt === state.finishedAt) return;
  state = merged;
  listeners.forEach((fn) => fn());
}

export function resetActivity(): void {
  setActivity({ ...IDLE });
}

const subscribe = (fn: () => void) => {
  listeners.add(fn);
  return () => listeners.delete(fn);
};

export function useActivity(): Activity {
  return useSyncExternalStore(subscribe, getActivity, getActivity);
}
