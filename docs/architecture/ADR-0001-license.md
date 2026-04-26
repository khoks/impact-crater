# ADR-0001 — License: Business Source License 1.1

**Status:** Accepted
**Deciders:** Rahul Singh Khokhar
**Date:** 2026-04-25
**Phase:** scaffolding

## Context

Impact Crater is being open-sourced from day 1 in a public GitHub repository. The author wants three things from the license:

1. **Free self-hosting** — anyone should be able to run Impact Crater on their own hardware for personal, family, or internal team use without paying or asking permission.
2. **Protected commercial moat** — competitors should not be able to spin up a hosted Impact Crater service that competes with the author's eventual offering.
3. **Eventual full openness** — the protection is temporary; the code should become permissively licensed within a reasonable horizon.

## Decision

License Impact Crater under the **Business Source License 1.1**, with the following parameters:

- **Licensor:** Rahul Singh Khokhar
- **Licensed Work:** Impact Crater (© 2026 Rahul Singh Khokhar)
- **Additional Use Grant:** Free for self-hosted personal use, family use, or internal team use. Hosting Impact Crater as a paid third-party service that competes with the Licensor's offering is **not** permitted.
- **Change Date:** 2030-04-25 (four years from the project's first public commit)
- **Change License:** Apache License 2.0

The full license text lives in [`LICENSE`](../../LICENSE) at the repo root.

## Consequences

- **Self-hosters:** unlimited personal / family / team use. No registration, no key, no telemetry, no payment.
- **Forkers:** may fork, modify, and redistribute under the same BSL 1.1 terms; the same Additional Use Grant must apply downstream.
- **Hosted-service competitors:** blocked until 2030-04-25.
- **Contributors:** sign-off via DCO (or equivalent) will be expected once contribution is opened. License grant on contributions follows the project license.
- **On the Change Date** (or on the four-year anniversary of any specific version's first public release, whichever is first), the licensed terms automatically convert to Apache 2.0 for that version.
- **Trademarks** are not granted by the license. The "Impact Crater" name and any logo are reserved.

## Alternatives considered

- **Apache 2.0 from day 1.** Maximizes adoption but leaves no commercial moat; a competitor can launch a hosted service immediately. Rejected.
- **All-rights-reserved / proprietary.** Safest commercially, but contributors won't engage and the "self-hosted-first, open-source" positioning is lost. Rejected.
- **AGPL.** Forces hosted services to open their changes, but does not actually prevent hosted competition; many SaaS providers ship AGPL code happily. Rejected.

## Links

- LICENSE file: [`LICENSE`](../../LICENSE)
- Decision-log entry: D-002 in [`docs/decisions/DECISIONS_LOG.md`](../decisions/DECISIONS_LOG.md)
