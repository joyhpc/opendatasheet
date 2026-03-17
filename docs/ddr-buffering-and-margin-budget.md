# DDR Buffering And Margin Budget

> How to treat DDR as system elasticity, not just memory capacity.

## DDR is carrying more than storage

In many vision and routing platforms, DDR absorbs:
- ingress burst smoothing
- egress mismatch smoothing
- local analysis buffering
- bad-frame capture
- replay and debug context

## Good questions

- what peak ingress bursts must be absorbed
- what downstream stalls exist
- how much headroom remains during simultaneous analysis and forwarding
- what failure logging still works when bandwidth is stressed

## Common mistakes

- budgeting only GB, not GB/s and burst depth
- assuming software can always drain the buffer in time
- consuming key banks with other interfaces before DDR is really placed

## Architecture rule

Review DDR together with:
- ingress interface
- egress interface
- clocking
- thermal and power budget

## Official practice baseline

Use package- and board-specific implementation facts. In high-channel-count boards, DDR is part of the architecture margin budget, not an optional convenience.
