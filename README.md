# Brand Threat Monitor

Local desktop application for collecting Meta Ad Library ads, reviewing possible brand impersonation and recording human decisions. Built with Python, Tkinter and SQLite. The interface is in English; reports to Meta are submitted manually.

## Requirements and installation

- Python **3.11 or newer**, with Tkinter.
- Internet access for collection and web image previews.
- Dependencies declared in `pyproject.toml`: `meta-ads-collector`, Pillow and timezone data.

From the project root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe iniciar_interfaz.py
```

Run commands from the project root to use its local workspace. An alternative workspace can be selected with `iniciar_interfaz.py --workspace PATH`.

## Search setup

1. Add or edit a country and search criteria.
2. Enable the rows you want to execute. Disabled rows are skipped.
3. Set **Days to review** and collection limits.
4. Select **Run searches**. **Stop** cancels collection while preserving received results.

The supplied example profile uses **Sample** in Colombia. Replace it with your search criteria. Search rows, enabled states, days and limits are saved automatically in `data/search_list.json` and restored when the application opens. **Export search list** saves a separate copy; **Load search JSON** accepts editable search lists or profile manifests.

**Days to review** defaults to **1**, meaning today in `America/Bogota`. Larger values include today and the preceding days. Date boundaries are inclusive and apply to the ad start date after collection.

### Automatic repeat

The limit fields accept typed numbers without arrow controls. Enable **Repeat automatically** and enter **Every (h)** to schedule repeated batches while the application remains open. Default frequency is 24 hours; values from 1 to 8760 hours are supported; intervals below one hour are rejected. The next interval starts after the current batch finishes, preventing overlap. Enabling repeat schedules the first automatic run after that interval; **Run searches** starts immediately. **Stop** cancels the current search and turns repeat off. Repeat settings are saved with the search list; restoring an enabled setting schedules a fresh interval from application startup. There is no background execution after closing the application.

### Collection limits

Each enabled search receives its own budget. The first applicable limit stops collection.

| Control | Default | Allowed range |
| --- | --- | --- |
| Max ads | 100 | 1-100000 |
| Max pages | 20 | 1-10000 |
| Total seconds | 120 | 1-86400 |
| Idle seconds | 45 | 1-3600 |

**Max ads** counts scanned ads before date filtering, not accepted matches. **Max pages** counts successfully fetched result pages, including empty pages. Idle time measures time since the last received ad; an empty page does not reset it. Existing saved configurations retain their values until edited. Changes made during execution apply to subsequent executions.

## Ad review

Saved results in the local SQLite database load automatically on startup and when entering **Ad review**. A copied `results.json` is not imported automatically: use **Load results JSON** below the queue to select and import it. Imports clear view filters, preserve existing decisions and skip identical runs without duplicates. Choose the collector result file, not `run_summary.json`; the source file is not modified.

- The card uses fixed publisher and ad image panels, each occupying one quarter of the width. Text and metadata occupy the remaining half with independent scrolling.
- Web images load in the background. **Retry web images** retries unavailable previews. Video thumbnails are supported; videos are not played inside the card.
- Click the publisher photo to open its Facebook profile, or the ad image to open its Meta Ad Library page.
- **External links in this ad** lists detected destinations and links in ad text across creatives. External destinations open only when clicked.
- Click the ad start-date column to switch between newest-first and oldest-first order.
- **Show dates in UTC** switches the list and card between UTC and Colombia time (UTC-05:00). This changes presentation only. Review/history From/To filters use observation dates or run start dates, according to the view.
- **All information** shows readable fields, diagnostics, observations and case history without displaying raw JSON blocks.

### Classification and lists

| Action | Effect |
| --- | --- |
| Spam (this ad) | Adds the individual ad to the brownlist in the case scope. |
| Flag advertiser | Adds the publisher to the global blacklist; requires a known publisher ID and an existing local evidence file. |
| Keep pending | Records a pending decision without adding a list entry. |
| Clear unreviewed | Removes eligible unreviewed entries matching the current queue filters without assigning a category or deleting history. A later observation can return an ad to the queue. |

Classification is saved directly without confirmation or a reason dialog. Standard reasons and audit events are recorded automatically. **Clear unreviewed** retains its separate confirmation. Correction workflows require justification and preserve earlier evidence and events.

Whitelist/blacklist entries identify publishers; brownlist entries identify individual ads. Conflicts require explicit resolution. Existing findings prioritize review; they do not automatically confirm fraud or submit reports. **Manage lists** supports administration and JSON/CSV exchange.

The UI uses `local_operator` as its internal audit actor. Local evidence can be previewed and attached to cases as managed copies with hashes. Web previews are not automatically stored as evidence. History, corrections, manual report tracking and case export are available from the review interface.

## Collection behavior and coverage

The tested Meta endpoint did not reliably honor requested date ranges. The application therefore collects without server-side date filters and applies local post-filtering to the available capture. Encountering an old ad does not stop collection.

The process preserves received ads, separates invalid records and date exclusions, deduplicates accepted ads, then sorts matches by ad start time. Only accepted ads enter the review database; excluded content remains in result diagnostics. Received data is saved after completion, controlled cancellation or a handled source failure. An abrupt application/process termination before final persistence can lose in-memory results.

**Results are bounded and coverage is partial.** Increasing budgets or sorting results does not guarantee all matches or equivalence with the manual Library. Image URLs may expire or become inaccessible; retry or open the original ad when necessary.

## Local files

| Path | Purpose |
| --- | --- |
| `profiles/example.json` | Neutral Sample search profile. |
| `profiles/searches.json` | Example profile manifest. |
| `profiles/local/` | Private local profiles. |
| `lists/` | Whitelist, blacklist and brownlist JSON inputs. |
| `data/search_list.json` | Automatically saved UI searches and limits. |
| `data/database/monitor.sqlite3` | Runs, ads, observations, cases, list decisions and audit history. |
| `data/results/<run_id>/results.json` | Capture, matches, diagnostics, applied limits and stop reason. |
| `data/results/<run_id>/run_summary.json` | Counts, connector statistics and persistence outcome. |
| `data/evidence/` | Managed local evidence. |
| `data/exports/` | Export destination used by the application. |
| `data/backups/` | Default backup location. |

Runtime data and private profiles are excluded from Git. Files under `lists/` and the public example profile are versioned; keep private information out of those files. The functional requirements PDF is kept in the ignored documentation directory.

## Command line

Preview a search without contacting Meta:

```powershell
.\.venv\Scripts\python.exe ejecutar_busqueda.py --dry-run
```

Run the Sample profile with explicit budgets:

```powershell
.\.venv\Scripts\python.exe ejecutar_busqueda.py --profile profiles/example.json --max-scan 100 --max-pages 20 --max-duration 120 --idle-timeout 45 --actor local_operator
```

The standalone search CLI defaults to 30 scanned ads; its other budget defaults match the table above. Use `--manifest profiles/searches.json` to run a manifest, or `--output PATH` for a single query's result file.

Discover administration, history, exports and backup commands:

```powershell
.\.venv\Scripts\python.exe -m brand_threat_monitor --help
.\.venv\Scripts\python.exe -m brand_threat_monitor backup-workspace --help
.\.venv\Scripts\python.exe -m brand_threat_monitor restore-workspace --help
```

Workspace backups include the database, profiles, lists, saved searches and referenced local evidence. Restoration verifies integrity and writes to a new destination. Backups contain data, not application code, and may contain sensitive information.

## Verification and project references

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests/unit -q
.\.venv\Scripts\python.exe iniciar_interfaz.py --check
```

Latest recorded verification: **146 tests passed**. Test results do not establish complete Meta coverage.

- [Developer manual (PDF)](docs/Ad_monitor_Manual_del_desarrollador.pdf): architecture, methods, external connections, SQLite schema and maintenance (Spanish).
- `ROADMAP.md`: completion status of configurable collection limits.
- `docs/ARCHITECTURE.md`: module organization.
- `docs/META_REQUEST_RESEARCH.md`: source and request research.
- `URL_SEARCH_SPEC.md`: URL parsing and adaptation rules.
