import { useEffect, useState } from "react";
import { isPdf } from "../lib/files";

/** Временный адрес для предпросмотра выбранного файла; для PDF и пустого файла — null. */
export function useObjectUrl(file: Blob | null | undefined, name = ""): string | null {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    if (!file || isPdf({ name: name || (file as File).name || "", type: file.type })) {
      setUrl(null);
      return;
    }
    const u = URL.createObjectURL(file);
    setUrl(u);
    return () => URL.revokeObjectURL(u);
  }, [file, name]);
  return url;
}
