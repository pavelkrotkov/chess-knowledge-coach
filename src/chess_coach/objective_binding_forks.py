"""Version-to-goal and verifier bindings for owned fork objectives."""

from .objective_fork_avoidance_contract import GOAL as AVOIDANCE_GOAL
from .objective_fork_avoidance_contract import OBJECTIVE as AVOIDANCE_OBJECTIVE
from .objective_fork_avoidance_contract import VERSION as AVOIDANCE_VERSION
from .objective_fork_contract import GOAL as EXECUTE_GOAL
from .objective_fork_contract import OBJECTIVE as EXECUTE_OBJECTIVE
from .objective_fork_contract import VERSION as EXECUTE_VERSION
from .objective_fork_defense_contract import GOAL as DEFENSE_GOAL
from .objective_fork_defense_contract import OBJECTIVE as DEFENSE_OBJECTIVE
from .objective_fork_defense_contract import VERSION as DEFENSE_VERSION

SCOPES = {
    (EXECUTE_VERSION, EXECUTE_GOAL),
    (AVOIDANCE_VERSION, AVOIDANCE_GOAL),
    (DEFENSE_VERSION, DEFENSE_GOAL),
}
BINDINGS = {
    (EXECUTE_VERSION, EXECUTE_OBJECTIVE),
    (AVOIDANCE_VERSION, AVOIDANCE_OBJECTIVE),
    (DEFENSE_VERSION, DEFENSE_OBJECTIVE),
}
