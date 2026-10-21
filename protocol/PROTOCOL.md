# Evaluation protocol

Each renderable image-distance pair produces two candidate orders.  Numeric,
Calibrated Numeric, and Oracle Physicalized reuse the same image, question,
candidate identities, values, and order; only candidate-state access changes.

The exact per-cell prompts and gold request specifications are in
`data/manifests/requests2232.jsonl`.  Every provider is scored on all 744
ordered cells per interface.  A failed transport or parse attempt is retried
under the same `request_id`; no response is filtered by its predicted choice.
The compact formal ledger therefore contains 3 providers x 3 interfaces x 744
cells = 6,696 parsed final responses.

Factorial StateBind uses two image-level geometry proposers and an independent
component verifier.  It never receives human geometry or evaluator answers at
inference.  The four target-lattice recombinations are deterministic offline
operations.  Dev69 selects maximum coverage subject to at least 95% candidate
precision among nine predefined agreement-by-distance rules.  Held-out labels
are used only for final scoring.
