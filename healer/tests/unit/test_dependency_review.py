from datetime import date

from scripts.audit_dependencies import review_findings


def test_exceptions_are_exact_and_expire():
    exception = {"package": "demo", "version": "1", "id": "CVE-known", "expires": "2026-11-06"}
    report = {
        "dependencies": [
            {"name": "demo", "version": "1", "vulns": [{"id": "CVE-known"}, {"id": "CVE-new"}]}
        ]
    }
    blocked, accepted = review_findings(report, [exception], date(2026, 10, 7))
    assert blocked == [("demo", "1", "CVE-new")]
    assert accepted == [("demo", "1", "CVE-known")]
    assert len(review_findings(report, [exception], date(2026, 11, 7))[0]) == 2
    report["dependencies"][0]["version"] = "2"
    assert len(review_findings(report, [exception], date(2026, 10, 7))[0]) == 2
