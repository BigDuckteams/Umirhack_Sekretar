import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import type { AssistantState, DialogInfo } from "../types";

/**
 * Сессия анкеты на столе: состояние диалога, шаблоны DOCX, канал отправки в деканат.
 * Сессия анонимная — идентификатор в HttpOnly-cookie, анкету и карточку документа хранит сервер (с ограниченным сроком).
 * Если сессия недоступна, стол работает как раньше: только проверка документов и вопросы по Положению.
 */
export function useAssistant() {
  const [info, setInfo] = useState<AssistantState | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (): Promise<AssistantState | null> => {
    try {
      const st = await api.assistant.state();
      setInfo(st);
      setError(null);
      return st;
    } catch (e) {
      setError((e as Error).message);
      return null;
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const setDialog = useCallback((dialog: DialogInfo) => setInfo((s) => (s ? { ...s, dialog } : s)), []);

  return {
    info,
    error,
    ready: !!info,
    dialog: info?.dialog ?? null,
    templates: info?.templates ?? [],
    delivery: info?.delivery ?? null,
    load,
    setDialog,
  };
}

export type AssistantSession = ReturnType<typeof useAssistant>;
