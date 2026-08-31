# TICKET-4127: bramble-x leaderboard jump looks wrong

- **Filed:** 2026-08-13, support-ops (Priya N.)
- **Priority:** high -- vendor scorecards go out Friday
- **Component:** ticket-triage benchmark, August run

The August leaderboard (leaderboard.csv, and RESULTS.md) has **bramble-x at
rank 2 with 0.8112**. In the July run it was rank 4 at
0.7098 (docs/archive/RESULTS_2026-07.md). That is a big month-over-month
jump for a model the vendor hasn't updated since spring, and it doesn't match
what we see triaging with it day to day.

The one thing that did change on our side this cycle is the label
normalization update in `pipeline/normalize.py` (see docs/CHANGELOG.md,
2026-08-12 -- same day as the scoring run). I don't know the scoring internals,
but that's the only change on our side this cycle, so I suspect it's somehow
inflating bramble-x's numbers.

Can someone verify the scoring and re-issue the leaderboard before Friday?
I'd start with that normalize change.
