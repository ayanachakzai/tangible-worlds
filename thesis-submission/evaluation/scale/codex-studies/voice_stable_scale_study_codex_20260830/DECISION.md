# Decision

**Current `scale <value>` remains best despite acoustic limitation.** [READ][RAN]

Semantic holdout results:

| Candidate | TP | FP | FN | TN | Precision | Recall |
|---|---:|---:|---:|---:|---:|---:|
| A: `size <value>` | 24 | 3 | 0 | 121 | 88.9% | 100% |
| B: `size is <value>` | 24 | 6 | 0 | 118 | 80.0% | 100% |
| C: current `scale <value>` | 24 | 0 | 0 | 124 | 100% | 100% |

Candidate A and B fail the effectively-perfect semantic precision requirement. Candidate C is the only grammar that preserves arbitrary ordinary meanings across the fresh 148-case holdout, but Ayan's repeated live result—`scale tiny` transcribed as `scaled tiny`—remains a real acoustic failure. Synthetic Pocket TTS evidence does not override that live-user evidence. [RAN]

No follow-up parser patch was created because neither alternative qualified and production already implements Candidate C.

Exactly one next production action: add one facilitator instruction to the participant protocol—if confirmation says `scaled <value>`, answer no and repeat `scale <value>`.
