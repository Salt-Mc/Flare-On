import json, argparse, sys
from collections import deque

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--closures", required=True)
    ap.add_argument("--H", required=True)
    ap.add_argument("--count", type=int, default=10000)
    ap.add_argument("--verify-permutation", action="store_true")
    args = ap.parse_args()

    with open(args.closures, "r") as f:
        closures = {int(k): v for k,v in json.load(f).items()}
    with open(args.H, "r") as f:
        H = json.load(f)

    N = args.count
    if len(H) != N:
        print("[-] H length mismatch", file=sys.stderr)
        sys.exit(1)

    # Build contributors (row -> list of modules contributing)
    contributors = [[] for _ in range(N)]
    for m, deps in closures.items():
        for d in deps:
            contributors[d].append(m)

    remaining_sum = H[:]  # residual sums for each row
    remaining_contribs = [set(lst) for lst in contributors]

    # Queue rows that currently have exactly one contributor
    q = deque([d for d in range(N) if len(remaining_contribs[d]) == 1])
    position = {}  # module -> position
    used_positions = set()

    processed_rows = 0
    while q:
        d = q.popleft()
        if len(remaining_contribs[d]) != 1:
            continue
        (m,) = tuple(remaining_contribs[d])
        if m in position:
            continue  # already solved this variable through another row
        pos = remaining_sum[d]
        if args.verify_permutation and (pos < 0 or pos >= N or pos in used_positions):
            print(f"[!] Invalid position candidate {pos} for module {m}; aborting.", file=sys.stderr)
            sys.exit(2)
        position[m] = pos
        used_positions.add(pos)
        processed_rows += 1
        # Subtract this variable from every row it appears in (its closure)
        for d2 in closures[m]:
            if m in remaining_contribs[d2]:
                remaining_sum[d2] -= pos
                remaining_contribs[d2].discard(m)
                if len(remaining_contribs[d2]) == 1:
                    q.append(d2)

    print(f"[+] Solved {len(position)} module positions by peeling.")
    if len(position) == N:
        print("[+] Full solution found.")
        # Build order array (inverse permutation)
        order = [None]*N
        for m,pos in position.items():
            if pos < 0 or pos >= N:
                print(f"[!] Out-of-range pos {pos} for module {m}", file=sys.stderr)
                sys.exit(3)
            if order[pos] is not None:
                print(f"[!] Duplicate position {pos} for modules {order[pos]} and {m}", file=sys.stderr)
                sys.exit(4)
            order[pos] = m
        if any(o is None for o in order):
            print("[-] Gap in order construction", file=sys.stderr)
        else:
            with open("ordering.json", "w") as f:
                json.dump(order, f)
            print("[+] Wrote ordering.json (license module id sequence).")
    else:
        unresolved = N - len(position)
        print(f"[*] Peeling stalled with {unresolved} modules unresolved.")
        print("[*] Next step: need enhanced strategy (subset-difference or dense solve).")

if __name__ == "__main__":
    main()