"""Dispatch source-bound transfer commands without changing their handlers."""

from . import cli_related_capture as capture
from . import cli_related_fork as fork
from . import cli_related_mate as mate
from . import cli_related_protection as protection

COMMANDS = {
    "related-captures": capture.listing,
    "start-related-capture": capture.begin,
    **fork.COMMANDS,
    "related-protections": protection.listing,
    "start-related-protection": protection.begin,
    **mate.commands(),
}
