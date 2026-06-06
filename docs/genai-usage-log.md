# GenAI Usage and Code Refinement Log

This appendix log is maintained incrementally for the Hybrid FTP project. Each entry should preserve enough detail for the report and oral defense: what was asked, what the AI returned, what the human accepted or changed, what was rejected, and how the result was verified.

## Entry: 2026-06-04 — Project planning and Phase 1 planning

### Prompt

Define the Hybrid FTP project roadmap and plan Phase 1 for a Python standard-library TCP control MVP under the assignment constraints.

### Raw AI Output Summary

The AI helped organize project requirements, roadmap phases, Phase 1 decisions, and an executable plan for a TCP control-plane vertical slice with authentication, reply codes, command parsing, logging, tests, and demo evidence.

### Human Refinement

The user selected the Excellent-level target, Python CLI direction, standard-library-only constraint, TCP/UDP separation, active/passive modes in later phases, and local-only planning artifacts.

### Accepted Changes

- Phase 1 scoped to TCP control only.
- Later filesystem and UDP transfer commands are protected placeholders in Phase 1.
- Demo credentials are `student` / `cs494`.
- Evidence files are stable under `demo/evidence/phase1/`.

### Rejected Changes

- No third-party FTP or transfer libraries.
- No file payload transfer over TCP.
- No GUI-first implementation.
- No concurrency evidence in Phase 1.

### Verification Evidence

Planning artifacts were created under `.planning/`. Implementation verification should be recorded in later entries after code is run and reviewed.
