const norm = (s: string): string => s.toLowerCase().replace(/ё/g, "е");

/**
 * Простой нечёткий поиск для палитры команд: все слова запроса должны встретиться в тексте.
 * Чем раньше и чем ближе к началу слова совпадение — тем выше оценка. Возвращает null, если не подходит.
 */
export function score(query: string, text: string): number | null {
  const q = norm(query).trim();
  if (!q) return 0;
  const t = norm(text);
  let total = 0;
  for (const word of q.split(/\s+/)) {
    const i = t.indexOf(word);
    if (i < 0) return null;
    const atWordStart = i === 0 || /[\s\-–—:.,()«»/]/.test(t[i - 1]!);
    total += (atWordStart ? 100 : 40) - Math.min(i, 60) * 0.5;
  }
  return total;
}

export function rank<T>(items: T[], query: string, text: (item: T) => string, limit = 30): T[] {
  if (!query.trim()) return items.slice(0, limit);
  return items
    .map((item) => ({ item, s: score(query, text(item)) }))
    .filter((x): x is { item: T; s: number } => x.s !== null)
    .sort((a, b) => b.s - a.s)
    .slice(0, limit)
    .map((x) => x.item);
}
