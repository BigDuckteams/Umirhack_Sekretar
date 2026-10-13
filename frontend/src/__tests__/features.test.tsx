import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AnswerTurn } from "../components/desk/AnswerTurn";
import { Composer } from "../components/desk/Composer";
import { DocStrip } from "../components/desk/DocStrip";
import { UserTurn } from "../components/desk/UserTurn";
import type { Turn } from "../hooks/useDesk";
import { scaleBoxes } from "../lib/annotate";
import { answerToText, followUps } from "../lib/followups";
import type { AnalysisResult, FieldResult } from "../types";

const noop = () => {};

const field = (over: Partial<FieldResult>): FieldResult => ({
  id: "f",
  title: "ФИО студента",
  export_title: "ФИО студента",
  kind: "person",
  status: "found",
  found: true,
  value: "Иванов Иван",
  normalized: null,
  confidence: 0.9,
  method: "label",
  evidence: "",
  boxes: [],
  parts: [],
  ...over,
});

const result = (over: Partial<AnalysisResult> = {}): AnalysisResult => ({
  doc_type: { id: "study_certificate", title: "Справка об обучении", how: "auto", confidence: 0.9, uncertain: false, ranking: [], candidates: [], reason: "" },
  ocr: { engine: "tesseract", pages: [], text: "" },
  fields: [field({}), field({ id: "form", title: "Форма обучения", value: "очная" }), field({ id: "x", title: "Печать", kind: "marks" })],
  answer: { verdict: "ok", text: "Справка содержит все данные.", intent: "check", sources: [], missing: [], related: [], confidence: 0.9, notes: [], debug: {} },
  warnings: [],
  timings: {},
  images: [],
  export: {},
  ...over,
});

describe("followUps", () => {
  it("suggests a check, found fields and rules, never the question just asked", () => {
    const list = followUps(result(), "Хватит ли этого документа?", ["Сколько дней рассматривается заявление?"]);
    expect(list).not.toContain("Хватит ли этого документа?");
    expect(list).toContain("Укажи ФИО студента");
    expect(list).toContain("Укажи форма обучения");
    expect(list).toContain("Сколько дней рассматривается заявление?");
    expect(list.length).toBeLessThanOrEqual(4);
  });

  it("asks what is missing when the verdict was «missing»", () => {
    const r = result({ answer: { ...result().answer, verdict: "missing" } });
    expect(followUps(r, "", [])[0]).toBe("Чего не хватает в документе?");
  });

  it("does not offer marks as fields and offers document questions for a foreign document", () => {
    expect(followUps(result(), "", []).join("|")).not.toContain("печать");
    const foreign = result({ doc_type: { ...result().doc_type, id: null, title: null, how: "none" }, fields: [] });
    expect(followUps(foreign, "О чём документ?", [])).toEqual(["Какая дата документа?", "Какой номер документа?", "Что указано в п. 1?"]);
  });

  it("formats the answer for the clipboard", () => {
    expect(answerToText("Чего-то не хватает", "Не хватает даты.", ["п. 3.4"])).toBe("Чего-то не хватает: Не хватает даты.\nИсточник: п. 3.4");
    expect(answerToText("Ответа нет", "Нет.", [])).toBe("Ответа нет: Нет.");
  });
});

describe("scaleBoxes", () => {
  it("rescales boxes of one page to a smaller preview", () => {
    const boxes = [
      { page: 0, x0: 100, y0: 200, x1: 300, y1: 240 },
      { page: 1, x0: 1, y0: 1, x1: 2, y1: 2 },
    ];
    expect(scaleBoxes(boxes, 0, 1000, 500, 1400, 700)).toEqual([{ x: 50, y: 100, w: 100, h: 20 }]);
  });
});

describe("DocStrip", () => {
  beforeAll(() => {
    URL.createObjectURL = vi.fn(() => "blob:test");
    URL.revokeObjectURL = vi.fn();
  });

  const docs = [
    { key: "1", file: new File(["a"], "one.png", { type: "image/png" }), name: "one.png" },
    { key: "2", file: new File(["b"], "two.png", { type: "image/png" }), name: "two.png" },
  ];

  it("switches between documents and offers «Другой документ»", async () => {
    const onSelect = vi.fn();
    const onAnother = vi.fn();
    render(<DocStrip docs={docs} active={0} onSelect={onSelect} onAnother={onAnother} />);
    expect(screen.getByRole("button", { name: /one.png/ })).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(screen.getByRole("button", { name: /two.png/ }));
    expect(onSelect).toHaveBeenCalledWith(1);
    await userEvent.click(screen.getByRole("button", { name: /Другой документ/ }));
    expect(onAnother).toHaveBeenCalledTimes(1);
  });

  it("disables the button while a check is running", () => {
    render(<DocStrip docs={docs} active={0} disabled onSelect={noop} onAnother={noop} />);
    expect(screen.getByRole("button", { name: /Другой документ/ })).toBeDisabled();
  });
});

const turn = (over: Partial<Turn> = {}): Turn => ({
  id: "t1",
  at: Date.now(),
  question: "Хватит ли этого документа?",
  docType: "auto",
  fileName: "",
  file: null,
  phase: "done",
  progress: null,
  result: result(),
  error: null,
  ...over,
});

describe("UserTurn", () => {
  it("lets the user edit the question", async () => {
    const onEdit = vi.fn();
    render(<UserTurn turn={turn()} typeTitle={(id) => id} onEdit={onEdit} />);
    await userEvent.click(screen.getByRole("button", { name: /Изменить вопрос/ }));
    expect(onEdit).toHaveBeenCalledWith(expect.objectContaining({ id: "t1" }));
  });
});

describe("AnswerTurn follow-ups", () => {
  const props = {
    turn: turn(),
    active: true,
    types: [],
    busy: false,
    activeField: null,
    rules: ["Сколько дней рассматривается заявление?"],
    onActivate: noop,
    onFocusSource: noop,
    onClause: noop,
    onFieldHover: noop,
    onFieldSelect: noop,
    onChooseType: noop,
    onAsk: noop,
  };

  it("asks a suggested question on click", async () => {
    const onAsk = vi.fn();
    render(<AnswerTurn {...props} onAsk={onAsk} />);
    await userEvent.click(screen.getByRole("button", { name: /Сколько дней рассматривается заявление\?/ }));
    expect(onAsk).toHaveBeenCalledWith("Сколько дней рассматривается заявление?");
  });

  it("is disabled while another check runs", () => {
    render(<AnswerTurn {...props} busy />);
    expect(screen.getByRole("button", { name: /Сколько дней рассматривается заявление\?/ })).toBeDisabled();
  });
});

describe("Composer question recall", () => {
  const base = {
    file: null,
    question: "",
    docType: "auto",
    types: [],
    suggestions: [],
    maxMb: 25,
    busy: false,
    onFile: noop,
    onQuestion: noop,
    onDocType: noop,
    onSubmit: noop,
    onCancel: noop,
    onError: noop,
  };

  it("brings back the last question with the Up arrow in an empty field", () => {
    const onQuestion = vi.fn();
    render(<Composer {...base} onQuestion={onQuestion} recall="Сколько стоит обучение?" />);
    fireEvent.keyDown(screen.getByLabelText("Вопрос"), { key: "ArrowUp" });
    expect(onQuestion).toHaveBeenCalledWith("Сколько стоит обучение?");
  });

  it("does not overwrite text that is already typed", () => {
    const onQuestion = vi.fn();
    render(<Composer {...base} question="Уже набрано" onQuestion={onQuestion} recall="Прошлый вопрос" />);
    fireEvent.keyDown(screen.getByLabelText("Вопрос"), { key: "ArrowUp" });
    expect(onQuestion).not.toHaveBeenCalled();
  });
});
