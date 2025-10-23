#!/usr/bin/env python3
"""
Parallel optimized ordered DLL recovery script.

Enhancements:
  - Optional multiprocessing (--workers N).
  - Per-process mmap snapshot reader (fast random access).
  - orjson for JSON decode speed.
  - Caching: matrix params, transform orders, internal constants per process.
  - Ordered deterministic output while computing in parallel.
  - Resume support preserved (reads existing recovery_simple.log).
  - Optional eager preload of metadata in parent (reduces disk contention).

Usage (PowerShell):
  python recover_bytes.py --workers 8
  python recover_bytes.py --workers 0          # auto = cpu count
  python recover_bytes.py --workers 1          # original single-process behavior
  python recover_bytes.py --eager-preload      # preload all matrix/transform/internal constant files
  python recover_bytes.py --checkpoint-every 200

"""

from __future__ import annotations
from pathlib import Path
import os
import argparse
import mmap
import struct
import ast
import traceback
import orjson
import time
import re
from typing import Dict, List, Any, Optional, Set, Tuple
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import lru_cache
import multiprocessing

# NEW: optional tqdm import
try:
    from tqdm import tqdm
except ImportError:
    tqdm = None

# ---- Import transform primitives ----
from invert import (
    parse_exponent_constants,
    forward_exponent,
    inverse_exponent,
    parse_sbox_constants,
    forward_sbox,
    inverse_sbox,
    parse_permutation_constants,
    forward_permutation,
    inverse_permutation,
    invert_matrix_root,
    ensure_charpoly_cache_loaded,
    enable_charpoly_batch_mode,
    flush_charpoly_cache,
)

# ---------------- Configuration ----------------
BASE = Path(__file__).parent
STAGE2 = BASE.parent / "Stage2"
STAGE1 = BASE.parent / "Stage1"

if not STAGE2.exists() or not STAGE2.is_dir():
    raise FileNotFoundError(f"STAGE2 directory not found: {STAGE2}")

if not STAGE1.exists() or not STAGE1.is_dir():
    raise FileNotFoundError(f"STAGE1 directory not found: {STAGE1}")

@lru_cache(maxsize=1)
def load_dll_order() -> List[int]:
    return orjson.loads((STAGE1 / "ordering.json").read_bytes())
DLL_ORDER: List[int] = load_dll_order()

STRICT_FAIL_ON_MISSING_INTERNAL = False
OUTPUT_SIMPLE = BASE / "recovered.ndjson"
OUTPUT_DIAG = BASE / "recovery_diagnostics.json"

DIR_CALL_CHAIN = STAGE2 / "call_chain"
DIR_CONFUSIONS = STAGE2 / "confusions"
DIR_DIFFUSIONS = STAGE2 / "diffusions"
DIR_PERMUTATIONS = STAGE2 / "permutations"
DIR_MAT = STAGE2 / "mat_transforms"
DIR_ORDER = STAGE2 / "transform_order"
XOR_FILE_JSON = STAGE2 / "snapshots.ndjson"
OFFSETS_FILE = STAGE2 / "offsets.bin"

CHECKPOINT_DEFAULT = 50
FLUSH_EVERY_DEFAULT = 100
CACHE_INVERT_FLAG = os.environ.get("DISK_CACHE_INVERTED") == "1"

_CACHE_INVERT_DIR = Path(__file__).parent / "cache_inverted"
_CACHE_INVERT_DIR.mkdir(exist_ok=True)

def get_type_name(kind: str) -> str:
    if kind == "diffusion":
        return "exponent"
    if kind == "confusion":
        return "sbox"
    if kind == "permutation":
        return kind
    return "unknown"

# ---------- Lightweight orjson helpers ----------

def read_json_bytes(path: Path) -> Any:
    return orjson.loads(path.read_bytes())

def atomic_write_json(path: Path, obj) -> None:
    text = orjson.dumps(obj, option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS) + b"\n"
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(text)
    tmp.replace(path)

def load_processed_keys(filepath: Path) -> Set[int]:
    if not filepath.exists():
        return set()
    keys: Set[int] = set()
    for line in filepath.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        dct = ast.literal_eval(line.strip())  # log line is a Python literal dict
        keys.update(int(k) for k in dct.keys())
    return keys

# ---------- Load XOR values from snapshot ----------
# ---- New globals for selective xor extraction ----
_key_re_cache: Dict[str, re.Pattern] = {}
_dll_dependencies: Dict[int, Set[int]] = {}
_xor_stats = {
    "raw_reads": 0,
    "fast_full_parse": 0,
    "selective_large": 0,
    "missing_needed_keys": 0,
    "combined_regex_used": 0
}

SMALL_LINE_THRESHOLD = 4096        # bytes
MAX_COMBINED_KEYS = 50             # safety cap for alternation size
FORCE_FULL_PARSE_IF_MANY_KEYS = 60 # if dependencies unexpectedly explode

def _get_dll_dependencies(dll_no: int) -> Set[int]:
    """Return set of external DLL numbers referenced via 'import' transforms."""
    if dll_no in _dll_dependencies:
        return _dll_dependencies[dll_no]
    externals: Set[int] = set()
    order = _load_transform_order(dll_no)
    for step in order:
        if (step.get("classification") or "").lower() == "import":
            raw = step.get("dllno")
            if raw is None:
                continue
            try:
                externals.add(int(raw))
            except ValueError:
                continue
    _dll_dependencies[dll_no] = externals
    return externals

def _read_snapshot_raw(index: int) -> bytes:
    """Return raw line bytes without JSON parsing (adds basic instrumentation)."""
    start = _reader.offsets[index]
    end = _reader.line_end_offsets[index]
    raw = _reader.mm[start:end].rstrip(b"\r\n")
    _xor_stats["raw_reads"] += 1
    return raw

def _build_combined_pattern(keys: Set[str]) -> re.Pattern:
    """
    Build one alternation regex: "(\"(k1|k2|k3)\"\\s*:\\s*(\\d+))"
    Captures:
      group 1: whole match
      group 2: key
      group 3: value
    """
    # Sort for deterministic pattern (optional)
    parts = sorted(keys)
    # Escape not needed for digits, but be robust:
    alternation = "|".join(re.escape(k) for k in parts)
    pat = rb'"(' + alternation.encode() + rb')"\s*:\s*(\d+)'
    return re.compile(pat)

def _extract_needed(raw_line: bytes, needed: Set[str]) -> Dict[str, int]:
    """
    Adaptive extraction:
      - Small line: full parse
      - Few keys and large line: combined regex
      - Many keys: (optional) full parse
    """
    size = len(raw_line)
    need_count = len(needed)

    # Case 1: tiny line -> parse everything
    if size <= SMALL_LINE_THRESHOLD:
        try:
            obj = orjson.loads(raw_line)
        except Exception:
            # Fallback: return empty; caller will default missing to 0
            _xor_stats["missing_needed_keys"] += need_count
            return {}
        _xor_stats["fast_full_parse"] += 1
        return {k: obj[k] for k in needed if k in obj}

    # Case 2: too many needed keys -> just parse
    if need_count > FORCE_FULL_PARSE_IF_MANY_KEYS:
        try:
            obj = orjson.loads(raw_line)
            return {k: obj[k] for k in needed if k in obj}
        except Exception:
            _xor_stats["missing_needed_keys"] += need_count
            return {}

    # Case 3: use combined regex if feasible
    if need_count <= MAX_COMBINED_KEYS:
        try:
            # Cache by frozenset signature to avoid rebuild if reused
            sig = frozenset(needed)
            pat = _key_re_cache.get(str(sig))
            if pat is None:
                pat = _build_combined_pattern(needed)
                _key_re_cache[str(sig)] = pat
            matches = pat.findall(raw_line)
            _xor_stats["combined_regex_used"] += 1
            out: Dict[str, int] = {}
            # matches is list of tuples (key, value)
            for key, val in matches:
                # key/value are bytes because of pattern; decode key
                if isinstance(key, bytes):
                    k_str = key.decode()
                else:
                    k_str = key
                out[k_str] = int(val)
            # Track missing keys if any
            missing = need_count - len(out)
            if missing:
                _xor_stats["missing_needed_keys"] += missing
            _xor_stats["selective_large"] += 1
            return out
        except Exception:
            # Defensive fallback
            try:
                obj = orjson.loads(raw_line)
                return {k: obj[k] for k in needed if k in obj}
            except Exception:
                _xor_stats["missing_needed_keys"] += need_count
                return {}

    # Case 4: fallback full parse for mid-size sets
    try:
        obj = orjson.loads(raw_line)
        return {k: obj[k] for k in needed if k in obj}
    except Exception:
        _xor_stats["missing_needed_keys"] += need_count
        return {}

def _load_xor_values(snapshot_index: int, dll_no: Optional[int] = None) -> Dict[str, int]:
    """
    Optimized loader:
      If dll_no supplied, extract only required check bytes (dll_no + its external dependencies).
      Otherwise, preserve legacy full parse behavior.
    """
    if dll_no is None:
        return _reader.read_snapshot(snapshot_index)

    externals = _get_dll_dependencies(dll_no)
    needed_keys: Set[str] = {str(dll_no)}
    for ext in externals:
        needed_keys.add(str(ext))

    raw = _read_snapshot_raw(snapshot_index)
    return _extract_needed(raw, needed_keys)

# ---------- Snapshot Reader (per process) ----------

class MMapSnapshotReader:
    __slots__ = ("f", "mm", "offsets", "line_end_offsets")

    def __init__(self, ndjson_path: Path, index_path: Path):
        self.f = ndjson_path.open("rb")
        self.mm = mmap.mmap(self.f.fileno(), 0, access=mmap.ACCESS_READ)
        data = index_path.read_bytes()
        # Parse start offsets
        self.offsets = [struct.unpack_from("<Q", data, i)[0]
                        for i in range(0, len(data), 8)]
        # Precompute end offsets (exclusive)
        file_len = len(self.mm)
        self.line_end_offsets = []
        for i, start in enumerate(self.offsets):
            if i + 1 < len(self.offsets):
                self.line_end_offsets.append(self.offsets[i + 1])
            else:
                self.line_end_offsets.append(file_len)

    def read_snapshot(self, index: int) -> dict:
        start_t = time.perf_counter()
        start = self.offsets[index]
        end = self.line_end_offsets[index]
        raw = self.mm[start:end].rstrip(b"\r\n")
        obj = orjson.loads(raw)
        dt = time.perf_counter() - start_t
        _snapshot_stats["reads"] += 1
        _snapshot_stats["parse_time"] += dt
        return obj

    def close(self):
        try:
            self.mm.close()
        finally:
            self.f.close()

# Global per-process objects (initialized in worker)
_reader: Optional[MMapSnapshotReader] = None
_resolver: Optional["ExternalResolver"] = None
_preloaded_matrix: Dict[int, Dict[str, Any]] = {}
_preloaded_order: Dict[int, List[Dict[str, Any]]] = {}
_preloaded_internal_constants: Dict[Tuple[int, str], Dict[str, List[Any]]] = {}
_parsed_constants_cache: Dict[Tuple[int, str, str], Any] = {}
_inverted_matrices: Dict[int, bytes] = {}  # dll_no -> bytes (a1_bytes)

_inversion_stats = {"disk_hits": 0, "computed": 0, "fail": 0, "time_compute": 0.0}
_snapshot_stats = {"reads": 0, "parse_time": 0.0}
_recover_stats = {
    "dlls": 0,
    "time_transform_loop": 0.0,
    "time_order_load": 0.0,
    "time_checkbyte_lookup": 0.0,
    "time_total": 0.0
}

def worker_init(eager: bool):
    """Initialize per-process state; rely on OS for cleanup at exit."""
    global _reader, _preloaded_matrix, _preloaded_order, _preloaded_internal_constants, _resolver
    os.environ["CACHE_WRITE_ROLE"] = "worker"
    os.environ["CHARPOLY_READ_ONLY"] = "1"  # hint to avoid any flush work in workers
    ensure_charpoly_cache_loaded()
    _reader = MMapSnapshotReader(XOR_FILE_JSON, OFFSETS_FILE)
    _resolver = ExternalResolver()

    if eager:
        # Preload matrix params
        for p in DIR_MAT.glob("*.json"):
            try:
                dll_no = int(p.stem)
                mp = _load_matrix_params(dll_no)
                if mp:
                    _preloaded_matrix[dll_no] = mp
            except Exception:
                pass
        # Preload transform orders
        for p in DIR_ORDER.glob("*_transform_order.json"):
            stem = p.name.split("_")[0]
            if stem.isdigit():
                dll_no = int(stem)
                _preloaded_order[dll_no] = _load_transform_order(dll_no)
        # Preload internal constants (diffusion/confusion/permutation)
        for kind, dir_path in (
            ("diffusion", DIR_DIFFUSIONS),
            ("confusion", DIR_CONFUSIONS),
            ("permutation", DIR_PERMUTATIONS),
        ):
            for p in dir_path.glob("*_*.json"):
                # Filenames like 1234_diffusions.json
                stem = p.name.split("_")[0]
                if not stem.isdigit():
                    continue
                dll_no = int(stem)
                mapping = _load_constants_file(dll_no, kind)
                if mapping:
                    _preloaded_internal_constants[(dll_no, kind)] = mapping

        # Optionally precompute matrix inversions during eager preload:
        for dll_no in list(_preloaded_matrix.keys()):
            _ensure_inverted_matrix(dll_no)

def _load_inverted_cache(dll_no: int) -> Optional[bytes]:
    if not CACHE_INVERT_FLAG:
        return None
    f = _CACHE_INVERT_DIR / f"a1_{dll_no}.bin"
    if not f.exists():
        return None
    data = f.read_bytes()
    if len(data) == 32:
        return data
    return None

def _save_inverted_cache(dll_no: int, a1_bytes: bytes):
    if not CACHE_INVERT_FLAG:
        return
    tmp = _CACHE_INVERT_DIR / f"a1_{dll_no}.bin.tmp"
    tmp.write_bytes(a1_bytes)
    final = tmp.with_suffix("")
    tmp.replace(final)

def _ensure_inverted_matrix(dll_no: int) -> Optional[bytes]:
    if dll_no in _inverted_matrices:
        return _inverted_matrices[dll_no]
    cached = _load_inverted_cache(dll_no)
    if cached:
        _inverted_matrices[dll_no] = cached
        _inversion_stats["disk_hits"] += 1
        return cached
    mparams = _load_matrix_params(dll_no)
    if not mparams:
        _inversion_stats["fail"] += 1
        return None
    t0 = time.perf_counter()
    try:
        p = mparams["p"]; e = mparams["e"]; T_flat = mparams["T_flat"]; R_const = mparams["R_const"]
        inv = invert_matrix_root(p, e, T_flat, R_const)
    except Exception as ex:
        print(f"[invert-fail] dll={dll_no} {ex}")
        traceback.print_exc()
        _inversion_stats["fail"] += 1
        return None
    dt = time.perf_counter() - t0
    _inversion_stats["computed"] += 1
    _inversion_stats["time_compute"] += dt
    a1_bytes = bytes(inv["a1_bytes"])
    _inverted_matrices[dll_no] = a1_bytes
    _save_inverted_cache(dll_no, a1_bytes)
    return a1_bytes

# ---------- Load helpers with optional preloaded lookup ----------

def _load_matrix_params(dll_no: int) -> Optional[Dict[str, Any]]:
    if dll_no in _preloaded_matrix:
        return _preloaded_matrix[dll_no]
    f = DIR_MAT / f"{dll_no}.json"
    if not f.exists():
        return None
    j = read_json_bytes(f)
    try:
        p = int(j["p"], 16)
        e = int(j["e"], 16)
        T_flat = [int(x, 16) for x in j["T_flat"]]
        R_const = [int(x, 16) for x in j["R_const"]]
        if len(T_flat) != 16 or len(R_const) != 16:
            raise ValueError("Bad matrix dimension")
        res = {"p": p, "e": e, "T_flat": T_flat, "R_const": R_const}
        _preloaded_matrix[dll_no] = res
        return res
    except KeyError as ex:
        raise ValueError(f"Matrix JSON missing key {ex}") from ex

def _load_transform_order(dll_no: int) -> List[Dict[str, Any]]:
    if dll_no in _preloaded_order:
        return _preloaded_order[dll_no]
    f = DIR_ORDER / f"{dll_no}_transform_order.json"
    if not f.exists():
        return []
    j = read_json_bytes(f)
    result: List[Dict[str, Any]] = []
    if isinstance(j, dict):
        for k in ("reverse", "order", "transforms"):
            v = j.get(k)
            if isinstance(v, list):
                result = [x for x in v if isinstance(x, dict)]
                break
    elif isinstance(j, list):
        result = [x for x in j if isinstance(x, dict)]
    _preloaded_order[dll_no] = result
    return result

def _load_call_chain(dll_no: int) -> Dict[str, Dict[str, Any]]:
    f = DIR_CALL_CHAIN / f"{dll_no}_call_chain.json"
    if not f.exists():
        return {}
    j = read_json_bytes(f)
    mapping = {}
    if isinstance(j, list):
        for e in j:
            if isinstance(e, dict) and "name" in e:
                mapping[e["name"]] = e
    elif isinstance(j, dict):
        for v in j.values():
            if isinstance(v, list):
                for e in v:
                    if isinstance(e, dict) and "name" in e:
                        mapping[e["name"]] = e
    return mapping

def _load_constants_file(dll_no: int, kind: str) -> Dict[str, Any]:
    key = (dll_no, kind)
    if key in _preloaded_internal_constants:
        return _preloaded_internal_constants[key]
    kind = get_type_name(kind)
    if kind == "exponent":
        f = DIR_DIFFUSIONS / f"{dll_no}_diffusions.json"
    elif kind == "sbox":
        f = DIR_CONFUSIONS / f"{dll_no}_confusions.json"
    elif kind == "permutation":
        f = DIR_PERMUTATIONS / f"{dll_no}_permutations.json"
    else:
        return {}
    if not f.exists():
        return {}
    j = read_json_bytes(f)
    mapping = {k: v for k, v in j.items() if isinstance(v, list)}
    _preloaded_internal_constants[key] = mapping
    return mapping

# ---------------- External Resolver ----------------

class ExternalResolver:
    def __init__(self):
        self._call_chain_cache: Dict[int, Dict[str, Dict[str, Any]]] = {}
        self._constants_cache: Dict[Tuple[int, str], Dict[str, Any]] = {}

    def resolve(self, dll_no: int, func_name: str) -> Optional[Dict[str, Any]]:
        call_map = self._call_chain_cache.get(dll_no)
        if call_map is None:
            call_map = _load_call_chain(dll_no)
            self._call_chain_cache[dll_no] = call_map
        entry = call_map.get(func_name)
        if not entry:
            return None
        actual_type = entry.get("classification", "").lower()
        if get_type_name(actual_type) not in {"exponent", "sbox", "permutation"}:
            return None
        key = (dll_no, actual_type)
        const_map = self._constants_cache.get(key)
        if const_map is None:
            const_map = _load_constants_file(dll_no, actual_type)
            self._constants_cache[key] = const_map
        raw_list = const_map.get(func_name)
        if raw_list is None:
            return None
        return {
            "actual_type": actual_type,
            "raw_constants": raw_list
        }

# ---------------- Transform Application ----------------

def apply_inverse(data: bytes, t_type: str, raw_constants: Any, check_byte: int) -> bytes:
    t_type = get_type_name(t_type)
    if t_type == "exponent":
        exp_bytes = parse_exponent_constants(raw_constants)
        return inverse_exponent(data, exp_bytes, check_byte)
    if t_type == "sbox":
        table_bytes = parse_sbox_constants(raw_constants)
        return inverse_sbox(data, check_byte, table_bytes)
    if t_type == "permutation":
        idx_bytes = parse_permutation_constants(raw_constants)
        return inverse_permutation(data, check_byte, idx_bytes)
    return data

def apply_forward(data: bytes, t_type: str, raw_constants: Any, check_byte: int) -> bytes:
    t_type = get_type_name(t_type)
    if t_type == "exponent":
        exp_bytes = parse_exponent_constants(raw_constants)
        return forward_exponent(data, exp_bytes, check_byte)
    if t_type == "sbox":
        table_bytes = parse_sbox_constants(raw_constants)
        return forward_sbox(data, check_byte, table_bytes)
    if t_type == "permutation":
        idx_bytes = parse_permutation_constants(raw_constants)
        return forward_permutation(data, check_byte, idx_bytes)
    return data

# ---------------- DLL Recovery Core ----------------

def recover_dll(dll_no: int,
                xor_values: Dict[str, int],
                resolver: ExternalResolver) -> Dict[str, Any]:
    t_total_start = time.perf_counter()
    t_order_start = time.perf_counter()
    order = _load_transform_order(dll_no)
    _recover_stats["time_order_load"] += time.perf_counter() - t_order_start

    # (existing logic reorganized minimally)
    diag: Dict[str, Any] = {
        "dll_no": dll_no,
        "status": "fail",
        "errors": [],
        "unresolved_externals": [],
        "missing_internal": [],
        "transform_applied": 0
    }

    a1_bytes = _ensure_inverted_matrix(dll_no)
    if not a1_bytes:
        diag["errors"].append("matrix_params_missing_or_inversion_fail")
        _recover_stats["dlls"] += 1
        _recover_stats["time_total"] += time.perf_counter() - t_total_start
        return {"hex": None, "diag": diag}
    current = bytearray(a1_bytes)

    if not order:
        diag["status"] = "ok"
        _recover_stats["dlls"] += 1
        _recover_stats["time_total"] += time.perf_counter() - t_total_start
        return {"hex": current.hex(), "diag": diag}

    t_cb_start = time.perf_counter()
    try:
        check_byte = xor_values[str(dll_no)]
    except KeyError:
        diag["errors"].append("missing_check_byte")
        _recover_stats["time_checkbyte_lookup"] += time.perf_counter() - t_cb_start
        _recover_stats["dlls"] += 1
        _recover_stats["time_total"] += time.perf_counter() - t_total_start
        return {"hex": None, "diag": diag}
    _recover_stats["time_checkbyte_lookup"] += time.perf_counter() - t_cb_start

    t_loop_start = time.perf_counter()
    for step in order:
        # (original transform loop unchanged)
        name = step.get("name")
        classification = (step.get("classification") or "").lower()
        if not name or not classification:
            continue
        if classification == "import":
            dll_ref_raw = step.get("dllno")
            if dll_ref_raw is None:
                diag["unresolved_externals"].append(name); continue
            try:
                dll_ref = int(dll_ref_raw)
            except ValueError:
                diag["unresolved_externals"].append(name); continue
            resolved = resolver.resolve(dll_ref, name)
            if not resolved:
                diag["unresolved_externals"].append(name); continue
            parsed = _get_parsed_transform(dll_ref, resolved["actual_type"], name)
            if parsed is None:
                diag["unresolved_externals"].append(name); continue
            current_before = current
            current = apply_inverse_parsed(current, resolved["actual_type"], parsed, xor_values.get(str(dll_ref), 0))
            if current != current_before:
                diag["transform_applied"] += 1
        else:
            parsed = _get_parsed_transform(dll_no, classification, name)
            if parsed is None:
                diag["missing_internal"].append(name); continue
            current_before = current
            current = apply_inverse_parsed(current, classification, parsed, check_byte)
            if current != current_before:
                diag["transform_applied"] += 1
    _recover_stats["time_transform_loop"] += time.perf_counter() - t_loop_start

    if diag["errors"]:
        pass
    elif diag["unresolved_externals"]:
        diag["errors"].append("unresolved_external_transforms")
    elif STRICT_FAIL_ON_MISSING_INTERNAL and diag["missing_internal"]:
        diag["errors"].append("missing_internal_transforms")
    else:
        diag["status"] = "ok"

    _recover_stats["dlls"] += 1
    _recover_stats["time_total"] += time.perf_counter() - t_total_start
    return {"hex": bytes(current).hex() if diag["status"] == "ok" else None,
            "diag": diag}

def _get_parsed_transform(dll_no: int, classification: str, func_name: str):
    """Return parsed constants for a specific transform."""
    key = (dll_no, classification, func_name)
    if key in _parsed_constants_cache:
        return _parsed_constants_cache[key]
    const_map = _load_constants_file(dll_no, classification)
    classification = get_type_name(classification)
    raw_list = const_map.get(func_name)
    if raw_list is None:
        return None
    if classification == "exponent":
        parsed = parse_exponent_constants(raw_list)
    elif classification == "sbox":
        parsed = parse_sbox_constants(raw_list)
    elif classification == "permutation":
        parsed = parse_permutation_constants(raw_list)
    else:
        return None
    _parsed_constants_cache[key] = parsed
    return parsed

# Modify apply_inverse to accept already-parsed constants (new helper)
def apply_inverse_parsed(data: bytearray, t_type: str, parsed_constants: Any, check_byte: int) -> bytearray:
    t_type = get_type_name(t_type)
    if t_type == "exponent":
        return bytearray(inverse_exponent(data, parsed_constants, check_byte))
    if t_type == "sbox":
        return bytearray(inverse_sbox(data, check_byte, parsed_constants))
    if t_type == "permutation":
        return bytearray(inverse_permutation(data, check_byte, parsed_constants))
    return data

# ---------------- Worker wrapper ----------------

def worker_task(snapshot_index: int, dll_no: int) -> Tuple[int, Dict[str, Any], Optional[str]]:
    xor_values = _load_xor_values(snapshot_index, dll_no)
    res = recover_dll(dll_no, xor_values, _resolver)
    return dll_no, res["diag"], res["hex"]

def worker_task_batch(batch: List[Tuple[int,int]]) -> List[Tuple[int, Dict[str,Any], Optional[str]]]:
    out = []
    for snapshot_index, dll_no in batch:
        xor_values = _load_xor_values(snapshot_index, dll_no)
        res = recover_dll(dll_no, xor_values, _resolver)
        out.append((dll_no, res["diag"], res["hex"]))
    return out

# ---------------- Parallel Main ----------------

def run_parallel(workers: int,
                 checkpoint_every: int,
                 eager_preload: bool,
                 progress_interval: float,
                 verbose_complete: bool,
                 progress_style: str,
                 suppress_order_print: bool,
                 flush_every: int,
                 precompute_inversions: bool):
    # (drop no_fast_shutdown & shutdown_warn_timeout)
    if not XOR_FILE_JSON.exists() or not OFFSETS_FILE.exists():
        print("snapshots.ndjson or offsets.bin missing")
        return
    if os.environ.get("DISK_CACHE_INVERTED") != "1":
        os.environ["DISK_CACHE_INVERTED"] = "1"
    os.environ["CACHE_WRITE_ROLE"] = "parent"
    ensure_charpoly_cache_loaded()
    processed = load_processed_keys(OUTPUT_SIMPLE)
    pending: List[Tuple[int, int]] = [
        (idx, dll) for idx, dll in enumerate(DLL_ORDER) if dll not in processed
    ]
    if not pending:
        print("All DLLs already processed.")
        return
    next_write_index_start = 0
    while next_write_index_start < len(DLL_ORDER) and DLL_ORDER[next_write_index_start] in processed:
        next_write_index_start += 1
    if precompute_inversions:
        enable_charpoly_batch_mode()
        print(f"[precompute] Inverting {len(pending)} matrices (may take time)...")
        start_pc = time.time()
        pre_ok = 0
        for _, dll in pending:
            mp = _load_matrix_params(dll)
            if not mp:
                continue
            if _load_inverted_cache(dll):
                continue
            if dll not in _inverted_matrices:
                try:
                    inv = invert_matrix_root(mp["p"], mp["e"], mp["T_flat"], mp["R_const"])
                    _inverted_matrices[dll] = bytes(inv["a1_bytes"])
                    _save_inverted_cache(dll, _inverted_matrices[dll])
                    pre_ok += 1
                except Exception as ex:
                    print(f"[precompute-fail] dll={dll} {ex}")
        dur_pc = time.time() - start_pc
        print(f"[precompute] Complete ok={pre_ok} elapsed={dur_pc:.2f}s")
        flush_charpoly_cache()

    diag_map: Dict[str, Any] = {}
    if workers in (0, None):
        workers = os.cpu_count() or 1
    total = len(pending)
    print(f"[parallel] Workers={workers} pending={total} eager_preload={eager_preload} "
          f"progress={progress_style} flush_every={flush_every} precompute={precompute_inversions}")

    ok_count = 0
    fail_count = 0
    completed_count = 0

    use_tqdm = (progress_style == "tqdm" and tqdm is not None)
    bar = tqdm(total=total, desc="DLLs", unit="dll", dynamic_ncols=True, mininterval=0.2) if use_tqdm else None
    mp_ctx = multiprocessing.get_context("spawn")
    pool = ProcessPoolExecutor(
        max_workers=workers,
        initializer=worker_init,
        initargs=(eager_preload,),
        mp_context=mp_ctx
    )
    try:
        batch_size = 16
        batches = [pending[i:i + batch_size] for i in range(0, len(pending), batch_size)]
        futures = {pool.submit(worker_task_batch, batch): batch for batch in batches}
        next_write_index = next_write_index_start
        ordered_queue: Dict[int, Tuple[Dict[str, Any], Optional[str]]] = {}
        processed_since_flush_ordered = 0
        processed_since_flush_any = 0
        completions_to_checkpoint = 0
        with OUTPUT_SIMPLE.open("a", encoding="utf-8") as log_f:
            for fut in as_completed(futures):
                try:
                    results = fut.result()
                except Exception as ex:
                    print(f"[future-error] {ex}")
                    continue
                batch_ok = 0
                batch_fail = 0
                for dll_no, diag, hex_val in results:
                    diag_map[str(dll_no)] = diag
                    ordered_queue[dll_no] = (diag, hex_val)
                    if diag["status"] == "ok" and hex_val:
                        ok_count += 1; batch_ok += 1
                    else:
                        fail_count += 1; batch_fail += 1
                    completed_count += 1
                    processed_since_flush_any += 1
                    completions_to_checkpoint += 1
                if bar:
                    bar.update(len(results))
                    bar.set_postfix(ok=ok_count, fail=fail_count, batch_ok=batch_ok, batch_fail=batch_fail, chkpt=completed_count)
                elif verbose_complete:
                    print(f"[batch] size={len(results)} batch_ok={batch_ok} batch_fail={batch_fail} "
                          f"tot_ok={ok_count} tot_fail={fail_count}")
                while next_write_index < len(DLL_ORDER):
                    dll_expected = DLL_ORDER[next_write_index]
                    if dll_expected in processed and dll_expected not in ordered_queue:
                        next_write_index += 1; continue
                    item = ordered_queue.get(dll_expected)
                    if item is None:
                        break
                    _, hex_item = item
                    log_f.write(f'{{"{dll_expected!r}": "{hex_item}"}}\n')
                    del ordered_queue[dll_expected]
                    next_write_index += 1
                    processed_since_flush_ordered += 1
                    # (suppressed individual OK/FAIL printing)
                if processed_since_flush_any >= flush_every or processed_since_flush_ordered >= flush_every:
                    log_f.flush()
                    atomic_write_json(OUTPUT_DIAG, diag_map)
                    processed_since_flush_any = 0
                    processed_since_flush_ordered = 0
                if completions_to_checkpoint >= checkpoint_every:
                    atomic_write_json(OUTPUT_DIAG, diag_map)
                    completions_to_checkpoint = 0
                    if bar:
                        bar.set_postfix(ok=ok_count, fail=fail_count, batch_ok=batch_ok, batch_fail=batch_fail, chkpt=completed_count)
        atomic_write_json(OUTPUT_DIAG, diag_map)
        if bar:
            bar.close()
        if _inversion_stats["computed"] or _inversion_stats["disk_hits"]:
            avg_comp = (_inversion_stats["time_compute"] / _inversion_stats["computed"]
                        if _inversion_stats["computed"] else 0.0)
            print(f"[stats-inversion] computed={_inversion_stats['computed']} disk_hits={_inversion_stats['disk_hits']} "
                  f"fail={_inversion_stats['fail']} t_compute={_inversion_stats['time_compute']:.2f}s "
                  f"avg_compute={avg_comp*1000:.2f}ms")
        if _snapshot_stats["reads"]:
            print(f"[stats-snapshots] reads={_snapshot_stats['reads']} parse_time={_snapshot_stats['parse_time']:.2f}s "
                  f"avg_parse={( _snapshot_stats['parse_time'] / _snapshot_stats['reads'] )*1000:.2f}ms")
        if _recover_stats["dlls"]:
            print(f"[stats-recover] dlls={_recover_stats['dlls']} "
                  f"t_total={_recover_stats['time_total']:.2f}s "
                  f"t_loop={_recover_stats['time_transform_loop']:.2f}s "
                  f"t_order={_recover_stats['time_order_load']:.2f}s "
                  f"t_checkbyte={_recover_stats['time_checkbyte_lookup']:.2f}s "
                  f"avg_total={( _recover_stats['time_total'] / _recover_stats['dlls'] )*1000:.2f}ms "
                  f"avg_loop={( _recover_stats['time_transform_loop'] / _recover_stats['dlls'] )*1000:.2f}ms")
        print(f"[done] total={completed_count} ok={ok_count} fail={fail_count}")
    finally:
        print("[shutdown] fast pool shutdown...")
        t0 = time.perf_counter()
        pool.shutdown(wait=False, cancel_futures=False)
        del pool
        print(f"[shutdown] dispatched in {(time.perf_counter()-t0):.3f}s; OS will reap workers.")

# ---------------- Serial Main (fallback) ----------------

def run_serial(checkpoint_every: int):
    if not XOR_FILE_JSON.exists() or not OFFSETS_FILE.exists():
        print("snapshots.ndjson or offsets.bin missing")
        return
    processed = load_processed_keys(OUTPUT_SIMPLE)
    diag_map: Dict[str, Any] = {}
    resolver = ExternalResolver()
    processed_since_flush = 0  # NEW initialization

    with OUTPUT_SIMPLE.open("a", encoding="utf-8") as log_f:
        log_f.write("[\n")  # start of JSON array
        for idx, dll in enumerate(DLL_ORDER):
            if dll in processed:
                continue
            xor_values = _load_xor_values(idx)
            res = recover_dll(dll, xor_values, resolver)
            diag_map[str(dll)] = res["diag"]
            log_f.write(f'"{dll!r}": "{res["hex"]}"\n')
            processed_since_flush += 1
            if processed_since_flush >= FLUSH_EVERY_DEFAULT or (idx + 1) % checkpoint_every == 0:
                log_f.flush()
                atomic_write_json(OUTPUT_DIAG, diag_map)
                processed_since_flush = 0
        log_f.write("]\n")  # end of JSON array
    atomic_write_json(OUTPUT_DIAG, diag_map)
    print("Serial recovery complete.")

# ---------------- CLI ----------------
def parse_args():
    ap = argparse.ArgumentParser(description="Parallel DLL recovery")
    ap.add_argument("--workers", type=int, default=0,
                    help="Number of worker processes (0=cpu count, 1=serial)")
    ap.add_argument("--checkpoint-every", type=int, default=CHECKPOINT_DEFAULT,
                    help="How often to checkpoint diagnostics (by DLL completions, not writes)")
    ap.add_argument("--eager-preload", action="store_true",
                    help="Preload matrix/order/internal constants in each process initializer")
    ap.add_argument("--progress-interval", type=float, default=10.0,
                    help="(Reserved, currently unused heartbeat interval)")
    ap.add_argument("--verbose-complete", action="store_true",
                    help="Print a line for every batch completion when not using tqdm")
    ap.add_argument("--progress", choices=["tqdm", "none"], default="tqdm",
                    help="Progress display style")
    ap.add_argument("--suppress-order-print", action="store_true",
                    help="Don't print [OK]/[FAIL] lines for ordered flush")
    ap.add_argument("--flush-every", type=int, default=FLUSH_EVERY_DEFAULT,
                    help="Flush results & diagnostics every N completions or ordered writes")
    ap.add_argument("--precompute-inversions", action="store_true",
                    help="Precompute all matrix inversions in parent before spawning workers")
    return ap.parse_args()

def main():
    args = parse_args()
    if args.workers == 1:
        run_serial(args.checkpoint_every)
    else:
        run_parallel(
            workers=args.workers,
            checkpoint_every=args.checkpoint_every,
            eager_preload=args.eager_preload,
            progress_interval=args.progress_interval,
            verbose_complete=args.verbose_complete,
            progress_style=args.progress,
            suppress_order_print=args.suppress_order_print,
            flush_every=args.flush_every,
            precompute_inversions=args.precompute_inversions
        )

if __name__ == "__main__":
    main()