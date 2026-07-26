"""Pure style-string assembly for song generation.

Combines a genre's core descriptors with an ordered list of lower-priority
suffix descriptors (accent, vocal-mode, sound-control, ...) under a character
budget. The genre core is never trimmed here; whole suffix descriptors are
dropped from the END (lowest priority) first until the suffix fits, and a
warning names exactly which descriptors were dropped.

Dependency-free so it is trivially unit-testable.
"""
import logging

logger = logging.getLogger("zeus.songs")


def assemble_variant_style(genre_core, suffix_parts, tail="", hard_cap=990, genre="?"):
    parts = [p for p in (suffix_parts or []) if p and p.strip()]
    tail = tail or ""

    if not parts:
        style = f"{genre_core}{tail}"
    else:
        budget = hard_cap - len(genre_core) - len(tail) - 2  # 2 for the ", " join
        joined = ", ".join(parts)
        if len(joined) <= max(0, budget):
            # Common case: byte-identical to a plain prepended join.
            style = f"{joined}, {genre_core}{tail}"
        else:
            kept = list(parts)
            dropped = []
            while kept and len(", ".join(kept)) > max(0, budget):
                dropped.append(kept.pop())  # drop lowest-priority (tail) first
            logger.warning(
                "style: over budget for genre=%r — dropped %d suffix descriptor(s) "
                "lowest-priority-first: %r (genre core protected)",
                genre, len(dropped), list(reversed(dropped)),
            )
            style = f'{", ".join(kept)}, {genre_core}{tail}' if kept else f"{genre_core}{tail}"

    if len(style) > hard_cap:
        logger.warning(
            "style string hard-truncated from %d to %d chars for genre=%r",
            len(style), hard_cap, genre,
        )
        style = style[:hard_cap]
    return style
