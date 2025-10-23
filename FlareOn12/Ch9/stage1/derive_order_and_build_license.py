import argparse, json, struct, sys
from pathlib import Path
from typing import Dict, List, Set

def is_trivial_permutation(H: List[int]) -> bool:
    n = len(H)
    return len(set(H)) == n and set(H) == set(range(n))

def derive_trivial_order(H: List[int]) -> List[int]:
    # H[id] = position
    n = len(H)
    order = [0]*n
    for module_id, pos in enumerate(H):
        if pos < 0 or pos >= n:
            raise ValueError(f"Out-of-range position {pos} for module {module_id}")
        if order[pos] != 0 or pos == 0:
            # We'll verify properly; allow duplicates detection below.
            pass
        order[pos] = module_id
    # Validate uniqueness
    if len(set(order)) != len(order):
        raise ValueError("Duplicate positions detected; not trivial after all.")
    return order

def solve_with_dependencies(H: List[int], closures: Dict[int, List[int]]) -> Dict[int, int]:
    """
    closures[m] = list of dependency ids including m itself.
    Equations: For each d: H[d] = sum_{m : d in closures[m]} PPos[m]
    Build inverse index: contributors[d] = set of m.
    Then iteratively pick any d with single contributor left.
    """
    n = len(H)
    # Build contributor sets
    contributors: Dict[int, Set[int]] = {d: set() for d in range(n)}
    for m, deps in closures.items():
        for d in deps:
            contributors[d].add(m)

    # Copy H so we can subtract as we solve
    residual = H[:]
    solution: Dict[int, int] = {}
    unresolved_contributors: Dict[int, Set[int]] = {d: set(ms) for d, ms in contributors.items()}

    changed = True
    while len(solution) < len(closures) and changed:
        changed = False
        singles = [d for d, ms in unresolved_contributors.items() if len(ms) == 1]
        for d in singles:
            (m,) = tuple(unresolved_contributors[d])
            if m in solution:
                continue
            # Assign position of module m
            pos = residual[d]
            solution[m] = pos
            changed = True
            # Subtract its contribution from all rows where it appears
            for d2, ms2 in unresolved_contributors.items():
                if m in ms2 and d2 != d:
                    residual[d2] -= pos
                ms2.discard(m)
        # Optional: detect negatives / inconsistencies early
        for r in residual:
            if r < 0:
                raise ValueError("Residual went negative; inconsistent closures or corrupted H.")

    if len(solution) != len(closures):
        unresolved = set(closures.keys()) - set(solution.keys())
        raise RuntimeError(f"Could not resolve all positions; unresolved modules: {sorted(unresolved)[:20]} ...")

    # Validate solution is a permutation
    values = list(solution.values())
    if len(set(values)) != len(values):
        raise RuntimeError("Derived positions are not unique (duplicate positions).")

    return solution

def build_license(order: List[int], payloads: Dict[int, bytes], out_path: Path):
    """
    order: list of module ids in positional order 0..N-1
    payloads: mapping module id -> 32-byte payload (must pass checker later)
    For any missing module, we write 32 zero bytes as placeholder.
    """
    with out_path.open("wb") as f:
        for module_id in order:
            data = payloads.get(module_id, b"\x00"*32)
            if len(data) != 32:
                raise ValueError(f"Payload for module {module_id} length {len(data)} != 32")
            f.write(struct.pack("<H", module_id))
            f.write(data)
    print(f"[+] Wrote license skeleton: {out_path} ({len(order)} records)")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--H", required=True, help="JSON file containing H array (length 10000)")
    ap.add_argument("--closures", help="JSON mapping moduleId -> list of dependency ids (including itself)")
    ap.add_argument("--payloads", help="JSON mapping moduleId -> hex string of 32 bytes (optional)")
    ap.add_argument("--out", default="license.bin", help="Output license file")
    args = ap.parse_args()

    with open(args.H, "r") as f:
        H = json.load(f)
    if len(H) != 10000:
        print("[-] H length must be 10000", file=sys.stderr)
        sys.exit(1)

    payloads: Dict[int, bytes] = {}
    if args.payloads:
        import binascii
        with open(args.payloads, "r") as f:
            raw = json.load(f)
        for k, hexstr in raw.items():
            mid = int(k)
            payloads[mid] = binascii.unhexlify(hexstr)
    
    if not args.closures:
        # Attempt trivial path
        if is_trivial_permutation(H):
            order = derive_trivial_order(H)
            build_license(order, payloads, Path(args.out))
            print("[+] Trivial case handled.")
        else:
            print("[-] Non-trivial dependencies detected. Provide --closures JSON.", file=sys.stderr)
            sys.exit(2)
    else:
        with open(args.closures, "r") as f:
            closures_json = json.load(f)
        # Normalize keys to int
        closures = {int(k): list(map(int, v)) for k, v in closures_json.items()}
        solution = solve_with_dependencies(H, closures)
        # Build order list by inverting position mapping
        n = len(solution)
        order = [None]*n
        for m, pos in solution.items():
            if pos < 0 or pos >= n:
                raise ValueError(f"Position {pos} for module {m} out of range")
            if order[pos] is not None:
                raise ValueError(f"Duplicate position {pos} for modules {order[pos]} and {m}")
            order[pos] = m
        if any(o is None for o in order):
            raise RuntimeError("Gap in derived ordering.")
        build_license(order, payloads, Path(args.out))
        print("[+] Non-trivial dependency case solved (skeleton).")

if __name__ == "__main__":
    main()