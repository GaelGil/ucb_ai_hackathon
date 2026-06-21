import { SimpleGrid } from "@mantine/core";

import type { PosModel } from "@/types/domain";

import { ModelTrainingCard } from "./ModelTrainingCard";

export function ModelsPanel({
  acceptedPosCount,
  posModel,
  working,
  onTrainPos,
}: {
  acceptedPosCount: number;
  posModel: PosModel | null;
  working: boolean;
  onTrainPos: () => void;
}) {
  const minimumExamples = posModel?.minimum_examples ?? 20;
  const minimumMet = posModel?.minimum_examples_met ?? acceptedPosCount >= minimumExamples;
  const trainingMode = posModel?.mode ?? "demo";
  const posStatus = posModel
    ? `${trainingMode === "demo" ? "demo " : ""}${posModel.status.replaceAll("_", " ")}`
    : "not started";
  const posDescription = minimumMet
    ? `${acceptedPosCount} reviewed examples are ready for the tagger.`
    : `${acceptedPosCount}/${minimumExamples} reviewed examples; demo mode can still run for the presentation.`;

  return (
    <SimpleGrid cols={{ base: 1, md: 3 }} spacing="md">
      <ModelTrainingCard
        actionLabel="Train OCR Model"
        description="Tune OCR extraction for PDFs and image scans in this language workspace."
        disabled
        status="Needs document examples"
        title="OCR"
        tone="grape"
      />
      <ModelTrainingCard
        actionLabel="Train Translation Model"
        description="Train a translation model from aligned text, corrections, and reviewer suggestions."
        disabled
        status="Dataset alignment needed"
        title="Translation"
        tone="violet"
      />
      <ModelTrainingCard
        actionLabel="Run Demo POS Training"
        description={posDescription}
        disabled={working}
        onAction={onTrainPos}
        status={posStatus}
        title="POS Tagging"
        tone="green"
      />
    </SimpleGrid>
  );
}
