"""Check exact sources and transfer candidates for one finder page."""

import time
from contextlib import suppress

from .related_capture import _assessment_options, present
from .related_capture_familiar import familiarity
from .related_protection import selection
from .related_protection_source import source_for_evidence


class SourceChecks:
    def __init__(self, db, subject, corpus, until):
        self.db, self.subject, self.corpus, self.until = db, subject, corpus, until
        self.checked = 0
        self.familiar = None
        self.result = {"items": []}

    def check(self):
        if time.monotonic() >= self.until:
            raise TimeoutError

    def source(self, evidence_id):
        with suppress(ValueError, TypeError, KeyError, IndexError):
            self._source(evidence_id)

    def _source(self, evidence_id):
        self.check()
        source_for_evidence(self.db, self.subject, evidence_id)
        self.checked += 1
        if self.familiar is None:
            self.familiar = familiarity(self.db, self.subject, check=self.check)
        chosen = selection(
            self.db,
            self.subject,
            evidence_id,
            self.corpus,
            familiar_data=self.familiar,
            check=self.check,
        )
        self.check()
        result = present(chosen, None)
        if chosen is not None:
            self.check()
            _assessment_options(self.db, result["items"], chosen[3], None, result["scope"])
            self.check()
            result.update(
                source_outcome=chosen[0]["outcome"],
                protection_scan=chosen[2]["protection_scan"],
                corpus_limited=chosen[2]["limited"],
            )
        result["evidence_id"] = evidence_id
        self.result = result
