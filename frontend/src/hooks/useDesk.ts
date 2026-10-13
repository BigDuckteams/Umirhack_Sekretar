import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, runAnalysis } from "../api";
import type { AnalysisResult, JobSnapshot } from "../types";

export interface RunInput {
  file?: Blob | null;
  fileName?: string;
  question: string;
  docType: string;
}

export type TurnPhase = "running" | "done" | "error" | "cancelled";

/** Один обмен «вопрос → разбор → ответ» в диалоге на столе. */
export interface Turn {
  id: string;
  at: number;
  question: string;
  docType: string;
  fileName: string;
  file: Blob | null;
  /** пояснение для повторного запуска: «Пересчитано как …» */
  note?: string;
  phase: TurnPhase;
  progress: JobSnapshot | null;
  result: AnalysisResult | null;
  error: string | null;
}

const MAX_TURNS = 10;
let seq = 0;
const uid = () => `t${Date.now().toString(36)}${(seq++).toString(36)}`;

export function useDesk() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const ctrl = useRef<AbortController | null>(null);
  const jobId = useRef<string | null>(null);
  const activeId = useRef<string | null>(null);

  const patch = useCallback((id: string, change: Partial<Turn>) => setTurns((list) => list.map((t) => (t.id === id ? { ...t, ...change } : t))), []);

  useEffect(() => () => ctrl.current?.abort(), []);

  const cancel = useCallback(() => {
    ctrl.current?.abort();
    if (jobId.current) void api.cancelJob(jobId.current);
    const id = activeId.current;
    if (id) patch(id, { phase: "cancelled", progress: null });
    activeId.current = null;
  }, [patch]);

  const run = useCallback(
    async (input: RunInput, note?: string): Promise<Turn | null> => {
      if (activeId.current) cancel();
      const id = uid();
      const turn: Turn = {
        id,
        at: Date.now(),
        question: input.question.trim(),
        docType: input.docType,
        fileName: input.fileName ?? "",
        file: input.file ?? null,
        note,
        phase: "running",
        progress: { id: "", status: "queued", stage: "queued", label: "Отправляю на сервер", fraction: 0.02, elapsed: 0 },
        result: null,
        error: null,
      };
      setTurns((list) => [...list, turn].slice(-MAX_TURNS));
      const mine = new AbortController();
      ctrl.current = mine;
      activeId.current = id;
      jobId.current = null;
      try {
        const result = await runAnalysis(
          input,
          { onProgress: (progress) => !mine.signal.aborted && patch(id, { progress }), onJobId: (jid) => (jobId.current = jid) },
          mine.signal,
        );
        if (mine.signal.aborted) return null;
        activeId.current = null;
        const done: Turn = { ...turn, phase: "done", progress: null, result };
        patch(id, { phase: "done", progress: null, result });
        return done;
      } catch (e) {
        if (mine.signal.aborted || (e as Error)?.name === "AbortError") return null;
        activeId.current = null;
        patch(id, { phase: "error", progress: null, error: e instanceof ApiError ? e.message : "Не удалось выполнить проверку" });
        return null;
      }
    },
    [cancel, patch],
  );

  const clear = useCallback(() => {
    cancel();
    setTurns([]);
  }, [cancel]);

  const busy = turns.some((t) => t.phase === "running");
  return { turns, run, cancel, clear, busy };
}
