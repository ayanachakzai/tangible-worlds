# Codex run notes

- [READ] Confirmed current production already contains optional-comma `scale <value>`, cached scale fields, renderer target use, and the live voice route.
- [RAN] Captured status and five protected hashes before study creation.
- [RAN] Froze 148 semantic cases before candidate parser code existed or ran.
- [RAN] Existing Pocket TTS and Moonshine services were available; ran a 12-phrase synthetic bakeoff with no install or production edit.
- [RAN] A scored 88.9% precision with three false positives; B scored 80% with six; C scored 100% with none.
- [RAN] Synthetic marker recognition was A 3/4, B 4/4, C 4/4. Kept the synthetic limitation explicit and retained Ayan's repeated `scale -> scaled` result as stronger live evidence.
- [RAN] Typed/voice contract, cache identity, renderer target wiring, and movement invariant passed without repeating renderer GLB tests.
- [RAN] No follow-up patch was created because neither new candidate met semantic precision and current C already exists in production.
- [RAN] No production edit, runtime JSON write, generation, install, commit, push, restore, or clean occurred.
