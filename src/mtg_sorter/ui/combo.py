"""Shared QComboBox sizing for native Windows style.

Under the Qt Windows style, combos in tight or nested layouts can collapse to
near-zero width (seen in Browse → Customize). Prefer this helper over relying
on ``AdjustToContents`` alone, and avoid nesting a combo's QGroupBox inside
another QGroupBox.
"""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox

# Short toolbar / form fields (filter, theme, export format, …).
DEFAULT_COMBO_CONTENTS_LENGTH = 12
# Searchable pickers with long deck/card names.
SEARCHABLE_COMBO_CONTENTS_LENGTH = 24
# Edition codes ("C21 — Commander 2021").
EDITION_COMBO_CONTENTS_LENGTH = 16


def configure_data_combo(
    combo: QComboBox,
    *,
    min_contents: int = DEFAULT_COMBO_CONTENTS_LENGTH,
) -> QComboBox:
    """Give ``combo`` a stable minimum width based on character cells."""
    combo.setSizeAdjustPolicy(
        QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
    )
    combo.setMinimumContentsLength(min_contents)
    return combo
