"""Validation script that suppresses devices judged as disconnected.

This does not change the NVDA add-on. It is an experiment based on the
current local samples:
- classic Bluetooth: prefer Win32 fConnected
- BLE / generic fallback: skip when DevNodeStatus contains DN_DEVICE_DISCONNECTED
"""

from __future__ import annotations

import sys

import experiment_bluetooth_connection_status as experiment


def collect_reportable_bluetooth_battery() -> list[tuple[str, int]]:
	reportable: list[tuple[str, int]] = []

	for row in experiment.collect_bluetooth_connection_experiment():
		if row["best_effort_connection"] == "disconnected":
			continue
		name = str(row["name"])
		battery = int(row["battery"])
		reportable.append((name, battery))

	return reportable


def main() -> int:
	sys.stdout.reconfigure(encoding="utf-8", errors="replace")
	results = collect_reportable_bluetooth_battery()
	if not results:
		print("No connected Bluetooth battery information is available.")
		return 1

	for name, battery in results:
		print(f"{name}: {battery}%")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
