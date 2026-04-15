"""Pygame entrypoint.

    python main.py                                    # Phase 1 baseline, observer
    python main.py --species phase2                   # Phase 2 roster, observer
    python main.py --species phase2 --play            # play (biomes on by default)
    python main.py --species phase2 --biomes          # observer with biomes
    python main.py --species phase2 --play --no-biomes  # play on a flat grid
"""
import argparse

from foodchain.render.pygame_view import App
from foodchain.sim import SimConfig
from foodchain.sim.config import CLASSIC_SPECIES, PHASE2_SPECIES

ROSTERS = {"classic": CLASSIC_SPECIES, "phase2": PHASE2_SPECIES}

# Default biome mix when --biomes is on. Tuned to give meaningful cover and
# chokepoints without fragmenting the map into islands.
DEFAULT_FOREST_FRAC = 0.22
DEFAULT_WATER_FRAC = 0.06


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--species", choices=ROSTERS, default="classic")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--play", action="store_true", help="player-controlled mode")
    group = p.add_mutually_exclusive_group()
    group.add_argument("--biomes", dest="biomes", action="store_true",
                       help="enable forest + water terrain")
    group.add_argument("--no-biomes", dest="biomes", action="store_false",
                       help="flat uniform grid")
    p.set_defaults(biomes=None)
    args = p.parse_args()

    # Biomes default: on in --play mode, off otherwise. Explicit flags override.
    if args.biomes is None:
        args.biomes = args.play

    cfg = SimConfig(seed=args.seed, species=list(ROSTERS[args.species]))
    if args.biomes:
        cfg.terrain_forest_frac = DEFAULT_FOREST_FRAC
        cfg.terrain_water_frac = DEFAULT_WATER_FRAC

    App(cfg, play=args.play).run()


if __name__ == "__main__":
    main()
