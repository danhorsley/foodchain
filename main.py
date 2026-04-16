"""Pygame entrypoint.

Native:
    python main.py                                    # Phase 2 baseline, observer
    python main.py --species classic                  # Phase 1 roster, observer
    python main.py --species phase2 --play            # play (biomes on by default)
    python main.py --species phase2 --biomes          # observer with biomes
    python main.py --species phase2 --play --no-biomes  # play on a flat grid

Browser (via pygbag):
    When sys.platform is "emscripten" (Pyodide), we skip argparse entirely
    and go straight into play mode with the Phase 2 roster + biomes. argparse
    reading sys.argv in the browser can silently SystemExit in some setups.
"""
import asyncio
import sys

# Prints to stdout show up in the browser DevTools console under pygbag —
# these give us boot milestones so a blank screen isn't a total mystery.
print("[foodchain] boot: importing app", flush=True)

from foodchain.render.pygame_view import App
from foodchain.sim import SimConfig
from foodchain.sim.config import CLASSIC_SPECIES, PHASE2_SPECIES

ROSTERS = {"classic": CLASSIC_SPECIES, "phase2": PHASE2_SPECIES}

DEFAULT_FOREST_FRAC = 0.22
DEFAULT_WATER_FRAC = 0.06

IS_BROWSER = sys.platform in ("emscripten", "wasi")


def _browser_config():
    """Hard-coded config for the browser build — no argparse."""
    cfg = SimConfig(seed=12, species=list(PHASE2_SPECIES))
    cfg.terrain_forest_frac = DEFAULT_FOREST_FRAC
    cfg.terrain_water_frac = DEFAULT_WATER_FRAC
    return cfg, True


def _native_config():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--species", choices=ROSTERS, default="phase2")
    p.add_argument("--seed", type=int, default=12)
    p.add_argument("--play", action="store_true", help="player-controlled mode")
    group = p.add_mutually_exclusive_group()
    group.add_argument("--biomes", dest="biomes", action="store_true")
    group.add_argument("--no-biomes", dest="biomes", action="store_false")
    p.set_defaults(biomes=None)
    args = p.parse_args()

    if args.biomes is None:
        args.biomes = args.play

    cfg = SimConfig(seed=args.seed, species=list(ROSTERS[args.species]))
    if args.biomes:
        cfg.terrain_forest_frac = DEFAULT_FOREST_FRAC
        cfg.terrain_water_frac = DEFAULT_WATER_FRAC
    return cfg, args.play


async def main() -> None:
    print(f"[foodchain] platform={sys.platform} browser={IS_BROWSER}", flush=True)
    if IS_BROWSER:
        cfg, play = _browser_config()
    else:
        cfg, play = _native_config()
    print(f"[foodchain] starting app play={play}", flush=True)
    await App(cfg, play=play).run()


if __name__ == "__main__":
    asyncio.run(main())
