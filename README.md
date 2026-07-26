# Hybrid FTP Application

A Python standard-library Hybrid FTP client/server for CS494 Internetworking
Protocols. It uses **TCP only for control** (commands, replies, authentication,
and session state) and a **custom reliable UDP protocol for every file payload**.

## Excellent-level capabilities

- FTP-style TCP control channel, authentication, standard three-digit replies,
  safe server-root filesystem commands, and password-redacted logs.
- Per-session UDP active/passive data mode (`PASV` / `PORT`).
- Custom 32-byte RDT header with transfer ID, sequence/ACK numbers, receive
  window, payload length, flags, and CRC-32 validation.
- Selective-repeat-style retransmission, duplicate suppression, out-of-order
  buffering, bounded sliding window, FIN/FIN_ACK completion, and abort cleanup.
- Byte-preserving text and binary transfer with temporary receive files and
  atomic final rename only after UDP completion.
- `RETR`, `STOR`, `STOU`, `APPE`, `HASH`, `TYPE`, and `MODE S`; `ABOR` safely resets an idle prepared data channel.
- Streaming SHA-256 comparisons, concurrent TCP sessions, and a visible
  active-session table through `STAT`.

## Requirements

- Python 3.14+ (standard library only)
- No dependency installation is required.

Demo credentials are deliberately local-only:

```text
username: student
password: cs494
```

## Start the server

```powershell
py -3 -m hybridftp.server --host 127.0.0.1 --port 2121 --root ./server_root --log-file ./logs/server.log
```

or:

```powershell
py -3 server.py --host 127.0.0.1 --port 2121 --root ./server_root
```

## Start the client

```powershell
py -3 -m hybridftp.client 127.0.0.1 2121
# Wrapper alternative: py -3 client.py 127.0.0.1 2121
```

To begin disconnected and issue `open 127.0.0.1 2121` from the FTP prompt:

```powershell
py -3 -m hybridftp.client --no-connect
```

The client accepts standard control commands and these local convenience aliases:

```text
put <local-file> [remote-file]        # PASV + STOR through reliable UDP
get <remote-file> [local-file]        # PASV + RETR through reliable UDP
append <local-file> <remote-file>     # PASV + APPE through reliable UDP
put-unique <local-file> [remote-name] # PASV + STOU through reliable UDP
```

A minimal binary-safe upload/download sequence:

```text
USER student
PASS cs494
TYPE I
MODE S
put .\fixture.bin fixture.bin
get fixture.bin downloaded.bin
HASH fixture.bin
STAT
QUIT
```

The client prints SHA-256 local/server comparison after a successful alias
transfer. `TYPE A` and `TYPE I` record the requested FTP type; both preserve
raw bytes so no unsafe newline conversion corrupts binary files. `MODE B` and
`MODE C` receive a clear `504` unsupported response.

## Active mode

For a defense demonstration, bind a UDP client endpoint and issue a standard
`PORT h1,h2,h3,h4,p1,p2` command before `STOR` or `RETR`. The server accepts
only an endpoint matching the TCP peer (loopback aliases are accepted locally).
Passive mode is the default behind the local `put` and `get` aliases.

## Tests

```powershell
py -3 -m unittest discover -s tests -v
```

Tests cover parsing, filesystem sandboxing, packet encoding/CRC, binary RDT
transfer, FTP command behavior, passive TCP+UDP transfer, and concurrent session
isolation.

## Generate evidence

Historical TCP-control evidence can be regenerated with:

```powershell
py -3 demo/phase1_control_demo.py
```

Generate final submission evidence with:

```powershell
py -3 demo/final_submission_demo.py
```

This produces curated, password/path-redacted output under
`demo/evidence/final/`. See `docs/technical-report.md` for the report sections,
packet diagram, workflow diagrams, assignment matrix, and evidence map.
