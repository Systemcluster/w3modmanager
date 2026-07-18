"""3-way text merge for Witcher 3 script/XML mod files.

Provides the text-merging algorithm that replaces the KDiff3 dependency
of `Witcher Script Merger`. Compares two modified versions against a common
base, produces a merged result, and marks unresolvable overlaps with
git-style conflict markers.

Public API:
    - `merge(base, mod1, mod2)`  3-way merge of two mods against base.
    - `merge_many(base, *mods)`  iterative N-way merge (mod1, mod2, ...).
    - `merge_with_result(base, *mods)`  N-way merge with structured conflicts.
    - `find_conflicts(text)`     conflict regions produced by `merge`.
    - `has_conflicts(text)`      true if `text` contains complete conflict
                                 regions produced by `merge`.

Notes:
    - Input is split by lines; CRLF and LF are treated equivalently and
      output is LF-terminated (mirroring how the game engine reads files).
    - Trailing newlines are preserved when any input had one.
    - Conflict markers are the same three tokens git uses.
    - To uninstall a mod, recompute `merge_many(base, *remaining_mods)` only
      when no cached post-resolution output exists for that remaining mod set.
      A local "unmerge" primitive is intentionally not provided: without
      per-line provenance a change appearing in both the removed mod and
      the merged result is indistinguishable from a change shared with
      another installed mod, so any such primitive would risk silently
      dropping another mod's contribution.
"""

import difflib

from dataclasses import dataclass


CONFLICT_START = '<<<<<<<'
CONFLICT_MID = '======='
CONFLICT_END = '>>>>>>>'


@dataclass(frozen=True)
class ConflictRegion:
    """One complete conflict marker block in merged output.

    Line numbers are 1-based so callers can pass them directly to UI surfaces.
    """

    start_line: int
    mid_line: int
    end_line: int
    mod1_lines: tuple[str, ...]
    mod2_lines: tuple[str, ...]


@dataclass(frozen=True)
class MergeResult:
    """Merged text plus complete conflict regions found in that text."""

    text: str
    conflicts: tuple[ConflictRegion, ...]

    @property
    def has_conflicts(self) -> bool:
        return bool(self.conflicts)


def _get_edits(
    base_lines: list[str], mod_lines: list[str]
) -> list[tuple[int, int, list[str]]]:
    """Return non-equal diff operations as (base_start, base_end, replacement_lines) triples."""
    sm = difflib.SequenceMatcher(None, base_lines, mod_lines, autojunk=False)
    return [
        (i1, i2, mod_lines[j1:j2])
        for tag, i1, i2, j1, j2 in sm.get_opcodes()
        if tag != 'equal'
    ]


def _reconstruct(
    base: list[str], start: int, end: int, edits: list[tuple[int, int, list[str]]]
) -> list[str]:
    """Reconstruct what one branch produces for base[start:end] given its edits."""
    result: list[str] = []
    pos = start
    for es, ee, elines in edits:
        result.extend(base[pos:es])
        result.extend(elines)
        pos = ee
    result.extend(base[pos:end])
    return result


def _merge_lines(base: list[str], mod1: list[str], mod2: list[str]) -> list[str]:
    edits_a = _get_edits(base, mod1)
    edits_b = _get_edits(base, mod2)

    result: list[str] = []
    ia = 0
    ib = 0
    base_pos = 0
    n = len(base)

    while ia < len(edits_a) or ib < len(edits_b):
        ea_s, ea_e, ea_lines = edits_a[ia] if ia < len(edits_a) else (n + 1, n + 1, [])
        eb_s, eb_e, eb_lines = edits_b[ib] if ib < len(edits_b) else (n + 1, n + 1, [])

        next_pos = min(ea_s, eb_s)
        result.extend(base[base_pos:next_pos])
        base_pos = next_pos

        a_here = ia < len(edits_a) and ea_s == base_pos
        b_here = ib < len(edits_b) and eb_s == base_pos

        if a_here and not b_here and (ib >= len(edits_b) or eb_s >= ea_e):
            result.extend(ea_lines)
            base_pos = ea_e
            ia += 1

        elif b_here and not a_here and (ia >= len(edits_a) or ea_s >= eb_e):
            result.extend(eb_lines)
            base_pos = eb_e
            ib += 1

        else:
            # Both edits start at base_pos, or one edit's range contains the other's start.
            # If one is a pure insert and the other modifies content, the insert goes first.
            if ea_e == base_pos and eb_e > base_pos:
                result.extend(ea_lines)
                ia += 1
                continue

            if eb_e == base_pos and ea_e > base_pos:
                result.extend(eb_lines)
                ib += 1
                continue

            # Both are pure inserts at the same position: apply both (mod1 first),
            # or once if they are identical. Pure inserts don't remove base content
            # so there is no ordering conflict -- only a potential duplication.
            if ea_e == base_pos and eb_e == base_pos:
                result.extend(ea_lines)
                if ea_lines != eb_lines:
                    result.extend(eb_lines)
                ia += 1
                ib += 1
                continue
            # Expand the conflict region to cover all edits that overlap it.
            conflict_end = max(ea_e, eb_e)
            ia_end = ia + 1
            ib_end = ib + 1

            changed = True
            while changed:
                changed = False
                while ia_end < len(edits_a) and edits_a[ia_end][0] < conflict_end:
                    conflict_end = max(conflict_end, edits_a[ia_end][1])
                    ia_end += 1
                    changed = True
                while ib_end < len(edits_b) and edits_b[ib_end][0] < conflict_end:
                    conflict_end = max(conflict_end, edits_b[ib_end][1])
                    ib_end += 1
                    changed = True

            a_version = _reconstruct(base, base_pos, conflict_end, edits_a[ia:ia_end])
            b_version = _reconstruct(base, base_pos, conflict_end, edits_b[ib:ib_end])

            if a_version == b_version:
                result.extend(a_version)
            else:
                result.append(CONFLICT_START)
                result.extend(a_version)
                result.append(CONFLICT_MID)
                result.extend(b_version)
                result.append(CONFLICT_END)

            base_pos = conflict_end
            ia = ia_end
            ib = ib_end

    result.extend(base[base_pos:])
    return result


def merge(base: str, mod1: str, mod2: str) -> str:
    """3-way merge of base, mod1, and mod2.

    Returns merged content with changes from both mods applied.
    Conflicting changes are marked with CONFLICT_START / CONFLICT_MID / CONFLICT_END markers.
    A trailing newline is preserved if any input had one.
    """
    result = '\n'.join(_merge_lines(base.splitlines(), mod1.splitlines(), mod2.splitlines()))
    if base.endswith('\n') or mod1.endswith('\n') or mod2.endswith('\n'):
        result += '\n'
    return result


def merge_many(base: str, *mods: str) -> str:
    """Iteratively 3-way merge any number of mod versions against `base`.

    Equivalent to `reduce(lambda acc, m: merge(base, acc, m), mods, base)`.
    Mods are applied in order -- the first mod takes precedence in same-position
    pure inserts, and unresolved conflict markers from earlier merges propagate
    into later ones (matching `Witcher Script Merger`'s iterative behaviour).

    Returns `base` unchanged if no mods are supplied, or the sole mod if one
    is supplied.
    """
    if not mods:
        return base
    result = mods[0]
    for mod in mods[1:]:
        result = merge(base, result, mod)
    return result


def merge_with_result(base: str, *mods: str) -> MergeResult:
    """Merge any number of mods and return text plus structured conflicts."""
    text = merge_many(base, *mods)
    return MergeResult(text=text, conflicts=find_conflicts(text))


def find_conflicts(text: str) -> tuple[ConflictRegion, ...]:
    """Return complete conflict marker regions produced by `merge`.

    Markers must occupy whole lines and appear in start/mid/end order. This
    avoids treating comments or malformed partial marker text as merge conflicts.
    """
    lines = text.splitlines()
    conflicts: list[ConflictRegion] = []
    pos = 0

    while pos < len(lines):
        if lines[pos] != CONFLICT_START:
            pos += 1
            continue

        mid = pos + 1
        while mid < len(lines) and lines[mid] != CONFLICT_MID:
            mid += 1
        if mid >= len(lines):
            pos += 1
            continue

        end = mid + 1
        while end < len(lines) and lines[end] != CONFLICT_END:
            end += 1
        if end >= len(lines):
            pos += 1
            continue

        conflicts.append(ConflictRegion(
            start_line=pos + 1,
            mid_line=mid + 1,
            end_line=end + 1,
            mod1_lines=tuple(lines[pos + 1:mid]),
            mod2_lines=tuple(lines[mid + 1:end]),
        ))
        pos = end + 1

    return tuple(conflicts)


def has_conflicts(text: str) -> bool:
    """Return True if `text` contains unresolved conflict regions from `merge`.

    Callers use this to decide whether a merge result is safe to write out
automatically or needs manual resolution.
    """
    return bool(find_conflicts(text))
