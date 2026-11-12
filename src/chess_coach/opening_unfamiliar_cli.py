"""Parse a complete optional unfamiliar-course selection."""


def selection(args, parser):
    values = (args.color, args.parent, args.move)
    if not any(value is not None for value in values):
        return None
    if not args.unfamiliar or any(value is None for value in values):
        parser.error("selected unfamiliar publication requires --color, --parent and --move")
    return dict(zip(("color", "parent", "move"), values, strict=True))


def add_arguments(parser):
    parser.add_argument("--color", choices=("white", "black"))
    parser.add_argument("--parent")
    parser.add_argument("--move")
