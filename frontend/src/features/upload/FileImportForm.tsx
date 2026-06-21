import { Button, FileInput, Group, Select, Stack, Text } from "@mantine/core";
import { TbUpload } from "react-icons/tb";

import { PaperPanel } from "@/components/ui/PaperPanel";
import { IMPORT_KIND_OPTIONS } from "@/lib/constants";
import { csvFormatHint } from "@/lib/format";
import type { ImportKind, ImportRecord } from "@/types/domain";

import { ImportsTable } from "./ImportsTable";

export function FileImportForm({
  fileImportKind,
  uploadFile,
  uploadFileIsCsv,
  imports,
  loading,
  working,
  onFileImportKindChange,
  onUploadFileChange,
  onImport,
}: {
  fileImportKind: ImportKind;
  uploadFile: File | null;
  uploadFileIsCsv: boolean;
  imports: ImportRecord[];
  loading: boolean;
  working: boolean;
  onFileImportKindChange: (value: ImportKind) => void;
  onUploadFileChange: (file: File | null) => void;
  onImport: () => void;
}) {
  return (
    <PaperPanel title="Files and Imports" eyebrow="CSV, TXT, PDF, image">
      <Stack gap="md">
        <Select
          data={IMPORT_KIND_OPTIONS}
          label="CSV format"
          name="fileImportKind"
          value={fileImportKind}
          onChange={value => onFileImportKindChange((value as ImportKind | null) ?? "generic")}
        />
        <Text
          c={fileImportKind !== "generic" && uploadFile && !uploadFileIsCsv ? "red" : "dimmed"}
          size="xs"
        >
          {fileImportKind !== "generic" && uploadFile && !uploadFileIsCsv
            ? "Translation and POS label imports require a .csv file."
            : csvFormatHint(fileImportKind)}
        </Text>
        <Group align="end" wrap="wrap">
          <FileInput
            flex={1}
            label="Upload file"
            name="uploadFile"
            placeholder="Choose CSV, TXT, PDF, or image…"
            value={uploadFile}
            onChange={onUploadFileChange}
          />
          <Button
            color="green"
            disabled={working || !uploadFile || (fileImportKind !== "generic" && !uploadFileIsCsv)}
            leftSection={<TbUpload aria-hidden="true" size={16} />}
            onClick={onImport}
          >
            {working ? "Uploading..." : "Upload"}
          </Button>
        </Group>
        <ImportsTable imports={imports} loading={loading} />
      </Stack>
    </PaperPanel>
  );
}
