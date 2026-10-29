"""Run bounded pin scans with independent execute and prevent cursors."""

from functools import partial

from .fork_worker import process_forks
from .fork_worker_cursor import scan
from .fork_worker_item import process_item
from .pin_pipeline import process_decision


def process_pins(db, config, operation):
    policy = f"pin-{operation}-worker-v1"
    scanner = partial(scan, namespace=f"pin-{operation}-cursor-v1:", policy=policy)
    detector = partial(process_decision, operation=operation)
    processor = partial(process_item, detector=detector)
    return process_forks(db, config, scanner=scanner, processor=processor, policy=policy)
