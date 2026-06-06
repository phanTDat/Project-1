# Hybrid FTP Application

Hybrid FTP is a CS494 socket-programming project that separates the FTP-style control plane from the data plane. Phase 1 implements the TCP control MVP: server/client startup, `220` greeting, FTP-style replies, `USER`/`PASS` login, `HELP`, `NOOP`, `QUIT`, protected command gating, logs, tests, and demo evidence.

## Constraints

- Python standard library only.
- TCP is control-only for commands, replies, authentication, and session state.
- UDP file payload transfer is deferred to later phases and must not be sent over TCP.
- Do not use `ftplib`, `pyftpdlib`, KCP, QUIC, libcurl FTP wrappers, or third-party transfer libraries.

## Demo Credentials

Phase 1 includes demo-only credentials for local testing, not production security:

- Username: `student`
- Password: `cs494`

## Start the Server

```powershell
python -m hybridftp.server --host 127.0.0.1 --port 2121 --root ./server_root
```

Top-level wrapper alternative:

```powershell
python server.py --host 127.0.0.1 --port 2121 --root ./server_root
```

The server creates `./server_root`, logs its absolute path, listens on TCP, and sends `220 Hybrid FTP server ready` when a client connects.

## Immediate Client Mode

```powershell
python -m hybridftp.client 127.0.0.1 2121
```

Top-level wrapper alternative:

```powershell
python client.py 127.0.0.1 2121
```

The client connects immediately and prints raw FTP-style replies before the `ftp> ` prompt accepts commands.

## Open-Style Client Mode

```powershell
python -m hybridftp.client --no-connect
```

At the `ftp> ` prompt:

```text
open 127.0.0.1 2121
```

Before `open`, normal FTP commands receive a local `530 Not connected; use open <host> <port>` message. After `open`, all FTP commands are sent over the TCP control channel.

## Phase 1 Command Walkthrough

```text
USER unknown
PASS anything
LIST
USER student
PASS wrong
USER student
PASS cs494
HELP
HELP USER
NOOP
BOGUS
LIST
QUIT
```

Expected behavior includes `530 Invalid username`, `503 Bad sequence of commands`, pre-login `530 Not logged in`, `331 User name okay, need password`, `530 Login incorrect`, `230 User logged in`, multiline `214` help, `200 NOOP ok`, `500 Unknown command`, authenticated placeholder `502 Command not implemented yet`, and `221 Goodbye`.

## Run Tests

```powershell
python -m unittest discover -s tests -v
```

## Generate Phase 1 Evidence

```powershell
python demo/phase1_control_demo.py
```

The script overwrites stable evidence files under `demo/evidence/phase1/`:

- `phase1-control-transcript.txt`
- `phase1-server.log`

Passwords are redacted in client transcript echoes and server logs.

## Later Phases

Phase 1 deliberately does not implement UDP payload transfer, real filesystem commands, active/passive modes, reliable UDP, binary transfer, hashes, or concurrency evidence. Those capabilities are planned in later phases.
