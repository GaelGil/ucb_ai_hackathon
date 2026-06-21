import { Badge, Box, Button, Group, Select, Stack, Text } from "@mantine/core";

import { CompactPanel } from "@/components/ui/CompactPanel";
import type { DetailContent, ResearchArtifact, ResearchType } from "@/types/domain";

export function ResearchPanel({
  activeType,
  research,
  working,
  onOpenDetail,
  onResearch,
  onRefreshResearch,
  onTypeChange,
}: {
  activeType: ResearchType;
  research: ResearchArtifact | null;
  working: boolean;
  onOpenDetail: (detail: DetailContent) => void;
  onResearch: () => void;
  onRefreshResearch: () => void;
  onTypeChange: (type: ResearchType) => void;
}) {
  const title = activeType === "pos" ? "POS research" : "Translation research";
  return (
    <CompactPanel title="Cached Research Notes" eyebrow="Dataset + language + task">
      <Stack gap="sm">
        <Group align="end" gap="xs" wrap="wrap">
          <Select
            data={[
              { value: "pos", label: "POS" },
              { value: "translation", label: "Translation" },
            ]}
            label="Research type"
            name="researchType"
            onChange={value => onTypeChange((value as ResearchType | null) ?? "pos")}
            value={activeType}
            w={180}
          />
          <Button disabled={working} onClick={onResearch}>
            {research ? `Use Cached ${title}` : `Run ${title}`}
          </Button>
          <Button color="green" disabled={working} onClick={onRefreshResearch} variant="light">
            Refresh
          </Button>
        </Group>
        {research ? (
          <>
            <Group gap="xs">
              <Badge color="violet" radius="sm" variant="light">
                {research.guidelines.length} Guidelines
              </Badge>
              <Badge color="gray" radius="sm" variant="light">
                {research.sources.length} Sources
              </Badge>
              {research.warnings.length > 0 ? (
                <Badge color="yellow" radius="sm" variant="light">
                  {research.warnings.length} Warnings
                </Badge>
              ) : null}
            </Group>
            <Text lineClamp={2} size="sm" style={{ overflowWrap: "anywhere" }}>
              {research.summary}
            </Text>
            <Button
              color="violet"
              onClick={() =>
                onOpenDetail({
                  title,
                  rows: [
                    { label: "Summary", value: research.summary },
                    { label: "Guidelines", value: research.guidelines.join("\n") || "No guidelines" },
                    {
                      label: "Sources",
                      value:
                        research.sources.map(source => `${source.title}\n${source.url}\n${source.excerpt}`).join("\n\n") ||
                        "No sources",
                    },
                    {
                      label: "Warnings",
                      value:
                        research.warnings
                          .map(warning => `${warning.provider} ${warning.stage}: ${warning.message}`)
                          .join("\n") || "No warnings",
                    },
                  ],
                })
              }
              size="compact-sm"
              variant="light"
              w="fit-content"
            >
              View Details
            </Button>
          </>
        ) : (
          <Text c="dimmed" size="sm">
            {title} has not been generated for this workspace yet.
          </Text>
        )}
      </Stack>
    </CompactPanel>
  );
}
