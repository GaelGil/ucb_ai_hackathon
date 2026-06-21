import type { ReactNode } from "react";

export type SourceType = "text" | "csv" | "txt" | "pdf" | "image";
export type ImportKind = "generic" | "translation" | "pos";
export type ResearchType = "pos" | "translation";
export type ReviewFilter = "all" | "needs_review";
export type TranslationReviewFilter = "all" | "needs_review";
export type SuggestionType = "pos" | "ocr" | "translation" | "emotion" | "intention" | "text" | "custom";
export type SuggestionStatus = "pending" | "accepted" | "denied" | "updated" | "approved" | "edited";
export type LabelSource = "csv_import" | "human" | "ai_accepted" | "ai_updated";

export type ProviderWarning = {
  provider: string;
  stage: string;
  message: string;
  fallback: boolean;
};

export type Dataset = {
  id: string;
  name: string;
  language_code: string;
  language_name: string;
};

export type ImportRecord = {
  id: string;
  dataset_id: string;
  source_type: SourceType;
  filename: string | null;
  item_count: number;
  asset_count: number;
  label_count: number;
  status: string;
  column_mapping: Record<string, unknown>;
  created_at: string;
};

export type ResearchArtifact = {
  id: string;
  type: ResearchType;
  summary: string;
  guidelines: string[];
  sources: { title: string; url: string; excerpt: string }[];
  warnings: ProviderWarning[];
};

export type TokenSuggestion = {
  index: number;
  token: string;
  suggested_pos: string;
  confidence: number;
  rationale: string;
};

export type Suggestion = {
  id: string;
  type: SuggestionType;
  status: SuggestionStatus;
  original_text: string;
  suggested_text: string | null;
  tokens: TokenSuggestion[];
  confidence: number;
  rationale: string;
};

export type AnnotationRow = {
  id: string;
  dataset_id: string;
  data_row_id: string;
  text: string;
  type: SuggestionType;
  source_type: SourceType;
  created_at: string;
  pending_suggestion: Suggestion | null;
};

export type Label = {
  id: string;
  dataset_id: string;
  data_row_id: string;
  data_text: string | null;
  import_id: string | null;
  ai_suggestion_id: string | null;
  type: SuggestionType;
  name: string | null;
  value: Record<string, unknown>;
  source: LabelSource;
  original_column_name: string | null;
  created_at: string;
  pending_suggestion: Suggestion | null;
};

export type PaginationMeta = {
  total: number;
  limit: number;
  offset: number;
};

export type SuggestionsResponse = PaginationMeta & {
  suggestions: Suggestion[];
};

export type AnnotationRowsResponse = PaginationMeta & {
  rows: AnnotationRow[];
};

export type LabelsResponse = PaginationMeta & {
  labels: Label[];
};

export type WorkspacePagination = {
  posRows: number;
  ocrSuggestions: number;
  translationLabels: number;
};

export type PosModel = {
  status: string;
  mode: "demo" | "real";
  minimum_examples_met: boolean;
  accepted_sentence_count: number;
  minimum_examples: number;
  model_name: string | null;
  metrics: Record<string, number>;
};

export type Dashboard = {
  dataset: Dataset;
  imports: ImportRecord[];
  research: ResearchArtifact | null;
  suggestion_counts: Record<string, number>;
  item_count: number;
  pos_model: PosModel;
};

export type Job = {
  id: string;
  type: string;
  status: string;
  progress: number;
  message: string;
  error: string | null;
  metadata: Record<string, unknown>;
};

export type DetailRow = {
  label: string;
  value: ReactNode;
};

export type DetailContent = {
  title: string;
  rows: DetailRow[];
};

export type Toast = {
  tone: "violet" | "red" | "green";
  message: string;
};

export type DraftMap = Record<string, TokenSuggestion[]>;
export type TextDraftMap = Record<string, string>;
export type WorkspaceTab = "pos" | "ocr" | "translate" | "upload" | "models";
