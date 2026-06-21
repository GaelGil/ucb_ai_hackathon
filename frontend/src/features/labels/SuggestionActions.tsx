import { Button, Group } from "@mantine/core";
import { TbCheck, TbPencil, TbX } from "react-icons/tb";

import type { Suggestion, SuggestionStatus } from "@/types/domain";

const ICON_SIZE = 15;

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
      <Button
        aria-label="Approve suggestion"
        color="teal"
        disabled={working}
        leftSection={<TbCheck aria-hidden="true" size={ICON_SIZE} />}
        onClick={() => onReview(suggestion, "accepted")}
        radius="md"
        size="xs"
        variant="light"
      >
        Approve
      </Button>
      <Button
        aria-label="Save edited suggestion"
        color="violet"
        disabled={working}
        leftSection={<TbPencil aria-hidden="true" size={ICON_SIZE} />}
        onClick={() => onReview(suggestion, "updated")}
        radius="md"
        size="xs"
        variant="filled"
      >
        Save Edit
      </Button>
      <Button
        aria-label="Deny suggestion"
        color="red"
        disabled={working}
        leftSection={<TbX aria-hidden="true" size={ICON_SIZE} />}
        onClick={() => onReview(suggestion, "denied")}
        radius="md"
        size="xs"
        variant="light"
      >
        Deny
      </Button>
    </Group>
  );
}
