# Running NaiBra on Windows

Keep two PowerShell terminals open.

## Backend

```powershell
cd "$env:USERPROFILE\Downloads\backend-24-antennas"
powershell -ExecutionPolicy Bypass -File .\start-backend.ps1
```

Add `-Setup` on a fresh installation. Desktop storage uses `data/desktop.sqlite3`. Add `-Mongo` to use your existing MongoDB environment instead. API: http://localhost:8001/docs.

## Android emulator

```powershell
cd "$env:USERPROFILE\Downloads\naibra-app\naibra-app"
powershell -ExecutionPolicy Bypass -File .\start-frontend.ps1 -Android
```

The emulator reaches the PC at `http://10.0.2.2:8001/api`. Add `-Setup` to install frontend dependencies on a fresh installation. Omit `-Android` for the web app at http://localhost:8081. Use `-Mobile` for a physical phone; both devices must share a network. Optional `-ApiUrl http://YOUR_PC_IP:8001/api` overrides the API URL.

## Scans

- Simulated twin uses the original coloured dot cloud, scores out of 100, Full 60-second and Quick 12-second timing.
- Wired selects real scanner capture. Failed hardware scans do not silently become simulations.
- Bluetooth selects the hardware path, but the existing capture driver only implements wired acquisition.
- Developer mode has optional true X/Y/Z coordinates in cm. Origin is the base centre; +Y toward RX5–8, +X clockwise from +Y viewed from above, +Z upward. The point must lie inside the 8 cm dome.
- True coordinates are saved separately and displayed as an opaque blue cross. They do not alter reconstruction.

After backend code updates, stop with Ctrl+C and restart. Reload or restart Expo for frontend updates.

See RESTORATION_REVIEW.md for the restoration audit and checks. Saved records were not rewritten; earlier unscored records display an unavailable score rather than a dot count.

## Hardware thermal dot display

New real scans convert DMAS-CF field voxels directly into the original dome dot renderer. The stored raw intensity and position are preserved. Relative intensity determines colour and size: red >=75%, orange >=45%, green >=20%, blue >=5% of the scan peak; smaller values are omitted. The existing confidence gate still applies. Colours represent relative reconstructed signal, not clinical safety or severity. No radial halo or artificial positions are added. Simulated colours/scores/timing and the opaque pink reference star are unchanged. Restart the backend and reload the app; capture a new hardware scan to obtain all intensity bands (older stored scans only contain the previously selected voxels).

Update 2026-09-16: Valid low-confidence DMAS fields are now displayed with an explicit inconclusive-preview notice. Confidence calculation and confirmed peak output remain unchanged. Earlier scans saved with zero display dots need a new capture to store the complete field display; saved scans are not rewritten using current calibration.
