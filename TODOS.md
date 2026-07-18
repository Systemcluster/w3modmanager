# TODOs

## Features

- Profiles
- Typing jump to mod
- confirm for bin only mods
- Cache per-file merge results so uninstalling a mod does not re-invoke user
  interaction for conflicts the user has already resolved. User interaction is by
  far the highest cost in the merge pipeline and dominates every other trade-off.

  Design:
  - Key: `(file_path, base_hash, sorted set of (mod_id, mod_file_hash) for contributing mods)`.
  - Value: the **post-resolution** file (i.e. after the user resolved conflicts in
    the merger UI), not the raw merger output. Store alongside the resolution
    decisions if useful for debugging.
  - Uninstall of mod M for file F:
    1. Look up cache for the remaining-mods subset of F.
       Hit → write the cached file. Zero interaction, no merge computed.
    2. Miss → **regional fallback**, not a fresh `merge_many`:
       - For every region where M's diff against `base` does not overlap the
         current merged file, keep the merged file byte-identical (preserves all
         other resolutions).
       - For regions where M contributed, subtract M's contribution using the
         other enabled mods' diffs at that region:
         * If another enabled mod produces the same edit → keep it.
         * If M was the sole contributor → revert to `base`.
         * If the region is a conflict block containing M's side → strip M's side;
           if the remaining sides still disagree, re-prompt only for that region.
       - Cache the result under the new key.
  - Fresh `merge_many` is only appropriate on initial install of a new mod set,
    where there are no prior resolutions to preserve.
  - Invalidation: entries keyed on file hashes, so any mod update naturally
    produces a new key; old entries can be GC'd by "no live key references them".

  This also removes the need for a local `unmerge` primitive, which cannot
  distinguish a change unique to the uninstalling mod from a change shared with
  another installed mod without provenance, and would silently drop the shared
  case.
