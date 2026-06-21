import { Button, Select, Stack, Text, Textarea } from "@mantine/core";
import { TbFileText } from "react-icons/tb";

import { PaperPanel } from "@/components/ui/PaperPanel";
import { IMPORT_KIND_OPTIONS } from "@/lib/constants";
import { csvFormatHint } from "@/lib/format";
import type { ImportKind, SourceType } from "@/types/domain";

export function ManualImportForm({
  manualSource,
  manualImportKind,
  manualText,
  working,
  onManualSourceChange,
  onManualImportKindChange,
  onManualTextChange,
  onImport,
}: {
  manualSource: SourceType;
  manualImportKind: ImportKind;
  manualText: string;
  working: boolean;
  onManualSourceChange: (value: SourceType) => void;
  onManualImportKindChange: (value: ImportKind) => void;
  onManualTextChange: (value: string) => void;
  onImport: () => void;
}) {
  return (
    <PaperPanel title="Manual Sentences" eyebrow="Text import">
      <Stack gap="md">
        <Select
          data={[
            { value: "text", label: "Manual text" },
            { value: "csv", label: "CSV text" },
            { value: "txt", label: "TXT lines" },
          ]}
          label="Source type"
          name="manualSource"
          value={manualSource}
          onChange={value => onManualSourceChange((value as SourceType | null) ?? "text")}
        />
        {manualSource === "csv" ? (
          <>
            <Select
              data={IMPORT_KIND_OPTIONS}
              label="CSV format"
              name="manualImportKind"
              value={manualImportKind}
              onChange={value => onManualImportKindChange((value as ImportKind | null) ?? "generic")}
            />
            <Text c="dimmed" size="xs">
              {csvFormatHint(manualImportKind)}
            </Text>
          </>
        ) : null}
        <Textarea
          autoComplete="off"
          autosize
          label="Sentences"
          minRows={8}
          name="manualText"
          onChange={event => onManualTextChange(event.currentTarget.value)}
          placeholder="Enter one sentence per line…"
          value={manualText}
        />
        <Button
          color="green"
          disabled={working || !manualText.trim()}
          leftSection={<TbFileText aria-hidden="true" size={16} />}
          onClick={onImport}
        >
          {working ? "Importing..." : "Import Sentences"}
        </Button>
      </Stack>
    </PaperPanel>
  );
}
