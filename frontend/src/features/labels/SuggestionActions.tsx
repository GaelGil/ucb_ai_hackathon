import { Button, Group } from "@mantine/core";

import type { Suggestion, SuggestionStatus } from "@/types/domain";

export function SuggestionActions({
  suggestion,
  working,
  onReview,
}: {
  suggestion: Suggestion;
  working: boolean;
  onReview: (suggestion: Suggestion, action: SuggestionStatus) => void;
}) {
  return (
    <Group gap="xs">
      <Button color="green" disabled={working} onClick={() => onReview(suggestion, "accepted")} size="compact-xs">
        Approve
      </Button>
      <Button
        color="violet"
        disabled={working}
        onClick={() => onReview(suggestion, "updated")}
        size="compact-xs"
        variant="light"
      >
        Save Edit
      </Button>
      <Button color="red" disabled={working} onClick={() => onReview(suggestion, "denied")} size="compact-xs" variant="light">
        Deny
      </Button>
    </Group>
  );
}
