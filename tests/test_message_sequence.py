from __future__ import annotations

import pytest

from app.modules.messages.service import next_sequence_for_channel


@pytest.mark.parametrize(
    ("existing_sequences", "expected"),
    [([], 1), ([10, 12, 14], 15), ([100, 101, 102], 103)],
)
def test_next_sequence_for_channel(existing_sequences: list[int], expected: int) -> None:
    assert next_sequence_for_channel(existing_sequences) == expected
