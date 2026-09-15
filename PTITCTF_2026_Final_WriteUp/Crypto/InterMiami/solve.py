#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import socket
import sys

HOST = sys.argv[1] if len(sys.argv) > 1 else "144.79.188.39"
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 46786
PAIR_FILE = sys.argv[3] if len(sys.argv) > 3 else "pairs.txt"
DEFAULT_BULK = 1


class Tube:
    def __init__(self, host: str, port: int):
        self.sock = socket.create_connection((host, port))
        self.buf = b""

    def recv_until(self, token: bytes) -> bytes:
        while token not in self.buf:
            chunk = self.sock.recv(1 << 16)
            if not chunk:
                raise EOFError("connection closed")
            self.buf += chunk
        i = self.buf.index(token) + len(token)
        out, self.buf = self.buf[:i], self.buf[i:]
        return out

    def readline(self) -> bytes:
        while b"\n" not in self.buf:
            chunk = self.sock.recv(1 << 16)
            if not chunk:
                raise EOFError("connection closed")
            self.buf += chunk
        i = self.buf.index(b"\n") + 1
        out, self.buf = self.buf[:i], self.buf[i:]
        return out.strip()

    def sendline(self, s: str) -> None:
        self.sock.sendall(s.encode() + b"\n")


def grab_int(pattern: bytes, data: bytes, default: int | None = None) -> int:
    m = re.search(pattern, data)
    if not m:
        if default is not None:
            return default
        raise ValueError(f"missing field: {pattern!r}")
    return int(m.group(1).replace(b",", b""))


def collect_pairs() -> tuple[int, int, list[int]]:
    r = Tube(HOST, PORT)
    banner = r.recv_until(b"> ")
    q = grab_int(rb"q\s*=\s*([0-9,]+)", banner)
    need = grab_int(rb"available pairs\s*=\s*([0-9,]+)", banner)
    bulk = grab_int(rb"bulk\s*=\s*([0-9,]+)", banner, DEFAULT_BULK)

    ys = [0] * need
    seen = bytearray(need)
    collected = 0

    while collected < need:
        cnt = min(bulk, need - collected)
        r.sendline(f"1 {cnt}")
        for _ in range(cnt):
            p = int(r.readline().split(b"=", 1)[1])
            c = int(r.readline().split(b"=", 1)[1])
            if not 0 <= p < need:
                raise RuntimeError(f"plaintext outside expected range: {p}")
            if seen[p]:
                raise RuntimeError(f"server repeated plaintext p = {p}")
            seen[p] = 1
            ys[p] = c
            collected += 1

        print(f"[+] collected {collected}/{need}", end="\r", flush=True)
        r.recv_until(b"> ")

    with open(PAIR_FILE, "w", buffering=1024 * 1024) as f:
        f.write(f"# q = {q}\n# pairs = {need}\n")
        for p, c in enumerate(ys):
            f.write(f"{p} {c}\n")

    print(f"\n[+] saved to {PAIR_FILE}")
    return q, need, ys


def load_pairs() -> tuple[int | None, int | None, list[int]]:
    if not os.path.exists(PAIR_FILE):
        return None, None, []

    q: int | None = None
    need: int | None = None
    ys: list[int] = []
    seen = bytearray()
    loaded = 0

    with open(PAIR_FILE) as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if line.startswith("# q"):
                q = int(line.split("=", 1)[1])
            elif line.startswith("# pairs"):
                need = int(line.split("=", 1)[1])
                ys = [0] * need
                seen = bytearray(need)
            elif line and not line.startswith("#"):
                if need is None:
                    raise RuntimeError("# pairs header must appear before pair data")
                p, c = map(int, line.split())
                if not 0 <= p < need:
                    raise RuntimeError(f"bad p on line {lineno}: {p}")
                if seen[p]:
                    raise RuntimeError(f"duplicate p on line {lineno}: {p}")
                seen[p] = 1
                ys[p] = c
                loaded += 1

    if need is not None and loaded != need:
        return q, need, []
    return q, need, ys


def build_invfact(n: int, q: int) -> list[int]:
    fact = 1
    for k in range(2, n + 1):
        fact = fact * k % q
    invfact = [1] * (n + 1)
    invfact[n] = pow(fact, q - 2, q)
    for k in range(n, 0, -1):
        invfact[k - 1] = invfact[k] * k % q
    return invfact


def lagrange_at(x: int, ys: list[int], q: int, invfact: list[int]) -> int:
    x %= q
    n = len(ys) - 1
    if 0 <= x <= n:
        return ys[x]

    pref = [1] * (n + 2)
    for i in range(n + 1):
        pref[i + 1] = pref[i] * ((x - i) % q) % q

    all_prod = pref[n + 1]
    inv_all = pow(all_prod, q - 2, q)
    ans, suff = 0, 1
    for i in range(n, -1, -1):
        inv_x_i = pref[i] * suff % q * inv_all % q
        term = all_prod * inv_x_i % q * invfact[i] % q * invfact[n - i] % q
        if (n - i) & 1:
            term = -term % q
        ans = (ans + ys[i] * term) % q
        suff = suff * ((x - i) % q) % q
    return ans


if __name__ == "__main__":
    q, need, ys = load_pairs()
    if q is None or need is None or len(ys) != need:
        q, need, ys = collect_pairs()
    else:
        print(f"[+] loaded {len(ys)} pairs from {PAIR_FILE}")

    print("[+] building interpolation helper")
    invfact = build_invfact(len(ys) - 1, q)

    while True:
        s = input("Plaintext p = ").strip()
        if not s:
            break
        print("Ciphertext c =", lagrange_at(int(s, 0), ys, q, invfact))
