import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import { ClauseDrawer } from "../components/ClauseDrawer";
import { Composer, type ComposerHandle } from "../components/desk/Composer";
import type { DeskDoc, Highlight } from "../components/desk/highlight";
import { PaperViewer } from "../components/desk/PaperViewer";
import { Thread } from "../components/desk/Thread";
import { Tray } from "../components/desk/Tray";
import { type Turn, useDesk } from "../hooks/useDesk";
import { useFetch } from "../hooks/useFetch";
import { useHistory } from "../hooks/useHistory";
import { useObjectUrl } from "../hooks/useObjectUrl";
import { resetActivity, setActivity } from "../lib/activity";
import { useBus } from "../lib/bus";
import { fileFromClipboard, isPdf, validateFile } from "../lib/files";
import { fieldBoxes } from "../lib/format";
import { STAGES, stageIndex } from "../lib/stages";
import { suggestionsFor } from "../lib/suggestions";
import { AUTO_TYPE, type Box, type DocTypeSummary, type FieldResult, GENERIC_TYPE, type Health, type PartResult, type SampleItem, type Source } from "../types";
import { Portal } from "../ui/Portal";
import { useToast } from "../ui/Toasts";

interface Props {
  types: DocTypeSummary[];
  health: Health | null;
  onOpenClause: (ref: string) => void;
}

const isNarrow = () => typeof matchMedia === "function" && matchMedia("(max-width: 1099px)").matches;

export function CheckView({ types, health, onOpenClause }: Props) {
  const toast = useToast();
  const desk = useDesk();
  const history = useHistory();
  const samples = useFetch<SampleItem[]>(api.samples);
  const rules = useFetch(api.ruleSuggestions);
  const composer = useRef<ComposerHandle>(null);
  const stageRef = useRef<HTMLElement>(null);

  const [file, setFile] = useState<File | null>(null);
  const [question, setQuestion] = useState("");
  const [docType, setDocType] = useState(AUTO_TYPE);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [highlight, setHighlight] = useState<Highlight | null>(null);
  const [hover, setHover] = useState<Highlight | null>(null);
  const [activeField, setActiveField] = useState<string | null>(null);
  const [showAll, setShowAll] = useState(false);
  const [drawer, setDrawer] = useState<{ ref: string; quote: string } | null>(null);
  const [dragging, setDragging] = useState(false);

  const { turns, busy } = desk;
  const maxMb = health?.max_upload_mb ?? 25;
  const lastTurn = turns[turns.length - 1];
  const activeTurn = turns.find((t) => t.id === activeId) ?? lastTurn ?? null;

  // ход проверки виден в верхней панели и в заголовке вкладки
  const wasBusy = useRef(false);
  const running = turns.find((t) => t.phase === "running");
  const runFraction = running?.progress?.fraction ?? 0;
  const runLabel = running?.progress ? (STAGES[Math.min(stageIndex(running.progress.stage), STAGES.length - 1)]?.title ?? "Проверяю") : "";
  useEffect(() => {
    if (running) {
      wasBusy.current = true;
      setActivity({ busy: true, fraction: runFraction, label: runLabel });
    } else if (wasBusy.current) {
      wasBusy.current = false;
      setActivity({ busy: false, fraction: 1, label: "", finishedAt: Date.now() });
    }
  }, [!!running, runFraction, runLabel]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => () => resetActivity(), []);

  // новая реплика становится активной
  useEffect(() => {
    if (lastTurn) {
      setActiveId(lastTurn.id);
      setHover(null);
    }
  }, [lastTurn?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  // пришёл ответ: сразу показываем на снимке то, на чём он основан
  const lastDone = lastTurn?.phase === "done" ? lastTurn.result : null;
  useEffect(() => {
    if (!lastDone || !lastTurn) return;
    const all = [...lastDone.answer.sources, ...lastDone.answer.related];
    for (const s of all) {
      const boxes = s.boxes.length ? s.boxes : lastDone.fields.filter((f) => f.id === s.ref).flatMap(fieldBoxes);
      if (boxes.length) {
        setHighlight({ id: `${s.kind}:${s.ref}`, label: s.label, boxes });
        setActiveField(s.kind === "field" ? s.ref : null);
        return;
      }
    }
    setHighlight(null);
    setActiveField(null);
  }, [lastDone]); // eslint-disable-line react-hooks/exhaustive-deps

  const submit = useCallback(
    async (o?: { file?: File | null; question?: string; docType?: string }) => {
      const f = o && "file" in o ? (o.file ?? null) : file;
      const q = o?.question ?? question;
      const t = o?.docType ?? docType;
      setHighlight(null);
      setActiveField(null);
      setQuestion("");
      const done = await desk.run({ file: f, fileName: f?.name, question: q, docType: t });
      if (done?.result) {
        history.add({ id: done.id, at: done.at, question: q.trim(), fileName: f?.name ?? "", docType: t, typeTitle: done.result.doc_type.title ?? "", verdict: done.result.answer.verdict, answer: done.result.answer.text.slice(0, 160) });
      }
    },
    [file, question, docType, desk, history],
  );

  const loadSample = useCallback(
    async (s: SampleItem) => {
      try {
        const res = await fetch(api.sampleUrl(s.file));
        if (!res.ok) throw new Error("Не удалось загрузить пример");
        const blob = await res.blob();
        const f = new File([blob], s.file, { type: blob.type || "image/png" });
        const t = s.doc_type === GENERIC_TYPE ? GENERIC_TYPE : AUTO_TYPE;
        setFile(f);
        setDocType(t);
        await submit({ file: f, question: s.question, docType: t });
      } catch (e) {
        toast.show((e as Error).message, "error");
      }
    },
    [submit, toast],
  );

  const reset = useCallback(() => {
    desk.clear();
    setFile(null);
    setQuestion("");
    setDocType(AUTO_TYPE);
    setHighlight(null);
    setHover(null);
    setActiveId(null);
    setActiveField(null);
  }, [desk]);

  useBus<SampleItem>("sample", (s) => void loadSample(s));
  useBus("new-desk", reset);
  useBus("pick-file", () => composer.current?.pickFile());
  useBus("focus-question", () => composer.current?.focusQuestion());

  // файл можно бросить на любое место стола, вставить из буфера; Esc отменяет проверку; «/» — к вопросу
  useEffect(() => {
    let depth = 0;
    const hasFiles = (e: DragEvent) => !!e.dataTransfer && Array.from(e.dataTransfer.types).includes("Files");
    const onEnter = (e: DragEvent) => hasFiles(e) && (depth++, setDragging(true));
    const onLeave = (e: DragEvent) => hasFiles(e) && (depth = Math.max(0, depth - 1)) === 0 && setDragging(false);
    const onOver = (e: DragEvent) => hasFiles(e) && e.preventDefault();
    const onDrop = (e: DragEvent) => {
      if (!hasFiles(e)) return;
      e.preventDefault();
      depth = 0;
      setDragging(false);
      const f = e.dataTransfer?.files[0];
      if (!f || busy) return;
      const problem = validateFile(f, maxMb);
      problem ? toast.show(problem, "error") : setFile(f);
    };
    const onPaste = (e: ClipboardEvent) => {
      const f = fileFromClipboard(e);
      if (f && !busy) (setFile(f), toast.show(`Вставлено из буфера: ${f.name}`, "info"));
    };
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement | null)?.tagName;
      const typing = tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";
      if (e.key === "Escape" && busy) desk.cancel();
      if (e.key === "/" && !typing && !e.ctrlKey && !e.metaKey) (e.preventDefault(), composer.current?.focusQuestion());
    };
    window.addEventListener("dragenter", onEnter);
    window.addEventListener("dragleave", onLeave);
    window.addEventListener("dragover", onOver);
    window.addEventListener("drop", onDrop);
    window.addEventListener("paste", onPaste);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("dragenter", onEnter);
      window.removeEventListener("dragleave", onLeave);
      window.removeEventListener("dragover", onOver);
      window.removeEventListener("drop", onDrop);
      window.removeEventListener("paste", onPaste);
      window.removeEventListener("keydown", onKey);
    };
  }, [busy, maxMb, toast, desk]);

  const typeTitle = (id: string) => (id === GENERIC_TYPE ? "Другой документ" : (types.find((t) => t.id === id)?.title ?? id));

  const flyToStage = () => isNarrow() && stageRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });

  const focusSource = (turn: Turn, s: Source, boxes: Box[]) => {
    setActiveId(turn.id);
    if (!boxes.length) return toast.show("Для этого источника на снимке нет отдельной рамки", "info");
    setActiveField(s.kind === "field" ? s.ref : null);
    setHighlight({ id: `${s.kind}:${s.ref}`, label: s.label, boxes });
    flyToStage();
  };

  const selectField = (turn: Turn, f: FieldResult, part?: PartResult) => {
    setActiveId(turn.id);
    setActiveField(part ? `${f.id}.${part.id}` : f.id);
    setHighlight({ id: `field:${f.id}${part ? "." + part.id : ""}`, label: part ? `${f.title}: ${part.title}` : f.title, boxes: part ? part.boxes : fieldBoxes(f) });
    flyToStage();
  };

  const chooseType = (turn: Turn, typeId: string) => {
    setDocType(typeId);
    setHighlight(null);
    void desk
      .run({ file: turn.file, fileName: turn.fileName, question: turn.question, docType: typeId }, `Пересчитано как «${typeTitle(typeId)}»`)
      .then((done) => done?.result && history.add({ id: done.id, at: done.at, question: turn.question, fileName: turn.fileName, docType: typeId, typeTitle: done.result.doc_type.title ?? "", verdict: done.result.answer.verdict, answer: done.result.answer.text.slice(0, 160) }));
  };

  // что показывать на столе: идущая или выбранная проверка, иначе файл из поля ввода, иначе пустой лоток
  const stageTurn = turns.find((t) => t.phase === "running") ?? activeTurn;
  const composerFileIsNew = !!file && (!stageTurn || stageTurn.file !== file);
  const subjectFile: Blob | null = composerFileIsNew ? file : (stageTurn?.file ?? null);
  const subjectName = composerFileIsNew ? (file?.name ?? "") : (stageTurn?.fileName ?? "");
  const subjectResult = composerFileIsNew ? null : (stageTurn?.phase === "done" ? stageTurn.result : null);
  const subjectUrl = useObjectUrl(subjectFile, subjectName);
  const hasSubject = !!subjectFile || !!subjectResult;
  const scanning = !composerFileIsNew && stageTurn?.phase === "running";
  const progress = stageTurn?.progress?.fraction ?? 0;
  const stageLabel = stageTurn?.progress ? (STAGES[Math.min(stageIndex(stageTurn.progress.stage), STAGES.length - 1)]?.title ?? "") : "";

  const allBoxes = useMemo(() => (subjectResult ? subjectResult.fields.flatMap(fieldBoxes) : []), [subjectResult]);

  // все документы, которые клали на стол в этой сессии, плюс файл из поля ввода
  const docs = useMemo<DeskDoc[]>(() => {
    const list: DeskDoc[] = [];
    const seen = new Set<Blob>();
    for (const t of turns) {
      if (t.file && !seen.has(t.file)) {
        seen.add(t.file);
        list.push({ key: t.id, file: t.file, name: t.fileName });
      }
    }
    if (file && !seen.has(file)) list.push({ key: "new", file, name: file.name });
    return list;
  }, [turns, file]);
  const activeDoc = docs.findIndex((d) => d.file === subjectFile);

  const selectDocByFile = (f: Blob) => {
    const i = docs.findIndex((d) => d.file === f);
    if (i >= 0) selectDoc(i);
  };

  const selectDoc = (i: number) => {
    const d = docs[i];
    if (!d) return;
    setFile(d.file as File);
    const last = [...turns].reverse().find((t) => t.file === d.file);
    if (last) setActiveId(last.id);
    setHighlight(null);
    setHover(null);
    setActiveField(null);
  };
  const suggestions = suggestionsFor(types, docType, activeTurn?.result?.doc_type.id, rules.data?.rules ?? []);

  return (
    <div className="desk">
      <section className="desk-chat" aria-label="Диалог">
        <div className="chat-scroll">
          <Thread
            turns={turns}
            activeId={activeTurn?.id ?? null}
            types={types}
            busy={busy}
            activeField={activeField}
            history={history.entries}
            onActivate={(id) => {
              setActiveId(id);
              setHighlight(null);
              setActiveField(null);
            }}
            onCancel={desk.cancel}
            onRetry={(t) => void desk.run({ file: t.file, fileName: t.fileName, question: t.question, docType: t.docType })}
            onFocusSource={focusSource}
            onClause={(s) => setDrawer({ ref: s.ref, quote: s.quote })}
            onFieldHover={setHover}
            onFieldSelect={selectField}
            onChooseType={chooseType}
            onPickHistory={(e) => {
              setQuestion(e.question);
              setDocType(e.docType);
              composer.current?.focusQuestion();
            }}
            onClearHistory={history.clear}
            rules={(rules.data?.rules ?? []).map((r) => r.text)}
            onAsk={(t, q) => void submit({ file: t.file as File | null, question: q, docType: t.docType })}
            onEdit={(t) => {
              setQuestion(t.question);
              setDocType(t.docType);
              if (t.file) selectDocByFile(t.file);
              composer.current?.focusQuestion();
            }}
          />
        </div>
        <Composer
          ref={composer}
          file={file}
          question={question}
          docType={docType}
          types={types}
          suggestions={suggestions}
          maxMb={maxMb}
          busy={busy}
          onFile={setFile}
          onQuestion={setQuestion}
          onDocType={setDocType}
          onSubmit={() => void submit()}
          onCancel={desk.cancel}
          onError={(m) => toast.show(m, "error")}
          recall={lastTurn?.question}
        />
      </section>

      <section className={`desk-stage ${hasSubject ? "has-subject" : "is-empty"}`} ref={stageRef} aria-label="Стол с документом">
        {hasSubject ? (
          <PaperViewer
            src={subjectUrl}
            pages={subjectResult?.images?.length ? subjectResult.images : null}
            fileName={subjectName}
            pdf={!!subjectFile && isPdf({ name: subjectName, type: subjectFile.type })}
            scanning={!!scanning}
            progress={progress}
            stageLabel={stageLabel}
            highlight={highlight}
            hover={hover}
            allBoxes={allBoxes}
            showAll={showAll}
            revealKey={`${stageTurn?.id}:${stageTurn?.phase}`}
            onToggleAll={() => setShowAll((v) => !v)}
            onClear={() => (setHighlight(null), setActiveField(null))}
            docs={docs}
            activeDoc={activeDoc}
            busy={busy}
            onSelectDoc={selectDoc}
            onAnother={() => composer.current?.pickFile()}
            cta={composerFileIsNew && !busy ? { label: question.trim() ? "Проверить с моим вопросом" : "Проверить документ целиком", onClick: () => void submit() } : null}
          />
        ) : (
          <Tray maxMb={maxMb} samples={samples.data ?? []} dragging={dragging} busy={busy} onFile={setFile} onSample={(s) => void loadSample(s)} onError={(m) => toast.show(m, "error")} />
        )}
      </section>

      <Portal>
        <ClauseDrawer refId={drawer?.ref ?? null} quote={drawer?.quote ?? ""} onClose={() => setDrawer(null)} onOpenRegulation={(ref) => (setDrawer(null), onOpenClause(ref))} />
        <div className="drop-veil" data-on={dragging} aria-hidden="true">
          <div>
            <strong>Отпустите — положу на стол</strong>
            <span>JPG, PNG или PDF</span>
          </div>
        </div>
      </Portal>
    </div>
  );
}
