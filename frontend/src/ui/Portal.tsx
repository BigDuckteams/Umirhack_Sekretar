import type { ReactNode } from "react";
import { createPortal } from "react-dom";

/**
 * Рисует содержимое прямо в <body>. Панели и затемнение с position: fixed нельзя класть внутрь анимированных блоков:
 * активная анимация transform/filter делает такой блок «опорным», и fixed-элемент привязывается к нему, а не к окну.
 */
export function Portal({ children }: { children: ReactNode }) {
  return typeof document === "undefined" ? null : createPortal(children, document.body);
}
