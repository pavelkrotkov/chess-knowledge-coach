# Licensed direct-prompt collections

A collection consists of a project-local FEN CSV or PGN file, its original
source file, and a JSON manifest. Only operator-verified MIT and CC0-1.0
material is accepted. License metadata is a declaration by the operator: the
importer checks the notice and hashes, but cannot determine whether a remote
publisher actually granted those terms. No remote download or redistribution
occurs during import. Keep the source and its full license notice with the
collection. Do not import material whose terms have not been verified.

The manifest has exactly these string fields: `version`, `source_url` (HTTPS),
`source_revision`, `source_sha256`, `content_sha256`, `content_format`
(`fen_csv` or `pgn`), `license` (`MIT` or `CC0-1.0`), `attribution`, and
`license_notice`. The source and content digests refer to separate local
files, which may be the same file. `content_format` describes the normalized
input, not necessarily the upstream source format. The source-to-content
derivation is an operator declaration; the importer does not reconstruct it. MIT imports require the full copyright and
permission notice; task exports retain the notice and attribution. Manifest
and source sizes are bounded. Source and normalized content are hashed before
and after parsing, and a version cannot be overwritten.

FEN CSV uses the header `id,fen,objective,lines`, where `lines` is a JSON array
of UCI move strings. PGN uses `TaskId` and `Objective` tags, an optional FEN
setup, and mainline/variation moves. The initial FEN is the actual learner
prompt: there is no invented opponent setup move. Every line must be legal;
`checkmate` requires each line to end in mate delivered by the learner, and
`promotion` requires a learner pawn promotion. `legal_line` means only that
the supplied line is legal. None of these checks proves a forced win or that
all acceptable alternatives are included. Unsupported or invalid candidates
are counted as excluded. Duplicate identifiers abort the import.

```sh
chess-coach --db "$VALIDATION_DB" import-public-training "$CONTENT" \
  --source "$SOURCE" --manifest "$MANIFEST" --project-root "$CHESS_PROJECT_ROOT"
chess-coach --db "$VALIDATION_DB" list-public-training
chess-coach --db "$VALIDATION_DB" show-public-training --version "$VERSION" --task-id "$TASK_ID"
```

`show-public-training` without a task ID returns up to 100 tasks; use
`--after-id` to continue. Collection lists return at most 100 versions; use
`--after-version` to continue. Outputs carry source identity, attribution and the
license notice. The authenticated Library page shows a bounded task sample and
exclusion counts. Playable sessions, general alternative-aware grading and
training outcomes remain separate work.

## Prepared material

The project-local pinned [CrispChess drill source](https://github.com/CrispStrobe/CrispChess/blob/0d01798daf9661076675f8505b4cc6995a6529da/lib/chess/drill.dart)
and its [MIT license](https://github.com/CrispStrobe/CrispChess/blob/0d01798daf9661076675f8505b4cc6995a6529da/LICENSE)
are retained under `.runtime/public-training-139/source`. Its SHA-256 is
`0551aa60986335849398b657d82ebd0f369509b585eb0ee8796be0a8773b1963`.
The extraction reads FEN and `correctMove` pairs in source order, assigns
`crisp-001` through `crisp-021`, and declares a checkmate objective only when
the legal move actually ends in mate. Its normalized CSV SHA-256 is
`0867d9a7821b2d91782080f3469814e91240fca50300ee1974f39572634a9591`.
A deterministic extraction found 21 candidate FEN/move pairs. One is a
verified immediate mate; the other 20 have unverified source objectives and
are excluded. No source coaching prose is copied. The original MIT notice is
stored with the collection and included in task exports.

The separately authored CC0 canonical collection is a local source, rather
than a remote download. It contains these direct prompts and explicitly
validated examples:

| Task | Prompt FEN | Objective | Supplied UCI lines |
| --- | --- | --- | --- |
| Queen mate | `7k/8/6K1/2Q5/8/8/8/8 w - - 1 2` | Checkmate | `c5f8`, `c5c8` |
| Rook mate | `7k/8/6K1/8/8/8/8/R7 w - - 0 1` | Checkmate | `a1a8` |
| Pawn promotion | `8/P7/8/8/8/8/8/k6K w - - 0 1` | Legal promotion | `a7a8q`, `a7a8r`, `a7a8b`, `a7a8n` |
| King and pawn | `8/8/8/8/4k3/8/4P3/4K3 w - - 0 1` | Legal line | `e2e3` |

The local prepared CSVs and manifests are under `.runtime/public-training-139`.
They were imported into an isolated validation database only. Production
activation and playable practice remain outstanding.
