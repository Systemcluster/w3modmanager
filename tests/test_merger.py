"""
Test cases for 3-way text merger (merger2)
"""

from w3modmanager.domain.bin.merger2 import (
    CONFLICT_END,
    CONFLICT_MID,
    CONFLICT_START,
    MergeContributor,
    MergeResolutionCache,
    find_conflicts,
    find_script_scope,
    find_script_scopes,
    has_conflicts,
    merge,
    merge_contributors,
    merge_many,
    merge_with_result,
)

import pytest


# ---------------------------------------------------------------------------
# merge — non-conflicting cases
# ---------------------------------------------------------------------------

def test_merge_identical_inputs() -> None:
    base = 'a\nb\nc'
    assert merge(base, base, base) == base


def test_merge_only_mod1_changes() -> None:
    assert merge('a\nb\nc', 'a\nX\nc', 'a\nb\nc') == 'a\nX\nc'


def test_merge_only_mod2_changes() -> None:
    assert merge('a\nb\nc', 'a\nb\nc', 'a\nX\nc') == 'a\nX\nc'


def test_merge_non_overlapping_changes() -> None:
    # mod1 changes first line, mod2 changes last — both applied
    assert merge('a\nb\nc\nd', 'a\nX\nc\nd', 'a\nb\nc\nY') == 'a\nX\nc\nY'


def test_merge_identical_change_applied_once() -> None:
    assert merge('a\nb\nc', 'a\nX\nc', 'a\nX\nc') == 'a\nX\nc'


def test_merge_mod1_inserts_line() -> None:
    assert merge('a\nb\nc', 'a\nNEW\nb\nc', 'a\nb\nc') == 'a\nNEW\nb\nc'


def test_merge_mod2_inserts_line() -> None:
    assert merge('a\nb\nc', 'a\nb\nc', 'a\nNEW\nb\nc') == 'a\nNEW\nb\nc'


def test_merge_mod1_deletes_line() -> None:
    assert merge('a\nb\nc', 'a\nc', 'a\nb\nc') == 'a\nc'


def test_merge_mod2_deletes_line() -> None:
    assert merge('a\nb\nc', 'a\nb\nc', 'a\nc') == 'a\nc'


def test_merge_both_delete_same_line() -> None:
    assert merge('a\nb\nc', 'a\nc', 'a\nc') == 'a\nc'


def test_merge_insert_before_modification() -> None:
    # mod1 inserts NEW before b; mod2 replaces b with X — both applied
    assert merge('a\nb\nc', 'a\nNEW\nb\nc', 'a\nX\nc') == 'a\nNEW\nX\nc'


def test_merge_modification_before_insert() -> None:
    # mod2 inserts NEW before b; mod1 replaces b with X — insert emitted first
    assert merge('a\nb\nc', 'a\nX\nc', 'a\nNEW\nb\nc') == 'a\nNEW\nX\nc'


# ---------------------------------------------------------------------------
# merge — same-position pure inserts
# ---------------------------------------------------------------------------

def test_merge_both_insert_same_content() -> None:
    # Identical inserts at the same position applied once
    assert merge('a\nb', 'a\nb\nX', 'a\nb\nX') == 'a\nb\nX'


def test_merge_both_insert_different_content() -> None:
    # Different inserts at the same position: mod1 first, mod2 second
    assert merge('a\nb', 'a\nb\nX', 'a\nb\nY') == 'a\nb\nX\nY'


def test_merge_both_append_functions() -> None:
    # Typical WitcherScript case: both mods add new functions at end of file
    base = 'class Foo {\n  var x : int;\n}\n'
    mod1 = base + 'function Bar() {}\n'
    mod2 = base + 'function Baz() {}\n'
    assert merge(base, mod1, mod2) == base + 'function Bar() {}\nfunction Baz() {}\n'


# ---------------------------------------------------------------------------
# merge — conflict cases
# ---------------------------------------------------------------------------

def test_merge_conflict_produces_markers() -> None:
    result = merge('a\nb\nc', 'a\nX\nc', 'a\nY\nc')
    assert CONFLICT_START in result
    assert CONFLICT_MID in result
    assert CONFLICT_END in result


def test_merge_conflict_contains_both_versions() -> None:
    result = merge('a\nb\nc', 'a\nX\nc', 'a\nY\nc')
    assert 'X' in result
    assert 'Y' in result


def test_merge_conflict_preserves_surrounding_content() -> None:
    result = merge('a\nb\nc', 'a\nX\nc', 'a\nY\nc')
    lines = result.splitlines()
    assert lines[0] == 'a'
    assert lines[-1] == 'c'


def test_merge_conflict_mod1_is_first() -> None:
    result = merge('a\nb\nc', 'a\nX\nc', 'a\nY\nc')
    lines = result.splitlines()
    start = lines.index(CONFLICT_START)
    mid = lines.index(CONFLICT_MID)
    assert 'X' in lines[start:mid]
    assert 'Y' not in lines[start:mid]


def test_merge_conflict_delete_vs_replace() -> None:
    # mod1 deletes b, mod2 replaces b with Y — conflict
    result = merge('a\nb\nc', 'a\nc', 'a\nY\nc')
    assert CONFLICT_START in result
    assert 'Y' in result


def test_merge_conflict_overlapping_ranges() -> None:
    # mod1 changes lines 1-2, mod2 changes lines 0-2 — full overlap is a conflict
    base = 'a\nb\nc\nd'
    mod1 = 'a\nX\nY\nd'
    mod2 = 'P\nQ\nR\nd'
    result = merge(base, mod1, mod2)
    assert CONFLICT_START in result
    assert 'd' in result


# ---------------------------------------------------------------------------
# merge — trailing newline handling
# ---------------------------------------------------------------------------

def test_merge_trailing_newline_preserved_from_base() -> None:
    base = 'a\nb\n'
    mod1 = 'a\nX\n'
    assert merge(base, mod1, base).endswith('\n')


def test_merge_trailing_newline_not_added_when_absent() -> None:
    assert not merge('a\nb', 'a\nX', 'a\nb').endswith('\n')


def test_merge_trailing_newline_preserved_through_mod_addition() -> None:
    base = 'func A() {}\n'
    mod1 = base + 'func B() {}\n'
    assert merge(base, mod1, base) == mod1


# ---------------------------------------------------------------------------
# Real-world WitcherScript patterns
# ---------------------------------------------------------------------------

# Realistic snippet modelled after r4Player.ws — the most commonly conflicted
# file in the Witcher 3 modding community.
_WS_BASE = '''\
class CR4Player extends CNewNPC
{
\tvar fFOV : float;
\tvar bDodgePressed : bool;

\tfunction OnSpawn(template : CEntityTemplate) : bool
\t{
\t\treturn super.OnSpawn(template);
\t}

\tfunction GetCurrentSpeed() : float
\t{
\t\treturn 5.0;
\t}
}
'''

# modFOVTweak: changes fFOV initialisation and overrides GetCurrentSpeed
_WS_MOD1 = '''\
class CR4Player extends CNewNPC
{
\tvar fFOV : float;
\tvar bDodgePressed : bool;

\tfunction OnSpawn(template : CEntityTemplate) : bool
\t{
\t\tfFOV = 80.0;
\t\treturn super.OnSpawn(template);
\t}

\tfunction GetCurrentSpeed() : float
\t{
\t\treturn 7.0;
\t}
}
'''

# modExtraAbility: adds a new function, does not touch existing ones
_WS_MOD2 = '''\
class CR4Player extends CNewNPC
{
\tvar fFOV : float;
\tvar bDodgePressed : bool;

\tfunction OnSpawn(template : CEntityTemplate) : bool
\t{
\t\treturn super.OnSpawn(template);
\t}

\tfunction GetCurrentSpeed() : float
\t{
\t\treturn 5.0;
\t}

\tfunction HasExtraAbility() : bool
\t{
\t\treturn true;
\t}
}
'''

# modAlsoSpeed: independently raises the same return value — conflict with mod1
_WS_MOD3_CONFLICT = '''\
class CR4Player extends CNewNPC
{
\tvar fFOV : float;
\tvar bDodgePressed : bool;

\tfunction OnSpawn(template : CEntityTemplate) : bool
\t{
\t\treturn super.OnSpawn(template);
\t}

\tfunction GetCurrentSpeed() : float
\t{
\t\treturn 6.0;
\t}
}
'''


def test_ws_non_conflicting_mods_are_auto_merged() -> None:
    """Mod 1 modifies OnSpawn/GetCurrentSpeed; mod 2 adds a new function.
    No overlap — should auto-merge to contain all changes from both."""
    result = merge(_WS_BASE, _WS_MOD1, _WS_MOD2)
    assert CONFLICT_START not in result
    # mod1's changes preserved
    assert 'fFOV = 80.0;' in result
    assert 'return 7.0;' in result
    # mod2's addition preserved
    assert 'HasExtraAbility' in result


def test_ws_conflicting_mods_produce_markers() -> None:
    """Both mods change GetCurrentSpeed to different values — real conflict."""
    result = merge(_WS_BASE, _WS_MOD1, _WS_MOD3_CONFLICT)
    assert CONFLICT_START in result
    assert 'return 7.0;' in result
    assert 'return 6.0;' in result
    # Surrounding structure is intact
    assert 'CR4Player extends CNewNPC' in result
    assert 'OnSpawn' in result


def test_ws_three_mod_iterative_merge() -> None:
    """Script Merger merges 3+ mods iteratively: merge(A,B) then merge(result,C).
    All three independent changes must appear in the final output."""
    # mod3 adds yet another independent function
    mod3 = _WS_BASE.rstrip('\n') + '\n\nfunction ExtraC() {}\n'

    step1 = merge(_WS_BASE, _WS_MOD1, _WS_MOD2)
    step2 = merge(_WS_BASE, step1, mod3)

    assert CONFLICT_START not in step2
    assert 'fFOV = 80.0;' in step2      # from mod1
    assert 'HasExtraAbility' in step2   # from mod2
    assert 'ExtraC' in step2            # from mod3


# ---------------------------------------------------------------------------
# CRLF line-ending normalization
# ---------------------------------------------------------------------------

def test_crlf_input_is_normalized_to_lf() -> None:
    """readText() may return CRLF strings on Windows game files.
    splitlines() strips the \\r, so output is always LF-terminated."""
    base = 'a\r\nb\r\nc\r\n'
    mod1 = 'a\r\nX\r\nc\r\n'
    result = merge(base, mod1, base)
    assert '\r' not in result
    assert result == 'a\nX\nc\n'


def test_crlf_mixed_with_lf_does_not_conflict() -> None:
    """CRLF and LF variants of the same content are treated as equal
    after splitlines() normalisation, so no spurious conflict is raised."""
    base = 'a\nb\nc'
    mod1_crlf = 'a\r\nb\r\nc'   # same content, CRLF
    result = merge(base, mod1_crlf, base)
    assert CONFLICT_START not in result


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_merge_empty_base() -> None:
    """Both mods add different content to an empty base file.
    Since both are inserts at position 0, they are auto-merged (mod1 first)."""
    result = merge('', 'line1\nline2', 'lineA\nlineB')
    assert 'line1' in result
    assert 'lineA' in result
    assert CONFLICT_START not in result


def test_merge_mod1_reverts_to_base() -> None:
    """If mod1 is identical to base, merge should just return mod2."""
    base = 'a\nb\nc'
    mod2 = 'a\nX\nc'
    assert merge(base, base, mod2) == mod2


def test_merge_mod2_reverts_to_base() -> None:
    """If mod2 is identical to base, merge should just return mod1."""
    base = 'a\nb\nc'
    mod1 = 'a\nX\nc'
    assert merge(base, mod1, base) == mod1


def test_whitespace_only_change_conflicts_with_content_change() -> None:
    """A mod that only reformats (adds indentation) will conflict with a mod
    that changes the same line's content — known limitation, no whitespace
    normalisation is performed."""
    base = 'function foo() {\nreturn 1;\n}'
    reformatted = 'function foo() {\n  return 1;\n}'   # mod1 just re-indents
    changed = 'function foo() {\nreturn 2;\n}'          # mod2 changes value
    result = merge(base, reformatted, changed)
    assert CONFLICT_START in result


# ---------------------------------------------------------------------------
# has_conflicts
# ---------------------------------------------------------------------------

def test_has_conflicts_true_on_conflict_output() -> None:
    result = merge('a\nb\nc', 'a\nX\nc', 'a\nY\nc')
    assert has_conflicts(result) is True


def test_has_conflicts_false_on_clean_merge() -> None:
    result = merge('a\nb\nc', 'a\nX\nc', 'a\nb\nc')
    assert has_conflicts(result) is False


def test_has_conflicts_false_on_empty_input() -> None:
    assert has_conflicts('') is False


def test_has_conflicts_requires_all_three_markers() -> None:
    # A file that legitimately contains only one of the marker strings
    # (e.g. a comment with '=======') should not be reported as conflicted.
    assert has_conflicts('// ======= section divider =======\n') is False


def test_has_conflicts_requires_ordered_marker_lines() -> None:
    text = '<<<<<<< mentioned in prose\n=======\n>>>>>>>\n'
    assert has_conflicts(text) is False


def test_has_conflicts_rejects_incomplete_marker_block() -> None:
    text = f'{CONFLICT_START}\nleft\n{CONFLICT_MID}\nright\n'
    assert has_conflicts(text) is False



# ---------------------------------------------------------------------------
# structured conflict results
# ---------------------------------------------------------------------------

def test_find_conflicts_returns_conflict_regions() -> None:
    result = merge('a\nb\nc', 'a\nX\nc', 'a\nY\nc')
    conflicts = find_conflicts(result)

    assert len(conflicts) == 1
    assert conflicts[0].start_line == 2
    assert conflicts[0].mid_line == 4
    assert conflicts[0].end_line == 6
    assert conflicts[0].mod1_lines == ('X',)
    assert conflicts[0].mod2_lines == ('Y',)


def test_merge_with_result_reports_clean_merge() -> None:
    result = merge_with_result('a\nb\nc', 'a\nX\nc', 'a\nb\nY')
    assert result.text == 'a\nX\nY'
    assert result.conflicts == ()
    assert result.has_conflicts is False


def test_merge_with_result_reports_conflicts() -> None:
    result = merge_with_result('a\nb\nc', 'a\nX\nc', 'a\nY\nc')
    assert result.has_conflicts is True
    assert len(result.conflicts) == 1
    assert result.conflicts[0].mod1_lines == ('X',)
    assert result.conflicts[0].mod2_lines == ('Y',)


# ---------------------------------------------------------------------------
# WitcherScript structure metadata
# ---------------------------------------------------------------------------

def test_find_script_scopes_detects_classes_and_functions() -> None:
    scopes = find_script_scopes(_WS_BASE)
    assert ('class', 'CR4Player') in [(scope.kind, scope.name) for scope in scopes]
    assert ('function', 'OnSpawn') in [(scope.kind, scope.name) for scope in scopes]
    assert ('function', 'GetCurrentSpeed') in [(scope.kind, scope.name) for scope in scopes]


def test_find_script_scope_returns_innermost_scope() -> None:
    line = _WS_BASE.splitlines().index('\t\treturn 5.0;') + 1
    scope = find_script_scope(_WS_BASE, line)
    assert scope is not None
    assert scope.kind == 'function'
    assert scope.name == 'GetCurrentSpeed'


def test_ws_conflict_reports_function_scope() -> None:
    result = merge_with_result(_WS_BASE, _WS_MOD1, _WS_MOD3_CONFLICT)
    assert len(result.conflicts) == 1
    assert result.conflicts[0].scope is not None
    assert result.conflicts[0].scope.kind == 'function'
    assert result.conflicts[0].scope.name == 'GetCurrentSpeed'


# ---------------------------------------------------------------------------
# named contributor merge metadata
# ---------------------------------------------------------------------------

def test_merge_contributors_records_ordered_contributors() -> None:
    result = merge_contributors(
        'a\nb',
        MergeContributor('modA', 'a\nb\nA', 'hash-a'),
        MergeContributor('modB', 'a\nb\nB', 'hash-b'),
        file_path='content/scripts/foo.ws',
        base_hash='base-hash',
    )
    assert result.text == 'a\nb\nA\nB'
    assert result.contributors == ('modA', 'modB')
    assert result.cache_key is not None
    assert result.cache_key.file_path == 'content/scripts/foo.ws'
    assert result.cache_key.base_hash == 'base-hash'
    assert result.cache_key.contributors == (('modA', 'hash-a'), ('modB', 'hash-b'))


def test_merge_contributors_cache_key_is_order_sensitive() -> None:
    first = merge_contributors(
        'a\nb',
        MergeContributor('modA', 'a\nb\nA', 'hash-a'),
        MergeContributor('modB', 'a\nb\nB', 'hash-b'),
    )
    second = merge_contributors(
        'a\nb',
        MergeContributor('modB', 'a\nb\nB', 'hash-b'),
        MergeContributor('modA', 'a\nb\nA', 'hash-a'),
    )
    assert first.text != second.text
    assert first.cache_key != second.cache_key


def test_resolution_cache_stores_clean_merge_result() -> None:
    result = merge_contributors(
        'a\nb',
        MergeContributor('modA', 'a\nb\nA', 'hash-a'),
    )
    cache = MergeResolutionCache()

    resolution = cache.put_result(result)

    assert result.cache_key is not None
    assert resolution.text == result.text
    assert cache.get(result.cache_key) == resolution


def test_resolution_cache_rejects_unresolved_conflict_output() -> None:
    result = merge_contributors(
        'a\nb\nc',
        MergeContributor('modA', 'a\nX\nc', 'hash-a'),
        MergeContributor('modB', 'a\nY\nc', 'hash-b'),
    )
    cache = MergeResolutionCache()

    with pytest.raises(ValueError, match='Conflicting merge result requires resolved text'):
        cache.put_result(result)


def test_resolution_cache_accepts_resolved_conflict_output() -> None:
    result = merge_contributors(
        'a\nb\nc',
        MergeContributor('modA', 'a\nX\nc', 'hash-a'),
        MergeContributor('modB', 'a\nY\nc', 'hash-b'),
    )
    cache = MergeResolutionCache()

    resolution = cache.put_result(result, resolved_text='a\nresolved\nc')

    assert resolution.text == 'a\nresolved\nc'


# ---------------------------------------------------------------------------
# merge_many — iterative N-way merge
# ---------------------------------------------------------------------------

def test_merge_many_no_mods_returns_base() -> None:
    assert merge_many('a\nb\nc') == 'a\nb\nc'


def test_merge_many_single_mod_returns_that_mod() -> None:
    assert merge_many('a\nb\nc', 'a\nX\nc') == 'a\nX\nc'


def test_merge_many_two_mods_matches_merge() -> None:
    base = 'a\nb\nc\nd'
    mod1 = 'a\nX\nc\nd'
    mod2 = 'a\nb\nc\nY'
    assert merge_many(base, mod1, mod2) == merge(base, mod1, mod2)


def test_merge_many_three_independent_mods() -> None:
    base = 'a\nb\nc\nd\ne'
    mod1 = 'a\nX\nc\nd\ne'   # change line 1
    mod2 = 'a\nb\nc\nY\ne'   # change line 3
    mod3 = 'a\nb\nc\nd\nZ'   # change line 4
    result = merge_many(base, mod1, mod2, mod3)
    assert result == 'a\nX\nc\nY\nZ'
    assert not has_conflicts(result)


def test_merge_many_matches_iterative_call_pattern() -> None:
    """merge_many must produce the exact same output as manual iterative merging."""
    base = 'class Foo {\n  var x : int;\n}\n'
    mod1 = base + 'function A() {}\n'
    mod2 = base + 'function B() {}\n'
    mod3 = base + 'function C() {}\n'

    iterative = merge(base, merge(base, mod1, mod2), mod3)
    assert merge_many(base, mod1, mod2, mod3) == iterative


def test_merge_many_propagates_conflict_from_earlier_merge() -> None:
    """If mods 1 and 2 conflict, the conflict markers survive merging with mod 3."""
    base = 'a\nb\nc'
    mod1 = 'a\nX\nc'
    mod2 = 'a\nY\nc'
    mod3 = 'a\nb\nZ'   # independent change at last line
    result = merge_many(base, mod1, mod2, mod3)
    assert has_conflicts(result)
    assert 'X' in result
    assert 'Y' in result
    assert 'Z' in result
