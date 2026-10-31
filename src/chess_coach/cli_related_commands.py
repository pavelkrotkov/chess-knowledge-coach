"""Dispatch source-bound transfer commands without changing their handlers."""

from . import cli_related_backrank as backrank
from . import cli_related_capture as capture
from . import cli_related_fork as fork
from . import cli_related_mate as mate
from . import cli_related_pin as pin
from . import cli_related_protection as protection

COMMANDS = {
    "related-backrank-roots": backrank.list_roots,
    "related-backrank-attacks": backrank.listing,
    "start-related-backrank-attack": backrank.begin,
    "related-captures": capture.listing,
    "start-related-capture": capture.begin,
    **fork.COMMANDS,
    "related-protections": protection.listing,
    "start-related-protection": protection.begin,
    **mate.commands(),
    **pin.commands(),
}
