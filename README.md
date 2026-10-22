# Chat Encrypt

**An end-to-end encrypted terminal chat application, built from raw sockets in Python.**

---

## What it is

Chat Encrypt lets multiple people chat over a network with **end-to-end encryption**. Messages are encrypted on the sender's machine and only decrypted on the recipients' machines. The server in the middle is a *blind relay*: it forwards scrambled bytes and has no key, so it cannot read a single message — or even see who is talking.

It's built directly on Python's standard `socket` library (no chat framework) plus the audited [`cryptography`](https://cryptography.io) library for encryption.

## Features

- **End-to-end encryption** — AES-based authenticated encryption (Fernet); the relay never holds a key.
- **Passphrase-based** — everyone joins with a shared passphrase; it never crosses the network.
- **Multi-client** — many people chat at once, each handled on its own thread.
- **Live presence** — `/who` lists who's online; join/leave notices.
- **Commands** — `/help`, `/who`, `/me <action>`, `/quit`.
- **Timestamps and color** in the terminal (disable with `--no-color`).
- **Tamper detection** — altered or wrong-key messages are rejected, not shown as garbage.

## Security model

| Component | Can it read messages? | Why |
|-----------|----------------------|-----|
| **Client** | Yes | It holds the key (derived locally from the passphrase). |
| **Server/relay** | **No** | It never receives the passphrase or key and doesn't import any crypto. |
| **Network eavesdropper** | **No** | Only encrypted tokens travel over the wire. |
| **Someone with the wrong passphrase** | **No** | Decryption fails with `InvalidToken`. |

Proof of the blind-relay claim: `server.py` contains no cryptography import at all.

The encryption key is derived from the passphrase with **PBKDF2-HMAC-SHA256** (600,000 iterations), which makes brute-forcing the passphrase slow. Messages use **Fernet**, which encrypts *and* authenticates, so tampering is detected.

## How it works

```
 Alice (client)                 Server (blind relay)                Bob (client)
 --------------                 --------------------                ------------
 types "hi"
 encrypt with key   --token-->  receives opaque bytes  --token-->   decrypt with key
                                forwards, cannot read                shows "Alice: hi"
```

- The passphrase is stretched into a key locally (`crypto_util.derive_key`).
- Each message is a JSON payload, encrypted into a Fernet **token**, and sent newline-terminated.
- The server relays tokens to all other clients without inspecting them.
- Clients reassemble whole tokens from the TCP stream (message framing), decrypt, and display.

## Requirements

- Python 3.8+
- `cryptography` (see `requirements.txt`)

```bash
pip install -r requirements.txt
```

## Usage

Start the relay (one machine):

```bash
python server.py
```

Each person runs the client with the **same passphrase**:

```bash
python client.py -n Alice
python client.py -n Bob
```

To chat across a real network, point clients at the server's IP:

```bash
python client.py -H 192.168.1.50 -p 5000 -n Charlie
```

Commands inside the chat: `/help`, `/who`, `/me waves`, `/quit`.

## Project structure

```
chat-encrypt/
├── crypto_util.py     # key derivation + encrypt/decrypt (the only crypto)
├── server.py          # blind relay — no key, cannot read messages
├── client.py          # encrypted client, commands, presence, UI
├── requirements.txt
└── README.md
```

## Known limitations / roadmap

Honest about what this is and isn't:

- **Passphrase distribution is out-of-band.** Everyone must agree on the passphrase beforehand. The natural next step is a **Diffie-Hellman key exchange** so clients agree on a key over the network without ever sending it.
- **Unexpected disconnects** (a crash, not `/quit`) don't broadcast a "left" notice. A heartbeat/keepalive would fix this.
- **No persistent accounts or message history** — this is a live relay, not a stored-message service.
- **Terminal display** can tangle if a message arrives mid-typing; a TUI library (`prompt_toolkit`) would smooth that out.

## What I learned building this

Sockets and the client/server model, multithreaded connection handling, TCP as a byte stream and message framing, symmetric authenticated encryption, key derivation (PBKDF2), and the practical meaning of "end-to-end" — including why a blind relay *structurally* cannot read traffic.
