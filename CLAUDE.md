# CLAUDE.md

## Project

Hybrid FTP Application for CS494 / Internetworking Protocols Project 1.

Build a Python CLI client-server application with:

- TCP control channel for FTP commands, replies, authentication, and session state.
- UDP data channel for file payloads.
- Custom reliable UDP layer built from scratch.
- Excellent-level rubric target: binary transfers, directory support, active/passive modes, concurrency, sliding window/flow control, SHA-256 integrity verification, demo evidence, and full technical report.

## GSD Workflow

Planning artifacts live in `.planning/` and are intentionally local-only per user preference.

Before coding a phase:

1. Read `.planning/PROJECT.md`.
2. Read `.planning/REQUIREMENTS.md`.
3. Read `.planning/ROADMAP.md`.
4. For the current phase, run `/gsd:discuss-phase N` then `/gsd:plan-phase N` unless the user explicitly asks for a quicker route.

Current next step: `/gsd:discuss-phase 1`.

## Hard Constraints

- Use only Python standard-library modules unless the user explicitly approves otherwise and the assignment permits it.
- Do not use `ftplib`, `pyftpdlib`, KCP, QUIC, libcurl FTP wrappers, or any third-party transfer library.
- Do not transfer file payload over TCP. TCP is for control only.
- Keep UDP reliability logic custom and explainable.
- Keep code readable for oral defense; prefer explicit state over clever abstractions.
- Use binary file IO for binary transfers.
- Use a server-root sandbox for all filesystem operations.
- Write received files to temporary files and rename only after successful transfer verification.

## Demo/Defense Priorities

- Log commands, reply codes, client IPs, session state, ACKs, retransmissions, window movement, and transfer progress.
- Preserve evidence for the report: upload/download logs, hash comparisons, connected-client table, concurrent session test.
- Maintain a GenAI usage/refinement log for the mandatory appendix.

