# Assignment contract

## Selected marked record

```json
{
  "meaning": "castle, scale tiny",
  "generation_meaning": "castle",
  "explicit_scale_intent": "very_small",
  "target_size": 0.35,
  "scale_source": "participant_marked",
  "status": "generating",
  "rotation": {"x": 0, "y": 0, "z": 0}
}
```

- `meaning` preserves the participant phrase after existing route trimming, including the marker and typed terminal punctuation.
- `generation_meaning` removes exactly one qualified terminal control suffix. It is used for object generation, mesh-cache identity, rotation-cache identity, and relation-generation meaning.
- `explicit_scale_intent` and `target_size` are cached once at `/api/assign`.
- `scale_source` is `participant_marked` only for accepted Grammar A; otherwise it is `neutral_default`.
- Existing `status`, `rotation`, and eventual `mesh_url` fields remain.

## Neutral and compatibility record

Bare, malformed, ambiguous, conflicting, or unsupported wording keeps the full meaning:

```json
{
  "meaning": "castle, scale enormous",
  "generation_meaning": "castle, scale enormous",
  "explicit_scale_intent": "neutral",
  "target_size": 1.0,
  "scale_source": "neutral_default"
}
```

Old records without `target_size` render at the locked neutral target 1.00. No data migration is proposed.

## Route, generation, and movement invariants

Typed and voice inputs both converge at `/api/assign`; the scale parser belongs there. The working-tree `parseVoiceAssignment()` block is byte-identical in the isolated patched copy. Normal atmosphere commands still use `/api/converse`. [READ][RAN]

Generation and cache keys use `generation_meaning`, while `_mark()` continues matching the original `meaning`; this prevents status updates from orphaning a marked record. Labels retain `meaning`. Movement updates only the existing Three.js group's `x/z`; it does not reparse, rescale, reload, or regenerate. [READ][RAN]
