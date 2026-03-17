# Redriver Retimer Switch Review

> Choosing between linear redriver, retimer, and switch paths without hand-waving.

## First decision

Ask:
- is the problem channel loss, topology flexibility, or clock recovery
- does the protocol require link training or OOB behavior
- does the inserted device preserve or interfere with training

## Good review rules

- use a linear redriver when protocol behavior requires transparent EQ handling
- use a retimer when channel reach and jitter cleanup justify clock recovery
- use a switch only when topology flexibility is worth the added discontinuity and control complexity

## Common mistakes

- picking a retimer because it sounds stronger
- inserting a mux into a refclk path without loss and skew review
- forgetting power-up defaults and management path for the signal conditioner

## Official practice baseline

TI’s PCIe and signal-conditioning material is especially clear here: interfaces needing LT transparency often push you toward linear redrivers, while retimers are for different problems.
