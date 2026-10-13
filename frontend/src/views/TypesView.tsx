import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import { errorLine, extractFields } from "../lib/yaml";
import type { DocTypeSummary, TypeValidation } from "../types";
import { ConfirmDialog } from "../ui/Dialog";
import { Icon } from "../ui/Icon";
import { useToast } from "../ui/Toasts";

interface Props {
  types: DocTypeSummary[];
  editable: boolean;
  onChanged: () => void;
}

interface Editing {
  /** id редактируемого типа или "new" */
  id: string;
  yaml: string;
  original: string;
}

export function TypesView({ types, editable, onChanged }: Props) {
  const toast = useToast();
  const [editing, setEditing] = useState<Editing | null>(null);
  const [check, setCheck] = useState<TypeValidation | null>(null);
  const [saving, setSaving] = useState(false);
  const [toDelete, setToDelete] = useState<DocTypeSummary | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const gutter = useRef<HTMLDivElement>(null);

  const open = async (id: string) => {
    try {
      const yaml = id === "new" ? await api.typeTemplate() : await api.typeYaml(id);
      setEditing({ id, yaml, original: yaml });
      setCheck(null);
    } catch (e) {
      toast.show((e as Error).message, "error");
    }
  };

  // проверка YAML «на лету» с небольшой задержкой
  const validate = useCallback((yaml: string) => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      api.validateType(yaml).then(setCheck).catch((e: Error) => setCheck({ ok: false, error: e.message }));
    }, 350);
  }, []);

  useEffect(() => () => void (timer.current && clearTimeout(timer.current)), []);
  useEffect(() => {
    if (editing) validate(editing.yaml);
  }, [editing?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const save = useCallback(async () => {
    if (!editing || saving || !check?.ok) return;
    setSaving(true);
    try {
      const r = await api.saveType(editing.id, editing.yaml);
      toast.show(`Тип «${r.title}» сохранён — он уже работает`, "ok");
      setEditing(null);
      onChanged();
    } catch (e) {
      toast.show((e as Error).message, "error");
    } finally {
      setSaving(false);
    }
  }, [editing, saving, check, toast, onChanged]);

  // Ctrl+S в редакторе
  useEffect(() => {
    if (!editing) return;
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") (e.preventDefault(), void save());
      if (e.key === "Escape") setEditing(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [editing, save]);

  const remove = async () => {
    if (!toDelete) return;
    try {
      await api.deleteType(toDelete.id);
      toast.show(`Тип «${toDelete.title}» удалён`, "ok");
      onChanged();
    } catch (e) {
      toast.show((e as Error).message, "error");
    } finally {
      setToDelete(null);
    }
  };

  const dirty = !!editing && editing.yaml !== editing.original;
  const lines = editing ? editing.yaml.split("\n").length : 0;
  const errLine = check && !check.ok ? errorLine(check.error) : null;
  const preview = useMemo(() => (editing ? extractFields(editing.yaml) : []), [editing]);

  return (
    <div className="types">
      <header className="view-head">
        <div>
          <p className="eyebrow">Без единой строки кода</p>
          <h1>Типы документов</h1>
          <p className="muted">Каждый тип описан в YAML: поля, названия, ключевые фразы. Новый тип добавляется описанием полей — код не меняется.</p>
        </div>
        {editable && !editing && (
          <button type="button" className="btn primary" onClick={() => open("new")}>
            <Icon name="plus" /> Новый тип
          </button>
        )}
      </header>

      {editing ? (
        <section className="editor" aria-label="Редактор типа документа">
          <div className="editor-main">
            <header className="editor-bar">
              <h2>{editing.id === "new" ? "Новый тип документа" : editing.id}</h2>
              <span className={`validity ${check ? (check.ok ? "ok" : "bad") : ""}`} role="status">
                {!check ? "Проверяю…" : check.ok ? "Описание корректно" : "Ошибка в описании"}
              </span>
            </header>
            <div className="code-wrap">
              <div className="gutter" ref={gutter} aria-hidden="true">
                {Array.from({ length: lines }, (_, i) => (
                  <span key={i} className={errLine === i + 1 ? "err" : ""}>
                    {i + 1}
                  </span>
                ))}
              </div>
              <textarea
                className="code"
                spellCheck={false}
                wrap="off"
                value={editing.yaml}
                aria-label="YAML-описание типа"
                onScroll={(e) => gutter.current && (gutter.current.scrollTop = e.currentTarget.scrollTop)}
                onChange={(e) => {
                  setEditing({ ...editing, yaml: e.target.value });
                  validate(e.target.value);
                }}
              />
            </div>
            {check && !check.ok && (
              <p className="alert" role="alert">
                {check.error}
              </p>
            )}
            <div className="row">
              <button type="button" className="btn primary" disabled={saving || !check?.ok} onClick={() => void save()}>
                {saving ? "Сохраняю…" : "Сохранить"} <kbd>Ctrl S</kbd>
              </button>
              <button type="button" className="btn ghost" onClick={() => setEditing(null)}>
                {dirty ? "Отменить изменения" : "Закрыть"}
              </button>
            </div>
          </div>

          <aside className="editor-side" aria-label="Предпросмотр">
            <p className="eyebrow">Как это увидит секретарь</p>
            {check?.ok && (
              <div className="stats">
                <div>
                  <strong className="tabnum">{check.fields}</strong>
                  <span>полей</span>
                </div>
                <div>
                  <strong className="tabnum">{check.units}</strong>
                  <span>значений</span>
                </div>
              </div>
            )}
            <ol className="preview-fields" role="list">
              {preview.map((f, i) => (
                <li key={`${f.id}${i}`} style={{ ["--i" as string]: i }}>
                  <span className="glyph found">
                    <Icon name="check" size={11} />
                  </span>
                  <span>
                    <strong>{f.title || f.id}</strong>
                    <small>{f.id}</small>
                  </span>
                </li>
              ))}
              {!preview.length && <li className="faint">Поля появятся, когда в разделе <code>fields</code> будут описания.</li>}
            </ol>
          </aside>
        </section>
      ) : (
        <ul className="type-grid" role="list">
          {types.map((t, i) => (
            <li key={t.id} className="type-card" style={{ ["--i" as string]: i }}>
              <span className="folder-tab tabnum">{t.id}</span>
              <h2>{t.title}</h2>
              <p className="faint">Полей: {t.fields.length}</p>
              <ul className="field-chips" role="list">
                {t.fields.slice(0, 6).map((f) => (
                  <li key={f.id}>{f.title}</li>
                ))}
                {t.fields.length > 6 && <li className="more">+{t.fields.length - 6}</li>}
              </ul>
              {editable && (
                <div className="row">
                  <button type="button" className="btn small" onClick={() => open(t.id)}>
                    <Icon name="edit" size={14} /> Редактировать
                  </button>
                  <button type="button" className="btn ghost small" onClick={() => setToDelete(t)}>
                    <Icon name="trash" size={14} /> Удалить
                  </button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      <ConfirmDialog
        open={!!toDelete}
        title="Удалить тип документа?"
        message={toDelete ? `Тип «${toDelete.title}» перестанет определяться и выбираться. Файл с описанием будет удалён с диска.` : ""}
        confirmLabel="Удалить"
        danger
        onConfirm={remove}
        onCancel={() => setToDelete(null)}
      />
    </div>
  );
}
