"""Revalidate the selected follow-up mode at preview and admission."""


def expected_context(db, subject, corpus, evidence, attempt, harder):
    if harder:
        from .protection_difficulty import eligible

        return eligible(db, subject, corpus, evidence, attempt)
    from .protection_followup_prior import prior

    return prior(db, subject, corpus, evidence, attempt), None


def validate(db, subject, corpus, evidence, followup, assessment, chosen, harder, expected=None):
    if harder and not followup:
        raise ValueError("harder protection requires a follow-up")
    if followup:
        from .protection_followup_prior import selected

        selected(
            db,
            subject,
            corpus,
            evidence,
            followup,
            assessment,
            chosen,
            harder=harder,
            expected=expected,
        )
