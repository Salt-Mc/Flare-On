"""
Extract the password state machine (DFA) from the binary by:
  1. Resolving the jump table (default symbol: jpt_14000CA5A).
  2. For each state index, mapping to a code block (case handler).
  3. Parsing 'cmp <same operand>, imm8' + conditional jump ladders.
  4. For each conditional branch target, scanning the small block it lands in
     looking for the pattern:
        mov [rsp+...+next_state_id], <imm>
        inc  [rsp+...+accepted_chars]   (or equivalent load/inc/store)
     (i.e., the “accepted transition” pattern)
  5. Emitting JSON:
     {
       "password_length": 16,
       "jump_table_symbol": "jpt_14000CA5A",
       "states": {
          "0": {
             "ea": "0x140860241",
             "edges": [{"ch": "i","next":1}, {"ch":"J","next":2}, ...]
          },
          ...
       }
     }

If a branch target does not contain a recognizable 'next_state_id' pattern,
a fallback normalization maps the branch target (or bytes nearby) back to a
state handler entry (reverse map). Ambiguous targets are skipped.

Usage inside IDA:
  - Open the database (or run headless)
  - Run script via:  File -> Script file...  OR command line with -S
  - Arguments (after --) are parsed.
"""
import json
import argparse
from time import time
import traceback
from ida_domain import Database
from ida_domain.database import IdaCommandOptions

IDB_PATH_DEFAULT = "ntfsm5.i64"

def try_import_ida_modules():
    try:
        global idaapi, ida_bytes, ida_segment, ida_name, ida_auto, ida_allins, idautils
        import idaapi as idaapi
        import ida_bytes as ida_bytes
        import ida_segment as ida_segment
        import ida_name as ida_name
        import ida_auto as ida_auto
        import ida_allins as ida_allins
        import idautils as idautils
        return (idaapi, ida_bytes, ida_segment, ida_name, ida_auto, ida_allins, idautils)
    except ImportError as e:
        raise ImportError("This script must be run inside IDA Pro with the IDA Python environment.") from e

# ------------------ Config Defaults ------------------
DEFAULT_JT_SYMBOL = "jpt_14000CA5A"
DEFAULT_PASSWORD_LENGTH = 16
DEFAULT_MAX_STATE = 0xFFFF
SCAN_CASE_MAX_BYTES = 0x400
SCAN_ACCEPT_BLOCK_MAX = 0x80
# -----------------------------------------------------

def parse_args_from_ida():
    """
    IDA passes arguments after the script name in ida_pro command line.
    We can't rely on sys.argv[0] being the script path always, so we
    manually parse what IDA leaves us (idaapi.get_inf_structure etc. won't help).
    """
    import sys
    # IDA sometimes prepends its own flags; find our script name and take the tail.
    argv = sys.argv[1:]
    ap = argparse.ArgumentParser(description="Extract DFA from jump table + cmp ladders")
    ap.add_argument("--idb", default=IDB_PATH_DEFAULT, help="Path to .i64/.idb (used if ida_domain available)")
    ap.add_argument("--jump-table-symbol", default=DEFAULT_JT_SYMBOL)
    ap.add_argument("--out", default="fsm.json")
    ap.add_argument("--password-length", type=int, default=DEFAULT_PASSWORD_LENGTH)
    ap.add_argument("--max-state", type=int, default=DEFAULT_MAX_STATE)
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--limit-states", type=int, default=0, help="Stop after visiting this many states (0=all)")
    ap.add_argument("--disable-auto", action="store_true",
                    help="Pass auto_analysis=False to ida_domain (only affects domain open)")
    return ap.parse_args(argv)

def collect_exec_segments():
    segs = []
    qty = ida_segment.get_segm_qty()
    for i in range(qty):
        seg = ida_segment.getnseg(i)
        if not seg: 
            continue
        # typical execute perm has bit 4 or bit 1 set
        if seg.perm & 4 or seg.perm & 1:
            segs.append((seg.start_ea, seg.end_ea))
    return segs

def in_exec(ea, segments):
    for a,b in segments:
        if a <= ea < b:
            return True
    return False

def decode_insn(ea):
    ins = idaapi.insn_t()
    sz = idaapi.decode_insn(ins, ea)
    if sz == 0:
        return None, 0
    return ins, sz

def ensure_code(ea):
    flags = ida_bytes.get_flags(ea)
    if not ida_bytes.is_code(flags):
        ida_bytes.del_items(ea, 0)
        idaapi.create_insn(ea)

def is_cond_jcc(itype):
    iins = ida_allins
    J = {
        iins.NN_ja, iins.NN_jae, iins.NN_jb, iins.NN_jbe, iins.NN_jc,
        iins.NN_je, iins.NN_jg, iins.NN_jge, iins.NN_jl, iins.NN_jle,
        iins.NN_jna, iins.NN_jnae, iins.NN_jnb, iins.NN_jnbe, iins.NN_jnc,
        iins.NN_jne, iins.NN_jng, iins.NN_jnge, iins.NN_jnl, iins.NN_jnle,
        iins.NN_jno, iins.NN_jnp, iins.NN_jns, iins.NN_jnz, iins.NN_jo,
        iins.NN_jp, iins.NN_jpe, iins.NN_jpo, iins.NN_js, iins.NN_jz
    }
    return itype in J

def read_jump_table(symbol, max_states, segments, verbose=False):
    jt_ea = ida_name.get_name_ea(0, symbol)
    if jt_ea == idaapi.BADADDR:
        raise RuntimeError(f"Jump table symbol '{symbol}' not found.")
    image_base = idaapi.get_imagebase()
    targets = []
    reverse_map = {}
    for i in range(max_states+1):
        entry_ea = jt_ea + i*4
        if not in_exec(entry_ea, segments):
            break  # assume contiguous in .rdata; but keep reading if desired
        try:
            rel = ida_bytes.get_dword(entry_ea)
        except Exception:
            break
        if rel in (0xFFFFFFFF, 0):
            targets.append(None)
            continue
        abs_ea = image_base + rel
        if not in_exec(abs_ea, segments):
            targets.append(None)
            continue
        targets.append(abs_ea)
        reverse_map.setdefault(abs_ea, i)
    if verbose:
        valid = sum(1 for t in targets if t)
        print(f"[dbg] Jump table parsed: {len(targets)} entries, {valid} valid code targets")
    return jt_ea, targets, reverse_map

def scan_accept_block(start_ea):
    """
    Scan for 'mov [rsp+...next_state_id], IMM' then an 'inc' sequence touching accepted_chars.
    We return the IMM if found (next_state_id); else None.
    """
    max_bytes = SCAN_ACCEPT_BLOCK_MAX
    ea = start_ea
    scanned = 0
    while scanned < max_bytes:
        ins, size = decode_insn(ea)
        if not ins:
            break
        # pattern: mov [mem], imm
        if ins.itype == ida_allins.NN_mov and len(ins.ops) == 8:
            dst, src = ins.ops[0], ins.ops[1]
            if src.type == idaapi.o_imm and dst.type in (idaapi.o_displ, idaapi.o_phrase, idaapi.o_mem):
                imm = src.value
                # Heuristic: plausible state? (non-negative, not huge)
                if 0 <= imm <= 0xFFFFF:
                    # look ahead briefly for an 'inc' or add sequence referencing accepted_chars (optional)
                    return imm
        if ins.itype == ida_allins.NN_jmp:
            break
        scanned += size
        ea += size
    return None

def parse_case_block(case_ea, reverse_map, segments, verbose=False):
    """
    Parse the cmp ladder at the case handler.
    Returns list of (char, next_state_id).
    Strategy:
      - Walk linear instructions until unconditional jmp or size limit.
      - For each 'cmp X, imm8' followed immediately by 'jcc target':
           * take imm8 as candidate character
           * resolve branch target to a block that sets next_state_id (scan_accept_block)
           * if pattern fails, fallback: map the target (or a near backward offset) to a known state handler (reverse_map).
    """
    ensure_code(case_ea)
    edges = []
    cmp_operand_sig = None
    ea = case_ea
    scanned = 0
    while scanned < SCAN_CASE_MAX_BYTES:
        ins, size = decode_insn(ea)
        if not ins:
            break
        if ins.itype == ida_allins.NN_jmp:
            break
        if ins.itype == ida_allins.NN_cmp and len(ins.ops) >= 2:
            op0 = idaapi.print_operand(ea, 0)
            op1 = ins.ops[1]
            if op1.type == idaapi.o_imm and 0 <= op1.value <= 0xFF and op0:
                if cmp_operand_sig is None:
                    cmp_operand_sig = op0
                if op0 == cmp_operand_sig:
                    next_ea = ea + size
                    n_ins, n_sz = decode_insn(next_ea)
                    if n_ins and is_cond_jcc(n_ins.itype):
                        # Get branch target(s)
                        xrefs = [xr.to for xr in idautils.XrefsFrom(next_ea, 0)]
                        # Typically: one or two; choose all that are not the fallthrough.
                        fallthrough = next_ea + n_sz
                        for tgt in xrefs:
                            if tgt == fallthrough:
                                continue
                            # Attempt to read next_state
                            ns = scan_accept_block(tgt)
                            if ns is None:
                                # Fallback: map target or small backward window to reverse_map
                                for delta in (0, -1, -2, -3, -4, -5, -6, -7, -8, -9, -10):
                                    cand = tgt + delta
                                    if cand in reverse_map:
                                        ns = reverse_map[cand]
                                        if verbose:
                                            print(f"[norm] mapped target 0x{tgt:X} -> state {ns}")
                                        break
                            if ns is not None:
                                ch = chr(op1.value)
                                edges.append((ch, ns))
                                if verbose:
                                    print(f"[edge] case@0x{case_ea:X}: '{repr_char(ch)}' -> {ns}")
                    ea += size
                    scanned += size
                    continue
        ea += size
        scanned += size
    # Deduplicate by character
    ded = {}
    for ch, ns in edges:
        ded[ch] = ns
    return [(c, ded[c]) for c in ded]

def repr_char(c):
    o = ord(c)
    if 32 <= o < 127 and c not in ['\\', '"']:
        return c
    return f"\\x{o:02x}"

def main():
    args = parse_args_from_ida()
    open_start = time.perf_counter()
    ida_opts = IdaCommandOptions(auto_analysis=not args.disable_auto, new_database=False)
    db = Database.open(args.idb, ida_opts)
    try_import_ida_modules()
    print(f"[+] ida_domain open completed in {time.perf_counter()-open_start:.2f}s")

    segments = collect_exec_segments()
    jt_ea, jt_targets, reverse_map = read_jump_table(
        args.jump_table_symbol, args.max_state, segments, verbose=args.verbose
    )

    visited_states = {}
    queue = [0]
    out = {
        "password_length": args.password_length,
        "jump_table_symbol": args.jump_table_symbol,
        "states": {}
    }

    processed = 0
    while queue:
        st = queue.pop(0)
        if st in visited_states:
            continue
        if st >= len(jt_targets):
            continue
        case_ea = jt_targets[st]
        if case_ea is None:
            visited_states[st] = True
            out["states"][str(st)] = {"ea": None, "edges": []}
            continue
        edges = parse_case_block(case_ea, reverse_map, segments, verbose=args.verbose)
        out["states"][str(st)] = {
            "ea": f"0x{case_ea:X}",
            "edges": [{"ch": c, "next": ns} for c, ns in edges]
        }
        visited_states[st] = True
        processed += 1
        for _, ns in edges:
            if ns not in visited_states:
                queue.append(ns)
        if args.limit_states and processed >= args.limit_states:
            break

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, sort_keys=False)
    print(f"[+] Extracted {len(out['states'])} states -> {args.out}")
    return 0

if __name__ == "__main__":
    try:
        rc = main()
    except Exception as e:
        print(f"[!] Exception: {e}")
        
        traceback.print_exc()
        rc = 1
    idaapi.qexit(rc)
