const IMAGE_EXT = /\.(jpe?g|png|webp|bmp|tiff?|gif|heic)$/i;

/** Проверка файла до отправки: возвращает текст ошибки или null, если файл годится. */
export function validateFile(file: Pick<File, "name" | "type" | "size">, maxMb: number): string | null {
  const isPdf = file.type === "application/pdf" || /\.pdf$/i.test(file.name);
  const isImage = file.type.startsWith("image/") || IMAGE_EXT.test(file.name);
  if (!isPdf && !isImage) return "Нужен снимок (JPG, PNG) или PDF";
  if (file.size === 0) return "Файл пустой";
  if (file.size > maxMb * 1024 * 1024) return `Файл больше ${maxMb} МБ — сожмите снимок или уменьшите разрешение`;
  return null;
}

export const isPdf = (file: Pick<File, "name" | "type">): boolean => file.type === "application/pdf" || /\.pdf$/i.test(file.name);

/** Файл из буфера обмена (Ctrl+V скриншота или фото). */
export function fileFromClipboard(e: ClipboardEvent): File | null {
  const items = e.clipboardData?.items;
  if (!items) return null;
  for (const it of Array.from(items)) {
    if (it.kind === "file") {
      const f = it.getAsFile();
      if (f) return f.name ? f : new File([f], `снимок-${Date.now()}.png`, { type: f.type || "image/png" });
    }
  }
  return null;
}
