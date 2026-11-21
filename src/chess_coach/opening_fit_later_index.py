"""Select the context-preserving index or the unchanged earlier index."""

from .opening_course_public import _identity
from .opening_fit_context_index import INDEX_NAME as CONTEXT_INDEX
from .opening_fit_context_index import TRANSFORM as CONTEXT_TRANSFORM
from .opening_profile_index import INDEX_NAME as PREVIOUS_INDEX
from .opening_profile_read import _private_file
from .opening_profile_store import TRANSFORM as PREVIOUS_TRANSFORM
from .tactical_study_path import planning


def locate(root, subject):
    directory, _ = planning(root, subject)
    for name, transform in (
        (CONTEXT_INDEX, CONTEXT_TRANSFORM),
        (PREVIOUS_INDEX, PREVIOUS_TRANSFORM),
    ):
        path = directory / name
        if path.exists():
            if not _private_file(path, directory):
                raise ValueError("public opening index unavailable")
            return path, _identity(path), transform
    raise ValueError("public opening index unavailable")
