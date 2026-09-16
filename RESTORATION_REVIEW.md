# Restoration review

Restored the original frontend UI from its Git version for Home, Repository, Compare, Dome, Scan result hero, Scan result domes, Scan countdown, and the full scored PDF report. Retained the existing direct icon imports used by the installed app.

## Retained requested changes

- Backend/frontend launch scripts, Python dependencies, optional desktop SQLite storage, and emulator/API address correction.
- Explicit simulated versus hardware routing. Failed hardware capture does not become simulation.
- Original software twin severity dots and 0–100 score calculation, with Full 60-second and Quick 12-second timing.
- Developer true X/Y/Z input in cm, saved reference, separate opaque blue cross, and peak distance where available.
- Null scores from unscored hardware records display as unavailable instead of using dot counts.
- Existing hardware acquisition/cancellation integration remains; reconstruction physics was not edited in this task.

## Restored UI

- Original score labels and verdict colours, side scores, metrics and comparison rows.
- Original dot sizes/colours and High/Medium/Low/Baseline filters, tap visibility and long-press isolation.
- Original countdown ring, progress and antenna status text.
- Original scored report layout, sections and metrics. Unscored records use the compatible localization report.
- Original pre-existing pet assets, navigation and build optimizations were preserved; they predate this task.

The simulation no longer substitutes localization-dot counts for scores. Previously saved records are unchanged; records created during the temporary unscored simulation retain their original null scores.

A backup of the eight screens/report before this restoration is in `restoration_backup/`.

Verification: API/integration/localization tests pass; Full/Quick timing and developer coordinate submission checks pass; restored comparison deltas and full scored report generation pass. Full TypeScript checking still reports an existing RepositoryScreen label/never typing error. The Android export is checked separately.
Android export completed successfully: 3,959 modules bundled. Visual emulator verification and physical scanning were not performed during restoration.
