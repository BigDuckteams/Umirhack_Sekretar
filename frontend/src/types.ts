/** Типы ответов API (см. dekanat/models.py и dekanat/pipeline.py). Координаты рамок — в пикселях исходного снимка. */

export type Verdict = "ok" | "missing" | "no_answer";
export type FieldStatus = "found" | "partial" | "missing";

export interface Box {
  page: number;
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

export interface PartResult {
  id: string;
  title: string;
  found: boolean;
  value: string;
  normalized: unknown;
  confidence: number;
  boxes: Box[];
}

export interface FieldResult {
  id: string;
  title: string;
  export_title: string;
  kind: string;
  status: FieldStatus;
  found: boolean;
  value: string;
  normalized: unknown;
  confidence: number;
  method: string;
  evidence: string;
  boxes: Box[];
  parts: PartResult[];
}

export interface Source {
  kind: "clause" | "field" | "document" | string;
  ref: string;
  label: string;
  quote: string;
  boxes: Box[];
}

export interface MissingItem {
  unit?: string;
  title: string;
  clause?: string;
  [key: string]: unknown;
}

export interface Answer {
  verdict: Verdict;
  text: string;
  intent: string;
  sources: Source[];
  missing: MissingItem[];
  related: Source[];
  confidence: number;
  notes: string[];
  debug: Record<string, unknown>;
  /** структурированный ответ: вывод, факты документа, пункты, недостающее и сомнительное, оговорка о решении деканата */
  report?: {
    disclaimer?: string;
    explanation?: string;
    explanation_note?: string;
  };
}

export interface TypeCandidate {
  id: string;
  title: string;
  share: number;
}

export interface DocTypeInfo {
  id: string | null;
  title: string | null;
  how: "auto" | "manual" | "generic" | "none";
  confidence: number;
  uncertain: boolean;
  ranking: { id: string; score: number }[];
  candidates: TypeCandidate[];
  reason: string;
}

export interface OcrPageInfo {
  index: number;
  width: number;
  height: number;
  variant: string | null;
  deskew_angle: number | null;
  rotation: number | null;
  score: number | null;
  mean_conf: number | null;
  words: number | null;
  seconds: number | null;
}

export interface PagePreview {
  page: number;
  width: number;
  height: number;
  data_url: string;
}

export interface AnalysisResult {
  doc_type: DocTypeInfo;
  ocr: { engine: string | null; pages: OcrPageInfo[]; text: string };
  fields: FieldResult[];
  answer: Answer;
  warnings: string[];
  timings: Record<string, number | boolean>;
  images: PagePreview[];
  export: Record<string, unknown>;
}

export type JobStatus = "queued" | "running" | "done" | "error" | "cancelled";

export interface JobSnapshot {
  id: string;
  status: JobStatus;
  stage: string;
  label: string;
  fraction: number;
  elapsed: number;
  result?: AnalysisResult;
  error?: string;
}

export interface Suggestion {
  kind: "check" | "field" | "rules";
  text: string;
}

export interface DocTypeSummary {
  id: string;
  title: string;
  short_title: string;
  source: string;
  fields: { id: string; title: string; kind: string; parts: { id: string; title: string }[] }[];
  examples: string[];
  suggestions: Suggestion[];
}

export interface Health {
  version: string;
  allow_edit: boolean;
  /** можно ли именно этому посетителю править Положение и типы (нужен вход администратора на /admin) */
  can_edit?: boolean;
  max_upload_mb: number;
  ocr: { available?: boolean; version?: string; languages?: string[]; [k: string]: unknown };
  doc_types: { id: string; title: string; fields: number }[];
  regulation: { name: string; clauses: number };
  llm: { backend: string; [k: string]: unknown };
}

export interface SampleItem {
  file: string;
  title: string;
  question: string;
  doc_type?: string;
}

export interface Clause {
  number: string;
  label: string;
  text: string;
  section: string[];
}

export interface RegulationInfo {
  name: string;
  clauses: Clause[];
  editable: boolean;
}

export interface TypeValidation {
  ok: boolean;
  error?: string;
  id?: string;
  title?: string;
  fields?: number;
  units?: number;
}

/** Идентификатор режима «другой документ»: ответ по тексту самого документа без карточки полей. */
export const GENERIC_TYPE = "generic";
export const AUTO_TYPE = "auto";
