# foodchain

Discrete-grid ecosystem game. Climb the food chain from omnivore to apex by
eating the right things, hiding from the wrong ones, and not starving.

## Play

    python main.py --species phase2 --play

Welcome screen asks for a seed. The last two digits of the seed set how many
apex predators spawn at game start — seed ending `00` is chill mode, seed
ending `99` is nightmare.

### Controls
| key | action |
|-----|--------|
| arrows / WASD | move (or attack if edible prey there) |
| `.` / SPACE | wait one turn |
| `1` | dash (unlock L1) — up to 2 cells in a direction |
| `2` | hide (unlock L2) — invisible at distance > 1 for 3 turns |
| ESC | cancel pending ability |
| `r` | restart after death |
| `q` | quit |

### Tier progression
Eat enough of your current tier to unlock the next. Passive **dominance**
kicks in at level 3+ — the named predator stops hunting you entirely.

| level | food unlock | passive reward |
|-------|-------------|----------------|
| 0 | grass, multiplier | — |
| 1 | + hider | dash ability |
| 2 | + runner | hide ability |
| 3 | + stalker | stalker can no longer eat you |
| 4 | + sprinter | sprinter can no longer eat you |
| 5 | + apex | apex can no longer eat you — eat one to win |

## Observer mode
For watching the ecology without a player:

    python main.py --species phase2                   # flat grid
    python main.py --species phase2 --biomes          # with terrain

## Headless tuning

    python -m scripts.tune --species phase2 --ticks 3000 --every 100 > run.csv

## Ship to itch.io (browser build)

    pip install pygbag
    pygbag main.py

This builds `build/web/` — zip its contents and upload to itch.io as an
HTML5 project. The main loop is already async-aware.

## Layout
    foodchain/sim/        headless sim core (no pygame)
    foodchain/render/     pygame renderer
    scripts/tune.py       CLI: N ticks, population CSV
    tests/test_world.py   sanity + mechanics tests
    main.py               entrypoint (async, pygbag-friendly)
