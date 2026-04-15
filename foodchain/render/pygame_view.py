"""Pygame front-end for the sim.

Two modes:

* **Observer** (default): auto-ticks, user watches emergent dynamics. Keys:
    SPACE pause, `.` single-step, `+`/`-` speed, `r` reseed, `q`/ESC quit.

* **Player** (`play=True`): no auto-tick. Each player action advances the world
  by exactly one tick — Pixel-Dungeon style. Keys:
    arrows / WASD   move (or attack if edible prey in that cell)
    `.` / SPACE     wait one turn
    `r`             restart on game-over
    `q` / ESC       quit

Status bar shows ecology counts plus, in player mode, player energy / level /
kills toward the next tier.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import pygame

from foodchain.sim import SimConfig, World
from foodchain.sim.config import (
    PLAYER_DASH_LEVEL,
    PLAYER_HIDE_DURATION,
    PLAYER_HIDE_LEVEL,
    PLAYER_STRIKE_LEVEL,
)

BG = (12, 12, 16)
GRID_EMPTY = (30, 30, 36)
GRASS = (60, 140, 70)
FOREST = (25, 60, 30)            # dark evergreen — darker than grass so contrast is clear
WATER = (35, 65, 115)            # deep blue
TEXT = (210, 210, 220)
DIM_TEXT = (110, 110, 120)
PLAYER_COLOR = (255, 255, 255)
PLAYER_RING = (255, 240, 120)
PLAYER_HIDDEN_COLOR = (180, 180, 200)
PLAYER_HIDDEN_RING = (140, 180, 240)
PLAYER_PRIMED_RING = (255, 160, 80)   # pending ability visible on the player
GAMEOVER_TEXT = (255, 120, 120)
WIN_TEXT = (160, 255, 160)

TERRAIN_COLORS = {"forest": FOREST, "water": WATER}

CELL = 12
MARGIN = 8
HISTORY_W = 260
STATUS_H = 60           # three-line status bar in player mode (was 44)
HISTORY_LEN = 400

# Keys: 1=dash, 2=hide, 3=strike. Hide fires immediately, the other two prime
# and wait for a direction key.
_ABILITY_KEYS = {
    pygame.K_1: "dash",
    pygame.K_2: "hide",
    pygame.K_3: "strike",
}
_ABILITY_LEVEL = {
    "dash": PLAYER_DASH_LEVEL,
    "hide": PLAYER_HIDE_LEVEL,
    "strike": PLAYER_STRIKE_LEVEL,
}

# dx/dy mappings for both arrow keys and WASD
_MOVE_KEYS: Dict[int, Tuple[int, int]] = {
    pygame.K_UP: (0, -1),
    pygame.K_DOWN: (0, 1),
    pygame.K_LEFT: (-1, 0),
    pygame.K_RIGHT: (1, 0),
    pygame.K_w: (0, -1),
    pygame.K_s: (0, 1),
    pygame.K_a: (-1, 0),
    pygame.K_d: (1, 0),
}


class App:
    def __init__(self, cfg: SimConfig, play: bool = False):
        self.cfg = cfg
        self.play = play
        self.world = World(cfg)
        if play:
            self.world.place_player()

        grid_w = cfg.width * CELL
        grid_h = cfg.height * CELL
        self.grid_rect = pygame.Rect(MARGIN, MARGIN, grid_w, grid_h)
        self.hist_rect = pygame.Rect(
            MARGIN * 2 + grid_w, MARGIN, HISTORY_W, grid_h
        )
        status_h = STATUS_H if play else 28
        total_w = MARGIN * 3 + grid_w + HISTORY_W
        total_h = MARGIN * 2 + grid_h + status_h

        pygame.init()
        pygame.display.set_caption(
            "foodchain — play" if play else "foodchain — observer"
        )
        self.screen = pygame.display.set_mode((total_w, total_h))
        self.font = pygame.font.SysFont("menlo,monospace", 14)
        self.big_font = pygame.font.SysFont("menlo,monospace", 28, bold=True)
        self.clock = pygame.time.Clock()

        self.paused = False
        self.ticks_per_sec = 20
        self.history: List[Dict[str, int]] = []

        # Player-mode state
        self.last_message: str = ""
        self.game_over: Optional[str] = None   # 'died' | 'won'
        # "dash" or "strike" when waiting for a direction; None otherwise.
        # Hide fires immediately so never sits in this state.
        self.pending_ability: Optional[str] = None
        # Run summary captured at game-over so we can still render after
        # World.player has been cleared.
        self.summary: Optional[Dict[str, object]] = None

    # -------------------------------------------------------------- main loop

    def run(self) -> None:
        accumulator = 0.0
        running = True
        while running:
            dt = self.clock.tick(60) / 1000.0
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    running = self._on_key(event.key)

            if not self.play and not self.paused and self.game_over is None:
                accumulator += dt * self.ticks_per_sec
                while accumulator >= 1.0:
                    self._observer_tick()
                    accumulator -= 1.0
            else:
                accumulator = 0.0

            self._draw()
            pygame.display.flip()

        pygame.quit()

    # --------------------------------------------------------------- input

    def _on_key(self, key: int) -> bool:
        # Escape has context-sensitive meaning in play mode — cancel a pending
        # ability first, quit only if there's nothing to cancel.
        if key == pygame.K_q:
            return False
        if key == pygame.K_ESCAPE:
            if self.play and self.pending_ability is not None:
                self.pending_ability = None
                self.last_message = "cancelled"
                return True
            return False
        if key == pygame.K_r:
            self._restart()
            return True

        if self.play:
            if self.game_over is not None:
                return True

            # Arm / fire abilities
            if key in _ABILITY_KEYS:
                ab = _ABILITY_KEYS[key]
                # Toggle off if the same slot is pressed twice.
                if self.pending_ability == ab:
                    self.pending_ability = None
                    self.last_message = "cancelled"
                    return True
                if ab == "hide":
                    self._player_turn("hide")
                else:
                    self.pending_ability = ab
                    self.last_message = f"{ab}: pick a direction"
                return True

            # Movement / directional trigger for pending ability
            if key in _MOVE_KEYS:
                direction = _MOVE_KEYS[key]
                if self.pending_ability in ("dash", "strike"):
                    ability = self.pending_ability
                    self.pending_ability = None
                    self._player_turn(ability, direction)
                else:
                    self._player_turn("move", direction)
                return True

            if key in (pygame.K_PERIOD, pygame.K_SPACE):
                self._player_turn("wait")
                return True
        else:
            if key == pygame.K_SPACE:
                self.paused = not self.paused
            elif key == pygame.K_PERIOD and self.paused:
                self._observer_tick()
            elif key in (pygame.K_PLUS, pygame.K_EQUALS):
                self.ticks_per_sec = min(200, self.ticks_per_sec + 5)
            elif key == pygame.K_MINUS:
                self.ticks_per_sec = max(1, self.ticks_per_sec - 5)
        return True

    def _restart(self) -> None:
        self.world = World(self.cfg)
        if self.play:
            self.world.place_player()
        self.history.clear()
        self.last_message = ""
        self.game_over = None
        self.summary = None
        self.pending_ability = None

    # -------------------------------------------------------------- turn engine

    def _observer_tick(self) -> None:
        self.world.step()
        self.history.append(self.world.counts())
        if len(self.history) > HISTORY_LEN:
            self.history = self.history[-HISTORY_LEN:]

    def _player_turn(self, action: str, direction: Optional[Tuple[int, int]] = None) -> None:
        # Hold a reference to the player object. If they die during the world
        # step, World.player gets cleared but this object still carries final
        # meals/level (including any kill made on this same turn).
        pre_player = self.world.player

        info = self.world.step_with_player(action, direction)
        if not info["ticked"]:
            # Blocked move / locked ability — show the reason if the sim
            # provided one, otherwise stay silent for plain wall-bumps.
            if info.get("message"):
                self.last_message = info["message"]
            return
        self.history.append(self.world.counts())
        if len(self.history) > HISTORY_LEN:
            self.history = self.history[-HISTORY_LEN:]

        # Compose a tiny message for the status line.
        msgs = []
        if info.get("message"):
            msgs.append(info["message"])
        if info["ate"] is not None:
            msgs.append(f"ate {info['ate']}")
        if info["leveled_up"]:
            ability = {
                1: "dash",
                2: "hide",
                3: "strike",
            }.get(self.world.player.level)
            tag = f" — {ability} unlocked" if ability else ""
            msgs.append(f"level {self.world.player.level}{tag}")
        if info["won"]:
            msgs.append("you slew the apex — YOU WIN")
            self.game_over = "won"
            self._capture_summary("won", pre_player)
        if info["died_by"] is not None:
            msgs.append(f"you were {info['died_by']}")
            self.game_over = "died"
            self._capture_summary(info["died_by"], pre_player)
        self.last_message = " · ".join(msgs) if msgs else ""

    def _capture_summary(self, cause: str, player_ref) -> None:
        """Freeze the final run stats. Uses the live player object if the run
        is still going (e.g. win), or the held reference if the player was
        eaten this turn — the object still has final meals/level."""
        p = self.world.player or player_ref
        self.summary = {
            "ticks": self.world.tick,
            "level": p.level if p is not None else 0,
            "meals": dict(p.meals) if p is not None else {},
            "cause": cause,
        }

    # ----------------------------------------------------------------- render

    def _draw(self) -> None:
        self.screen.fill(BG)
        self._draw_grid()
        self._draw_history()
        self._draw_status()
        if self.game_over is not None:
            self._draw_gameover_banner()

    def _draw_grid(self) -> None:
        pygame.draw.rect(self.screen, GRID_EMPTY, self.grid_rect)
        gx, gy = self.grid_rect.topleft

        # Terrain layer (water + forest). Plains = the GRID_EMPTY background.
        for cell, kind in self.world.terrain.items():
            color = TERRAIN_COLORS.get(kind)
            if color is None:
                continue
            x, y = cell
            pygame.draw.rect(
                self.screen, color,
                (gx + x * CELL, gy + y * CELL, CELL, CELL),
            )

        # Grass sits on passable terrain only; drawn on top of forest/plains.
        for (x, y) in self.world.grass:
            pygame.draw.rect(
                self.screen, GRASS,
                (gx + x * CELL, gy + y * CELL, CELL, CELL),
            )

        defs = self.world.species_defs
        for a in self.world.animals:
            color = defs[a.species].color
            pygame.draw.rect(
                self.screen, color,
                (gx + a.x * CELL + 1, gy + a.y * CELL + 1, CELL - 2, CELL - 2),
            )

        if self.world.player is not None:
            p = self.world.player
            px = gx + p.x * CELL
            py = gy + p.y * CELL
            hidden = self.world.tick < p.hidden_until_tick
            fill = PLAYER_HIDDEN_COLOR if hidden else PLAYER_COLOR
            ring = (
                PLAYER_PRIMED_RING if self.pending_ability is not None
                else PLAYER_HIDDEN_RING if hidden
                else PLAYER_RING
            )
            pygame.draw.rect(self.screen, fill, (px + 1, py + 1, CELL - 2, CELL - 2))
            pygame.draw.rect(self.screen, ring, (px, py, CELL, CELL), 1)

    def _draw_history(self) -> None:
        r = self.hist_rect
        pygame.draw.rect(self.screen, GRID_EMPTY, r)
        if len(self.history) < 2:
            return

        species_names = [s.name for s in self.cfg.species if s.name != "player"]
        max_grass = max(1, max(h["grass"] for h in self.history))
        max_animal = max(
            1,
            max(max((h[n] for n in species_names), default=0) for h in self.history),
        )

        def plot(key: str, color: tuple, scale: int) -> None:
            pts = []
            for i, row in enumerate(self.history):
                x = r.left + int(i * (r.width - 1) / max(1, HISTORY_LEN - 1))
                y = r.bottom - 1 - int(row[key] * (r.height - 2) / scale)
                pts.append((x, y))
            if len(pts) >= 2:
                pygame.draw.lines(self.screen, color, False, pts, 1)

        plot("grass", GRASS, max_grass)
        for sdef in self.cfg.species:
            if sdef.name == "player":
                continue
            plot(sdef.name, sdef.color, max_animal)

    def _draw_status(self) -> None:
        counts = self.world.counts()
        y = MARGIN + self.cfg.height * CELL + 6

        # Line 1 — always shown: tick + ecology
        parts = [f"tick {self.world.tick:>5}", f"grass {counts['grass']:>4}"]
        for sdef in self.cfg.species:
            if sdef.name == "player":
                continue
            parts.append(f"{sdef.name[:4]} {counts[sdef.name]:>3}")
        if not self.play:
            parts.append(f"{self.ticks_per_sec} tps")
            if self.paused:
                parts.append("PAUSED")
        line1 = "   ".join(parts)
        self.screen.blit(self.font.render(line1, True, TEXT), (MARGIN, y))

        # Line 2 — player mode only: player stats
        if self.play and self.world.player is not None:
            p = self.world.player
            target = p.kills_to_next
            prog = f"{p.kills}/{target}" if target else "MAX"
            hide_ticks = max(0, p.hidden_until_tick - self.world.tick)
            hide_tag = f"  HIDDEN {hide_ticks}t" if hide_ticks > 0 else ""
            status = (
                f"energy {p.energy:>3}   level {p.level}   kills {prog}"
                f"{hide_tag}"
            )
            self.screen.blit(self.font.render(status, True, TEXT), (MARGIN, y + 18))

            # Line 3: ability slots + last message.
            self._draw_ability_bar(y + 36)
        elif self.play and self.last_message:
            self.screen.blit(self.font.render(self.last_message, True, TEXT), (MARGIN, y + 18))

    def _draw_ability_bar(self, y: int) -> None:
        """Row of [1] dash [2] hide [3] strike, dimmed if locked, highlighted
        if primed. Appended with the latest flash message."""
        p = self.world.player
        if p is None:
            return
        x = MARGIN
        for key_label, ability in (("1", "dash"), ("2", "hide"), ("3", "strike")):
            unlocked = p.level >= _ABILITY_LEVEL[ability]
            primed = self.pending_ability == ability
            if primed:
                color = PLAYER_PRIMED_RING
            elif unlocked:
                color = TEXT
            else:
                color = DIM_TEXT
            label = f"[{key_label}] {ability}"
            surf = self.font.render(label, True, color)
            self.screen.blit(surf, (x, y))
            x += surf.get_width() + 18
        if self.last_message:
            msg_surf = self.font.render(self.last_message, True, TEXT)
            self.screen.blit(msg_surf, (x + 10, y))

    def _draw_gameover_banner(self) -> None:
        won = (self.game_over == "won")
        title = "YOU WIN — apex slain" if won else "GAME OVER"
        color = WIN_TEXT if won else GAMEOVER_TEXT

        # Build body text lines from the captured summary.
        s = self.summary or {}
        meals: Dict[str, int] = s.get("meals", {}) or {}
        total_kills = sum(v for k, v in meals.items() if k != "grass")
        cause = s.get("cause", "")
        if cause == "starved":
            cause_line = "cause of death: starvation"
        elif cause == "won":
            cause_line = "you made it to the top of the food chain"
        elif cause:
            cause_line = f"cause of death: eaten by {cause}"
        else:
            cause_line = ""

        lines = [
            f"ticks survived: {s.get('ticks', 0)}",
            f"final level:    {s.get('level', 0)}",
            f"kills:          {total_kills}  (grass eaten: {meals.get('grass', 0)})",
        ]
        # Break out kills by species, in roster order so tiers read top-down.
        species_order = [sd.name for sd in self.cfg.species if sd.name != "player"]
        species_kills = [(n, meals.get(n, 0)) for n in species_order if meals.get(n, 0) > 0]
        if species_kills:
            lines.append("")
            lines.append("meal breakdown:")
            for name, count in species_kills:
                lines.append(f"  {name:<12} x {count}")
        if cause_line:
            lines.append("")
            lines.append(cause_line)

        # Render everything into a centred panel.
        title_surf = self.big_font.render(title, True, color)
        line_surfs = [self.font.render(ln, True, TEXT) for ln in lines]
        hint_surf = self.font.render("press r to restart, q to quit", True, TEXT)

        pad = 20
        line_h = self.font.get_linesize()
        content_w = max(
            [title_surf.get_width(), hint_surf.get_width()]
            + [ls.get_width() for ls in line_surfs]
        )
        content_h = (
            title_surf.get_height()
            + pad
            + line_h * len(line_surfs)
            + pad
            + hint_surf.get_height()
        )
        panel_w = content_w + pad * 2
        panel_h = content_h + pad * 2

        bg = pygame.Surface((panel_w, panel_h))
        bg.set_alpha(225)
        bg.fill((0, 0, 0))
        bg_rect = bg.get_rect(center=self.grid_rect.center)
        self.screen.blit(bg, bg_rect)
        pygame.draw.rect(self.screen, color, bg_rect, 1)

        y = bg_rect.top + pad
        self.screen.blit(
            title_surf,
            title_surf.get_rect(centerx=bg_rect.centerx, top=y),
        )
        y += title_surf.get_height() + pad

        for ls in line_surfs:
            self.screen.blit(ls, (bg_rect.left + pad, y))
            y += line_h
        y += pad

        self.screen.blit(
            hint_surf,
            hint_surf.get_rect(centerx=bg_rect.centerx, top=y),
        )
