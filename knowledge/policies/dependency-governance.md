# Dependency Governance

## Dependency pinning
Pin or constrain production dependencies and use a lockfile with hashes where the package ecosystem supports it. Review dependency updates and avoid floating unbounded versions in production.

## Vulnerability review
Check dependency manifests and lockfiles against a maintained vulnerability advisory source. Record package name, resolved version, advisory identifier, severity, and remediation version when available. Do not claim a dependency is vulnerable based only on a package name when its resolved version is unknown. Reference: https://osv.dev/

## Supply-chain provenance
Prefer trusted package registries, verify package provenance where supported, and review unexpected new dependencies. Keep build and release credentials scoped to the minimum required permissions. Reference: https://slsa.dev/
