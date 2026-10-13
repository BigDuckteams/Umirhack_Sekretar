import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import type { RegulationInfo } from "../types";

let cache: Promise<RegulationInfo> | null = null;

/** Положение грузится один раз на всё приложение: им пользуются и вкладка, и боковая панель пункта. */
export function loadRegulation(force = false): Promise<RegulationInfo> {
  if (!cache || force) {
    cache = api.regulation().catch((e) => {
      cache = null;
      throw e;
    });
  }
  return cache;
}

export function useRegulation(enabled = true) {
  const [data, setData] = useState<RegulationInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(enabled);

  const load = useCallback((force = false) => {
    setLoading(true);
    loadRegulation(force)
      .then((d) => (setData(d), setError(null)))
      .catch((e: Error) => setError(e.message || "Не удалось загрузить Положение"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (enabled) load();
  }, [enabled, load]);

  return { data, error, loading, reload: () => load(true) };
}
