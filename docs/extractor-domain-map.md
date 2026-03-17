# Extractor Domain Map

> Map of the modular extraction domains under `extractors/` and what each one is expected to own.

## Why this matters

The repo is moving toward domain-oriented data modeling. That only works if each domain has a clear boundary.

## Current extractor modules

- `extractors/design_context.py`
- `extractors/design_guide.py`
- `extractors/electrical.py`
- `extractors/package.py`
- `extractors/parametric.py`
- `extractors/pin.py`
- `extractors/power_sequence.py`
- `extractors/protocol.py`
- `extractors/register.py`
- `extractors/thermal.py`
- `extractors/timing.py`

## Practical ownership map

### `electrical`

Owns:
- absolute maximum ratings
- electrical characteristics
- numerical operating limits

### `pin`

Owns:
- package-to-pin mapping
- pin naming and direction
- pin-index-like structures

### `thermal`

Owns:
- thermal resistance style metrics
- dissipation-related normalized values

### `design_context`

Owns:
- external component hints
- layout hints
- equation hints
- design page candidates

### `design_guide`

Owns:
- structured design-guide style content from vendor collateral

### `timing`

Owns:
- timing parameters
- setup/hold/prop-delay style content

### `power_sequence`

Owns:
- rail order
- sequencing constraints
- bring-up dependencies

### `protocol`

Owns:
- interface capability extraction
- bus/protocol semantics

### `parametric`

Owns:
- comparison-oriented normalized spec summaries

### `package`

Owns:
- package metadata beyond raw pin records

### `register`

Owns:
- register-aware structured extraction

## Boundary rule

If a value is primarily numeric and tied to a datasheet parameter table, it usually belongs to `electrical` or `thermal`.

If it is about integration behavior, it usually belongs to `design_context`, `protocol`, or `power_sequence`.

## Why boundaries matter

Bad domain boundaries create:
- duplicated facts
- export drift
- conflicting provenance
- harder migration into `device-knowledge/2.0`
