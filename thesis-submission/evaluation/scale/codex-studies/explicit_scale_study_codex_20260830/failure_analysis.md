# Parser failure analysis

Expected labels and generation meanings were frozen before inference. No case was rescored.

## D1 anywhere-token baseline

- Precision: 27/42 = 64.3%.
- Recall: 27/36 = 75.0%.
- False positives: 15.
- False negatives: 9.

Its additional recall came from detecting trailing words such as `castle is huge`, but it also removed local/component words from `the castle has a small door`, `a model with a tiny window`, and `a house with huge windows`. It even converted `small-scale model` to `-scale model`. This architecture is rejected.

## D2 leading-only candidate

- Precision: 24/33 = 72.7%.
- Recall: 24/36 = 66.7%.
- False positives: 9.
- False negatives: 12.

### False positives

1. `tiny flag on a castle` -> scales the composite and generates `flag on a castle`.
2. `Big Ben` -> `large`, generates `Ben`.
3. `big ben` -> `large`, generates `ben`.
4. `large language model` -> `large`, generates `language model`.
5. `small talk` -> `small`, generates `talk`.
6. `huge fan of castles` -> `very_large`, generates `fan of castles`.
7. `miniature painting` -> `very_small`, generates `painting`.
8. `a big wheel inside a clock` -> `large`, generates `a wheel inside a clock`.
9. `a SMALL detail on the tower` -> `small`, generates `a detail on the tower`.

These are serious because the parser would silently alter both asset semantics and renderer size.

### False negatives

The candidate intentionally ignored six unsupported synonyms/hyphenated forms (`teeny`, `puny`, `little`, `modest-sized`, `enormous`, `colossal`), three trailing forms, and three comparative forms. Ignoring them is conservative and documented, but it limits natural-language recall.

## Why no further patch was attempted

Avoiding the nine false positives requires knowing whether a leading word is a physical whole-object modifier, a proper name, a lexicalized phrase, a non-physical intensifier, or a local component description. That is semantic analysis, not a safe regular-expression refinement. Noun-specific exceptions would violate the brief, while Qwen has already been rejected for direct scale control.

The concept and data path remain technically sound, but the current unmarked natural-language parser does not meet the false-positive standard for production.
