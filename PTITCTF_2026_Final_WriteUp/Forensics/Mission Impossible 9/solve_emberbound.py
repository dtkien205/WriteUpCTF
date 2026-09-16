#!/usr/bin/env python3
from pathlib import Path
import sys

from solve_emberbound import box_decrypt, tea_stream_block, fnv_check_value, run_vm


# Recovered once by the full solver after the 40 context updates.
# This skips the game-progress simulation and starts at the final message stage.
DERIVED_CTX = bytes.fromhex(
    "d113774d47447d4da2578174d69b69de"
    "cd105660c1db7cb9f18d3045ab9ce2e6"
)


def solve_fast(path):
    img = Path(path).read_bytes()
    packet = img[0xF7F20:0xF7F20 + 0x1F61]
    key = DERIVED_CTX

    try:
        for i in range(8):
            pt = box_decrypt(key, 0x46000000 + i, packet)
            key = pt[:32]
            packet = pt[32:]
    except ValueError as exc:
        raise SystemExit(
            "failed to decrypt final blob; use the PE-sieve unpacked dump, "
            f"not the packed original exe\n{exc}"
        ) from exc

    plain = bytearray()
    for off in range(0, len(packet), 8):
        ks = tea_stream_block(off >> 3, key)
        blk = packet[off:off + 8]
        plain.extend(b ^ ks[j] for j, b in enumerate(blk))

    plain = bytes(plain[:7425])
    print("ctx:", DERIVED_CTX.hex())
    print("fnv_last:", hex(fnv_check_value(plain)))
    print("VM output:", run_vm(plain).decode("ascii", "replace"))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(f"usage: {Path(sys.argv[0]).name} <unpacked_dump.exe>")
    solve_fast(sys.argv[1])
