"""Load exactly one requested own-game practice family."""

from typing import Any, cast

from flask import abort, render_template

from .back_rank_practice import list_candidates as back_rank
from .discovery_defense_list import candidates as discovery_defense
from .discovery_defense_list import material_candidates as discovery_material
from .discovery_practice import list_candidates as discovery
from .mate_practice import list_candidates as mate
from .objective_capture_list import candidates as capture
from .objective_defense_list import candidates as defense
from .objective_fork_avoidance_list import candidates as fork_avoidance
from .objective_fork_defense_list import candidates as fork_defense
from .objective_fork_list import candidates as fork
from .objective_mate_list import candidates as mate_one
from .objective_pawn_contract import VERSION as PAWN_OBJECTIVE_VERSION
from .objective_pin_list import candidates as pin
from .objective_pin_prevent_list import candidates as pin_prevent
from .objective_protection_list import candidates as protection
from .objective_short_list import candidates as short_mate
from .pawn_practice_list import list_candidates as pawn
from .unified_own_game import list_candidates as material

FAMILIES = {
    "material": ("Material practice", "own_game", material),
    "discovery": ("Discovered attack", "discovery_game", discovery),
    "discovery-defense": ("Discovered-mate defense", "discovery_defense_game", discovery_defense),
    "discovery-material": (
        "Discovered-material defense",
        "discovery_material_game",
        discovery_material,
    ),
    "mate": ("Prepared mate", "mate_game", mate),
    "mate-one": ("Mate in one", "mate_one_game", mate_one),
    "short-mate": ("Mate within two", "short_mate_game", short_mate),
    "pin-prevent": ("Pin prevention", "pin_prevent_game", pin_prevent),
    "pin": ("Pin execution", "pin_game", pin),
    "fork-avoidance": ("Created fork avoidance", "fork_avoidance_game", fork_avoidance),
    "fork-defense": ("Anchored fork defense", "fork_defense_game", fork_defense),
    "fork": ("Fork execution", "fork_game", fork),
    "protection": ("Threatened-piece defense", "protection_game", protection),
    "capture": ("Bounded captures", "capture_game", capture),
    "defense": ("Immediate-mate defense", "defense_game", defense),
    "pawn": ("Pawn endgames", "pawn_game", pawn),
    "back-rank": ("Back-rank practice", "back_rank_game", back_rank),
}


def render(db, subject, family, before):
    selected = FAMILIES.get(family)
    if selected is None:
        abort(404)
    _, field, selector = selected
    selector = cast(Any, selector)
    if family == "pawn":
        try:
            value = selector(db, subject, before=before)
        except ValueError:
            abort(400)
    else:
        value = selector(db, subject)
    return render_template(
        "library_owned.html",
        family=family,
        pawn_before=before,
        pawn_objective_version=PAWN_OBJECTIVE_VERSION,
        **{field: value},
    )


def links():
    return [(key, value[0]) for key, value in FAMILIES.items()]
