# Hybrid FTP Application — Technical Report

**Course:** Internetworking Protocols  
**Student:** Phan Tan Dat — `23125030`  
**Evaluation target:** Excellent Level

## 1. Application Scenario & Protocol Interaction

Hybrid FTP separates its reliable command/session channel from its custom data
protocol. TCP delivers only FTP commands and three-digit replies. Every file
payload byte goes through UDP using the project’s RDT packet format.

```text
Client                                      Server
  |---- TCP connect ------------------------>| 220 ready
  |---- USER / PASS ------------------------>| 331 / 230
  |---- PASV -------------------------------->| bind per-session UDP socket
  |<--- 227 (host, port) --------------------|
  |---- STOR remote.bin -------------------->| validate sandbox target
  |<--- 150 transfer_id ---------------------|
  |==== UDP DATA(seq=0..n), ACKs ===========>|
  |<=== UDP ACK(seq), receive-window =======|
  |==== UDP FIN ============================>|
  |<=== UDP FIN_ACK =========================|
  |<--- 226 bytes + SHA-256 -----------------|
  |---- HASH remote.bin -------------------->| streaming SHA-256
  |<--- 213 digest --------------------------|
```

`PORT h1,h2,h3,h4,p1,p2` provides the alternative active-mode endpoint. The
server validates it against the TCP peer before using it. `ABOR` resets a
prepared idle data channel; a future asynchronous transfer-worker refinement is
needed before it can interrupt an in-progress control-session transfer.

## 2. Project-Wide Data Structures

### TCP control format

Commands are UTF-8 lines ending in CRLF. `hybridftp.commands.parse_control_line`
limits lines to 1024 bytes. Replies use `hybridftp.replies.Reply` and three-digit
FTP framing; multiline replies use `code-...` lines and a final `code ...` line.

### Custom UDP RDT header

`hybridftp.rdt.Packet` uses this fixed 32-byte network-order header:

| Field | Bytes | Purpose |
|---|---:|---|
| magic `HFTP` | 4 | Reject unrelated UDP traffic |
| version | 1 | Protocol compatibility |
| flags | 1 | DATA, ACK, FIN, FIN_ACK, ABORT |
| header length | 2 | Defensive format validation |
| transfer ID | 8 | Isolates concurrent transfers |
| sequence | 4 | Packet sequence number |
| acknowledgement | 4 | Individually ACKed sequence |
| advertised window | 2 | Receiver capacity in packet slots |
| payload length | 2 | Bounded binary payload length |
| CRC-32 | 4 | Header+payload corruption detection |

Payloads are limited to 1200 bytes. A packet is discarded before file handling
if magic, version, flags, header length, length, or CRC verification fails.

### Session management

`hybridftp.session.Session` holds per-client authentication, current virtual
working directory, rename state, TYPE/MODE setting, active/passive endpoint,
and `TransferState`. `ServerContext` allocates session IDs and owns a
lock-protected `SessionRegistry`; `STAT` displays the connected-client table.

## 3. Functional Workflows

### Thread dispatch

```text
accept TCP socket -> allocate session ID -> start session worker thread
session worker -> parse/authenticate/dispatch TCP command
  PASV/PORT -> prepare per-session UDP state
  STOR/RETR -> send 150 -> execute UDP transfer -> send 226 or 426
  STAT -> read lock-protected active session snapshot
QUIT/disconnect -> close UDP socket -> unregister session
```

### Selective-repeat sender/receiver

```text
Sender: read <= window payload chunks -> send DATA(seq) -> retain in-flight
        ACK(seq) -> remove that entry -> slide base
        timeout -> retransmit only expired unacknowledged entries
        all ACKed -> FIN -> wait FIN_ACK

Receiver: validate CRC/header/transfer ID -> discard invalid
          duplicate -> ACK without writing
          in-window out-of-order -> buffer + ACK
          contiguous sequence -> write bytes, hash, drain buffered run
          expected FIN -> fsync temp -> atomic rename -> FIN_ACK
```

The sender supports a bounded sliding window, while the receiver suppresses
duplicates and only persists contiguous bytes. No incomplete download is
renamed into the requested final path.

### Active/passive toggle

```text
PASV: server binds UDP -> returns 227 -> client uses server endpoint
PORT: client announces UDP endpoint -> server validates/memorizes endpoint
next transfer consumes one endpoint -> cleanup/reset after final reply
```

## 4. Task Assignment Matrix

| Engineering component | Owner | Contribution |
|---|---|---:|
| TCP control/session/filesystem sandbox | Phan Tan Dat (23125030) | 20% |
| Custom UDP RDT and sliding window | Phan Tan Dat (23125030) | 30% |
| Transfer commands, hashes, data modes | Phan Tan Dat (23125030) | 25% |
| Testing, demo evidence, report, viva preparation | Phan Tan Dat (23125030) | 25% |

## 5. Self-Assessment & Peer Evaluation

Phan Tan Dat (23125030) completed the project as an individual contributor:
**100% contribution**. The implementation can be defended module-by-module:
packet byte layout (`rdt.py`), transfer state machines (`transfer.py`), endpoint
negotiation (`data_channel.py`), TCP command dispatch (`server.py`), and client
orchestration (`client.py`).

## 6. GenAI Usage & Code Refinement Log

The full ongoing appendix is `docs/genai-usage-log.md`. It records planning,
implementation prompts, constraints accepted/rejected, verification commands,
and student review. Before final submission, attach the exact raw transcript
exports for each implementation/review session as appendices; do not replace
raw outputs with summaries.

Critical refinement applied during implementation: AI-generated ideas were
reduced to standard-library modules only; no FTP framework, third-party RDT
library, or TCP file payload fallback was permitted. Packet parsing, temporary
file cleanup, and path sandbox checks were kept explicit so the implementation
is explainable in the oral defense.

## 7. Application Demo Evidence

Run `py -3 demo/final_submission_demo.py` to regenerate curated artifacts in
`demo/evidence/final/`:

- `final-transfer-transcript.txt` — authenticated binary upload/download,
  `150`/`226`, SHA-256 equality, and a session table.
- `final-server.log` — client/session logs plus RDT sends, ACKs, window movement,
  retransmissions when present, and completion hashes.

Automated coverage is under `tests/`: packet format, checksum rejection,
endpoint parsing, binary transfer, TCP+UDP integration, and two-client session
isolation. Execute `py -3 -m unittest discover -s tests -v` before a live demo.
