#!/usr/bin/env python3
"""
server.py - The Chat Encrypt relay server.

This is a BLIND relay. It never imports crypto_util, never has the key, and
forwards only encrypted blobs between clients. It cannot read messages or
even see who is talking - identities live inside the encrypted payloads.
"""

import socket
import threading
import argparse


APP_NAME = "Chat Encrypt"


clients = []
clients_lock = threading.Lock()


def banner(port):
    line = "=" * 50
    print(line)
    print(f"  {APP_NAME} relay")
    print(f"  listening on port {port}  (Ctrl+C to stop)")
    print(f"  this server is blind: it has no key and cannot")
    print(f"  read a single message.")
    print(line + "\n")


def relay(data, sender_conn):
    """Forward raw encrypted bytes to every client except the sender."""
    with clients_lock:
        for conn in clients:
            if conn is not sender_conn:
                try:
                    conn.sendall(data)
                except OSError:
                    pass  # dead connection; its own thread will clean up


def remove_client(conn):
    with clients_lock:
        clients[:] = [c for c in clients if c is not conn]


def handle_client(conn, addr):
    """One thread per client. Relays opaque encrypted bytes; never inspects them."""
    with clients_lock:
        clients.append(conn)
    with clients_lock:
        count = len(clients)
    print(f"[+] connection from {addr[0]}  (now {count} online)")

    while True:
        try:
            data = conn.recv(4096)
        except OSError:
            break
        if not data:
            break
        relay(data, sender_conn=conn)

    remove_client(conn)
    conn.close()
    print(f"[-] {addr[0]} disconnected")


def main():
    parser = argparse.ArgumentParser(description=f"{APP_NAME} relay server.")
    parser.add_argument("-H", "--host", default="0.0.0.0", help="Bind address.")
    parser.add_argument("-p", "--port", type=int, default=5000, help="Port.")
    args = parser.parse_args()

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((args.host, args.port))
    server.listen()
    banner(args.port)

    try:
        while True:
            conn, addr = server.accept()
            threading.Thread(
                target=handle_client, args=(conn, addr), daemon=True
            ).start()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        server.close()


if __name__ == "__main__":
    main()
