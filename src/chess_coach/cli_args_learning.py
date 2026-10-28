"""Arguments for learning commands."""


def configure(sub):
    validate = sub.add_parser("validate-evidence")
    validate.add_argument("evidence_id", type=int)
    mastery_update = sub.add_parser("update-mastery")
    mastery_update.add_argument("skill")
    mastery_update.add_argument("operation")
    mastery_update.add_argument("--subject", default="default")
    mastery_report_parser = sub.add_parser("mastery-report")
    mastery_report_parser.add_argument("--subject", default="default")
    training_create = sub.add_parser("create-training")
    training_create.add_argument("source_type", choices=["game", "puzzle", "canonical"])
    training_create.add_argument("source_ref")
    training_create.add_argument("skill")
    training_create.add_argument("operation")
    training_due = sub.add_parser("due-training")
    training_due.add_argument("--limit", type=int, default=100)
    training_review = sub.add_parser("review-training")
    training_review.add_argument("item_id", type=int)
    training_review.add_argument("rating", choices=["again", "hard", "good", "easy"])
    training_review.add_argument("--elapsed-seconds", type=int)
    sub.add_parser("evidence-report")
