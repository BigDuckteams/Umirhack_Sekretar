"use strict";

const $ = (id) => document.getElementById(id);
const TABS = [
  ["overview", "Обзор и статистика"],
  ["templates", "Шаблоны DOCX"],
  ["kb", "База знаний"],
  ["tickets", "Обращения"],
  ["history", "История изменений"],
  ["account", "Аккаунт"],
];
let current = "overview";

const STATUS_TITLES = { new: "новое", in_progress: "в работе", done: "обработано", rejected: "отклонено" };
const TYPE_TITLES = { transfer: "перевод", enrollment: "зачисление", other: "другое" };
const ACTION_TITLES = {
  "admin.login": "вход администратора", "admin.login_failed": "неудачный вход", "admin.logout": "выход", "admin.create": "создан администратор",
  "admin.password_change": "смена пароля", "template.create": "шаблон добавлен", "template.replace": "шаблон заменён", "template.rename": "шаблон переименован",
  "template.delete": "шаблон удалён", "kb.create": "документ добавлен", "kb.replace": "документ заменён", "kb.update": "документ изменён", "kb.delete": "документ удалён",
  "kb.reset_base": "возврат к файлу Положения", "kb.reindex": "переиндексация", "doctype.save": "тип документа сохранён", "doctype.delete": "тип документа удалён",
  "ticket.update": "обращение обновлено", "storage.purge": "очистка просроченных данных",
};

async function guarded(fn) {
  try {
    return await fn();
  } catch (e) {
    if (e.status === 401) return showLogin("Войдите, чтобы продолжить.");
    showBanner($("banner"), "bad", e.message);
  }
}

function showLogin(note) {
  $("login").classList.remove("hidden");
  $("app").classList.add("hidden");
  $("btn-logout").classList.add("hidden");
  $("who").textContent = "";
  showBanner($("banner"), note ? "warn" : "ok", note || "");
}

function table(headers, rows) {
  const t = el("table");
  const head = el("tr");
  for (const h of headers) head.appendChild(el("th", null, h));
  t.appendChild(head);
  for (const r of rows) {
    const tr = el("tr");
    for (const c of r) {
      const td = el("td");
      if (c instanceof Node) td.appendChild(c);
      else td.textContent = c === null || c === undefined ? "—" : String(c);
      tr.appendChild(td);
    }
    t.appendChild(tr);
  }
  return t;
}

function button(text, onClick, cls) {
  const b = el("button", cls || null, text, { type: "button" });
  b.addEventListener("click", onClick);
  return b;
}

function renderTabs() {
  const tabs = clear($("tabs"));
  for (const [id, title] of TABS) {
    const b = el("button", null, title, { role: "tab", "aria-selected": String(id === current), type: "button" });
    b.addEventListener("click", () => {
      current = id;
      renderTabs();
      render();
    });
    tabs.appendChild(b);
  }
}

async function render() {
  const panel = clear($("panel"));
  showBanner($("banner"), "ok", "");
  await guarded(() => ({ overview: view_overview, templates: view_templates, kb: view_kb, tickets: view_tickets, history: view_history, account: view_account })[current](panel));
}

// ---------------------------------------------------------------- обзор и статистика
async function view_overview(panel) {
  const [info, stats] = await Promise.all([api("GET", "/api/admin/info"), api("GET", "/api/admin/stats?days=30")]);
  const card = el("section", "card");
  card.appendChild(el("h2", null, "Состояние"));
  const llm = info.llm.enabled ? `включена (${info.llm.model}), ${info.llm.available ? "доступна" : "НЕДОСТУПНА — работает режим без модели"}` : "выключена (USE_LOCAL_LLM=false)";
  card.appendChild(table(["Параметр", "Значение"], [
    ["Положение", `${info.regulation.name} — ${info.regulation.clauses} пунктов`],
    ["Документов в базе знаний", info.kb_documents],
    ["Шаблонов DOCX", info.templates],
    ["Новых обращений", info.tickets_new],
    ["Активных сессий пользователей", info.active_sessions],
    ["Отправка обращений", info.delivery.available ? "работает (очередь в этой панели)" : `недоступна: ${info.delivery.reason}`],
    ["Локальная языковая модель", llm],
  ]));
  panel.appendChild(card);

  const t = stats.totals;
  const s = el("section", "card");
  s.appendChild(el("h2", null, `Статистика за ${stats.period_days} дней`));
  s.appendChild(table(["Показатель", "Число"], [
    ["Посещения страниц", t.visits], ["Уникальных сессий", t.sessions], ["Вопросов без документа", t.questions], ["Проверок документов", t.document_checks],
    ["Запущено анкет (перевод)", t.screenings_transfer], ["Запущено анкет (зачисление)", t.screenings_enrollment], ["Сформировано документов", t.documents_generated],
    ["Отправлено обращений", t.tickets_sent], ["Отказов от отправки", t.tickets_declined],
  ]));
  s.appendChild(el("h3", null, "Популярные темы"));
  if (!stats.topics.length) s.appendChild(el("p", "muted", "Пока нет данных."));
  const max = Math.max(1, ...stats.topics.map((x) => x.count));
  const topics = el("table");
  for (const x of stats.topics) {
    const tr = el("tr");
    const bar = el("progress", null, null, { max: String(max), value: String(x.count), "aria-label": x.topic });
    tr.append(el("td", null, x.topic), el("td", null, null), el("td", "num", String(x.count)));
    tr.children[1].appendChild(bar);
    topics.appendChild(tr);
  }
  s.appendChild(topics);
  s.appendChild(el("h3", null, "По дням"));
  s.appendChild(table(["День", "Посещения", "Вопросы", "Проверки", "Анкеты", "Документы"], stats.by_day.slice(-14).map((d) => [
    d.day, d.visit || 0, d.question || 0, d.document_check || 0, d.screening_started || 0, d.document_generated || 0,
  ])));
  s.appendChild(el("p", "muted", "В статистику попадают только дата, тема, сценарий и итог. Текст вопросов, OCR и персональные данные не сохраняются."));
  panel.appendChild(s);
}

// ---------------------------------------------------------------- шаблоны
async function view_templates(panel) {
  const items = await api("GET", "/api/admin/templates");
  const up = el("section", "card");
  up.appendChild(el("h2", null, "Добавить шаблон"));
  up.appendChild(el("p", "muted", "Файл .docx с оформлением, шапкой и подписями. Переменные записываются как {{ student_name }}, {{ passport_data }}, {{ current_university }}, {{ current_course }}, {{ current_specialty }}, {{ target_specialty }}, {{ education_form }}, {{ debts }}, {{ application_date }}; можно добавлять и свои."));
  up.appendChild(el("label", null, "Название (необязательно)", { for: "t-name" }));
  up.appendChild(el("input", null, null, { type: "text", id: "t-name", maxlength: "120" }));
  up.appendChild(el("label", null, "Файл .docx", { for: "t-file" }));
  up.appendChild(el("input", null, null, { type: "file", id: "t-file", accept: ".docx" }));
  up.appendChild(el("label", null, "Идентификатор (необязательно; нужен, чтобы заменить существующий шаблон)", { for: "t-id" }));
  up.appendChild(el("input", null, null, { type: "text", id: "t-id", maxlength: "64", placeholder: "например, perevod-2026" }));
  const rep = el("label", "inline");
  rep.append(el("input", null, null, { type: "checkbox", id: "t-replace" }), el("span", null, "Заменить существующий шаблон с этим идентификатором (прежняя версия останется в истории)"));
  up.appendChild(rep);
  up.appendChild(el("p")).appendChild(button("Загрузить", () => guarded(async () => {
    const f = $("t-file").files[0];
    if (!f) return showBanner($("banner"), "warn", "Выберите файл .docx");
    const form = new FormData();
    form.append("file", f);
    form.append("name", $("t-name").value);
    form.append("template_id", $("t-id").value);
    form.append("replace", $("t-replace").checked ? "true" : "false");
    const info = await api("POST", "/api/admin/templates", form);
    const keys = info.placeholders.map((p) => p.key).join(", ") || "плейсхолдеры не найдены";
    showBanner($("banner"), info.placeholders.length ? "ok" : "warn", `Шаблон «${info.name}» сохранён (id ${info.template_id}, версия ${info.version}). Найдено: ${keys}.`);
    render();
  }), "primary"));
  panel.appendChild(up);

  const list = el("section", "card");
  list.appendChild(el("h2", null, "Шаблоны"));
  if (!items.length) list.appendChild(el("p", "muted", "Шаблонов нет. Пока их нет, пользователи не смогут сформировать документ."));
  else list.appendChild(table(["Название", "Идентификатор", "Версия", "Ключи", "Обновлён", ""], items.map((t) => {
    const actions = el("span", "row");
    actions.append(
      el("a", "btn", "Скачать", { href: `/api/admin/templates/${encodeURIComponent(t.id)}/download` }),
      button("История", () => guarded(async () => showHistory("template", t.id))),
      button("Удалить", () => guarded(async () => {
        if (!confirm(`Удалить шаблон «${t.name}» со всеми версиями? Пользователи, не завершившие создание документа, получат сообщение, что шаблона больше нет.`)) return;
        await api("DELETE", `/api/admin/templates/${encodeURIComponent(t.id)}`);
        render();
      }), "danger"),
    );
    return [t.name, t.id, t.version, t.placeholders.map((p) => p.key).join(", "), fmtDate(t.updated_at), actions];
  })));
  panel.appendChild(list);
  panel.appendChild(el("div", null, null, { id: "history-box" }));
}

async function showHistory(type, id) {
  const path = type === "template" ? `/api/admin/templates/${encodeURIComponent(id)}/history` : `/api/admin/kb/${encodeURIComponent(id)}/history`;
  const h = await api("GET", path);
  const box = clear($("history-box"));
  const card = el("section", "card");
  card.appendChild(el("h2", null, `История: ${id}`));
  card.appendChild(table(["Версия", "Дата", "Кто", type === "kb" ? "Пунктов" : "Ключи"], h.versions.map((v) => [v.version, fmtDate(v.created_at), v.created_by, type === "kb" ? v.clauses : (v.placeholders || []).join(", ")])));
  card.appendChild(el("h3", null, "Журнал действий"));
  card.appendChild(table(["Когда", "Кто", "Действие"], h.log.map((l) => [fmtDate(l.ts), l.actor, ACTION_TITLES[l.action] || l.action])));
  box.appendChild(card);
  box.scrollIntoView();
}

// ---------------------------------------------------------------- база знаний
async function view_kb(panel) {
  const items = await api("GET", "/api/admin/kb");
  const up = el("section", "card");
  up.appendChild(el("h2", null, "Загрузить документ с регламентом"));
  up.appendChild(el("p", "muted", ".txt, .md, .docx или .pdf с текстовым слоем. Нумерация пунктов («3.4.», «п. 3.4») определяется автоматически. После загрузки индекс обновляется сразу."));
  up.appendChild(el("label", null, "Название документа", { for: "k-name" }));
  up.appendChild(el("input", null, null, { type: "text", id: "k-name", maxlength: "120" }));
  up.appendChild(el("label", null, "Файл", { for: "k-file" }));
  up.appendChild(el("input", null, null, { type: "file", id: "k-file", accept: ".txt,.md,.docx,.pdf" }));
  const row = el("p", "row");
  row.appendChild(button("Загрузить", () => guarded(async () => {
    const f = $("k-file").files[0];
    if (!f) return showBanner($("banner"), "warn", "Выберите файл");
    const form = new FormData();
    form.append("file", f);
    form.append("name", $("k-name").value);
    const r = await api("POST", "/api/admin/kb", form);
    showBanner($("banner"), "ok", `Документ «${r.name}» добавлен: ${r.clauses} пунктов. Индекс обновлён.`);
    render();
  }), "primary"));
  row.appendChild(button("Обновить индекс", () => guarded(async () => {
    const r = await api("POST", "/api/admin/reindex");
    showBanner($("banner"), "ok", `Индекс пересобран: ${r.clauses} пунктов из ${r.documents} документов.`);
  })));
  up.appendChild(row);
  panel.appendChild(up);

  const list = el("section", "card");
  list.appendChild(el("h2", null, "Документы базы знаний"));
  list.appendChild(table(["Название", "Тип", "Пунктов", "Версия", "Статус", "Обновлён", ""], items.map((d) => {
    const act = el("span", "row");
    const replaceInput = el("input", null, null, { type: "file", accept: ".txt,.md,.docx,.pdf", "aria-label": `Заменить ${d.name}` });
    replaceInput.addEventListener("change", () => guarded(async () => {
      const f = replaceInput.files[0];
      if (!f) return;
      const form = new FormData();
      form.append("file", f);
      const r = await api("PUT", `/api/admin/kb/${encodeURIComponent(d.id)}`, form);
      showBanner($("banner"), "ok", `Документ заменён (версия ${r.version}, пунктов: ${r.clauses}). Прежняя версия сохранена в истории.`);
      render();
    }));
    act.append(
      replaceInput,
      button(d.active ? "Отключить" : "Включить", () => guarded(async () => { await api("PATCH", `/api/admin/kb/${encodeURIComponent(d.id)}`, { active: !d.active }); render(); })),
      button("История", () => guarded(async () => showHistory("kb", d.id))),
      button(d.kind === "base" ? "Вернуть файл" : "Удалить", () => guarded(async () => {
        const msg = d.kind === "base" ? "Вернуть основное Положение из файла в настройках? Загруженная замена будет убрана из действующих правил (в истории останется)." : `Удалить «${d.name}»? Его пункты перестанут использоваться в ответах.`;
        if (!confirm(msg)) return;
        await api("DELETE", `/api/admin/kb/${encodeURIComponent(d.id)}`);
        render();
      }), "danger"),
    );
    return [d.name, d.kind === "base" ? "основное Положение" : "дополнительный", d.clauses, d.version || "файл", d.active ? "действует" : "отключён", fmtDate(d.updated_at), act];
  })));
  panel.appendChild(list);
  panel.appendChild(el("div", null, null, { id: "history-box" }));
}

// ---------------------------------------------------------------- обращения
async function view_tickets(panel) {
  const f = el("section", "card");
  f.appendChild(el("h2", null, "Обращения по переводу и зачислению"));
  const row = el("div", "row");
  const mk = (label, node) => {
    const w = el("div", "grow");
    w.append(el("label", null, label), node);
    row.appendChild(w);
    return node;
  };
  const from = mk("С даты", el("input", null, null, { type: "date", id: "f-from" }));
  const to = mk("По дату", el("input", null, null, { type: "date", id: "f-to" }));
  const type = mk("Тип", el("select", null, null, { id: "f-type" }));
  const status = mk("Статус", el("select", null, null, { id: "f-status" }));
  const topic = mk("Тема", el("select", null, null, { id: "f-topic" }));
  f.appendChild(row);
  const out = el("div");
  f.appendChild(el("p")).appendChild(button("Показать", () => load(), "primary"));
  f.appendChild(out);
  panel.appendChild(f);
  panel.appendChild(el("div", null, null, { id: "ticket-box" }));

  const fill = (sel, values, titles) => {
    sel.appendChild(el("option", null, "все", { value: "" }));
    for (const v of values) sel.appendChild(el("option", null, titles ? titles[v] || v : v, { value: v }));
  };

  async function load() {
    const q = new URLSearchParams({ date_from: from.value, date_to: to.value, type: type.value, status: status.value, topic: topic.value });
    const res = await guarded(() => api("GET", "/api/admin/tickets?" + q));
    if (!res) return;
    if (!type.options.length) {
      fill(type, res.types, TYPE_TITLES);
      fill(status, res.statuses, STATUS_TITLES);
      fill(topic, res.topics);
    }
    clear(out);
    out.appendChild(el("p", "muted", `Найдено: ${res.total}`));
    out.appendChild(table(["№", "Создано", "Тип", "Тема", "Статус", ""], res.items.map((t) => [t.id, fmtDate(t.created_at), TYPE_TITLES[t.type] || t.type, t.topic, STATUS_TITLES[t.status] || t.status,
      button("Открыть", () => guarded(() => openTicket(t.id)))])));
  }

  async function openTicket(id) {
    const t = await api("GET", `/api/admin/tickets/${id}`);
    const box = clear($("ticket-box"));
    const card = el("section", "card");
    card.appendChild(el("h2", null, `Обращение № ${t.id}`));
    card.appendChild(el("p", "muted", `${TYPE_TITLES[t.type] || t.type} · ${t.topic || "—"} · ${fmtDate(t.created_at)}`));
    card.appendChild(table(["Поле", "Значение"], Object.entries((t.payload || {}).fields || {})));
    if (t.has_attachment) card.appendChild(el("p")).appendChild(el("a", "btn", "Скачать приложенный документ", { href: `/api/admin/tickets/${t.id}/attachment` }));
    const st = el("select", null, null, { id: "t-status", "aria-label": "Статус" });
    for (const s of Object.keys(STATUS_TITLES)) {
      const o = el("option", null, STATUS_TITLES[s], { value: s });
      if (s === t.status) o.selected = true;
      st.appendChild(o);
    }
    card.appendChild(el("label", null, "Статус", { for: "t-status" }));
    card.appendChild(st);
    card.appendChild(el("label", null, "Заметка сотрудника", { for: "t-note" }));
    const note = el("textarea", null, null, { id: "t-note", rows: "3", maxlength: "2000" });
    note.value = t.note || "";
    card.appendChild(note);
    card.appendChild(el("p")).appendChild(button("Сохранить", () => guarded(async () => {
      await api("PATCH", `/api/admin/tickets/${t.id}`, { status: st.value, note: note.value });
      showBanner($("banner"), "ok", "Сохранено.");
      load();
    }), "primary"));
    box.appendChild(card);
    box.scrollIntoView();
  }
  load();
}

// ---------------------------------------------------------------- журнал
async function view_history(panel) {
  const log = await api("GET", "/api/admin/audit?limit=200");
  const card = el("section", "card");
  card.appendChild(el("h2", null, "История изменений административных документов"));
  card.appendChild(el("p", "muted", "Шаблоны, документы базы знаний, типы документов, учётные записи. Содержимое паролей и документов в журнал не попадает."));
  card.appendChild(table(["Когда", "Кто", "Действие", "Объект", "Подробности"], log.map((l) => [
    fmtDate(l.ts), l.actor, ACTION_TITLES[l.action] || l.action, `${l.object_type}${l.object_id ? ": " + l.object_id : ""}`,
    Object.entries(l.details || {}).map(([k, v]) => `${k}=${Array.isArray(v) ? v.join(",") : v}`).join("; "),
  ])));
  panel.appendChild(card);
  card.appendChild(el("p")).appendChild(button("Удалить просроченные данные сейчас", () => guarded(async () => {
    const r = await api("POST", "/api/admin/purge");
    showBanner($("banner"), "ok", "Удалено по сроку хранения: " + Object.entries(r).map(([k, v]) => `${k}=${v}`).join(", "));
  })));
}

// ---------------------------------------------------------------- аккаунт
async function view_account(panel) {
  const card = el("section", "card");
  card.appendChild(el("h2", null, "Смена пароля"));
  card.appendChild(el("label", null, "Текущий пароль", { for: "pw-cur" }));
  card.appendChild(el("input", null, null, { type: "password", id: "pw-cur", autocomplete: "current-password" }));
  card.appendChild(el("label", null, "Новый пароль", { for: "pw-new" }));
  card.appendChild(el("input", null, null, { type: "password", id: "pw-new", autocomplete: "new-password" }));
  card.appendChild(el("p", "muted", "Не короче 10 символов, не из простых. После смены остальные ваши входы завершаются."));
  card.appendChild(el("p")).appendChild(button("Сменить пароль", () => guarded(async () => {
    await api("POST", "/api/admin/password", { current: $("pw-cur").value, new: $("pw-new").value });
    $("pw-cur").value = "";
    $("pw-new").value = "";
    showBanner($("banner"), "ok", "Пароль изменён.");
  }), "primary"));
  panel.appendChild(card);
}

// ---------------------------------------------------------------- вход / выход
async function start() {
  try {
    const me = await api("GET", "/api/admin/me");
    $("who").textContent = me.username;
    $("login").classList.add("hidden");
    $("app").classList.remove("hidden");
    $("btn-logout").classList.remove("hidden");
    renderTabs();
    render();
  } catch (e) {
    if (e.status === 401) showLogin("");
    else showBanner($("banner"), "bad", e.message);
  }
}

$("login-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  try {
    await api("POST", "/api/admin/login", { username: $("u").value, password: $("p").value });
    $("p").value = "";
    start();
  } catch (e) {
    showBanner($("banner"), "bad", e.message);
  }
});
$("btn-logout").addEventListener("click", async () => {
  await api("POST", "/api/admin/logout").catch(() => null);
  showLogin("Вы вышли.");
});

start();
