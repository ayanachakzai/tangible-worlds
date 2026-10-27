# Codex run notes

- [READ] Preserved the working-tree voice route `object <id> is <meaning>` and atmosphere fallback as authoritative.
- [RAN] Captured status and a 33-file protected manifest before study artifacts were created.
- [RAN] Froze 90 expected cases before creating or executing candidate parser code.
- [RAN] Both candidates achieved perfect holdout classification; selected Grammar A by the brief's tie-break rule.
- [RAN] Requested parity passed for route, object key, intent, target, source, detection state, and subject identity. The supplied voice phrases include `a` while the supplied typed phrases do not; original and generation strings correctly retain that participant wording difference.
- [RAN] Ten generation-semantics checks preserved original phrases and removed only the marker. The selected cache fixture used `castle.glb` while retaining `castle, scale tiny` as display/original meaning.
- [RAN] Persistence retained target 0.35 and both meaning fields after JSON round-trip. Twenty simulated moves left generation count at one.
- [RAN] An initial isolated cache check restored the process working directory too early, causing its relative fixture path to resolve at repository root and briefly start the local generator. The two study-started processes were stopped; the empty root-level `generated_meshes/castle` fixture and its parent were removed with `rmdir`. No production rendering file or runtime JSON was written. Evidence: `raw/accidental_generation_cleanup.txt`.
- [RAN] The corrected isolated check kept the proposed server's working directory inside `raw/patch_apply_check/` and passed.
- [RAN] No production patch application, runtime reset, Qwen scale call, commit, push, or web lookup occurred.
