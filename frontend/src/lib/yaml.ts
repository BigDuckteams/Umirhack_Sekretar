/** Поля типа документа из YAML — для живого предпросмотра в редакторе (без полноценного разбора YAML). */
export function extractFields(yaml: string): { id: string; title: string }[] {
  const out: { id: string; title: string }[] = [];
  let inFields = false;
  let cur: { id: string; title: string } | null = null;
  for (const line of yaml.split("\n")) {
    if (/^fields\s*:/.test(line)) {
      inFields = true;
      continue;
    }
    if (inFields && /^[^\s#-]/.test(line)) inFields = false; // следующий ключ верхнего уровня
    if (!inFields) continue;
    const m = line.match(/^ {2}-\s+id:\s*([^\s#]+)/);
    if (m) {
      cur = { id: m[1]!, title: "" };
      out.push(cur);
      continue;
    }
    const t = line.match(/^ {4}title:\s*(.+?)\s*(?:#.*)?$/);
    if (t && cur && !cur.title) cur.title = t[1]!.replace(/^["']|["']$/g, "");
  }
  return out;
}

/** Номер строки из текста ошибки сервера («line 5», «строка 5») — чтобы подсветить её в редакторе. */
export function errorLine(message: string | undefined): number | null {
  if (!message) return null;
  const m = message.match(/(?:line|строк[аиеу]?)\s*[:№]?\s*(\d+)/i);
  return m ? Number(m[1]) : null;
}
