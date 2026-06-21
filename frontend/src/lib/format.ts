import { PAGE_SIZE } from "@/lib/constants";
import type { ImportKind, Job, Label, ProviderWarning, SourceType, TokenSuggestion } from "@/types/domain";

export function sourceColor(source: SourceType) {
  switch (source) {
    case "text":
    case "txt":
      return "green";
    case "csv":
      return "violet";
    case "pdf":
      return "red";
    case "image":
      return "grape";
  }
}

export function statusColor(status: string) {
  switch (status) {
    case "accepted":
    case "approved":
    case "ready":
    case "succeeded":
      return "green";
    case "updated":
    case "edited":
    case "running":
      return "violet";
    case "denied":
    case "failed":
      return "red";
    case "pending":
    case "queued":
      return "yellow";
    default:
      return "gray";
  }
}

export function formatPercent(value: number) {
  return `${Math.round(value * 100)}%`;
}

export function csvFormatHint(importKind: ImportKind) {
  if (importKind === "translation") {
    return "Required columns: text,translation,source,src,target. Extra metadata columns are allowed.";
  }
  if (importKind === "pos") {
    return "CSV columns: text,tags. Tags must be UPOS values matching text tokens.";
  }
  return "Generic CSV uses text as the sentence column and creates labels from other columns.";
}

export function importSuccessMessage(base: string, job: Job) {
  if (isJobActive(job)) {
    return `${base.replace(/ imported$/, " import")} started`;
  }
  const skipped = Number(job.metadata.skipped_count ?? 0);
  if (!Number.isFinite(skipped) || skipped <= 0) {
    return base;
  }
  return `${base}; skipped ${skipped} row${skipped === 1 ? "" : "s"}`;
}

export function isJobActive(job: Job) {
  return job.status === "queued" || job.status === "running";
}

export function lastPageIndex(total: number) {
  return Math.max(0, Math.ceil(total / PAGE_SIZE) - 1);
}

export function assertJobSucceeded(job: Job) {
  if (job.status === "failed") {
    throw new Error(job.error || "Import failed");
  }
}

export function translationValue(label: Label) {
  const value = label.value["text"];
  return typeof value === "string" ? value : JSON.stringify(label.value);
}

export function formatTokenDetails(tokens: TokenSuggestion[]) {
  if (tokens.length === 0) return "No tokens";
  return tokens
    .map(token => `${token.index + 1}. ${token.token} -> ${token.suggested_pos} (${formatPercent(token.confidence)})`)
    .join("\n");
}

export function jobWarnings(job: Job): ProviderWarning[] {
  const warnings = job.metadata["warnings"];
  if (!Array.isArray(warnings)) return [];
  return warnings.filter(
    (warning): warning is ProviderWarning =>
      typeof warning === "object" &&
      warning !== null &&
      "provider" in warning &&
      "stage" in warning &&
      "message" in warning,
  );
}
