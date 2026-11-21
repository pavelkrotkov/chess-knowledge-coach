"""Identity and limits of the optional recent public rated-game prefix."""

URL = "https://database.lichess.org/standard/lichess_db_standard_rated_2026-10.pgn.zst"
SOURCE = "https://database.lichess.org/"
MONTH = "2026-10"
LICENSE = "CC0-1.0"
LICENSE_URL = "https://creativecommons.org/publicdomain/zero/1.0/"
KIND = "lichess-standard-rated-prefix-v1"
PREFIX_BYTES = 1024 * 1024
PREFIX_NAME = "opening-standard-rated-2026-10-prefix.zst"
MANIFEST_NAME = "opening-standard-rated-2026-10-prefix.json"
INDEX_NAME = "opening-standard-rated-2026-10-prefix-v1.sqlite"
TRANSFORM = "rated-prefix-v1:32MB-decoded;5000-records;1000-games;40-parent-plies;12-window-plies;512-game-plies"
