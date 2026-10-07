"""Fail on new dependency findings; report narrowly reviewed exceptions explicitly."""

import argparse
from datetime import date
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def review_findings(report, exceptions, today):
    blocked, accepted = [], []
    for package in report["dependencies"]:
        for vulnerability in package.get("vulns", []):
            finding = (package["name"], package["version"], vulnerability["id"])
            exception = next(
                (
                    item
                    for item in exceptions
                    if (item["package"], item["version"], item["id"]) == finding
                    and date.fromisoformat(item["expires"]) >= today
                ),
                None,
            )
            (accepted if exception else blocked).append(finding)
    return sorted(set(blocked)), sorted(set(accepted))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=ROOT / "output/python-audit.json")
    args = parser.parse_args()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    # Prevent a failed scan from accidentally reusing yesterday's report.
    args.report.unlink(missing_ok=True)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip_audit",
            "-r",
            str(ROOT / "healer/requirements.txt"),
            "--no-deps",
            "--disable-pip",
            "--timeout",
            "20",
            "--format",
            "json",
            "--output",
            str(args.report),
        ],
        check=False,
    )
    if result.returncode not in (0, 1) or not args.report.exists():
        print("Dependency scan failed; no security pass is claimed.")
        return 2
    report = json.loads(args.report.read_text(encoding="utf-8"))
    exceptions = json.loads((ROOT / "docs/dependency-exceptions.json").read_text(encoding="utf-8"))
    blocked, accepted = review_findings(report, exceptions, date.today())
    for finding in accepted:
        print("REVIEWED EXCEPTION (still reported):", *finding)
    for finding in blocked:
        print("BLOCKING:", *finding)
    print(
        f"{len(blocked)} blocking findings; {len(accepted)} reviewed exceptions. Report: {args.report}"
    )
    return 1 if blocked or (result.returncode == 1 and not accepted) else 0


if __name__ == "__main__":
    raise SystemExit(main())
