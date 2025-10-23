#!/usr/bin/env python3
"""
Produce per-iteration XOR snapshots for all DLLs involved at the stage of the current module,
using:
  - module_order.json: list of 10,000 module IDs (0..9999)
  - closure.json: mapping module_id -> list of unique IDs in its closure (including itself)

For iteration i with primary module P = module_order[i]:
  - Snapshot dict for all k in S_i (closure set): { str(k): B[k] }   # BEFORE AggregatePass(i)
  - Then AggregatePass(i): for all k in S_i, B[k] = (B[k] + i) & 0xFFFFFFFF

Outputs:
  - NDJSON mode: one line per iteration with the snapshot dict.
  - File-per-iteration mode: one JSON file per iteration under out_dir/snapshots/

This lets you use the correct XOR values for both the primary module and any imported DLLs
at the time the primary module executes its transforms.
"""

import argparse
import json
import os
import struct
from typing import Dict, List, Set

NUM_MODULES = 10000
UINT32_MASK = 0xFFFFFFFF


def load_module_order(path: str) -> List[int]:
    """Load module order from JSON list or newline-separated text file."""
    if not os.path.isfile(path):
        raise FileNotFoundError(f"module order file not found: {path}")

    # Try JSON first
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ValueError("module_order.json must be a JSON list of integers")
        order = [int(x) for x in data]
    except json.JSONDecodeError:
        # Fallback: text file with one id per line
        with open(path, "r", encoding="utf-8") as f:
            order = [int(line.strip()) for line in f if line.strip()]

    if len(order) != NUM_MODULES:
        raise ValueError(f"module order length {len(order)} != expected {NUM_MODULES}")
    for i, mid in enumerate(order):
        if not (0 <= mid < NUM_MODULES):
            raise ValueError(f"module_order[{i}]={mid} out of range 0..{NUM_MODULES-1}")
    return order


def load_closure(path: str) -> Dict[int, Set[int]]:
    """
    Load closure.json mapping module id -> list of ids in its closure.
    Ensures sets are unique, ids in 0..9999, and include the primary id itself.
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"closure file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, dict):
        raise ValueError("closure.json must be a dict: {module_id: [ids...], ...}")

    closure: Dict[int, Set[int]] = {}
    for k, v in raw.items():
        mid = int(k)
        s = set(int(x) for x in v)
        for x in s:
            if not (0 <= x < NUM_MODULES):
                raise ValueError(f"Invalid id in closure[{mid}]: {x} (must be 0..{NUM_MODULES-1})")
        if not (0 <= mid < NUM_MODULES):
            raise ValueError(f"Invalid module id in closure: {mid}")
        s.add(mid)  # ensure primary included
        closure[mid] = s
    return closure


def main():
    ap = argparse.ArgumentParser(description="Make per-iteration XOR snapshots for all DLLs involved.")
    ap.add_argument("--module-order", required=True, help="Path to module's order json or text (10,000 ids)")
    ap.add_argument("--closure", required=True, help="Path to closure.json (module_id -> [closure ids])")
    ap.add_argument("--out-dir", required=True, help="Output directory")
    ap.add_argument("--mode", choices=["ndjson", "files"], default="ndjson",
                    help="ndjson = one JSON per line; files = one JSON per iteration (default: ndjson)")
    ap.add_argument("--keys-as-string", action="store_true",
                    help="Write dict keys as strings (JSON standard). If not set, keys will be ints (ok for Python).")
    ap.add_argument("--dump-final-buffer", type=str, default=None,
                    help="Optional path to write final 40,000-byte buffer (<I × 10,000)")
    ap.add_argument("--compare-hardcoded", type=str, default=None,
                    help="Optional path to expected 40,000-byte blob for comparison")
    args = ap.parse_args()

    # Load inputs
    order = load_module_order(args.module_order)
    closure_map = load_closure(args.closure)

    # Prepare output dir(s)
    os.makedirs(args.out_dir, exist_ok=True)
    ndjson_path = os.path.join(args.out_dir, "snapshots.ndjson")
    files_dir = os.path.join(args.out_dir, "snapshots")
    if args.mode == "files":
        os.makedirs(files_dir, exist_ok=True)

    # Accumulator buffer (uint32)
    B = [0] * NUM_MODULES

    # Produce snapshots
    if args.mode == "ndjson":
        with open(ndjson_path, "w", encoding="utf-8") as fout:
            for i, mid in enumerate(order):
                S_i = closure_map.get(mid, {mid})
                S_i = {x for x in S_i if 0 <= x < NUM_MODULES}
                S_i.add(mid)

                # Snapshot BEFORE AggregatePass(i)
                if args.keys_as_string:
                    snap = {str(k): int(B[k]) for k in S_i}
                else:
                    snap = {int(k): int(B[k]) for k in S_i}
                fout.write(json.dumps(snap, separators=(",", ":")) + "\n")

                # AggregatePass(i): add +i to each id in S_i (mod 2^32)
                for k in S_i:
                    B[k] = (B[k] + i) & UINT32_MASK

        print(f"[OK] Wrote NDJSON snapshots to: {ndjson_path}")

    else:  # files mode
        for i, mid in enumerate(order):
            S_i = closure_map.get(mid, {mid})
            S_i = {x for x in S_i if 0 <= x < NUM_MODULES}
            S_i.add(mid)

            # Snapshot BEFORE AggregatePass(i)
            snap = {str(k): int(B[k]) for k in S_i} if args.keys_as_string else {int(k): int(B[k]) for k in S_i}

            # Name like 0000_5582.json (zero-padded iteration)
            fname = os.path.join(files_dir, f"{i:04d}_{mid}.json")
            with open(fname, "w", encoding="utf-8") as f:
                json.dump(snap, f, separators=(",", ":"))

            # AggregatePass(i)
            for k in S_i:
                B[k] = (B[k] + i) & UINT32_MASK

        print(f"[OK] Wrote per-iteration snapshot files to: {files_dir}")

    # Optional: final buffer dump
    if args.dump_final_buffer:
        with open(args.dump_final_buffer, "wb") as fb:
            for v in B:
                fb.write(struct.pack("<I", v))
        print(f"[OK] Wrote final buffer to: {args.dump_final_buffer}")

    # Optional: compare hardcoded expected blob
    if args.compare_hardcoded:
        with open(args.compare_hardcoded, "rb") as fexp:
            expected = fexp.read()
        final_bytes = b"".join(struct.pack("<I", v) for v in B)
        if len(expected) != len(final_bytes):
            print(f"[COMPARE] Size mismatch: expected {len(expected)} bytes, got {len(final_bytes)}")
        elif expected == final_bytes:
            print("[COMPARE] Final buffer matches expected blob")
        else:
            # Show first mismatch to aid debugging
            for off in range(0, len(expected), 4):
                if expected[off:off+4] != final_bytes[off:off+4]:
                    idx = off // 4
                    exp_val = struct.unpack("<I", expected[off:off+4])[0]
                    got_val = struct.unpack("<I", final_bytes[off:off+4])[0]
                    print(f"[COMPARE] Mismatch at index {idx}: expected {exp_val}, got {got_val}")
                    break


if __name__ == "__main__":
    main()