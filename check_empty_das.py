"""
check_empty_das.py -- capture a SECOND empty-dome scan and run DAS
against the saved baseline. With nothing in the dome, this should come
back with no result / no confident peak. If it confidently reports a
target position with an empty dome, that's a real false-positive bug.

Run capture_baseline.py first (only needs to be redone if the physical
setup changes). Dome must be EMPTY for this too.

Usage:
    python check_empty_das.py
"""
from capture_labeled_scan import capture_one_sweep, print_scan_scores

print("Capturing fresh empty-dome scan...")
fresh = capture_one_sweep()

print_scan_scores(fresh)