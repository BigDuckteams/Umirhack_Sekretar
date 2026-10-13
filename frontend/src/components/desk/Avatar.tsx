import { Logo } from "../../ui/Logo";

/** Аватар цифрового секретаря: знак деканата на тёмном круге; пока идёт проверка, вокруг вращается кольцо. */
export function Avatar({ busy = false, size = 34 }: { busy?: boolean; size?: number }) {
  return (
    <span className={`avatar ${busy ? "busy" : ""}`} style={{ width: size, height: size }} aria-hidden="true">
      <Logo bare size={size - 6} />
    </span>
  );
}
