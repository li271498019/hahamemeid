"""Daily Season 1 operations for one dayIndex (admin automation).

Runs at the 08:00 Beijing day boundary. Stages, each attempted
independently so one failure does not silently cancel the others:
  0. Snapshot: find the snapshot block, wait 15 confirmations, replay
     PointsChanged, compute the Merkle root + manifest, run the precheck.
  1. Publish root (setDayRoot): only if precheck.ok and remainingBlocks > 0.
     Re-checks the 256-block window live and never publishes a day twice.
  2. Task pack: generate the canonical JSON for the snapshot block, write
     it to /opt/haha-season1/day-taskpacks/, then setTaskPack on-chain.
  3. Fulfill the previous day's frozen batch (adminMint + attestFulfillment),
     one order at a time, only when that day has Pending orders. Day 20781
     (the first day) has no previous day, so this stage is skipped.

Writes a full JSON report to /opt/haha-season1/day-ops/ and prints it.
Nothing is sent when its gate fails. Never logs a private key.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, "/opt/haha-season1")
sys.path.insert(0, "/opt/haha-indexer")
sys.path.insert(0, "/opt/haha-season1/admin")

from admin_tx import AdminTxError
from snapshot_day import run_snapshot
from publish_root import publish_root
from gen_taskpack import generate_taskpack
from publish_taskpack import publish_taskpack
from fulfill import fulfill_day

OUTDIR = "/opt/haha-season1/day-ops"
FIRST_DAY = 20781
LAST_DAY = 20795
SEASON_START_TS = 1795478400  # 2026-11-24T00:00:00Z
DAY_SECONDS = 86400


def day_for_utc_now():
    """(dayIndex, boundaryTs) for the current UTC day, or None outside the season."""
    now = datetime.now(timezone.utc)
    today_start = int(now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
    day_index = FIRST_DAY + (today_start - SEASON_START_TS) // DAY_SECONDS
    if day_index < FIRST_DAY or day_index > LAST_DAY:
        return None
    return day_index, SEASON_START_TS + (day_index - FIRST_DAY) * DAY_SECONDS


def run_day(day_index, boundary_ts):
    """Run one day's operations. The retry deadline is boundary + 600s
    (08:10 Beijing): every admin tx retries until confirmed or that time.
    Once a stage succeeds it is never re-sent."""
    # Retry deadline: 08:10 Beijing = boundary (08:00 Beijing) + 10 min.
    deadline = int(boundary_ts) + 600
    report = {
        "ok": True,
        "dayIndex": int(day_index),
        "boundaryTs": int(boundary_ts),
        "retryDeadlineTs": deadline,
        "retryDeadlineBeijing": "08:10",
        "startedAt": datetime.now(timezone.utc).isoformat(),
        "stages": {},
    }
    snapshot = None
    # Stage 0: snapshot.
    try:
        snapshot = run_snapshot(day_index, boundary_ts)
        report["stages"]["snapshot"] = {"ok": bool(snapshot.get("ok")), **snapshot}
        if not snapshot.get("ok"):
            report["ok"] = False
    except Exception as exc:
        report["stages"]["snapshot"] = {"ok": False, "error": str(exc)}
        report["ok"] = False
    # Stage 1: publish root (needs a good snapshot).
    if snapshot and snapshot.get("ok"):
        try:
            result = publish_root(snapshot, deadline=deadline)
            report["stages"]["publishRoot"] = {"ok": True, **result}
        except AdminTxError as exc:
            report["stages"]["publishRoot"] = {"ok": False, "error": str(exc)}
            report["ok"] = False
    else:
        report["stages"]["publishRoot"] = {
            "ok": False, "skipped": True, "reason": "snapshot not ok"}
    # Stage 2: task pack (needs the snapshot block + hash).
    if snapshot and snapshot.get("ok"):
        try:
            pack = generate_taskpack(
                day_index, int(snapshot["snapshotBlock"]), snapshot["snapshotBlockHash"])
            report["stages"]["taskPack"] = {"ok": True, **pack}
            try:
                pub = publish_taskpack(day_index, pack["taskPackHash"], pack["path"],
                                       deadline=deadline)
                report["stages"]["publishTaskPack"] = {"ok": True, **pub}
            except AdminTxError as exc:
                report["stages"]["publishTaskPack"] = {"ok": False, "error": str(exc)}
                report["ok"] = False
        except Exception as exc:
            report["stages"]["taskPack"] = {"ok": False, "error": str(exc)}
            report["ok"] = False
    else:
        report["stages"]["taskPack"] = {
            "ok": False, "skipped": True, "reason": "snapshot not ok"}
    # Stage 3: fulfill the previous day (independent of today's snapshot).
    if day_index > FIRST_DAY:
        try:
            result = fulfill_day(day_index - 1, deadline=deadline)
            report["stages"]["fulfillPrevDay"] = {"ok": True, **result}
            if result.get("stopped"):
                report["ok"] = False
        except Exception as exc:
            report["stages"]["fulfillPrevDay"] = {"ok": False, "error": str(exc)}
            report["ok"] = False
    else:
        report["stages"]["fulfillPrevDay"] = {
            "ok": True, "skipped": True, "reason": "first day, no previous batch"}
    report["finishedAt"] = datetime.now(timezone.utc).isoformat()
    os.makedirs(OUTDIR, exist_ok=True)
    path = os.path.join(OUTDIR, "report-day%d.json" % day_index)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    report["reportPath"] = path
    return report


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", type=int, default=None,
                    help="dayIndex; omit to use today's UTC day")
    ap.add_argument("--boundary-ts", type=int, default=None,
                    help="day-boundary timestamp (UTC 00:00); omit to derive from --day")
    args = ap.parse_args()
    if args.day is None:
        derived = day_for_utc_now()
        if derived is None:
            print(json.dumps({"ok": False, "error": "today is outside the season"}, indent=2))
            sys.exit(2)
        day_index, boundary_ts = derived
    else:
        day_index = args.day
        boundary_ts = args.boundary_ts
        if boundary_ts is None:
            if day_index < FIRST_DAY or day_index > LAST_DAY:
                print(json.dumps({"ok": False, "error": "day outside the season"}, indent=2))
                sys.exit(2)
            boundary_ts = SEASON_START_TS + (day_index - FIRST_DAY) * DAY_SECONDS
    report = run_day(day_index, boundary_ts)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    sys.exit(0 if report.get("ok") else 2)
