# Delay calibration audit

**Result: the current delay calibration cannot be independently verified from the saved files. No calibration values were changed.**

The corrected reconstruction now includes cable/switch delay consistently. Remaining localization errors cannot be fixed by selecting the largest empty-scan peak and calling it direct propagation.

## Saved empty scans

- Pairs examined: 64; currently used: 56.
- Median absolute baseline-peak mismatch: 0.041 ns; maximum: 1.966 ns.
- Pairs with mismatch above 0.25 ns: 19.
- Pairs whose dominant peak moves over 0.25 ns between baseline and two empty scans: 3.

These are consistency checks, not proof of direct-path calibration. The 0.25 ns flag is a bandwidth-based diagnostic scale, not a 1 cm accuracy criterion.

| Pair | Expected direct peak (ns) | Baseline strongest peak (ns) | Absolute mismatch (ns) | Used |
|---|---:|---:|---:|---|
| TX6-RX5 | 7.409 | 9.375 | 1.966 | True |
| TX2-RX5 | 6.271 | 8.009 | 1.738 | True |
| TX7-RX1 | 6.291 | 7.906 | 1.614 | True |
| TX7-RX5 | 6.478 | 7.492 | 1.014 | True |
| TX4-RX1 | 7.057 | 8.030 | 0.973 | True |
| TX8-RX1 | 6.395 | 7.305 | 0.911 | True |
| TX5-RX4 | 6.643 | 7.430 | 0.786 | True |
| TX6-RX1 | 7.740 | 8.485 | 0.745 | True |

## Historical component measurements

| Saved file | Strongest peak (ns) |
|---|---:|
| direct_thru_test | 0.000 |
| tx_isolation_test | 1.697 |
| rx_isolation_test | 1.697 |
| dualboard_tx1_rx1_open | 19.599 |
| dualboard_tx1_rx1__jumper | 4.346 |

These files do not record the exact wiring, terminations, or calibration reference planes. Comparing their peak times cannot establish which component caused an artifact, or provide a verified per-pair correction.

## Required physical verification

1. Record the current VNA calibration reference planes and actual port-to-antenna mapping.
2. Measure a known, characterized through connection between the selected TX and RX feed paths, replacing the antennas, while keeping both switch paths and feed cables in the measurement. Document the connection delay and exact wiring.
3. Repeat the connected measurement with the channel fixed, then after switching away and back. This separates repeatability from fixed path delay.
4. Start with TX1-RX1, then a flagged pair such as TX6-RX5. Extend calibration to other paths only after this method is checked.
5. Subtract the independently known through-connection delay to estimate the feed-chain delay. Antenna phase response remains a separate calibration requirement.
6. Reconnect the antennas, obtain a fresh baseline, and validate with target positions that were not used to fit calibration.

Do not automatically overwrite the current 64 offsets using the strongest empty-dome peaks. No new hardware measurement was performed by this audit.
