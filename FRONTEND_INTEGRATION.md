# DMAS-CF integration

Frontend: C:/Users/prasr/Downloads/naibra-app/naibra-app.

## Connect

Run the existing FastAPI service on port 8000, bound to 0.0.0.0, using its existing MongoDB environment. Use one Uvicorn worker for the physical scanner; the acquisition lock is process-local.

Set EXPO_PUBLIC_API_URL to the computer's reachable LAN address including /api (for example http://192.168.1.40:8000/api), then restart Expo. Otherwise the development app derives the host from Expo's host URI, falling back to 10.0.2.2 on Android or localhost on web/iOS. Physical phones and release builds should use an explicit reachable address. Phone and computer need network access to each other on port 8000.

Connect the wired scanner through the bridge screen. Scan requests allow ten minutes, ordinary requests 15 seconds. Missing hardware returns HTTP 503 instead of simulated locations.

## Results

New scans use algorithm dmas-cf, display_mode localization, and capture_scope shared. Reconstruction physics and the existing tissue permittivity assumption are unchanged; the air diagnostic output is not the displayed field.

Dots come exclusively from the full DMAS-CF voxel field. Coordinates are divided by the physical dome radius (8 cm), and displayed antennas use the same reconstruction geometry. Dots carry raw intensity and source dmas-cf, with uniform color and size and no severity category.

The existing SNR confidence gate is retained. Confident fields display voxels at or above 50% of peak intensity, capped at 4096 deterministic samples. This threshold selects displayed field shape. Results include peak_location_cm, selected_voxel_count, and sampled. Low confidence is inconclusive; empty/failed reconstruction is unavailable. Scores are null.

There is one physical capture per scan. Left and right views share it; independent bilateral acquisition is not implemented. Leaving the view ignores late UI responses but does not abort physical acquisition. Its saved result may still appear in history.

Old records are preserved and labeled legacy. Their untagged severity dots are hidden; capture a new scan to display locations. The severity threshold recomputation endpoint returns HTTP 410.

## Verification

Backend: test_dmas_localization.py and test_reconstruction_timing.py pass 15 tests covering coordinates, confidence, malformed fields, marker limits, scan routing, errors, concurrency, and reconstruction timing. Tests use synthetic inputs and mocked infrastructure without acquiring hardware or writing MongoDB.

Frontend: frontend_changes/test.cjs covers URL selection, deduplication, retry, acquisition, rescan, cancellation, errors, and report output. frontend_changes/check.cjs compares TypeScript diagnostics against the original frontend. Existing unrelated TypeScript errors remain, so a full clean build is not established. Live scanner and visual app testing remain outstanding.

frontend_changes/apply.ps1 checks original hashes, copies only prepared files into the external frontend folder, and verifies their hashes. Writing that folder requires filesystem approval.
