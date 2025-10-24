import json
import argparse
from collections import defaultdict

def parse_args():
    ap = argparse.ArgumentParser(description="Solve DFA password from extracted FSM JSON")
    ap.add_argument("--fsm", default="fsm.json", help="Extractor output JSON")
    ap.add_argument("--length", type=int, default=0, help="Override password length (0=use JSON)")
    ap.add_argument("--dot", default="", help="Optional DOT output")
    ap.add_argument("--raw-case-detail", default="", help="Fallback: path to original case_detail2.json (heuristic)")
    ap.add_argument("--max-solutions", type=int, default=0, help="Stop after N solutions (>0)")
    return ap.parse_args()

def load_fsm(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    states = data.get("states", {})
    pw_len = data.get("password_length", 0)
    graph = {}
    for sid, info in states.items():
        edges = info.get("edges", [])
        graph[int(sid)] = [(e["ch"], int(e["next"])) for e in edges]
    return graph, pw_len

def dfs(graph, target_len, max_solutions=0):
    solutions = []
    def walk(state, depth, acc):
        if depth == target_len:
            solutions.append(''.join(acc))
            return
        for ch, nxt in graph.get(state, []):
            if len(solutions) == max_solutions and max_solutions > 0:
                return
            walk(nxt, depth+1, acc+[ch])
    walk(0, 0, [])
    return solutions

def write_dot(graph, path):
    with open(path, "w", encoding="utf-8") as f:
        f.write("digraph DFA {\n")
        for s, edges in graph.items():
            for ch, nxt in edges:
                label = ch if 32 <= ord(ch) < 127 else f"\\x{ord(ch):02x}"
                f.write(f'  n{s} -> n{nxt} [label="{label}"];\n')
        f.write("}\n")

# ------------- Heuristic salvage for raw case_detail2.json -------------
def salvage_from_raw(raw_path, target_len):
    """
    Best-effort if you only have the original case_detail2.json without source state IDs.
    Assumptions:
      - Each JSON object = one (unknown) source state's outgoing comparisons.
      - A single start state (0) whose id never appears as a next_state_id OR
        must be manually set to 0.
    Strategy:
      - Collect union of all next_state_ids.
      - Guess root = smallest id that does NOT appear as a next_state_id (often 0).
      - Arbitrarily assign source ids by matching earliest appearance of target groups.
    WARNING: This is not guaranteed correct; prefer real extraction.
    """
    with open(raw_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    # Gather all next ids
    all_next = set()
    blocks = []
    for addr, entry in raw.items():
        comps = entry.get("comparisons", [])
        blocks.append((addr, comps))
        for c in comps:
            nid = c.get("next_state_id")
            if isinstance(nid, int):
                all_next.add(nid)

    # Heuristic root
    root = 0
    source_assign = {}
    assigned_states = set()

    # We attempt to assign states incrementally:
    current_queue = [root]
    # Very naive: sort blocks by min(next_state_id) to try layering
    blocks_sorted = sorted(blocks, key=lambda x: min([c["next_state_id"] for c in x[1]] or [999999]))

    graph = defaultdict(list)
    # This degrades if structure isn't a simple outward layering.
    # We just connect characters to next_state_id without really knowing source state ordering.
    # So: treat the sequence of blocks in sorted order as states 0,1,2,... (root forced to 0).
    state_counter = 0
    for addr, comps in blocks_sorted:
        if state_counter == 0:
            sid = root
        else:
            sid = state_counter
        source_assign[addr] = sid
        for c in comps:
            ch = c.get("char")
            nxt = c.get("next_state_id")
            if isinstance(ch, str) and isinstance(nxt, int):
                graph[sid].append((ch, nxt))
        state_counter += 1

    # We cannot reliably ensure a single correct path; enumerate paths anyway
    sols = []
    def dfs_guess(state, depth, acc):
        if depth == target_len:
            sols.append(''.join(acc))
            return
        for ch, nxt in graph.get(state, []):
            dfs_guess(nxt, depth+1, acc+[ch])
    dfs_guess(root, 0, [])

    return graph, sols

# -----------------------------------------------------------------------
def main():
    args = parse_args()

    if args.raw_case_detail:
        print("[!] Using heuristic salvage mode on raw case_detail2.json (NOT guaranteed).")
        target_len = args.length if args.length else 16
        graph, sols = salvage_from_raw(args.raw_case_detail, target_len)
        print(f"[=] Salvage produced {len(sols)} candidate paths of length {target_len}.")
        uniq = sorted(set(sols))
        for s in uniq[:50]:
            print("  ", s)
        if len(uniq) == 1:
            print("[+] Unique candidate:", uniq[0])
        else:
            print("[!] Ambiguous; run proper extractor for authoritative result.")
        if args.dot:
            write_dot(graph, args.dot)
            print(f"[+] DOT written: {args.dot}")
        return 0

    graph, plen_json = load_fsm(args.fsm)
    target_len = args.length if args.length else plen_json
    if not target_len:
        raise SystemExit("[-] Could not determine password length (use --length).")

    solutions = dfs(graph, target_len, max_solutions=args.max_solutions)
    uniq = sorted(set(solutions))
    print(f"[=] Found {len(solutions)} paths (unique={len(uniq)}) of length {target_len}")
    for s in uniq:
        print("   ", s)
    if len(uniq) == 1:
        print("[+] Unique password:", uniq[0])
    else:
        print("[!] Multiple candidates; inspect divergences.")

    if args.dot:
        write_dot(graph, args.dot)
        print(f"[+] DOT written: {args.dot}")
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())