#!/usr/bin/env python3
import secrets
import socketserver
import sys
from typing import Optional

from algorithm import init_cipher
from setup import BULK_LIMIT, FLAG, HOST, PORT, TIMEOUT_SECONDS

CIPHER = init_cipher()


def _log(msg: str) -> None:
    print(f"[server] {msg}", file=sys.stderr, flush=True)


class RandomPairOrder:
    __slots__ = ("size", "position", "_bits", "_mask", "_rounds")

    def __init__(self, size: int) -> None:
        if size < 1:
            raise ValueError("size must be positive")

        self.size = size
        self.position = 0
        self._bits = max(2, (size - 1).bit_length())
        self._mask = (1 << self._bits) - 1

        self._rounds: tuple[tuple[int, int, int, int, int], ...] = tuple(
            (
                secrets.randbits(self._bits) | 1,
                secrets.randbits(self._bits),
                secrets.randbits(self._bits),
                1 + secrets.randbelow(self._bits - 1),
                1 + secrets.randbelow(self._bits - 1),
            )
            for _ in range(4)
        )

    @property
    def remaining(self) -> int:
        return self.size - self.position

    def _permute_power_of_two_domain(self, value: int) -> int:
        x = value
        bits = self._bits
        mask = self._mask

        for multiplier, additive, xor_key, shift, rotation in self._rounds:
            x ^= xor_key
            x = (x * multiplier + additive) & mask
            x ^= x >> shift
            x &= mask
            x = ((x << rotation) | (x >> (bits - rotation))) & mask

        return x

    def next_plaintext(self) -> int:
        if self.position >= self.size:
            raise StopIteration("all pairs have already been returned")

        value = self.position
        self.position += 1
        while True:
            value = self._permute_power_of_two_domain(value)
            if value < self.size:
                return value


class ChallengeHandler(socketserver.StreamRequestHandler):
    def setup(self) -> None:
        super().setup()
        self.request.settimeout(TIMEOUT_SECONDS)
        self.pair_order = RandomPairOrder(CIPHER.max_pairs)

    def send(self, data: str) -> None:
        self.wfile.write(data.encode())
        self.wfile.flush()

    def sendline(self, data: str = "") -> None:
        self.send(data + "\n")

    def recvline(self, limit: int = 4096) -> Optional[str]:
        line = self.rfile.readline(limit)
        if not line:
            return None
        return line.decode(errors="ignore").strip()

    def banner(self) -> None:
        info = CIPHER.public_info()
        self.sendline("+--------------------------+")
        self.sendline("|  WELCOME TO PTITCTF 2026 |")
        self.sendline("+--------------------------+")
        self.sendline("Blackbox encryption service")
        self.sendline(f"q = {info['q']}")
        self.sendline(f"available pairs = {info['available_pairs']}")
        self.sendline()

    def menu(self) -> None:
        self.sendline("1. get pair")
        self.sendline("2. get flag")
        self.send("> ")

    def handle_get_pair(self, count: int) -> None:
        if self.pair_order.remaining == 0:
            self.sendline("No more pairs for this connection.")
            return

        count = max(1, min(count, BULK_LIMIT, self.pair_order.remaining))
        out = []
        for _ in range(count):
            p = self.pair_order.next_plaintext()
            _, c = CIPHER.get_pair(p)
            out.append(f"p = {p}\n")
            out.append(f"c = {c}\n")
        self.send("".join(out))

    def handle_get_flag(self) -> None:
        challenge_plaintext = CIPHER.random_challenge_plaintext()
        self.sendline(f"p = {challenge_plaintext}")
        self.send("c = ")
        line = self.recvline()
        if line is None:
            return

        try:
            submitted = int(line, 0)
        except ValueError:
            self.sendline("Ciphertext không hợp lệ")
            return

        if CIPHER.verify(challenge_plaintext, submitted):
            self.sendline("Chúc mừng bạn đã thám mã thành công!")
            self.sendline(f"Flag: {FLAG}")
        else:
            self.sendline("Sai rồi!")

    def handle(self) -> None:
        self.banner()

        while True:
            self.menu()
            line = self.recvline()
            if line is None:
                return
            if not line:
                continue

            parts = line.split()
            cmd = parts[0].lower()

            if cmd in {"q", "quit", "exit"}:
                self.sendline("bye")
                return

            if cmd in {"1", "get", "pair", "getpair"}:
                count = 1
                if len(parts) >= 2:
                    try:
                        count = int(parts[1], 10)
                    except ValueError:
                        count = 1
                self.handle_get_pair(count)
                continue

            if cmd in {"2", "flag", "getflag"}:
                self.handle_get_flag()
                return

            self.sendline("Invalid choice.")


class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main() -> None:
    info = CIPHER.public_info()
    _log(f"listening on {HOST}:{PORT}")
    _log(f"available_pairs={info['available_pairs']:,}")
    with ThreadedTCPServer((HOST, PORT), ChallengeHandler) as server:
        server.serve_forever()


if __name__ == "__main__":
    main()
