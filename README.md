# foodchain

Discrete-grid ecosystem sim, built as a staged prototype.

## Phases
1. **Phase 1 (now):** grass + one herbivore species + one predator species.
   Goal: parameter values that give sustained oscillation rather than extinction cascades.
2. **Phase 2:** three herbivore variants (multiplier, hider, runner) and three
   predator variants (stalker, sprinter, apex) with distinct behaviours — not
   just stat spreads.
3. **Phase 3:** player character (omnivore) in a Pixel-Dungeon-style turn
   system — one player action advances the world by one tick.

## Layout
    foodchain/sim/        headless sim core (no pygame)
    foodchain/render/     pygame renderer (added once sim is stable)
    scripts/tune.py       CLI: run N ticks headless, emit population CSV
    tests/                sanity tests

## Quickstart
    python main.py                            # pygame view
    python -m scripts.tune --ticks 2000       # headless, CSV to stdout
    python tests/test_world.py

Pygame keys: SPACE pause, `.` single-step, `+`/`-` speed, `r` reseed, `q` quit.

All tunables live in `foodchain/sim/config.py` and are exposed as CLI flags
on `tune.py` (e.g. `--grass-regrow-prob 0.03`).
