# Requirements: Hybrid FTP Application

**Defined:** 2026-06-04
**Core Value:** A user can reliably upload and download files through a TCP-controlled, UDP-data Hybrid FTP system and explain every protocol decision during oral defense.

## v1 Requirements

Requirements for the course submission. Each maps to roadmap phases.

### Project Foundation

- [x] **FOUND-01**: Developer can run the Python client and server from CLI entrypoints on a clean machine using only standard-library dependencies.
- [x] **FOUND-02**: Server stores files under a configured server root and rejects path traversal outside that root.
- [x] **FOUND-03**: Client and server display clear logs for network states, commands, replies, transfer progress, and errors.
- [x] **FOUND-04**: Source code is version-controlled with incremental commits suitable for authorship verification.

### TCP Control Channel

- [x] **CTRL-01**: Client opens a TCP control connection to the server and receives a `220` service-ready reply.
- [x] **CTRL-02**: Client transmits every approved FTP command over the TCP control channel.
- [x] **CTRL-03**: Server responds to every command using standard three-digit FTP-style reply codes.
- [x] **CTRL-04**: Server supports `USER <username>` and replies `331` when a known username needs a password.
- [x] **CTRL-05**: Server supports `PASS <password>` and replies `230` on successful login or `530` on failure.
- [x] **CTRL-06**: Server prevents protected file operations before authentication and returns `530 Not logged in`.
- [x] **CTRL-07**: Server supports `QUIT`, closes the session gracefully, and replies `221`.
- [x] **CTRL-08**: Server supports `NOOP` as a keep-alive and replies `200`.
- [x] **CTRL-09**: Server supports `HELP [command]` for all implemented commands.

### Filesystem Commands

- [ ] **FS-01**: User can run `PWD` to print the server session's current working directory.
- [ ] **FS-02**: User can run `CWD <path>` to change current directory within the server root.
- [ ] **FS-03**: User can run `CDUP` to move to the parent directory without escaping the server root.
- [ ] **FS-04**: User can run `MKD <dirname>` to create a directory.
- [ ] **FS-05**: User can run `RMD <dirname>` to remove an empty directory.
- [ ] **FS-06**: User can run `LIST [path]` to receive detailed file/directory listings.
- [ ] **FS-07**: User can run `NLST [path]` to receive name-only listings.
- [ ] **FS-08**: User can run `STAT [path]` to receive server status or file/directory metadata.
- [ ] **FS-09**: User can run `SIZE <filename>` to receive exact byte size.
- [ ] **FS-10**: User can run `MDTM <filename>` to receive last modification timestamp in `YYYYMMDDhhmmss` format.
- [ ] **FS-11**: User can run `DELE <filename>` to delete a file.
- [ ] **FS-12**: User can run `RNFR <oldname>` followed by `RNTO <newname>` to rename a file or directory.

### Transfer Modes and Data Types

- [ ] **MODE-01**: User can run `TYPE A` to select ASCII text transfer behavior.
- [ ] **MODE-02**: User can run `TYPE I` to select binary/image transfer behavior.
- [ ] **MODE-03**: User can run `MODE S` for stream-style transfer mode.
- [ ] **MODE-04**: Server handles `MODE B` and `MODE C` with a correct reply, either implemented or explicitly not implemented if outside final scope.
- [ ] **MODE-05**: User can run `PASV` and receive a server UDP endpoint for passive data transfer.
- [ ] **MODE-06**: User can run `PORT <h1,h2,h3,h4,p1,p2>` and register a client UDP endpoint for active data transfer.

### Reliable UDP Layer

- [ ] **RDT-01**: UDP packet format includes documented header fields for sequence number, ACK, checksum, flags, payload length, and transfer/session identity.
- [ ] **RDT-02**: Sender splits file bytes into UDP payload chunks and assigns monotonically increasing sequence numbers.
- [ ] **RDT-03**: Receiver detects corrupted packets using checksum validation and rejects them.
- [ ] **RDT-04**: Receiver eliminates duplicate packets without duplicating file bytes.
- [ ] **RDT-05**: Receiver reconstructs payloads in correct byte order even if packets arrive out of order.
- [ ] **RDT-06**: Sender retransmits packets when ACKs are missing after a timeout.
- [ ] **RDT-07**: Sender and receiver complete transfer using explicit FIN/completion signaling.
- [ ] **RDT-08**: RDT implementation supports a sliding window or equivalent flow-control mechanism to limit in-flight packets.
- [ ] **RDT-09**: Transfer can be aborted with `ABOR`, resetting data-channel state and returning an appropriate FTP reply.

### File Transfer Commands

- [ ] **XFER-01**: User can run `RETR <filename>` to download a server file via UDP data channel.
- [ ] **XFER-02**: User can run `STOR <filename>` to upload a local file via UDP data channel.
- [ ] **XFER-03**: User can run `STOU` to upload a file using a guaranteed unique server-generated filename.
- [ ] **XFER-04**: User can run `APPE <filename>` to append uploaded data to an existing file or create it if absent.
- [ ] **XFER-05**: Successful transfers return preliminary `150`/`125` style replies and final `226 Transfer complete` replies.
- [ ] **XFER-06**: Failed or aborted transfers return appropriate `4xx`/`5xx` replies and do not leave corrupt final files.
- [ ] **XFER-07**: ASCII text files can be uploaded and downloaded successfully.
- [ ] **XFER-08**: Binary files such as images, archives, or videos can be uploaded and downloaded without byte corruption.

### Integrity Verification

- [ ] **HASH-01**: User can run `HASH <filename>` to request a SHA-256 hash of a server file.
- [ ] **HASH-02**: Client can compute local SHA-256 hashes before upload and after download.
- [ ] **HASH-03**: Demo can show matching pre-transfer and post-transfer hashes for text and binary files.

### Concurrency and Session Isolation

- [ ] **CONC-01**: Server accepts multiple concurrent TCP clients.
- [ ] **CONC-02**: Each client has isolated authentication state, working directory, type, mode, rename state, and data-channel state.
- [ ] **CONC-03**: Server log displays connected client IPs, executed commands, and an active session table.
- [ ] **CONC-04**: Demo can show at least two clients connected simultaneously without state leakage.

### Demo and Tests

- [ ] **DEMO-01**: Clean-machine instructions start server and client without errors.
- [ ] **DEMO-02**: Demo evidence shows one successful upload and one successful download.
- [ ] **DEMO-03**: Demo evidence shows binary transfer hash equality.
- [ ] **DEMO-04**: Demo evidence shows connected-client table and concurrent session test.
- [ ] **DEMO-05**: Automated or scripted checks cover command parsing, packet encoding/checksum, text transfer, binary transfer, and concurrency smoke tests.

### Technical Report

- [ ] **DOC-01**: Report includes Application Scenario & Protocol Interaction with a sequence diagram of the full TCP + UDP lifecycle.
- [ ] **DOC-02**: Report includes project-wide data structures: TCP control format, UDP custom header fields, and session management structures.
- [ ] **DOC-03**: Report includes flowcharts for server thread dispatch, reliable UDP sender/receiver state machines, and active/passive mode toggle.
- [ ] **DOC-04**: Report includes Task Assignment Matrix for module owners and collaborators.
- [ ] **DOC-05**: Report includes Self-Assessment & Peer Evaluation with contribution percentages totaling 100%.
- [ ] **DOC-06**: Report includes mandatory GenAI Usage & Code Refinement Log with exact prompts, raw outputs, and critical refinements.
- [ ] **DOC-07**: Report includes screenshots/logs for upload, download, hash comparison, connected-client table, and concurrent session test.
- [ ] **DOC-08**: Report diagrams and explanations accurately reflect the final live codebase.

## v2 Requirements

Deferred enhancements not required for the current course submission.

### Polish

- **POLISH-01**: GUI client for non-technical users.
- **POLISH-02**: TLS or encrypted authentication channel.
- **POLISH-03**: Full RFC 959 compatibility beyond the assignment command list.
- **POLISH-04**: Configurable user database with persisted password hashing.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Third-party FTP or reliable transfer libraries | Banned by the assignment; custom socket/RDT implementation is required. |
| Production deployment security | The grading focus is socket workflow, TCP/UDP split, RDT, concurrency, and documentation. |
| GUI-first implementation | CLI gives clearer demo evidence and avoids UI distraction. |
| Full FTP RFC coverage | The assignment defines the complete approved command list. |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| FOUND-01 | Phase 1 | Complete |
| FOUND-02 | Phase 1 | Complete |
| FOUND-03 | Phase 1 | Complete |
| FOUND-04 | Phase 1 | Complete |
| CTRL-01 | Phase 1 | Complete |
| CTRL-02 | Phase 1 | Complete |
| CTRL-03 | Phase 1 | Complete |
| CTRL-04 | Phase 1 | Complete |
| CTRL-05 | Phase 1 | Complete |
| CTRL-06 | Phase 1 | Complete |
| CTRL-07 | Phase 1 | Complete |
| CTRL-08 | Phase 1 | Complete |
| CTRL-09 | Phase 1 | Complete |
| FS-01 | Phase 2 | Pending |
| FS-02 | Phase 2 | Pending |
| FS-03 | Phase 2 | Pending |
| FS-04 | Phase 2 | Pending |
| FS-05 | Phase 2 | Pending |
| FS-06 | Phase 2 | Pending |
| FS-07 | Phase 2 | Pending |
| FS-08 | Phase 2 | Pending |
| FS-09 | Phase 2 | Pending |
| FS-10 | Phase 2 | Pending |
| FS-11 | Phase 2 | Pending |
| FS-12 | Phase 2 | Pending |
| MODE-01 | Phase 3 | Pending |
| MODE-02 | Phase 3 | Pending |
| MODE-03 | Phase 3 | Pending |
| MODE-04 | Phase 3 | Pending |
| MODE-05 | Phase 5 | Pending |
| MODE-06 | Phase 5 | Pending |
| RDT-01 | Phase 3 | Pending |
| RDT-02 | Phase 3 | Pending |
| RDT-03 | Phase 3 | Pending |
| RDT-04 | Phase 3 | Pending |
| RDT-05 | Phase 3 | Pending |
| RDT-06 | Phase 3 | Pending |
| RDT-07 | Phase 3 | Pending |
| RDT-08 | Phase 4 | Pending |
| RDT-09 | Phase 5 | Pending |
| XFER-01 | Phase 3 | Pending |
| XFER-02 | Phase 3 | Pending |
| XFER-03 | Phase 5 | Pending |
| XFER-04 | Phase 5 | Pending |
| XFER-05 | Phase 3 | Pending |
| XFER-06 | Phase 3 | Pending |
| XFER-07 | Phase 3 | Pending |
| XFER-08 | Phase 4 | Pending |
| HASH-01 | Phase 4 | Pending |
| HASH-02 | Phase 4 | Pending |
| HASH-03 | Phase 4 | Pending |
| CONC-01 | Phase 6 | Pending |
| CONC-02 | Phase 6 | Pending |
| CONC-03 | Phase 6 | Pending |
| CONC-04 | Phase 6 | Pending |
| DEMO-01 | Phase 7 | Pending |
| DEMO-02 | Phase 7 | Pending |
| DEMO-03 | Phase 7 | Pending |
| DEMO-04 | Phase 7 | Pending |
| DEMO-05 | Phase 7 | Pending |
| DOC-01 | Phase 7 | Pending |
| DOC-02 | Phase 7 | Pending |
| DOC-03 | Phase 7 | Pending |
| DOC-04 | Phase 7 | Pending |
| DOC-05 | Phase 7 | Pending |
| DOC-06 | Phase 7 | Pending |
| DOC-07 | Phase 7 | Pending |
| DOC-08 | Phase 7 | Pending |

**Coverage:**
- v1 requirements: 68 total
- Mapped to phases: 68
- Unmapped: 0 ✓

---
*Requirements defined: 2026-06-04*
*Last updated: 2026-06-04 after initial definition*
