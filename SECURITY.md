# Security Audit: Phase 01 tcp-control-mvp

**Phase:** 01 — tcp-control-mvp
**ASVS Level:** 1
**Block On:** HIGH,MEDIUM
**Threats Closed:** 6/6
**Threats Open:** 0

## Threat Verification

| Threat ID | Category | Disposition | Status | Evidence |
|-----------|----------|-------------|--------|----------|
| T-01 | Tampering / Denial of Service | mitigate | CLOSED | `hybridftp/commands.py:9` defines `MAX_CONTROL_LINE = 1024`; `hybridftp/commands.py:67-77` rejects overlong and invalid UTF-8 input with `ParseError`; `hybridftp/server.py:137-162` caps network read lines; `hybridftp/server.py:177-190` converts parser failures to safe `501` replies; `tests/test_commands.py:18-24` and `tests/test_tcp_smoke.py:47-50` cover overlong/undecodable input. |
| T-02 | Elevation of Privilege | mitigate | CLOSED | `hybridftp/commands.py:13-37` centralizes protected placeholders; `hybridftp/server.py:107-119` checks `is_protected_placeholder()` before dispatch and returns `530` pre-auth / `502` post-auth; `tests/test_server_protocol.py:65-69` and `tests/test_tcp_smoke.py:76-78,94-97` verify protected command gating. |
| T-03 | Information Disclosure / Tampering | mitigate | CLOSED | `hybridftp/path_utils.py:8-12` creates/resolves server root; `hybridftp/server.py:209-211` resolves and logs root on startup; `hybridftp/server.py:165-166` stores resolved root in `Session`; `hybridftp/session.py:15-17` includes `server_root`; `tests/test_path_utils.py:9-14` covers root creation and absolute resolution. |
| T-04 | Information Disclosure | mitigate | CLOSED | `hybridftp/server.py:26-33` redacts all `PASS` commands via `sanitize_command_for_log`; `hybridftp/server.py:110` uses the sanitizer for command logging; `hybridftp/client.py:25-29` redacts PASS transcript echoes; `tests/test_server_protocol.py:32-33,83-91` verifies server log redaction; `tests/test_tcp_smoke.py:110-113` verifies transcript redaction; evidence contains `PASS ********` and no raw `anything`, `wrong`, or `cs494` in `demo/evidence/phase1/phase1-control-transcript.txt:4,10,14` and `demo/evidence/phase1/phase1-server.log:8,17,23`. |
| T-05 | Information Disclosure / Boundary Violation | mitigate | CLOSED | `hybridftp/commands.py:13-37` treats file/transfer commands as protected placeholders; `hybridftp/server.py:111-119` returns only control replies `530`/`502`; no transfer/file handlers exist in dispatch table `hybridftp/server.py:98-104`; `tests/test_server_protocol.py:65-69`, `tests/test_tcp_smoke.py:76-78,94-97`, and `demo/evidence/phase1/phase1-control-transcript.txt:6-7,33-34` verify placeholder control replies only. |
| T-06 | Tampering / Path Traversal | mitigate | CLOSED | `hybridftp/path_utils.py:8-12` implements `resolve_server_root`; `hybridftp/path_utils.py:15-22` implements `ensure_within_root` and rejects candidates outside root; `tests/test_path_utils.py:16-28` covers in-root acceptance and `..` traversal rejection. |

## Accepted Risks

None for Phase 01. No threats in the register have disposition `accept`.

## Transferred Risks

None for Phase 01. No threats in the register have disposition `transfer`.

## Unregistered Flags

None. `01-SUMMARY.md` reports no unplanned threat flags.
