# Pin Domain Contract

## Role

The `pin` domain converts human-readable pin tables, pinouts, and package mappings into a structured logical-pin model that downstream exporters can use.

## Output Shape

The repository expects the pin domain to separate:

- logical pin identity
- electrical direction
- signal type
- package-specific physical pin mapping

This distinction matters because one device family may appear in multiple packages with different numbering.

## Why Pin Extraction Is Separate

Pin data has different failure modes than electrical tables:

- pin names may appear in diagrams instead of tables
- direction must be normalized
- one logical pin may map to multiple package pins
- unused pins require explicit treatment

Keeping this logic outside `electrical` prevents a large mixed prompt that is hard to debug.

## Good Pin Extraction Behavior

- extract enough structure for package-indexed lookups
- normalize direction and signal class
- tolerate cover-page or sparse datasheets when a dedicated pin page does not exist
- return a clean empty result when the source genuinely has no pin table

## Common Mistakes

- mixing physical numbering with logical identity
- forcing package assumptions too early
- treating every passive pin as identical even when the symbol names differ
- failing hard just because no dedicated pin page exists

## Discrete-Part Behavior

For simple diodes, TVS devices, and small MOSFETs, pin extraction is still valuable because downstream tools often need:

- anode/cathode or drain/source/gate labeling
- package-level numbering
- passive or bidirectional signal semantics

This is why `pin` remains in the discrete fast-path allowlist.

## Review Questions

- Can a downstream export rebuild package-specific pin maps from the result?
- Are pin names stable enough for schematic review?
- Did the extractor overfit to one vendor's drawing style?
