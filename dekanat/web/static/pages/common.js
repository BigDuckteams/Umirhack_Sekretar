/* Общие помощники страниц. Весь пользовательский текст выводится только через textContent — HTML из данных не вставляется. */
"use strict";

function el(tag, cls, text, attrs) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined && text !== null) node.textContent = text;
  if (attrs) for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  return node;
}

function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
  return node;
}

class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

async function api(method, path, body) {
  const init = { method, credentials: "same-origin", headers: {} };
  if (body instanceof FormData) init.body = body;
  else if (body !== undefined) {
    init.headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }
  let res;
  try {
    res = await fetch(path, init);
  } catch (e) {
    throw new ApiError(0, "Нет связи с сервером. Проверьте, что он запущен, и повторите.");
  }
  let data = null;
  const type = res.headers.get("content-type") || "";
  if (type.includes("application/json")) data = await res.json().catch(() => null);
  if (!res.ok) {
    let msg = data && data.detail ? data.detail : `Ошибка ${res.status}`;
    if (Array.isArray(msg)) msg = msg.map((m) => m.msg || String(m)).join("; ");
    throw new ApiError(res.status, String(msg));
  }
  return data;
}

function fmtDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return isNaN(d) ? iso : d.toLocaleString("ru-RU", { dateStyle: "short", timeStyle: "short" });
}

function showBanner(container, kind, text) {
  clear(container);
  if (!text) return;
  container.appendChild(el("p", `banner ${kind}`, text, { role: kind === "bad" ? "alert" : "status" }));
}

function verdictTitle(v) {
  return { ok: "Документ в порядке", missing: "Чего-то не хватает", no_answer: "Ответа нет" }[v] || v;
}
