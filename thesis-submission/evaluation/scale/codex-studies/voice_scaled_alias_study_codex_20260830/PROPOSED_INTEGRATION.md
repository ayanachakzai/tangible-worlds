# Proposed integration

`voice_scaled_alias_candidate.patch` is one unapplied, dependency-free patch against the current working tree. It changes only `phase3-tabletop/rendering/index.html`.

## Integration boundary

The patch adds `normalizeVoiceScaleAlias(meaning)` beside the existing voice-assignment parser and calls it only inside `routeAcceptedVoiceCommand` after `parseVoiceAssignment(command)` succeeds. It does not change transcript capture, spoken confirmation, atmosphere fallback, typed submission, `/api/assign`, the current Python scale parser, generation, caching, rendering, movement, tracker, mapping, conversation code, or runtime data.

The exact reserved alias is:

```text
VOICE object <id> is <meaning> scaled <tiny|miniature|small|big|large|huge>
```

The assignment sent to the existing endpoint replaces only the final standalone `scaled` token with `scale`. Earlier supported control fragments and semicolon/colon boundaries are rejected to preserve the current conflict-safe behavior.

The patch comments link MDN's `RegExp` and `String.match` references and label the grammar boundary as a project decision dated 30 Aug 2026.

## Limitation

Voice meanings literally ending in `scaled <supported-size>` are reserved control syntax and must be rephrased. Typed meanings are not reserved: typed `a car scaled tiny` remains ordinary semantic language.

## Verification

- Patch scope: `index.html` only, 29 insertions and 1 deletion.
- `git apply --check`: pass against the current working tree.
- Isolated-copy apply: pass.
- Patched module syntax: pass.
- Patched assignment regression: 94/94.
- Full frozen contract: 104/104.
- Actual server parser/cache fixture: pass, `a-car` cache identity, zero generator calls.
- Production protected hashes: unchanged.

The patch is intentionally unapplied.
