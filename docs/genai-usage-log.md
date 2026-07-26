# GenAI Usage and Code Refinement Log

This mandatory appendix records how GenAI was used as a planning, implementation,
and review aid for the Hybrid FTP project. It is written to distinguish AI
suggestions from student decisions and to make the final codebase defensible in
an oral examination.

## Record availability and terminology

GenAI assistance occurred across more than one conversation and device during
development. A complete, unified export of every interaction is not available.
This log is therefore a **specific reconstruction based on retained prompts,
project commits, source code, tests, and demo artifacts**. It must not be read
as a verbatim export of all conversations.

The labels below are used throughout the appendix:

- **Retained prompt text** — a prompt preserved in a project note or retained
  record. It is quoted as retained text, not claimed to be a complete chat
  export.
- **Reconstructed prompt/topic** — the remembered engineering question or work
  topic, reconstructed from the resulting implementation and records.
- **Reconstructed AI-output summary** — a non-verbatim description of ideas
  considered during that work. It is not raw AI output. The historical heading
  **Raw AI Output Summary** is retained only for compatibility with earlier
  project checks; this document does not use it to label reconstructed material.
- **Student refinement and verification** — decisions made by the student,
  tied to the final source, tests, or evidence. These are the accountable
  project decisions.

If an original chat excerpt is recovered later, it should be attached as a
separate appendix labeled with its source/date and should not replace this
record. No unavailable prompt, AI response, code snippet, date, or screenshot
has been fabricated for this document.

## Entry: 2026-06-04 — Project scope and Phase 1 planning

### Retained Prompt Text

> Define the Hybrid FTP project roadmap and plan Phase 1 for a Python
> standard-library TCP control MVP under the assignment constraints.

### Reconstructed AI-output summary

The planning discussion considered a vertical development order: first the TCP
control channel and session state, then filesystem sandboxing, then a custom
UDP transfer layer, reliability upgrades, data modes, concurrency, evidence,
and report preparation. It also identified the project constraints that must
remain visible in the code: standard-library sockets only, FTP-style reply
codes, no third-party FTP/RDT library, and no file payload sent over TCP.

### Human Refinement and Verification

The student adopted the staged scope but constrained it to an implementation
that could be explained line-by-line during the viva:

- `hybridftp/commands.py` parses bounded UTF-8 control lines and defines the
  supported command/help vocabulary.
- `hybridftp/replies.py` centralizes three-digit FTP-style replies and multiline
  reply framing instead of scattering raw response strings through handlers.
- `hybridftp/session.py` keeps authentication, current directory, transfer
  settings, and pending rename state explicit per client.
- `hybridftp/server.py` and `hybridftp/client.py` keep commands/replies on TCP;
  later transfer code uses UDP for payload bytes.

The student rejected a generic FTP-library approach because the assignment
requires native socket APIs and a custom reliable UDP layer. The student also
rejected hiding protocol state behind a large framework because the individual
packet, session, and transfer transitions must be explainable in oral defense.

Verification recorded for this stage:

```powershell
py -3 -m unittest discover -s tests -v
py -3 demo/phase1_control_demo.py
```

Relevant checks include `tests/test_commands.py`, `tests/test_replies.py`,
`tests/test_server_protocol.py`, and `tests/test_tcp_smoke.py`. Curated output
is stored under `demo/evidence/phase1/`.

## Entry: 2026-06-07 — Filesystem command slice

### Retained Prompt Text

> Execute the filesystem command slice while preserving standard-library-only,
> TCP-control-only scope and server-root sandboxing.

### Reconstructed AI-output summary

The discussion considered adding per-session virtual directories, normalized
path resolution, listing and metadata operations, mutation commands, and the
`RNFR`/`RNTO` sequence. It also raised the need to reject traversal and unsafe
link targets rather than treating the process working directory as the FTP
root.

### Accepted Refinements

The student implemented a virtual POSIX-facing filesystem interface rather than
exposing host paths directly:

- `hybridftp/filesystem.py` validates arguments, resolves virtual paths against
  the configured server root, blocks traversal and unsafe symlink targets, and
  implements `PWD`, `CWD`, `CDUP`, `MKD`, `RMD`, `LIST`, `NLST`, `STAT`, `SIZE`,
  `MDTM`, `DELE`, and `RNFR`/`RNTO` helpers.
- `hybridftp/path_utils.py` provides the root-containment check used by runtime
  root resolution.
- `hybridftp/session.py` stores the current virtual directory and pending
  rename source per session, avoiding cross-client leakage.
- `hybridftp/server.py` applies authentication gating and converts filesystem
  failures into FTP reply codes.

### Student Critical Analysis and Refinements

The student did not accept a simple `Path.joinpath()` implementation without
post-resolution checks: that can permit `..` traversal or links that resolve
outside the server root. The final code validates virtual path syntax, verifies
root containment after resolution, and rejects link escapes. The student also
kept `RNFR`/`RNTO` state explicit and cleared it after invalid/failed sequences
so a stale rename source cannot be reused accidentally.

The directory/listing work remains on the TCP control channel. File payload
transfer was intentionally deferred; this prevents a misleading early design
that might send file data over TCP.

### Verification

```powershell
py -3 -m unittest discover -s tests -v
py -3 demo/phase2_filesystem_demo.py
```

The relevant automated checks are `tests/test_filesystem.py`,
`tests/test_path_utils.py`, and filesystem cases in `tests/test_tcp_smoke.py`.
Curated, password/path-redacted evidence is stored under `demo/evidence/phase2/`.

## Entry: 2026-07-26 — Reliable UDP, transfer commands, and final refinement

### Retained Prompt Text

> Make the Hybrid FTP project submit-ready at Excellent level: custom reliable
> UDP packet format, ACK/sequence/checksum/FIN handling, bounded sliding
> window, binary SHA-256 verification, PASV/PORT, advanced transfer commands,
> concurrent session isolation, final evidence, report, and viva map. Use only
> the Python standard library; do not send payload bytes on TCP.

### Reconstructed AI-output summary

The implementation/review work considered a fixed binary UDP header, explicit
packet/state structures, selective-repeat-style sending and receiving,
streamed hashing, temporary receive files, per-session active/passive UDP
endpoints, a threaded control server, and test/demo layers. These ideas were
inputs for review; the student selected, simplified, or rejected them based on
the assignment restrictions and explainability requirements.

### Student Critical Analysis and Refinements

#### 1. Packet format and RDT behavior

- **Accepted and implemented:** `hybridftp/rdt.py` uses an explicit network-order
  packet encoding with magic/version fields, flags, transfer ID, sequence and
  acknowledgement numbers, advertised receive window, payload length, and
  CRC-32 validation.
- **Student refinement:** the header is fixed at 32 bytes and payloads are
  bounded, so parsing checks can reject malformed length, version, flag, and
  checksum values before transfer code writes any file bytes.
- **Rejected:** KCP, QUIC, `ftplib`, `pyftpdlib`, libcurl wrappers, or any
  third-party reliable-transfer abstraction. These violate the assignment and
  would prevent explanation of packet handling.
- **Verification:** `tests/test_rdt.py` checks round-trip header preservation,
  control packets, default window configuration, and rejection of tampered or
  malformed packets.

#### 2. Transfer lifecycle and file safety

- **Accepted and implemented:** `hybridftp/transfer.py` sends numbered UDP DATA
  packets, retains unacknowledged packets within a bounded window, processes
  individual ACKs, retransmits expired packets, and completes with FIN/FIN_ACK.
  The receiver buffers valid in-window out-of-order packets, suppresses
  duplicates, and writes only contiguous data.
- **Student refinement:** received data is written to a temporary file and only
  atomically renamed after successful completion; an abort or failed transfer
  removes the temporary output instead of leaving a corrupt final filename.
- **Student refinement:** `TYPE I` preserves byte values, while `TYPE A`
  normalizes only 7-bit ASCII line endings through a streamed conversion path;
  unsupported `MODE B` and `MODE C` receive a clear `504` response.
- **Verification:** `tests/test_transfer.py` checks bounded-window behavior and
  atomic destination handling; `tests/test_transfer_protocol.py` covers passive
  binary upload/download and hash equality; `tests/test_integrity.py` checks
  streamed and path-based SHA-256; the final test suite exercises TYPE A.

#### 3. TCP/UDP split and active/passive endpoint safety

- **Accepted and implemented:** TCP carries `PASV`, `PORT`, `RETR`, `STOR`,
  `STOU`, `APPE`, `ABOR`, and their FTP replies, while every file payload flows
  through the UDP protocol.
- **Student refinement:** the server sends the preliminary `150` reply before
  its transfer state machine runs, preventing a control/data startup deadlock.
- **Student refinement:** `hybridftp/data_channel.py` parses `PORT` values,
  validates the announced endpoint against the TCP peer, and creates a
  per-session passive UDP socket for `PASV`. The prepared endpoint is consumed
  and reset after the transfer.
- **Verification:** `tests/test_data_channel.py` checks endpoint parsing and the
  peer guard; `tests/test_transfer_protocol.py` performs TCP+UDP passive-mode
  integration coverage.

#### 4. Concurrent sessions and cancellation

- **Accepted and implemented:** `hybridftp/server.py` accepts TCP clients in
  separate session workers; `hybridftp/session_registry.py` provides a
  lock-protected snapshot for the `STAT` active-session table.
- **Student refinement:** per-session state includes authentication, virtual
  directory, transfer type/mode, rename source, data endpoint, transfer ID,
  cancellation event, and byte count. `ABOR` signals the active worker, resets
  data-channel state, and preserves the temporary-file cleanup guarantee.
- **Verification:** `tests/test_concurrency.py` confirms two clients keep
  isolated working directories and appear in the visible session table. Active
  transfer/cancellation paths are exercised by `tests/test_transfer_protocol.py`
  and the final suite.

#### 5. Evidence and report review

- **Accepted and implemented:** `demo/final_submission_demo.py` produces a
  redacted binary upload/download transcript, SHA-256 comparison, RDT log
  excerpts, and an isolated two-client session demonstration.
- **Student refinement:** the script normalizes run-specific ports, IDs, and
  sensitive values in the curated output, while preserving the command/reply
  and integrity evidence required for the report.
- **Verification:** `tests/test_final_artifacts.py` regenerates the final demo
  and checks the report headings plus transfer hash and session evidence.

### Planned Verification

```powershell
py -3 -m unittest discover -s tests -v
py -3 demo/final_submission_demo.py
```

The oral-defense preparation traces packet bytes in `hybridftp/rdt.py`, sender
and receiver transitions in `hybridftp/transfer.py`, endpoint negotiation in
`hybridftp/data_channel.py`, session state in `hybridftp/session.py` and
`hybridftp/session_registry.py`, TCP dispatch in `hybridftp/server.py`, and
client-side transfer orchestration in `hybridftp/client.py`.

## Implementation-to-evidence matrix

| Topic discussed with GenAI assistance | Student-owned final implementation | Verification and evidence |
|---|---|---|
| TCP control parsing and replies | `hybridftp/commands.py`, `hybridftp/replies.py`, `hybridftp/server.py`, `hybridftp/client.py` | `tests/test_commands.py`, `tests/test_replies.py`, `tests/test_server_protocol.py`, `tests/test_tcp_smoke.py`, `demo/evidence/phase1/` |
| Server-root filesystem sandbox | `hybridftp/filesystem.py`, `hybridftp/path_utils.py`, `hybridftp/session.py` | `tests/test_filesystem.py`, `tests/test_path_utils.py`, `demo/evidence/phase2/` |
| Custom RDT packet and flow control | `hybridftp/rdt.py`, `hybridftp/transfer.py` | `tests/test_rdt.py`, `tests/test_transfer.py`, final server log RDT send/ACK/window entries |
| Binary integrity and final file safety | `hybridftp/integrity.py`, `hybridftp/transfer.py` | `tests/test_integrity.py`, `tests/test_transfer_protocol.py`, `demo/evidence/final/final-transfer-transcript.txt` |
| PASV/PORT and transfer commands | `hybridftp/data_channel.py`, `hybridftp/server.py`, `hybridftp/client.py` | `tests/test_data_channel.py`, `tests/test_transfer_protocol.py` |
| Session isolation and live evidence | `hybridftp/session.py`, `hybridftp/session_registry.py`, `demo/final_submission_demo.py` | `tests/test_concurrency.py`, `tests/test_final_artifacts.py`, `demo/evidence/final/` |

## Student responsibility statement

GenAI was used for learning, design alternatives, implementation review, and
debugging support. The student remains responsible for the final code and can
explain the TCP/UDP split, control replies, server-root sandbox, every RDT
header field, checksum validation, ACK/window/retransmission behavior,
temporary-file cleanup, active/passive endpoint handling, session isolation,
and the tests/evidence listed above. Suggestions conflicting with the course
rules or oral-defense clarity were rejected or rewritten before inclusion.
