import type { AnnotationRow, Dataset, ImportKind, Label, Suggestion } from "@/types/domain";

export const PAGE_SIZE = 10;

export const UPOS_TAGS = [
  "ADJ",
  "ADP",
  "ADV",
  "AUX",
  "CCONJ",
  "DET",
  "INTJ",
  "NOUN",
  "NUM",
  "PART",
  "PRON",
  "PROPN",
  "PUNCT",
  "SCONJ",
  "SYM",
  "VERB",
  "X",
] as const;

export const UI = {
  background: "#030304",
  header: "rgba(7, 7, 8, 0.96)",
  navbar: "#09090b",
  panel: "rgba(18, 18, 22, 0.96)",
  panelSoft: "rgba(14, 14, 18, 0.84)",
  border: "rgba(255, 255, 255, 0.11)",
};

export const SIDEBAR_WIDTH = 304;
export const SIDEBAR_COLLAPSED_WIDTH = 84;

export const IMPORT_KIND_OPTIONS = [
  { value: "generic", label: "Generic CSV" },
  { value: "translation", label: "Translation labels" },
  { value: "pos", label: "POS tags" },
] satisfies { value: ImportKind; label: string }[];

export const EMPTY_DATASETS: Dataset[] = [];
export const EMPTY_ANNOTATION_ROWS: AnnotationRow[] = [];
export const EMPTY_SUGGESTIONS: Suggestion[] = [];
export const EMPTY_LABELS: Label[] = [];
