# Roadmap: Hybrid FTP Application

**Created:** 2026-06-04
**Mode:** Vertical MVP
**Core Value:** A user can reliably upload and download files through a TCP-controlled, UDP-data Hybrid FTP system and explain every protocol decision during oral defense.

## Overview

| # | Phase | Goal | Requirements | Success Criteria |
|---|-------|------|--------------|------------------|
| 1 | TCP Control MVP | 1/1 | Complete   | 2026-06-06 |
| 2 | Filesystem Command Slice | Add defendable server-root filesystem navigation, listing, metadata, delete, and rename commands. | FS-01..12 | 5 |
| 3 | UDP Transfer MVP | Deliver first end-to-end upload/download over UDP with custom reliable packet layer and text transfer support. | MODE-01..04, RDT-01..07, XFER-01..07 | 5 |
| 4 | Excellent Transfer Reliability | Upgrade transfer layer for binary safety, sliding-window flow control, and SHA-256 integrity verification. | RDT-08, XFER-08, HASH-01..03 | 5 |
| 5 | FTP Data Modes and Advanced Transfer Commands | Implement PASV/PORT, APPE, STOU, ABOR, and robust data-channel reset behavior. | MODE-05..06, RDT-09, XFER-03..04 | 5 |
| 6 | Concurrent Server and Session Isolation | Support multiple isolated clients and visible active session table for demo and viva. | CONC-01..04 | 4 |
| 7 | Demo, Tests, Report, and Defense Pack | Produce clean-machine demo evidence, tests, report sections, diagrams, and GenAI appendix. | DEMO-01..05, DOC-01..08 | 5 |

## Phases

### Phase 1: TCP Control MVP

**Goal:** Establish a runnable Python CLI client/server with TCP control, authentication, standard reply codes, and visible session logging.
**Mode:** mvp

**Requirements:** FOUND-01, FOUND-02, FOUND-03, FOUND-04, CTRL-01, CTRL-02, CTRL-03, CTRL-04, CTRL-05, CTRL-06, CTRL-07, CTRL-08, CTRL-09

**Success Criteria:**
1. Server starts from CLI, listens for TCP clients, and prints a `220` greeting on connection.
2. Client starts from CLI, connects to server, sends commands, and prints raw FTP-style replies.
3. USER/PASS authentication works with `331`, `230`, `530`, and protected-operation enforcement.
4. QUIT, NOOP, and HELP work through the TCP control channel.
5. Logs show connected client address, issued commands, replies, and session state changes.

**Key Build Notes:**
- Create package skeleton and common reply/command utilities.
- Keep static user store simple and explainable.
- Add `.gitignore` and commit source changes incrementally.

### Phase 2: Filesystem Command Slice

**Goal:** Add defendable server-root filesystem navigation, listing, metadata, delete, and rename commands.
**Mode:** mvp

**Requirements:** FS-01, FS-02, FS-03, FS-04, FS-05, FS-06, FS-07, FS-08, FS-09, FS-10, FS-11, FS-12

**Success Criteria:**
1. PWD/CWD/CDUP operate per session and cannot escape the configured server root.
2. MKD/RMD create and remove directories with correct success/failure reply codes.
3. LIST/NLST return detailed and plain listings for current or specified paths.
4. STAT/SIZE/MDTM return accurate metadata with assignment-required timestamp format.
5. DELE and RNFR/RNTO modify files only inside server root and handle errors safely.

**Key Build Notes:**
- Implement path normalization and sandbox checks before all file operations.
- Keep filesystem command handlers independent from transfer logic.

### Phase 3: UDP Transfer MVP

**Goal:** Deliver the first end-to-end upload/download over UDP with a custom reliable packet layer and text transfer support.
**Mode:** mvp

**Requirements:** MODE-01, MODE-02, MODE-03, MODE-04, RDT-01, RDT-02, RDT-03, RDT-04, RDT-05, RDT-06, RDT-07, XFER-01, XFER-02, XFER-05, XFER-06, XFER-07

**Success Criteria:**
1. UDP packet header is implemented and documented with sequence number, ACK, checksum, flags, payload length, and transfer ID.
2. Stop-and-wait or initial windowed RDT sends text file chunks over UDP and reconstructs them correctly.
3. Corrupted, duplicate, missing, and out-of-order packet scenarios are handled by checksum, deduplication, ordering, and retransmission logic.
4. RETR and STOR use UDP for payloads and TCP only for commands/replies.
5. Text upload and download demos complete with `150`/`226` style replies and no corrupt final files.

**Key Build Notes:**
- Start with PASV-like localhost UDP endpoint if needed, then formalize modes in Phase 5.
- Use temp files for received data and rename only after successful completion.

### Phase 4: Excellent Transfer Reliability

**Goal:** Upgrade transfer layer for binary safety, sliding-window flow control, and SHA-256 integrity verification.
**Mode:** mvp

**Requirements:** RDT-08, XFER-08, HASH-01, HASH-02, HASH-03

**Success Criteria:**
1. RDT sender supports a sliding window or equivalent flow-control mechanism limiting in-flight packets.
2. Binary files are transferred using byte-preserving IO with matching SHA-256 hashes after upload/download.
3. HASH command returns server-side SHA-256 for a requested file.
4. Client computes local hashes before upload and after download, displaying comparison results.
5. Logs show window movement, ACKs, retransmissions, and final integrity verification.

**Key Build Notes:**
- Prefer a clear Go-Back-N or Selective Repeat implementation that can be explained during viva.
- Add tests for packet loss/retransmission and binary hash equality.

### Phase 5: FTP Data Modes and Advanced Transfer Commands

**Goal:** Implement PASV/PORT, APPE, STOU, ABOR, and robust data-channel reset behavior.
**Mode:** mvp

**Requirements:** MODE-05, MODE-06, RDT-09, XFER-03, XFER-04

**Success Criteria:**
1. PASV opens a server UDP endpoint and returns a correct FTP-style host/port tuple.
2. PORT registers a client UDP endpoint and server uses it for active transfers.
3. STOU stores uploads under guaranteed unique server-generated filenames.
4. APPE appends uploaded bytes to an existing file or creates the file if absent.
5. ABOR cancels active transfers, resets data-channel state, and leaves no corrupt final file.

**Key Build Notes:**
- Keep mode state per session.
- Test both modes on localhost and document directionality for oral defense.

### Phase 6: Concurrent Server and Session Isolation

**Goal:** Support multiple isolated clients and a visible active session table for demo and viva.
**Mode:** mvp

**Requirements:** CONC-01, CONC-02, CONC-03, CONC-04

**Success Criteria:**
1. Server accepts multiple concurrent TCP clients using threads or thread pool.
2. Each client has independent auth, cwd, TYPE, MODE, PORT/PASV, RNFR, and transfer state.
3. Server displays connected client IPs, executed commands, and active session table.
4. Two-client demo shows simultaneous sessions without cwd/mode/auth leakage.

**Key Build Notes:**
- Use explicit session objects and minimal locks around shared session registry/log display.
- Keep file writes safe for concurrent access.

### Phase 7: Demo, Tests, Report, and Defense Pack

**Goal:** Produce clean-machine demo evidence, tests, report sections, diagrams, and GenAI appendix required for submission and oral defense.
**Mode:** mvp

**Requirements:** DEMO-01, DEMO-02, DEMO-03, DEMO-04, DEMO-05, DOC-01, DOC-02, DOC-03, DOC-04, DOC-05, DOC-06, DOC-07, DOC-08

**Success Criteria:**
1. Clean-machine instructions run server/client and demonstrate upload/download without errors.
2. Automated/scripted checks cover command parsing, packet encode/checksum, text transfer, binary transfer, and concurrency smoke test.
3. Report includes all seven mandatory sections from the assignment.
4. Demo evidence includes screenshots/logs of upload, download, hash comparison, connected-client table, and concurrent session test.
5. GenAI appendix records prompts, raw AI outputs, refinements, debugging, and student critical analysis.

**Key Build Notes:**
- Create diagrams from the implemented module names and packet fields.
- Prepare viva notes for TCP vs UDP split, active/passive mode, RDT state machines, socket calls, and header bytes.

## Requirement Coverage

- v1 requirements: 68 total
- Mapped to phases: 68
- Unmapped: 0 ✓

## Next Step

Run `/gsd:discuss-phase 1` to gather implementation context for Phase 1, then `/gsd:plan-phase 1` to create the executable coding plan.

---
*Roadmap created: 2026-06-04 after initial project setup*
