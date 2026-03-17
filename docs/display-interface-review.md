# Display Interface Review

> Review checklist for eDP, HDMI, LVDS, OpenLDI, and related display egress paths.

## Key questions

- which side owns link training or mode setup
- which clocking assumptions are embedded in the interface
- where ESD and level translation live
- whether muxes or switches are inserted in the path

## Common mistakes

- using a display connector footprint before routing feasibility is proven
- mixing display and generic high-speed assumptions
- forgetting AUX, HPD, EDID, and sideband control paths

## Good review package

- lane map
- refclk or pixel-clock source
- AUX/DDC ownership
- hot-plug detect behavior
- protection strategy at the connector

## Official practice baseline

AMD display IP docs explicitly point designers back to PCB design guides and schematic review checklists. Follow that pattern: treat display links as board-topology problems, not only protocol problems.
