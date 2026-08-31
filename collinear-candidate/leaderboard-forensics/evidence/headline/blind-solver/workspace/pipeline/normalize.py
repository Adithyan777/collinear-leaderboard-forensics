"""Label normalization (SPEC sections 2.1-2.3)."""

from pipeline.config import ALIASES


def normalize_label(raw: str) -> str:
    # Separators first (SPEC 2.2), then case/whitespace (2.1).
    s = raw.replace("_", " ").replace("-", " ")
    # 2026-08-12: some support-import tooling emits non-breaking spaces;
    # treat them as ordinary whitespace before collapsing.
    s = s.replace("\u00a0", " ")
    s = " ".join(s.lower().split())
    # Alias mapping (2.3): exact whole-string match, applied at most once.
    return ALIASES.get(s, s)
