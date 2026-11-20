# Date filter experiment

Baseline pushed before the experiment: d8d4133.

Query: chivo; country: SV; requested date range: 2026-11-16 through 2026-11-17, inclusive, America/Bogota. The server still receives startDate on each page. Only the emergency date-mismatch stop was disabled for this run; local classification by date remains active.

Observed: 100 received ads, 10 requests/pages, 19 accepted ads (local start 2026-11-16), 81 excluded by date, no collector errors. The first ad was 1346032107580033 with start date 2026-05-09. Later pages contained in-range ads, proving that the first old ad is not a safe stopping point for this impressions-sorted query.

Local artifacts (excluded from Git): data/results/date_guard_experiment_20261117/results.json and run_summary.json. All received normalized ad content is available under received_ads, including available source fields and date decisions. Only in-range ads were imported into ads/observations; the full capture is also preserved inside the run payload.

Conclusions: keep bounded diagnostic collection available while investigating a server-side filter that actually works. Do not call zero accepted ads after an emergency stop an empty result. Do not claim full coverage: this run stopped at 100 ads. No chronological ordering has been established.

The working-tree experiment is not part of the pushed baseline. UI diagnostic mode is temporarily enabled by default; untick it to restore strict stopping. CLI requires --diagnostic.


## Follow-up: local post-filter as the normal pipeline

The current working tree no longer sends temporal min/max to the source. It retains every received ad, then applies an inclusive local start-date filter and sorts accepted results newest first. The diagnostic checkbox and first-old-ad emergency stop are no longer part of the normal workflow.

A separate chivo/SV run for 2026-11-16 to 2026-11-17 received 67 records, accepted 7 and excluded 60 before the 120-second total limit. The preserved partial capture was post-filtered and persisted to SQLite. Verified no server date range and descending start timestamps. Local artifact: data/results/post_filter_chivo_20261117/results.json. This bounded sample does not establish complete coverage or comparative recall against the earlier run.
