#!/usr/bin/env python3
"""
client.py - The Chat Encrypt client.

Everyone who wants to chat runs this with the SAME passphrase. Messages are
encrypted on your machine before they're sent and only decrypted on the
other clients. The relay server in the middle sees only scrambled bytes.

Commands:
    /help          show commands
    /who           list who's online (that this client knows about)
    /me <action>   send an action, e.g. /me waves
    /quit          leave
"""

import os
import socket
import threading
import argparse
from datetime import datetime

from crypto_util import make_cipher, encrypt_payload, decrypt_token


APP_NAME = "Chat Encrypt"


# --- Terminal color (safe to turn off with --no-color) ---
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    GRAY = "\033[90m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    MAGENTA = "\033[35m"


def enable_windows_ansi():
    """Turn on ANSI color codes in older Windows terminals. No-op elsewhere."""
    if os.name == "nt":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            # Enable virtual-terminal processing on stdout.
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            pass  # if it fails, --no-color is the fallback


# These get blanked out if the user passes --no-color.
USE_COLOR = True


def paint(text, color):
    return f"{color}{text}{Colors.RESET}" if USE_COLOR else text


def timestamp():
    return datetime.now().strftime("%H:%M")


class ChatClient:
    def __init__(self, host, port, name, passphrase):
        self.host = host
        self.port = port
        self.name = name
        self.cipher = make_cipher(passphrase)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # People we currently believe are online (starts with just us).
        self.roster = {name}

    # --- Network helpers ---
    def send(self, payload: dict):
        """Encrypt a message dict and send it, framed with a newline."""
        try:
            self.sock.sendall(encrypt_payload(self.cipher, payload))
        except OSError:
            pass

    def connect(self):
        self.sock.connect((self.host, self.port))

    # --- Receiving ---
    def receive_loop(self):
        """
        Background thread: read encrypted bytes, reassemble whole tokens
        (message framing), decrypt, and act on each message.
        """
        buffer = b""
        while True:
            try:
                data = self.sock.recv(4096)
            except OSError:
                break
            if not data:
                print(paint("\n* disconnected from server *", Colors.YELLOW))
                os._exit(0)  # stop the whole program; input() is blocking main

            buffer += data
            while b"\n" in buffer:
                token, buffer = buffer.split(b"\n", 1)
                if token.strip():
                    self.handle_message(token)

    def handle_message(self, token):
        msg = decrypt_token(self.cipher, token)
        if msg is None:
            # Wrong passphrase or tampered message - silently ignore.
            return

        mtype = msg.get("type")
        name = msg.get("name", "???")
        ts = paint(f"[{timestamp()}]", Colors.GRAY)

        if mtype == "join":
            # Someone new arrived. Record them, and reply with our presence
            # so the newcomer learns we're here too.
            self.roster.add(name)
            print(f"{ts} {paint('* ' + name + ' joined *', Colors.GREEN)}")
            if name != self.name:
                self.send({"type": "presence", "name": self.name})

        elif mtype == "presence":
            # A quiet "I'm here" reply - just update the roster, no banner.
            self.roster.add(name)

        elif mtype == "leave":
            self.roster.discard(name)
            print(f"{ts} {paint('* ' + name + ' left *', Colors.YELLOW)}")

        elif mtype == "action":
            text = msg.get("text", "")
            print(f"{ts} {paint('* ' + name + ' ' + text + ' *', Colors.MAGENTA)}")

        else:  # normal message
            text = msg.get("text", "")
            who = paint(name, Colors.CYAN + Colors.BOLD)
            print(f"{ts} {who}: {text}")

    # --- Sending / commands ---
    def handle_command(self, line):
        """Return True to keep going, False to quit."""
        parts = line.split(" ", 1)
        cmd = parts[0].lower()
        rest = parts[1].strip() if len(parts) > 1 else ""

        if cmd in ("/quit", "/exit"):
            return False

        if cmd == "/help":
            print(paint("Commands: /help  /who  /me <action>  /quit", Colors.DIM))

        elif cmd == "/who":
            people = ", ".join(sorted(self.roster))
            print(paint(f"Online ({len(self.roster)}): {people}", Colors.DIM))

        elif cmd == "/me":
            if rest:
                self.send({"type": "action", "name": self.name, "text": rest})
                print(f"{paint('[' + timestamp() + ']', Colors.GRAY)} "
                      f"{paint('* ' + self.name + ' ' + rest + ' *', Colors.MAGENTA)}")

        else:
            print(paint(f"Unknown command: {cmd}  (try /help)", Colors.DIM))

        return True

    def run(self):
        threading.Thread(target=self.receive_loop, daemon=True).start()

        # Announce ourselves (encrypted - only peers learn the name).
        self.send({"type": "join", "name": self.name})

        try:
            while True:
                line = input()
                if not line:
                    continue
                if line.startswith("/"):
                    if not self.handle_command(line):
                        break
                else:
                    self.send({"type": "msg", "name": self.name, "text": line})
                    # Echo our own message locally (the relay doesn't send it back).
                    who = paint(self.name, Colors.CYAN + Colors.BOLD)
                    print(f"{paint('[' + timestamp() + ']', Colors.GRAY)} {who}: {line}")
        except (KeyboardInterrupt, EOFError):
            pass
        finally:
            self.send({"type": "leave", "name": self.name})
            self.sock.close()
            print(paint("Left the chat.", Colors.YELLOW))


def banner():
    line = "=" * 50
    print(line)
    print(f"  {APP_NAME}  -  end-to-end encrypted chat")
    print(line)


def main():
    parser = argparse.ArgumentParser(description=f"{APP_NAME} encrypted client.")
    parser.add_argument("-H", "--host", default="127.0.0.1", help="Server address.")
    parser.add_argument("-p", "--port", type=int, default=5000, help="Server port.")
    parser.add_argument("-n", "--name", help="Your display name.")
    parser.add_argument("--no-color", action="store_true", help="Disable colors.")
    args = parser.parse_args()

    global USE_COLOR
    if args.no_color:
        USE_COLOR = False
    else:
        enable_windows_ansi()

    banner()
    name = args.name or input("Choose a name: ").strip() or "anon"
    passphrase = input("Shared passphrase (everyone must match): ").strip()

    client = ChatClient(args.host, args.port, name, passphrase)
    try:
        client.connect()
    except OSError as e:
        print(f"Could not connect to {args.host}:{args.port} - {e}")
        return

    print(paint(f"\nConnected as '{name}'. End-to-end encrypted. "
                f"Type /help for commands.\n", Colors.GREEN))
    client.run()


if __name__ == "__main__":
    main()
