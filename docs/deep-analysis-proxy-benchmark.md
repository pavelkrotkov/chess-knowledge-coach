# Synthetic deep-search budget proxy

Run `uv run python scripts/benchmark_deep_proxy.py` on a machine with Stockfish
at `/usr/games/stockfish`. The script uses only six hard-coded synthetic boards:
three tactical examples, both sides of one middlegame, and an endgame. Each
sample clears the engine hash, uses one thread and a 64 MiB hash, searches the
best three roots together, then separately searches one forced legal root.
The 200,000-node, eight-second-per-search result is a longer reference, not
truth or a measure of playing accuracy. This small nonrepresentative sample
cannot establish reliability, strength or training benefit.

Observed on Hermes with Stockfish 17.1 and load averages 7.65 / 7.47 / 7.95;
other work was running. Times are wall seconds for both searches combined. The
best nodes are the shared MultiPV search total, counted once. The played nodes
are separate; Stockfish can slightly overshoot a requested node limit or stop
early. Each entry is `best nodes / played nodes / seconds / disagrees`, where
`yes` means the best root differs from the 200,000-node result for that board.

| Synthetic board | 5,000 nodes, 1 s | 20,000 nodes, 1 s | 50,000 nodes, 2 s | 200,000 nodes, 8 s reference |
| --- | --- | --- | --- | --- |
| Tactical hanging piece | 5,001 / 5,008 / 1.275 / no | 20,007 / 20,018 / 0.217 / no | 50,000 / 50,054 / 0.294 / no | 200,049 / 200,209 / 0.962 |
| Tactical fork | 5,005 / 5,001 / 0.154 / yes | 20,019 / 19,690 / 0.346 / yes | 50,058 / 49,497 / 0.664 / no | 200,170 / 199,356 / 0.826 |
| Tactical mate | 5,002 / 5,001 / 0.123 / no | 20,015 / 20,018 / 0.260 / no | 22,796 / 50,038 / 0.546 / no | 22,796 / 200,066 / 0.712 |
| Middlegame, White | 5,001 / 5,000 / 0.174 / yes | 20,008 / 20,001 / 0.741 / yes | 50,064 / 50,035 / 1.206 / no | 200,068 / 200,173 / 5.488 |
| Middlegame, Black | 5,001 / 5,001 / 0.107 / yes | 20,001 / 20,005 / 0.633 / no | 50,033 / 50,036 / 1.462 / no | 200,188 / 200,011 / 6.800 |
| Endgame | 5,002 / 5,000 / 0.173 / no | 20,020 / 20,005 / 0.273 / yes | 50,028 / 50,012 / 0.510 / no | 200,083 / 200,171 / 0.952 |

The automatic worker defaults to 50,000 nodes and two seconds **per search**,
three alternatives, one thread, at most four decisions and four selected games
per invocation, and up to 100 scanned games. The earlier cheap pass defaults to
10,000 nodes and one second per search with one best line; both tiers also use a
separate forced-played search. Their settings do not establish relative accuracy.
This modest starting point limits
work and preserves responsiveness; it is not an accuracy guarantee. Three of
six 20,000-node best roots disagreed with this longer reference, while none of
the 50,000-node roots did in this sample. The 50,000-node paired searches took
0.294–1.462 seconds in this run; four decisions are allowed per invocation. The longer result can itself be wrong.
Engine startup, move reconstruction and database work add overhead beyond the
two search limits. The engine controls node/time enforcement; these are not
hard process deadlines. Search results remain estimates and create no mastery
evidence. Insufficient and unstable results are reported rather than promoted.
