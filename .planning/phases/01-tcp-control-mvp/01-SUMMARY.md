---
phase: 01-tcp-control-mvp
plan: 01
subsystem: tcp-control
tags: [python, standard-library, sockets, ftp-control, unittest]
requires: []
provides:
  - Runnable Python package and top-level wrappers for the Hybrid FTP TCP control server/client
  - FTP-style reply and command parsing foundations with multiline HELP support
  - Demo authentication flow using USER/PASS with protected placeholder gating
  - Curated Phase 1 transcript and server-log evidence
affects: [phase-2-filesystem-command-slice, phase-3-udp-transfer-mvp, phase-6-concurrency]
tech-stack:
  added: [Python standard library only]
  patterns:
    - Explicit Session dataclass for per-client control state
    - Central Reply dataclass and command parser modules
    - Server-root sandbox helper functions before filesystem command implementation
    - Scripted demo evidence generator
key-files:
  created:
    - hybridftp/replies.py
    - hybridftp/commands.py
    - hybridftp/session.py
    - hybridftp/path_utils.py
    - hybridftp/logging_utils.py
    - hybridftp/server.py
    - hybridftp/client.py
    - server.py
    - client.py
    - demo/phase1_control_demo.py
    - demo/evidence/phase1/phase1-control-transcript.txt
    - demo/evidence/phase1/phase1-server.log
    - README.md
    - docs/genai-usage-log.md
  modified:
    - .gitignore
key-decisions:
  - "Implemented Phase 1 as a TCP-control-only vertical slice; all file/transfer commands remain protected placeholders until later phases."
  - "Used only Python standard-library modules and unittest coverage to preserve assignment compliance and oral-defense readability."
  - "Preserved stable demo evidence files under demo/evidence/phase1 while ignoring general runtime artifacts."
patterns-established:
  - "Command dispatch table maps FTP verbs to focused handler functions in hybridftp/server.py."
  - "Client multiline reply reader consumes NNN- continuations through matching NNN terminator before sending the next command."
  - "PASS command arguments are redacted in logs and client transcripts while real bytes are sent over TCP."
requirements-completed: [FOUND-01, FOUND-02, FOUND-03, FOUND-04, CTRL-01, CTRL-02, CTRL-03, CTRL-04, CTRL-05, CTRL-06, CTRL-07, CTRL-08, CTRL-09]
duration: 10min
completed: 2026-06-06
---

# Phase 1 Plan 01: TCP Control MVP Vertical Slice Summary

**Python standard-library TCP control client/server with FTP-style replies, demo authentication, protected-command gating, logs, tests, and curated evidence**

## Performance

- **Duration:** 10 min
- **Started:** 2026-06-06T15:13:21Z
- **Completed:** 2026-06-06T15:23:35Z
- **Tasks:** 7
- **Files modified:** 21

## Accomplishments

- Built the `hybridftp` package with focused modules for replies, command parsing, session state, server-root safety, logging, TCP server behavior, and TCP client behavior.
- Implemented a runnable TCP control server that creates/logs the server root, sends `220`, handles `USER`/`PASS`, `HELP`, `NOOP`, `QUIT`, unknown commands, malformed input, and future protected placeholders with FTP-style reply codes.
- Implemented immediate and open-style client flows that print raw FTP replies, send CRLF commands over TCP, redact PASS echoes, and correctly consume multiline `214` replies.
- Added standard-library `unittest` coverage plus deterministic Phase 1 transcript/log evidence generation.
- Added README quickstart and a GenAI usage log stub for the required report appendix.

## Task Commits

Each task was committed atomically:

1. **Task 01-01: Create reply formatting and command parsing foundations** - `9714922` (feat)
2. **Task 01-02: Create explicit session state, logging setup, and protocol handler tests** - `72aa261` (feat)
3. **Task 01-03: Implement runnable TCP server and top-level server wrapper** - `8859746` (feat)
4. **Task 01-04: Implement interactive and scriptable TCP client** - `ae2da24` (feat)
5. **Task 01-05: Add deterministic Phase 1 demo evidence generation** - `8041aaf` (feat)
6. **Task 01-06: Add README quickstart and GenAI usage log stub** - `ae3666d` (docs)
7. **Task 01-07: Run final Phase 1 verification and prepare handoff evidence** - `588568e` (test)

## Files Created/Modified

- `.gitignore` - Ignores Python/runtime artifacts, server roots, logs, and `.planning/` while preserving curated Phase 1 evidence files.
- `README.md` - Phase 1 quickstart, commands, demo credentials, test command, evidence command, and TCP/UDP boundary notes.
- `docs/genai-usage-log.md` - Incremental appendix stub with the required refinement-log headings.
- `hybridftp/__init__.py` - Package marker and version.
- `hybridftp/replies.py` - FTP-style Reply dataclass, CRLF encoding, and multiline framing.
- `hybridftp/commands.py` - Control-line parser, max-line limit, protected placeholder set, and HELP catalog.
- `hybridftp/session.py` - Explicit Session dataclass and demo user store.
- `hybridftp/path_utils.py` - Server-root resolution and traversal guard helpers.
- `hybridftp/logging_utils.py` - Console/file logging setup for server evidence.
- `hybridftp/server.py` - TCP control server, handler dispatch table, auth flow, parser failure handling, and test-server helper.
- `hybridftp/client.py` - Immediate and open-style TCP client flows with multiline reply synchronization.
- `server.py` and `client.py` - Top-level launcher wrappers.
- `demo/phase1_control_demo.py` - Deterministic scripted demo/evidence generator.
- `demo/evidence/phase1/phase1-control-transcript.txt` - Curated Phase 1 command/reply transcript.
- `demo/evidence/phase1/phase1-server.log` - Curated Phase 1 server log evidence.
- `tests/test_replies.py`, `tests/test_commands.py`, `tests/test_path_utils.py`, `tests/test_server_protocol.py`, `tests/test_tcp_smoke.py` - Standard-library test coverage.

## Decisions Made

- Followed the Phase 1 boundary strictly: TCP carries commands/replies/session state only; no file payload transfer was implemented.
- Recognized later filesystem/transfer commands as protected placeholders so pre-auth `530` and post-auth `502` behavior is demonstrable now without claiming those commands work.
- Kept the Phase 1 server single-client for demo simplicity; concurrency remains explicitly deferred to Phase 6.
- Chose ephemeral ports in automated tests/demo helpers to avoid local port conflicts while keeping CLI defaults at `127.0.0.1:2121`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Handled Windows connection reset during test-server shutdown**
- **Found during:** Task 01-03 (TCP server smoke verification)
- **Issue:** The test helper's stop connection could close before the server read a line, raising `ConnectionResetError` on Windows and leaving the log file handle open.
- **Fix:** Treated socket `OSError` during control-line reads as a normal disconnect and closed/removing logger handlers in `serve()` cleanup.
- **Files modified:** `hybridftp/server.py`
- **Verification:** `python -m unittest discover -s tests -v` passed.
- **Committed in:** `8859746`

**2. [Rule 3 - Blocking] Made the demo script importable when executed by path**
- **Found during:** Task 01-05 (demo evidence verification)
- **Issue:** Running `python demo/phase1_control_demo.py` set `sys.path` to `demo/`, so `hybridftp` could not be imported.
- **Fix:** Inserted the project root into `sys.path` at demo-script startup.
- **Files modified:** `demo/phase1_control_demo.py`
- **Verification:** `python demo/phase1_control_demo.py` passed.
- **Committed in:** `8041aaf`

---

**Total deviations:** 2 auto-fixed (1 bug, 1 blocking issue)
**Impact on plan:** Both fixes were necessary for correctness and repeatable verification. No scope creep beyond Phase 1.

## Issues Encountered

- The repository started with untracked project files (`CLAUDE.md`, assignment PDFs) that pre-existed execution; they were left untouched and uncommitted.
- General test/demo console output is verbose because server logs intentionally print to console for screenshot-friendly evidence.

## Known Stubs

| File | Pattern | Reason |
|------|---------|--------|
| `hybridftp/commands.py` | `coming soon` HELP text for protected commands | Intentional Phase 1 placeholder behavior; real filesystem/transfer commands are planned for later phases. |
| `hybridftp/server.py` | Protected placeholders return `502 Command not implemented yet` after login | Intentional Phase 1 boundary; implementations begin in Phase 2 and later. |

## Threat Flags

None. Phase 1 introduces the planned TCP control server/client surface, authentication gating, logging, and server-root safety helpers described in the plan threat model. No unplanned network endpoint, auth path, file access pattern, or schema boundary was added.

## Verification

- `python -m unittest discover -s tests -v` passed with 17 tests.
- `python demo/phase1_control_demo.py` passed and refreshed `demo/evidence/phase1/phase1-server.log`.
- Source scan found no `ftplib`, `pyftpdlib`, KCP, QUIC, libcurl wrappers, or third-party transfer libraries.
- Evidence scan found no raw PASS arguments `anything`, `wrong`, or `cs494` in the curated transcript or server log.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Phase 2 can build on the explicit `Session.cwd`, `server_root`, protected placeholder gating, and `ensure_within_root()` sandbox helpers to implement filesystem commands safely. The existing command dispatch table and tests establish the pattern for adding real handlers while preserving pre-auth `530` behavior.

## Self-Check: PASSED

Verified key created files exist and all seven task commit hashes are present in git history.

---
*Phase: 01-tcp-control-mvp*
*Completed: 2026-06-06*
