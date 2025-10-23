import json, argparse, sys
from collections import defaultdict, Counter
from typing import Dict, List

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--closures", required=True, help="closures.json from build_closures.py")
    ap.add_argument("--H", required=True, help="hardcoded_expected.json (array of 10000 uint32s)")
    args = ap.parse_args()

    with open(args.closures, "r") as f:
        closures = {int(k): v for k, v in json.load(f).items()}
    with open(args.H, "r") as f:
        H = json.load(f)
    if len(H) != 10000:
        print("[-] H length != 10000", file=sys.stderr)
        sys.exit(1)

    # Basic checks
    bad = [k for k,v in closures.items() if k not in v]
    if bad:
        print(f"[!] {len(bad)} closures missing self id (example: {bad[:5]})")
    else:
        print("[+] All closures include self id.")

    # Inverse contributor sets
    contributors = defaultdict(set)
    for m, deps in closures.items():
        for d in deps:
            contributors[d].add(m)

    # Orphans: modules that appear in no closure (should be none)
    orphans = [d for d in range(len(H)) if d not in contributors]
    if orphans:
        print(f"[!] {len(orphans)} ids never appear in any closure: {orphans[:10]}")
    else:
        print("[+] Every module appears in at least one closure.")

    size_counts = Counter(len(v) for v in closures.values())
    print(f"[+] Closure size histogram (top 10): {size_counts.most_common(10)}")

    max_contrib = max(len(ms) for ms in contributors.values())
    print(f"[+] Max contributor count for any id: {max_contrib}")

    # Heuristic: If large overlaps, elimination ordering matters
    ambiguous = [d for d, ms in contributors.items() if len(ms) > 50]
    if ambiguous:
        print(f"[*] {len(ambiguous)} ids have >50 contributors (sample {ambiguous[:5]}).")

    # Quick consistency (non-negative H)
    neg = [i for i,v in enumerate(H) if v < 0]
    if neg:
        print(f"[!] Negative H entries (unexpected): {neg[:5]}")
    else:
        print("[+] All H entries non-negative.")

if __name__ == "__main__":
    main()