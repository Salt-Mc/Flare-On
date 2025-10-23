import pefile
import argparse
import json
import re
from pathlib import Path
from functools import lru_cache
import sys
from typing import Dict, List, Set
import tqdm

NUMERIC_IMPORT_RE = re.compile(r'^[0-9]{4}')

def is_numeric_import(name_bytes: bytes) -> bool:
    """
    Replicates the loader's check: first four chars each '0'..'9'.
    """
    if len(name_bytes) < 4:
        return False
    for b in name_bytes[:4]:
        if b < 0x30 or b > 0x39:
            return False
    return True

def dll_id_from_name(name_bytes: bytes) -> int:
    # Use same atoi-like approach (stop at first non-digit)
    s = ""
    for b in name_bytes:
        if 0x30 <= b <= 0x39:
            s += chr(b)
        else:
            break
    return int(s) if s else None

def parse_numeric_deps(pe_path: Path) -> List[int]:
    try:
        pe = pefile.PE(str(pe_path), fast_load=True)
        pe.parse_data_directories(
            directories=[
                pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_IMPORT']
            ]
        )
    except Exception as e:
        print(f"[-] Failed to parse {pe_path.name}: {e}", file=sys.stderr)
        return []
    deps = []
    if not hasattr(pe, 'DIRECTORY_ENTRY_IMPORT'):
        return deps
    for entry in pe.DIRECTORY_ENTRY_IMPORT:
        raw_name = entry.dll  # bytes
        if is_numeric_import(raw_name):
            mid = dll_id_from_name(raw_name)
            if mid is not None:
                deps.append(mid)
    return deps

def load_all_module_deps(mod_dir: Path, limit: int) -> Dict[int, List[int]]:
    deps: Dict[int, List[int]] = {}
    for mid in tqdm.tqdm(range(limit), desc="Loading module dependencies", unit="module"):
        dll_path = mod_dir / f"{mid}.dll"
        if not dll_path.is_file():
            print(f"[-] Missing module file: {dll_path}", file=sys.stderr)
            deps[mid] = []
            continue
        deps[mid] = parse_numeric_deps(dll_path)
    return deps

def build_closures(dep_graph: Dict[int, List[int]]) -> Dict[int, List[int]]:
    sys.setrecursionlimit(20000)
    visiting: Set[int] = set()
    closures: Dict[int, Set[int]] = {}

    @lru_cache(maxsize=None)
    def dfs(mid: int) -> Set[int]:
        if mid in visiting:
            # Cycle detected; return just itself to break
            print(f"[!] Cycle detected involving {mid}; truncating closure.")
            return {mid}
        visiting.add(mid)
        closure_set = {mid}
        for dep in dep_graph.get(mid, []):
            closure_set |= dfs(dep)
        visiting.remove(mid)
        return closure_set

    for mid in tqdm.tqdm(dep_graph.keys(), desc="Building closures", unit="module"):
        closures[mid] = dfs(mid)

    # Convert to sorted list
    return {mid: sorted(list(s)) for mid, s in closures.items()}

def stats(closures: Dict[int, List[int]]):
    sizes = [len(v) for v in closures.values()]
    mx = max(sizes)
    mn = min(sizes)
    avg = sum(sizes)/len(sizes)
    from collections import Counter
    common = Counter(sizes).most_common(5)
    print(f"[+] Closure size stats: min={mn} max={mx} avg={avg:.3f}")
    print(f"[+] Most common sizes: {common}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("modules_dir", help="Directory containing N.dll files (0..9999)")
    ap.add_argument("--count", type=int, default=10000, help="Number of modules (default 10000)")
    ap.add_argument("--out", default="closures.json", help="Output JSON filename")
    ap.add_argument("--deps-out", help="Optional: write raw direct dependency graph JSON")
    args = ap.parse_args()

    mod_dir = Path(args.modules_dir)
    if not mod_dir.is_dir():
        print(f"[-] Not a directory: {mod_dir}", file=sys.stderr)
        sys.exit(1)

    print("[*] Parsing direct numeric dependencies...")
    dep_graph = load_all_module_deps(mod_dir, args.count)

    print("[*] Building transitive closures...")
    closures = build_closures(dep_graph)

    stats(closures)

    with open(args.out, "w") as f:
        json.dump({str(k): v for k, v in closures.items()}, f)
    print(f"[+] Wrote closures to {args.out}")

    if args.deps_out:
        with open(args.deps_out, "w") as f:
            json.dump({str(k): v for k, v in dep_graph.items()}, f)
        print(f"[+] Wrote direct dependency graph to {args.deps_out}")

    # Quick heuristic: are all closure sizes 1? (Trivial permutation)
    if all(len(v) == 1 for v in closures.values()):
        print("[+] All closures are singleton => trivial ordering case.")
    else:
        multi = sum(1 for v in closures.values() if len(v) > 1)
        print(f"[*] Non-trivial: {multi} modules have dependencies >1.")

if __name__ == "__main__":
    main()