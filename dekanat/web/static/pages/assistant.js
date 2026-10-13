"use strict";

const $ = (id) => document.getElementById(id);
const log = $("log");
let busy = false;
let templates = [];
let deliveryInfo = null;
let dialog = null;

function addMsg(kind, text) {
  const m = el("div", `msg ${kind}`, text);
  log.appendChild(m);
  log.scrollTop = log.scrollHeight;
  return m;
}

function setBusy(on) {
  busy = on;
  for (const b of document.querySelectorAll("button")) b.disabled = on;
}

// ---------------------------------------------------------------- ответ ассистента: вывод, факты, пункты, недостающее, оговорка
function renderAnswer(ans) {
  const box = el("div", "answer");
  const head = el("p");
  head.appendChild(el("span", `badge ${ans.verdict}`, verdictTitle(ans.verdict)));
  box.appendChild(head);
  box.appendChild(el("p", null, ans.text));
  const rep = ans.report || {};
  if (rep.explanation) {
    box.appendChild(el("p", "muted", "Пересказ: " + rep.explanation));
  }
  if (rep.facts && rep.facts.length) {
    box.appendChild(el("h3", null, "Факты из документа"));
    const ul = el("ul");
    for (const f of rep.facts) ul.appendChild(el("li", null, `${f.title}: ${f.value}` + (f.doubtful ? " (прочитано неуверенно)" : "")));
    box.appendChild(ul);
  }
  const clauses = rep.clauses || [];
  if (clauses.length) {
    box.appendChild(el("h3", null, "Источник — Положение"));
    for (const c of clauses) {
      box.appendChild(el("strong", null, c.label));
      if (c.quote) box.appendChild(el("blockquote", null, c.quote));
    }
  }
  if (rep.document_fields && rep.document_fields.length) {
    box.appendChild(el("h3", null, "Источник — поле документа"));
    box.appendChild(el("p", null, rep.document_fields.map((f) => f.label).join(", ")));
  }
  if (rep.no_source) box.appendChild(el("p", "muted", "Подходящего пункта Положения или поля документа не найдено."));
  if (rep.missing && rep.missing.length) {
    box.appendChild(el("h3", null, "Отсутствует"));
    box.appendChild(el("p", null, rep.missing.join(", ")));
  }
  const doubts = [...(rep.doubtful || []), ...(ans.notes || [])];
  if (doubts.length) {
    box.appendChild(el("h3", null, "Сомнительное"));
    const ul = el("ul");
    for (const d of doubts) ul.appendChild(el("li", null, d));
    box.appendChild(ul);
  }
  box.appendChild(el("p", "disclaimer", rep.disclaimer || "Окончательное решение принимает сотрудник деканата."));
  log.appendChild(box);
  log.scrollTop = log.scrollHeight;
}

function renderOptions(options) {
  const holder = clear($("options"));
  for (const o of options || []) {
    const b = el("button", null, o, { type: "button" });
    b.addEventListener("click", () => send(optionText(o)));
    holder.appendChild(b);
  }
}

function optionText(label) {
  return { "Да, начать": "да", "Нет": "нет", "Верно": "верно", "Исправить": "исправить", "Сформировать документ": "сформировать" }[label] || label;
}

function renderDownloads(items) {
  const holder = clear($("downloads"));
  for (const d of items || []) {
    const p = el("p");
    const a = el("a", "btn", `Скачать: ${d.filename}`, { href: d.url, download: "" });
    p.appendChild(a);
    holder.appendChild(p);
  }
}

function applyDialog(d) {
  dialog = d;
  const show = d.state === "document_generation" || d.state === "completed";
  $("generate").classList.toggle("hidden", !show);
  $("submit-card").classList.toggle("hidden", d.state !== "completed");
  if (show) fillTemplates();
}

function fillTemplates() {
  const sel = clear($("template"));
  for (const t of templates) sel.appendChild(el("option", null, t.name, { value: t.id }));
  const none = templates.length === 0;
  $("template-empty").classList.toggle("hidden", !none);
  sel.classList.toggle("hidden", none);
  $("btn-generate").disabled = none;
}

// ---------------------------------------------------------------- документ сессии
function renderDocument(doc) {
  const holder = clear($("fields"));
  $("btn-doc-del").classList.toggle("hidden", !doc);
  if (!doc) return;
  const t = doc.doc_type || {};
  holder.appendChild(el("p", "muted", `Файл: ${doc.filename}. Тип: ${t.title || "не определён"}` + (t.how === "auto" ? " (определён автоматически)" : "")));
  for (const w of doc.warnings || []) holder.appendChild(el("p", "banner warn", w));
  if (!doc.fields.length) holder.appendChild(el("p", "muted", "Карточка полей не заполнена: выберите тип документа и проверьте снова."));
  for (const f of doc.fields) {
    const row = el("div", "field-row");
    const label = el("span", "title", f.title);
    const input = el("input", null, null, { type: "text", "aria-label": f.title, maxlength: "300", placeholder: f.kind === "mark" ? "есть / нет" : "не найдено" });
    input.value = f.found ? f.value : (f.kind === "mark" ? f.value : "");
    const tag = el("span", "tag" + (f.corrected ? "" : (f.found && f.confidence < 0.5 ? " warn" : "")), f.corrected ? "исправлено" : (f.found ? (f.confidence < 0.5 ? "неуверенно" : "") : "не найдено"));
    input.addEventListener("change", () => saveField(f.unit, input.value));
    row.append(label, input, tag);
    holder.appendChild(row);
  }
  if (doc.fields.length) holder.appendChild(el("p", "muted", "Изменили значение — оно сохранится при выходе из поля. Пустое поле означает «не найдено»."));
}

async function saveField(unit, value) {
  try {
    const res = await api("PATCH", "/api/assistant/document/fields", { unit, value });
    renderDocument(res.document);
    if (res.answer) renderAnswer(res.answer);
    showBanner($("doc-msg"), "ok", "Значение сохранено, ответ пересчитан.");
  } catch (e) {
    showBanner($("doc-msg"), "bad", e.message);
    await refreshDocument();
  }
}

async function refreshDocument() {
  try {
    renderDocument((await api("GET", "/api/assistant/document")).document);
  } catch (e) {
    showBanner($("doc-msg"), "bad", e.message);
  }
}

async function upload() {
  const file = $("file").files[0];
  if (!file) return showBanner($("doc-msg"), "warn", "Выберите файл (JPG, PNG или PDF).");
  const form = new FormData();
  form.append("file", file);
  form.append("doc_type", $("doc-type").value);
  setBusy(true);
  showBanner($("doc-msg"), "ok", "Читаю документ… это может занять несколько секунд.");
  try {
    const res = await api("POST", "/api/assistant/document", form);
    renderDocument(res.document);
    addMsg("bot", "Документ проверен. Ниже — предварительный вывод; поля справа можно уточнить.");
    renderAnswer(res.answer);
    showBanner($("doc-msg"), "ok", "Готово.");
    $("file").value = "";
  } catch (e) {
    showBanner($("doc-msg"), "bad", e.message);
  } finally {
    setBusy(false);
  }
}

// ---------------------------------------------------------------- диалог
async function send(text) {
  text = (text || "").trim();
  if (!text || busy) return;
  addMsg("user", text);
  $("text").value = "";
  setBusy(true);
  try {
    const res = await api("POST", "/api/assistant/message", { text, template_id: templates.length ? $("template").value || null : null });
    handleSession(res.session);
    applyDialog(res.dialog);
    if (res.answer) renderAnswer(res.answer);
    else if (res.reply.text) addMsg("bot", res.reply.text);
    if (res.reply.kind === "error" && log.lastChild) log.lastChild.classList.add("error");
    renderOptions(res.reply.options);
    if (res.download) {
      const state = await api("GET", "/api/assistant/state");
      renderDownloads(state.downloads);
    }
  } catch (e) {
    if (e.status === 410) return sessionExpired(e.message);
    addMsg("bot error", e.message);
  } finally {
    setBusy(false);
    $("text").focus();
  }
}

function handleSession(status) {
  if (status === "expired") showBanner($("banner"), "warn", "Сессия истекла, прежние данные удалены. Начните заново.");
}

function sessionExpired(message) {
  showBanner($("banner"), "warn", message);
  clear(log);
  renderOptions([]);
}

async function generate() {
  setBusy(true);
  try {
    const res = await api("POST", "/api/assistant/generate", { template_id: $("template").value || null });
    applyDialog(res.dialog);
    if (res.reply) addMsg("bot", res.reply.text);
    else addMsg("bot", "Этот документ уже был сформирован — он доступен для скачивания.");
    renderOptions([]);
    renderDownloads((await api("GET", "/api/assistant/state")).downloads);
  } catch (e) {
    if (e.status === 410) return sessionExpired(e.message);
    addMsg("bot error", e.message);
  } finally {
    setBusy(false);
  }
}

// ---------------------------------------------------------------- отправка в деканат
async function preview() {
  const holder = clear($("submit-body"));
  try {
    const include = document.getElementById("inc-pass") ? document.getElementById("inc-pass").checked : false;
    const res = await api("GET", "/api/assistant/submission?include_passport=" + include);
    if (!res.delivery.available) {
      holder.appendChild(el("p", "banner warn", `Автоматическая отправка пока недоступна: ${res.delivery.reason}. Скачайте готовый документ и передайте его в деканат лично.`));
      return;
    }
    if (res.already_sent) {
      holder.appendChild(el("p", "banner ok", `Обращение уже отправлено (№ ${res.already_sent}).`));
      return;
    }
    holder.appendChild(el("h3", null, `Будет отправлено: ${res.payload.request}`));
    const table = el("table");
    for (const [k, v] of Object.entries(res.payload.fields)) {
      const tr = el("tr");
      tr.append(el("th", null, k), el("td", null, v));
      table.appendChild(tr);
    }
    holder.appendChild(table);
    holder.appendChild(el("p", "muted", res.attachment ? "К обращению будет приложен сформированный документ (DOCX)." : "Документ не приложен."));
    if (res.excluded.length || include) {
      const lab = el("label", "inline");
      const cb = el("input", null, null, { type: "checkbox", id: "inc-pass" });
      cb.checked = include;
      cb.addEventListener("change", preview);
      lab.append(cb, el("span", null, "Передать паспортные данные (по умолчанию не передаются)"));
      holder.appendChild(lab);
    }
    const ok = el("label", "inline");
    const okCb = el("input", null, null, { type: "checkbox", id: "confirm-send" });
    ok.append(okCb, el("span", null, "Подтверждаю: хочу отправить эти данные в деканат"));
    holder.appendChild(ok);
    const row = el("p", "row");
    const send1 = el("button", "primary", "Отправить", { type: "button" });
    const decline = el("button", null, "Не отправлять", { type: "button" });
    send1.addEventListener("click", () => submit(okCb.checked));
    decline.addEventListener("click", () => submit(null));
    row.append(send1, decline);
    holder.appendChild(row);
  } catch (e) {
    holder.appendChild(el("p", "banner bad", e.message));
  }
}

async function submit(confirmed) {
  const include = document.getElementById("inc-pass") ? document.getElementById("inc-pass").checked : false;
  if (confirmed === false) return showBanner($("banner"), "warn", "Поставьте отметку подтверждения, чтобы отправить данные.");
  try {
    const res = await api("POST", "/api/assistant/submission", { confirm: confirmed === true, include_passport: include });
    clear($("submit-body")).appendChild(el("p", "banner ok", res.message + (res.ticket_id ? ` Номер обращения: ${res.ticket_id}.` : "")));
  } catch (e) {
    clear($("submit-body")).appendChild(el("p", "banner bad", e.message));
  }
}

async function deleteData() {
  if (!confirm("Удалить анкету, загруженный документ и готовые файлы? Это нельзя отменить.")) return;
  try {
    const res = await api("DELETE", "/api/assistant/data");
    clear(log);
    renderOptions([]);
    renderDownloads([]);
    renderDocument(null);
    clear($("submit-body"));
    $("generate").classList.add("hidden");
    $("submit-card").classList.add("hidden");
    showBanner($("banner"), "ok", res.message);
    await init(false);
  } catch (e) {
    showBanner($("banner"), "bad", e.message);
  }
}

async function init(showWelcome = true) {
  try {
    const st = await api("GET", "/api/assistant/state");
    handleSession(st.session);
    templates = st.templates;
    deliveryInfo = st.delivery;
    applyDialog(st.dialog);
    renderDocument(st.document);
    renderDownloads(st.downloads);
    if (showWelcome && !log.firstChild) addMsg("bot", st.welcome);
    if (st.dialog.state === "screening" || st.dialog.state === "review") addMsg("bot", "Анкета не завершена. Напишите «продолжить», чтобы увидеть текущий вопрос.");
  } catch (e) {
    showBanner($("banner"), "bad", e.message);
  }
}

$("composer").addEventListener("submit", (ev) => {
  ev.preventDefault();
  send($("text").value);
});
$("text").addEventListener("keydown", (ev) => {
  if (ev.key === "Enter" && !ev.shiftKey) {
    ev.preventDefault();
    send($("text").value);
  }
});
$("btn-upload").addEventListener("click", upload);
$("btn-generate").addEventListener("click", generate);
$("btn-preview").addEventListener("click", preview);
$("btn-delete").addEventListener("click", deleteData);
$("btn-doc-del").addEventListener("click", async () => {
  try {
    await api("DELETE", "/api/assistant/document");
    renderDocument(null);
    showBanner($("doc-msg"), "ok", "Документ убран из сессии.");
  } catch (e) {
    showBanner($("doc-msg"), "bad", e.message);
  }
});

init();
