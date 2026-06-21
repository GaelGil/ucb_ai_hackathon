import { Badge, Box, Divider, Group, Stack, Text } from "@mantine/core";

import { CompactPanel } from "@/components/ui/CompactPanel";
import { jobWarnings, statusColor } from "@/lib/format";
import type { Job } from "@/types/domain";

export function JobsPanel({ jobs }: { jobs: Job[] }) {
  const visibleJobs = jobs.slice(0, 3);
  return (
    <CompactPanel title="Recent Jobs" eyebrow="Last 3 runs">
      {visibleJobs.length === 0 ? (
        <Text c="dimmed" size="sm">
          No recent jobs.
        </Text>
      ) : (
        <Stack gap="xs">
          {visibleJobs.map((job, index) => {
          const warnings = jobWarnings(job);
          const usedFallback = job.metadata["used_fallback"] === true || warnings.length > 0;

          return (
            <Box key={job.id}>
              {index > 0 ? <Divider mb="xs" /> : null}
              <Stack gap={4}>
                <Group justify="space-between" wrap="nowrap">
                  <Box miw={0}>
                    <Text fw={700} size="sm" truncate="end">
                      {job.type}
                    </Text>
                    <Text c="dimmed" size="xs" truncate="end">
                      {job.message || job.id}
                    </Text>
                  </Box>
                  <Badge color={statusColor(job.status)} radius="sm" variant="dot" style={{ flexShrink: 0 }}>
                    {job.status}
                  </Badge>
                </Group>
                {usedFallback ? (
                  <Badge color="yellow" radius="sm" variant="light" w="fit-content">
                    Demo fallback
                  </Badge>
                ) : null}
                {warnings.slice(0, 1).map(warning => (
                  <Text key={`${job.id}-${warning.provider}-${warning.stage}`} c="dimmed" size="xs">
                    {warning.provider}: {warning.message}
                  </Text>
                ))}
              </Stack>
            </Box>
          );
        })}
        </Stack>
      )}
    </CompactPanel>
  );
}
