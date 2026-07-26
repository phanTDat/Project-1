# GenAI Usage and Code Refinement Log

This appendix is maintained for the Hybrid FTP project. It distinguishes AI
suggestions from student decisions and records the constraints checked before
accepting generated work. Exact raw session exports must be attached with the
final report submission; this in-repository log is the navigable index.

## Entry: 2026-06-04 — Project and Phase 1 planning

### Prompt

> Define the Hybrid FTP project roadmap and plan Phase 1 for a Python
> standard-library TCP control MVP under the assignment constraints.

### Raw AI Output Summary

The AI proposed a vertical roadmap covering TCP control, filesystem isolation,
UDP transfer, reliability, advanced modes, concurrency, testing, evidence, and
report preparation.

### Human Refinement and Verification

The student selected the Excellent-level target; required TCP/UDP separation;
Python standard library only; and local-only planning artifacts. No FTP
framework, transfer library, TCP payload fallback, or GUI-first scope was
accepted.

## Entry: 2026-06-07 — Filesystem command slice

### Prompt

> Execute the filesystem command slice while preserving standard-library-only,
> TCP-control-only scope and server-root sandboxing.

### Accepted Refinements

- Added virtual POSIX resolution, root/symlink checks, per-session cwd and
  rename state, and filesystem commands over TCP replies.
- Used deterministic demo transcripts and password/path redaction.
- Rejected UDP transfer behavior at that stage because it had not been designed
  or verified yet.

### Verification

```powershell
py -3 -m unittest discover -s tests -v
py -3 demo/phase2_filesystem_demo.py
```

## Entry: 2026-07-26 — Excellent-level UDP/RDT refinement

### Prompt

> Make the Hybrid FTP project submit-ready at Excellent level: custom reliable
> UDP packet format, ACK/sequence/checksum/FIN handling, bounded sliding
> window, binary SHA-256 verification, PASV/PORT, advanced transfer commands,
> concurrent session isolation, final evidence, report, and viva map. Use only
> the Python standard library; do not send payload bytes on TCP.

### Raw AI Output Summary

The AI proposed a fixed binary UDP header, dataclass state structures,
selective-repeat sender/receiver functions, streamed hashing, per-session data
endpoints, thread-per-control-session service, test layers, and curated evidence
scripts.

### Student Critical Analysis and Refinements

- **Accepted:** explicit `struct` header encoding, `zlib.crc32`, transfer IDs,
  individual ACKs, out-of-order receive buffer, bounded packet window,
  temporary receive file followed by atomic rename, and streaming SHA-256.
- **Rejected:** third-party RDT/FTP libraries, hidden abstractions that cannot
  be explained in viva, and any transfer of file bytes through TCP.
- **Refined:** the design makes the server send `150` before entering its UDP
  state machine, preventing a TCP/UDP startup deadlock. The client’s `put` and
  `get` aliases issue standard FTP commands but keep local paths and all file
  content on the client/UDP side.
- **Refined:** `PORT` checks the announced endpoint against the control peer;
  `PASV` owns one UDP socket per session; `SessionRegistry` exposes only safe
  session metadata.
- **Known review points before submission:** run the complete test suite and
  live two-client rehearsal; inspect packet retry and ABOR paths under loss;
  attach this session’s complete raw transcript and any debugging output to the
  final report appendix rather than claiming this summary alone is raw output.

### Planned Verification

```powershell
py -3 -m unittest discover -s tests -v
py -3 demo/final_submission_demo.py
```

The final oral-defense preparation explicitly traces `rdt.py` packet bytes,
`transfer.py` sender/receiver state transitions, and every synchronization point
in `server.py` / `session_registry.py`.
