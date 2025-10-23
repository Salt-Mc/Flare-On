import os, json, re, sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from pefile import PE
from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from functools import lru_cache
from tqdm import tqdm

MAX_FUNC_SCAN = 0x8000
EXPORT_SCAN_LIMIT = 0x600
CHECK_NAME = "_Z5checkPh"

SUBDIRS = ["call_chain", "permutations", "confusions", "diffusions", "transform_order", "mat_transforms"]

def load_pe(path: str) -> PE:
    with open(path, "rb") as f:
        return PE(data=f.read())

def section_for_rva(pe: PE, rva: int):
    for s in pe.sections:
        start = s.VirtualAddress
        end = start + max(s.Misc_VirtualSize, s.SizeOfRawData)
        if start <= rva < end:
            return s
    return None

def read_bytes(pe: PE, rva: int, size: int) -> bytes:
    sec = section_for_rva(pe, rva)
    if not sec:
        return b""
    off = rva - sec.VirtualAddress
    return sec.get_data()[off:off + size]

def build_export_map(pe: PE, image_base: int) -> Dict[str, int]:
    out = {}
    if hasattr(pe, "DIRECTORY_ENTRY_EXPORT"):
        for sym in pe.DIRECTORY_ENTRY_EXPORT.symbols:
            if sym.name:
                out[sym.name.decode()] = image_base + sym.address
    return out

def build_import_map(pe: PE, image_base: int) -> Dict[int, Tuple[str, str]]:
    out = {}
    if hasattr(pe, "DIRECTORY_ENTRY_IMPORT"):
        orig_base = pe.OPTIONAL_HEADER.ImageBase
        for entry in pe.DIRECTORY_ENTRY_IMPORT:
            dll = entry.dll.decode()
            for imp in entry.imports:
                if not imp.name:
                    continue
                slot_ea = image_base + (imp.address - orig_base)
                out[slot_ea] = (imp.name.decode(), dll)
    return out

md = Cs(CS_ARCH_X86, CS_MODE_64)
md.detail = False

def disassemble(code: bytes, start: int):
    for ins in md.disasm(code, start):
        yield ins

HEX_RE = re.compile(r'0x[0-9A-Fa-f]+')
RIP_CALL_PTR_RE = re.compile(r'\[(?:qword|dword|word|byte)?\s*ptr\s*\[?rip\+0x([0-9A-Fa-f]+)\]?\]', re.I)

# Register names we care about for call reg resolution
REG_NAMES = {
    "rax","rbx","rcx","rdx","rsi","rdi","rbp","rsp",
    "r8","r9","r10","r11","r12","r13","r14","r15",
    # 32-bit names (sometimes appear even in 64-bit disasm if operand size is forced)
    "eax","ebx","ecx","edx","esi","edi","ebp","esp"
}

def extract_matrix_constants(code: bytes, start_ea: int) -> Dict[str, List[str]]:
    movabs_started = False
    consts: List[int] = []
    for ins in disassemble(code, start_ea):
        if ins.mnemonic == "movabs":
            movabs_started = True
            parts = ins.op_str.split(",")
            if len(parts) == 2 and parts[1].strip().startswith("0x"):
                consts.append(int(parts[1].strip(), 16))
        if movabs_started and ins.mnemonic == "ret":
            break
        if len(consts) > 40:
            break
    if len(consts) != 34:
        return {}
    return {
        "type": "matrix_root",
        "p": f"0x{consts[0]:x}",
        "e": f"0x{consts[1]:x}",
        "R_const": [f"0x{x:x}" for x in consts[2:18]],
        "T_flat": [f"0x{x:x}" for x in consts[18:34]],
    }

def extract_calls_before_constants(code: bytes, start_ea: int) -> List[Dict[str, Optional[int]]]:
    """
    Return list of dicts for EVERY call encountered before first movabs block:
      {
        call_site: <ea>,
        target_ea: <resolved direct or IAT slot address or None>,
        slot_ea: <IAT slot address or None>,
        import_call: bool,
        indirect: bool,
        target_operand: <raw operand text if indirect/unknown>
      }

    Patterns handled:
      call 0xADDR                         (direct absolute)
      call qword ptr [rip+0xDISP]         (direct RIP-relative IAT slot)
      mov REG, qword ptr [rip+0xDISP]; call REG   (register indirect import)
      mov REG, 0xIMM; call REG            (direct absolute via register)
    Unresolved register/memory forms kept as indirect unknown.
    """
    calls: List[Dict[str, Optional[int]]] = []
    movabs_started = False
    prev_ins = None
    for ins in disassemble(code, start_ea):
        if ins.mnemonic == "movabs":
            movabs_started = True
        if movabs_started:
            if ins.mnemonic == "ret":
                break
            continue

        if ins.mnemonic == "call":
            op = ins.op_str.strip()
            entry = {
                "call_site": ins.address,
                "target_ea": None,
                "slot_ea": None,
                "import_call": False,
                "indirect": False
                # REMOVED: "target_operand": op
            }

            # 1. Absolute direct call
            if op.startswith("0x"):
                try:
                    entry["target_ea"] = int(op, 16)
                except ValueError:
                    pass

            # 2. RIP-relative memory call (call qword ptr [rip+0xXXXX])
            elif "rip" in op and "[" in op:
                m = RIP_CALL_PTR_RE.search(op)
                if m:
                    disp = int(m.group(1), 16)
                    cand1 = ins.address + disp                 # legacy invert logic
                    cand2 = ins.address + ins.size + disp      # architecturally correct
                    # We'll pick later in process_dll which matches import map; keep both?
                    # For now keep cand2 (more correct); process_dll will still match cand2 if map done right.
                    entry["target_ea"] = cand2
                    entry["slot_ea"] = cand2
                    entry["import_call"] = True
                else:
                    entry["indirect"] = True  # unknown complex RIP form

            # 3. Register indirect: call rax / call r10 etc.
            elif op in REG_NAMES:
                # Examine previous instruction for mov <reg>, qword ptr [rip+0xDISP] or mov <reg>, 0xIMM
                if prev_ins and prev_ins.mnemonic == "mov":
                    prev_op = prev_ins.op_str.replace(" ", "")
                    # mov<reg>,qwordptr[rip+0xDISP]
                    # Easier: ensure startswith f"{op}," and contains "rip+0x"
                    if prev_op.lower().startswith(f"{op.lower()},") and "rip+0x" in prev_op.lower():
                        m = re.search(r'rip\+0x([0-9A-Fa-f]+)', prev_op)
                        if m:
                            disp = int(m.group(1), 16)
                            cand1 = ins.address + disp
                            cand2 = ins.address + ins.size + disp
                            # Choose cand1 first for legacy parity; actual import match later might succeed with either.
                            slot_addr = cand1
                            entry["target_ea"] = slot_addr
                            entry["slot_ea"] = slot_addr
                            entry["import_call"] = True
                        else:
                            entry["indirect"] = True
                    # mov<reg>,0xIMM  (direct absolute)
                    elif prev_op.lower().startswith(f"{op.lower()},0x"):
                        imm_part = prev_op.split(",")[1]
                        try:
                            entry["target_ea"] = int(imm_part, 16)
                        except ValueError:
                            entry["indirect"] = True
                    else:
                        entry["indirect"] = True
                else:
                    entry["indirect"] = True

            # 4. Other forms
            else:
                entry["indirect"] = True

            calls.append(entry)

        prev_ins = ins
    return calls

def classify_export(code: bytes, start_ea: int) -> Tuple[str, List[int]]:
    movs: List[int] = []
    or_seen = False
    for ins in disassemble(code, start_ea):
        if ins.mnemonic == "movabs":
            parts = ins.op_str.split(",")
            if len(parts) == 2 and parts[1].strip().startswith("0x"):
                movs.append(int(parts[1].strip(), 16))
        elif ins.mnemonic == "or":
            or_seen = True
        elif ins.mnemonic == "jmp":
            break
        if len(movs) > 40:
            break
    if len(movs) == 32:
        return "confusion", movs
    if len(movs) == 4:
        return ("diffusion" if or_seen else "permutation"), movs
    return "unknown", movs

def to_hex_list(vals: List[int]) -> List[str]:
    return [f"0x{v:x}" for v in vals]

def diffusion_raw_constants(vals: List[int]) -> List[Dict[str,str]]:
    indices = [0, 8, 15, 23] if len(vals) == 4 else list(range(len(vals)))
    return [{"index": idx, "value": f"0x{v:x}"} for idx, v in zip(indices, vals)]

@lru_cache(maxsize=256)
def process_dll_cached(dllno: int, dll_path: str, out_root_str: str) -> Dict:
    return process_dll(dllno, dll_path, Path(out_root_str))

def _dllno_from_name(dll_name: str) -> str:
    base = dll_name.split("\\")[-1].split("/")[-1]
    if base.lower().endswith(".dll"):
        base = base[:-4]
    m = re.fullmatch(r'\d+', base)
    return m.group(0) if m else base

UNUSED_EXPORT_BASE = 0xA0000  # sentinel base for unused export indices

def process_dll(dllno: int, dll_path: str, out_root: Path) -> Dict:
    pe = load_pe(dll_path)
    image_base = pe.OPTIONAL_HEADER.ImageBase
    exports = build_export_map(pe, image_base)
    imports = build_import_map(pe, image_base)

    results = {"dllno": dllno, "status": "ok", "matrix": False,
               "calls": 0, "perms": 0, "confs": 0, "diffs": 0}

    for d in SUBDIRS:
        (out_root / d).mkdir(parents=True, exist_ok=True)

    call_chain: List[Dict] = []
    permutations: Dict[str,List[str]] = {}
    confusions: Dict[str,List[str]] = {}
    diffusions: Dict[str,List[Dict[str,str]]] = {}
    transform_order = {"reverse": []}

    check_ea = exports.get(CHECK_NAME)
    processed_names = set()

    if check_ea:
        rva = check_ea - image_base
        code = read_bytes(pe, rva, MAX_FUNC_SCAN)
        matrix_candidate = extract_matrix_constants(code, check_ea)
        if matrix_candidate:
            with open(out_root / "mat_transforms" / f"{dllno}.json", "w", encoding="utf-8") as f:
                json.dump(matrix_candidate, f, indent=2)
            results["matrix"] = True

        raw_calls = extract_calls_before_constants(code, check_ea)
        export_addr_rev = {addr: name for name, addr in exports.items()}

        for idx, c in enumerate(raw_calls):
            call_site = c["call_site"]
            tgt = c["target_ea"]
            slot_ea = c["slot_ea"]
            indirect_flag = c["indirect"]

            entry = {
                "index": idx,
                "call_site": f"0x{call_site:X}",
                "indirect": indirect_flag,
                "target_ea": f"0x{tgt:X}" if tgt is not None else None,
                # REMOVED: "target_operand": c["target_operand"] if (tgt is None or indirect_flag) else None,
                "name": None,
                "kind": None,
                "dllno": None,
                "classification": None,
                "iat_slot": bool(slot_ea),
            }

            if slot_ea and slot_ea in imports:
                iname, imod = imports[slot_ea]
                entry["name"] = iname
                entry["kind"] = "import"
                entry["dllno"] = _dllno_from_name(imod)
            elif tgt is not None and tgt in export_addr_rev:
                nm = export_addr_rev[tgt]
                entry["name"] = nm
                entry["kind"] = "internal"
                processed_names.add(nm)
                rva_t = tgt - image_base
                t_code = read_bytes(pe, rva_t, EXPORT_SCAN_LIMIT)
                kind, consts = classify_export(t_code, tgt)
                entry["classification"] = kind if kind != "unknown" else None
                if kind == "permutation":
                    permutations[nm] = to_hex_list(consts)
                elif kind == "confusion":
                    confusions[nm] = to_hex_list(consts)
                elif kind == "diffusion":
                    diffusions[nm] = diffusion_raw_constants(consts)
            else:
                entry["kind"] = "unknown"

            call_chain.append(entry)

        forward_chain = []
        for e in call_chain:
            if e["kind"] == "internal":
                forward_chain.append({
                    "name": e["name"],
                    "classification": e["classification"],
                    "origin": "internal"
                })
            elif e["kind"] == "import":
                forward_chain.append({
                    "name": e["name"],
                    "classification": "import",
                    "dllno": e["dllno"],
                    "origin": "external"
                })
        transform_order["reverse"] = list(reversed(forward_chain))

    # Remaining exports (classify those not seen in call chain)
    remaining_classified: Dict[str, str] = {}  # name -> classification
    for name, ea in exports.items():
        if name == CHECK_NAME or name in processed_names:
            continue
        rva = ea - image_base
        code = read_bytes(pe, rva, EXPORT_SCAN_LIMIT)
        kind, consts = classify_export(code, ea)
        if kind == "permutation":
            permutations[name] = to_hex_list(consts)
            remaining_classified[name] = "permutation"
        elif kind == "confusion":
            confusions[name] = to_hex_list(consts)
            remaining_classified[name] = "confusion"
        elif kind == "diffusion":
            diffusions[name] = diffusion_raw_constants(consts)
            remaining_classified[name] = "diffusion"
        # (skip unknown kinds – not appended)

    # ---- Append synthetic entries for remaining classified exports ----
    unused_idx_counter = 1
    for name, ctype in remaining_classified.items():
        # Skip if already present (defensive; processed_names should cover)
        if any(e.get("name") == name for e in call_chain):
            continue
        synthetic_entry = {
            "index": UNUSED_EXPORT_BASE + unused_idx_counter,
            "call_site": None,
            "indirect": None,
            "target_ea": None,
            "name": name,
            "kind": "internal",
            "dllno": None,
            "classification": ctype,
            "iat_slot": None
        }
        call_chain.append(synthetic_entry)
        unused_idx_counter += 1

    # Update stats after adding synthetic entries
    results.update({
        "calls": len(call_chain),
        "perms": len(permutations),
        "confs": len(confusions),
        "diffs": len(diffusions)
    })

    with open(out_root / "call_chain" / f"{dllno}_call_chain.json", "w", encoding="utf-8") as f:
        json.dump(call_chain, f, indent=2)
    with open(out_root / "permutations" / f"{dllno}_permutations.json", "w", encoding="utf-8") as f:
        json.dump(permutations, f, indent=2)
    with open(out_root / "confusions" / f"{dllno}_confusions.json", "w", encoding="utf-8") as f:
        json.dump(confusions, f, indent=2)
    with open(out_root / "diffusions" / f"{dllno}_diffusions.json", "w", encoding="utf-8") as f:
        json.dump(diffusions, f, indent=2)
    with open(out_root / "transform_order" / f"{dllno}_transform_order.json", "w", encoding="utf-8") as f:
        json.dump(transform_order, f, indent=2)

    return results

def _worker_init():
    pass

def _task(args: Tuple[int, str, str]) -> Dict:
    dllno, dll_path, out_root_str = args
    if not os.path.isfile(dll_path):
        return {"dllno": dllno, "status": "missing"}
    return process_dll_cached(dllno, dll_path, out_root_str)

def process_many(dll_dir: str, out_root: str, dll_list: List[int], workers: int = 8):
    from concurrent.futures import ProcessPoolExecutor, as_completed
    out_root_p = Path(out_root); out_root_p.mkdir(parents=True, exist_ok=True)
    arg_list = [(n, os.path.join(dll_dir, f"{n}.dll"), str(out_root_p)) for n in dll_list]

    total = len(arg_list)
    bar = tqdm(total=total, desc="DLLs", unit="dll", dynamic_ncols=True, mininterval=0.2)

    ok_count = 0
    missing_count = 0
    fail_count = 0

    results: List[Dict] = []
    with ProcessPoolExecutor(max_workers=workers, initializer=_worker_init) as exe:
        fut_map = {exe.submit(_task, a): a[0] for a in arg_list}
        for fut in as_completed(fut_map):
            res = fut.result()
            results.append(res)

            status = res.get("status")
            if status == "ok":
                ok_count += 1
            elif status == "missing":
                missing_count += 1
            else:
                fail_count += 1

            bar.update(1)
            bar.set_postfix(ok=ok_count, missing=missing_count, fail=fail_count)

    bar.close()
    print(f"Processed {len(results)} DLLs (ok={ok_count}, missing={missing_count}, fail={fail_count})")
    return results

ORDER_LIST_FILE = "order_list.txt"

def load_order_list():
    path = Path(ORDER_LIST_FILE)
    if not path.is_file():
        raise RuntimeError(f"Missing ORDER_LIST_FILE: {ORDER_LIST_FILE}")
    nums = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line=line.strip()
            if not line:
                continue
            if line.isdigit():
                nums.append(int(line))
            else:
                raise ValueError(f"Non-integer in order_list: {line}")
    return nums

if __name__ == "__main__":
    if len(sys.argv) >= 4:
        DLL_DIR = Path(sys.argv[1])
        if not DLL_DIR.exists() or not DLL_DIR.is_dir(): raise FileNotFoundError(f"Invalid DLL_DIR: {DLL_DIR}")
        OUT_DIR = Path(sys.argv[2])
        ORDER_LIST_FILE = Path(sys.argv[3])
        if not OUT_DIR.is_dir(): raise FileNotFoundError(f"Invalid OUT_DIR: {OUT_DIR}")
        if not ORDER_LIST_FILE.exists() or not ORDER_LIST_FILE.is_file(): raise FileNotFoundError(f"Invalid ORDER_LIST_FILE: {ORDER_LIST_FILE}")
    else:
        print("Usage: python extract_mat_and_transform_consts.py <DLL_DIR> <OUT_DIR> <ORDER_LIST_FILE>")
        exit(1)
    with open(ORDER_LIST_FILE, "r", encoding="utf-8") as f:
        SAMPLE = json.load(f)
    process_many(DLL_DIR.as_posix(), OUT_DIR.as_posix(), SAMPLE, workers=8)