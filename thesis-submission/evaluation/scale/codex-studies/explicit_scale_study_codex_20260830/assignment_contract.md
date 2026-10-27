# Assignment contract

## Minimal proposed record

```json
{
  "meaning": "a tiny castle",
  "generation_meaning": "a castle",
  "explicit_scale_intent": "very_small",
  "target_size": 0.35,
  "scale_source": "participant_explicit",
  "status": "generating",
  "rotation": {"x": 0, "y": 0, "z": 0}
}
```

Field decisions:

- `meaning`: exact participant phrase after the existing input-route trimming. It remains the displayed and relational meaning.
- `generation_meaning`: meaning sent to shape prompting, image generation, mesh generation, and the generated-mesh cache key. It differs only when the frozen parser removes one supported leading scale token.
- `explicit_scale_intent`: `very_small`, `small`, `neutral`, `large`, or `very_large`.
- `target_size`: cached project-tuned numeric renderer target: 0.35, 0.65, 1.00, 1.80, or 3.00.
- `scale_source`: `participant_explicit` when the leading grammar matches; otherwise `neutral_default`.
- existing `status`, `rotation`, and eventual `mesh_url` fields remain unchanged.

The record is cached once at `/api/assign`. Movement never changes it. The renderer uses only `target_size`; it does not parse language. Qwen is not involved in scale interpretation.

## Input parity

Typed input already posts `{object_key, meaning}` to `/api/assign`.

The live voice route already parses `object <id> is <meaning>` and posts the same shape. Therefore the explicit parser belongs server-side in `/api/assign`, after both routes converge. No voice grammar, STT, TTS, confirmation, or atmosphere route needs modification.

## Neutral and compatibility behavior

Bare or unsupported language receives:

```json
{
  "explicit_scale_intent": "neutral",
  "target_size": 1.0,
  "scale_source": "neutral_default"
}
```

Old assignment records without `target_size` must render at 1.00 in the proposed path. No migration is required for the prototype.
