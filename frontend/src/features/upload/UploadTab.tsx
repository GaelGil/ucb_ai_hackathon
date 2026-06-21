import { SimpleGrid } from "@mantine/core";

import type { ImportKind, ImportRecord, SourceType } from "@/types/domain";

import { FileImportForm } from "./FileImportForm";
import { ManualImportForm } from "./ManualImportForm";

export function UploadTab({
  manualSource,
  manualImportKind,
  manualText,
  fileImportKind,
  uploadFile,
  uploadFileIsCsv,
  imports,
  loading,
  working,
  onManualSourceChange,
  onManualImportKindChange,
  onManualTextChange,
  onFileImportKindChange,
  onUploadFileChange,
  onManualImport,
  onFileImport,
}: {
  manualSource: SourceType;
  manualImportKind: ImportKind;
  manualText: string;
  fileImportKind: ImportKind;
  uploadFile: File | null;
  uploadFileIsCsv: boolean;
  imports: ImportRecord[];
  loading: boolean;
  working: boolean;
  onManualSourceChange: (value: SourceType) => void;
  onManualImportKindChange: (value: ImportKind) => void;
  onManualTextChange: (value: string) => void;
  onFileImportKindChange: (value: ImportKind) => void;
  onUploadFileChange: (file: File | null) => void;
  onManualImport: () => void;
  onFileImport: () => void;
}) {
  return (
    <SimpleGrid cols={{ base: 1, lg: 2 }} spacing="md">
      <ManualImportForm
        manualSource={manualSource}
        manualImportKind={manualImportKind}
        manualText={manualText}
        working={working}
        onManualSourceChange={onManualSourceChange}
        onManualImportKindChange={onManualImportKindChange}
        onManualTextChange={onManualTextChange}
        onImport={onManualImport}
      />
      <FileImportForm
        fileImportKind={fileImportKind}
        uploadFile={uploadFile}
        uploadFileIsCsv={uploadFileIsCsv}
        imports={imports}
        loading={loading}
        working={working}
        onFileImportKindChange={onFileImportKindChange}
        onUploadFileChange={onUploadFileChange}
        onImport={onFileImport}
      />
    </SimpleGrid>
  );
}
