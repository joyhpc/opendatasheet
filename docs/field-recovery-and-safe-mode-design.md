# Field Recovery And Safe Mode Design

> Hardware review for boards that must recover from bad images, marginal rails, or broken peripherals without becoming dead assets.

## Good recovery features

- alternate programming path
- recoverable reset path
- observable boot state
- safe default straps
- minimal control-plane path that survives partial failure

## Common mistakes

- recovery assumes the main processor is alive
- only one boot source exists and it can brick the board
- debug access disappears in the exact failures where it is needed

## Review question

If the main image is corrupt and one peripheral rail is unhealthy, can the board still tell you what happened and accept recovery?
