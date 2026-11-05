"""Optional, bounded adapters for Semgrep CE and OSV-Scanner v2.

Only reconstructed added diff lines and a supplied dependency manifest are
written to temporary files. Pull-request source code is never executed.
"""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .models import Finding, ReleaseRequest, Severity

logger = logging.getLogger(__name__)
SCANNER_TIMEOUT_SECONDS = 45
MAX_OUTPUT_CHARS = 2_000_000


def _added_source(patch: str) -> str:
    """Extract added lines from a unified diff; accept raw source as a fallback."""
    added: list[str] = []
    saw_hunk = False
    for raw in patch.splitlines():
        if raw.startswith("@@"):
            saw_hunk = True
        elif raw.startswith(("+++", "---")):
            continue
        elif raw.startswith("+") and saw_hunk:
            added.append(raw[1:])
    return "\n".join(added) if saw_hunk else patch


def _run_json(command: list[str], cwd: Path) -> dict[str, Any] | None:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=SCANNER_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("Optional scanner could not complete: %s", type(exc).__name__)
        return None

    output = completed.stdout[:MAX_OUTPUT_CHARS]
    if not output.strip():
        logger.warning("Optional scanner returned no JSON output (exit %s)", completed.returncode)
        return None
    try:
        parsed = json.loads(output)
    except json.JSONDecodeError:
        logger.warning("Optional scanner returned invalid JSON (exit %s)", completed.returncode)
        return None
    return parsed if isinstance(parsed, dict) else None


def _semgrep_severity(value: str) -> Severity:
    return {
        "ERROR": Severity.HIGH,
        "WARNING": Severity.MEDIUM,
        "INFO": Severity.LOW,
    }.get(value.upper(), Severity.MEDIUM)


def scan_semgrep(request: ReleaseRequest) -> list[Finding]:
    """Run Semgrep CE on temporary files containing only added diff lines."""
    executable = shutil.which("semgrep")
    if not executable:
        return []

    findings: list[Finding] = []
    with tempfile.TemporaryDirectory(prefix="releaseguard-semgrep-") as temp:
        root = Path(temp)
        targets: list[Path] = []
        for index, changed in enumerate(request.changed_files):
            source = _added_source(changed.patch)
            if not source.strip():
                continue
            suffix = Path(changed.path).suffix
            suffix = suffix if suffix and len(suffix) <= 12 else ".txt"
            target = root / f"changed_{index}{suffix}"
            target.write_text(source, encoding="utf-8")
            targets.append(target)

        if not targets:
            return []
        payload = _run_json(
            [executable, "scan", "--config", "auto", "--json", "--metrics=off",
             "--no-git-ignore", str(root)],
            root,
        )
        if not payload:
            return []

        for item in payload.get("results", []):
            if not isinstance(item, dict):
                continue
            extra = item.get("extra") or {}
            if not isinstance(extra, dict):
                extra = {}
            path = str(item.get("path") or "")
            source_path = None
            try:
                source_path = Path(path).name
            except (TypeError, ValueError):
                pass
            try:
                index = int(source_path.removeprefix("changed_").split(".", 1)[0])
                original_file = request.changed_files[index].path
            except (ValueError, IndexError, AttributeError):
                original_file = None
            start = item.get("start") or {}
            line = start.get("line") if isinstance(start, dict) else None
            message = str(extra.get("message") or item.get("check_id") or "Semgrep finding")
            check_id = str(item.get("check_id") or "semgrep")
            findings.append(Finding(
                agent="security_analysis",
                severity=_semgrep_severity(str(extra.get("severity") or "WARNING")),
                category="static_analysis",
                title=check_id[:200],
                description=message[:1000],
                recommendation="Review the Semgrep finding and remediate or document an approved exception.",
                file=original_file,
                line=line if isinstance(line, int) and line > 0 else None,
                evidence=str((extra.get("lines") or message))[:500],
                confidence=0.9,
                source="semgrep",
            ))
    return findings


def _osv_severity(vulnerability: dict[str, Any]) -> Severity:
    severity_items = vulnerability.get("severity") or []
    scores: list[float] = []
    for item in severity_items:
        if not isinstance(item, dict):
            continue
        raw = str(item.get("score") or "")
        try:
            scores.append(float(raw))
        except ValueError:
            continue
    if not scores:
        return Severity.HIGH
    score = max(scores)
    if score >= 9.0:
        return Severity.CRITICAL
    if score >= 7.0:
        return Severity.HIGH
    if score >= 4.0:
        return Severity.MEDIUM
    return Severity.LOW


def scan_osv(request: ReleaseRequest) -> list[Finding]:
    """Run OSV-Scanner v2 against the supplied Python requirements manifest."""
    executable = shutil.which("osv-scanner")
    manifest = request.dependency_manifest
    if not executable or not manifest or request.dependency_ecosystem.lower() not in {
        "python", "pip", "requirements.txt"
    }:
        return []

    with tempfile.TemporaryDirectory(prefix="releaseguard-osv-") as temp:
        root = Path(temp)
        lockfile = root / "requirements.txt"
        lockfile.write_text(manifest, encoding="utf-8")
        payload = _run_json(
            [executable, "scan", "source", "--format", "json",
             f"--lockfile={lockfile}"],
            root,
        )
        if not payload:
            return []

    findings: list[Finding] = []
    for result in payload.get("results", []):
        if not isinstance(result, dict):
            continue
        for package_result in result.get("packages", []):
            if not isinstance(package_result, dict):
                continue
            package = package_result.get("package") or {}
            if not isinstance(package, dict):
                package = {}
            name = str(package.get("name") or "Unknown package")
            version = str(package.get("version") or "unknown version")
            for vulnerability in package_result.get("vulnerabilities", []):
                if not isinstance(vulnerability, dict):
                    continue
                vuln_id = str(vulnerability.get("id") or "OSV advisory")
                aliases = vulnerability.get("aliases") or []
                alias_text = ", ".join(str(alias) for alias in aliases[:5])
                summary = str(vulnerability.get("summary") or vulnerability.get("details") or "")
                evidence = f"{name}@{version} | {vuln_id}"
                if alias_text:
                    evidence += f" | aliases: {alias_text}"
                findings.append(Finding(
                    agent="dependency_analysis",
                    severity=_osv_severity(vulnerability),
                    category="known_vulnerability",
                    title=f"{name}: {vuln_id}"[:200],
                    description=(summary or "OSV-Scanner reported a known dependency vulnerability.")[:1000],
                    recommendation="Upgrade to a fixed version where available and rerun the dependency scan.",
                    file="requirements.txt",
                    evidence=evidence[:500],
                    confidence=0.98,
                    source="osv_scanner",
                ))
    return findings
