from __future__ import annotations

import argparse
import dataclasses
import hashlib
import mmap
import os
import pathlib
import pickle
import struct
import subprocess
import time
import bisect
from typing import Iterator


SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
ROOT = SCRIPT_DIR if (SCRIPT_DIR / "10000.exe").exists() else SCRIPT_DIR.parent
EXE = ROOT / "10000.exe"
ARTIFACT_DIR = SCRIPT_DIR / "solve_artifacts"
DEPS_PKL = ARTIFACT_DIR / "deps.pkl"
TARGET_PKL = ARTIFACT_DIR / "target.pkl"
ORDER_PKL = ARTIFACT_DIR / "order.pkl"
APLIB_SERVER_DLL = SCRIPT_DIR / "AplibServer" / "bin" / "Release" / "net8.0" / "AplibServer.dll"
MOD256 = 1 << 256
ODD_GROUP_EXP = 1 << 254
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)


def u16(buf: bytes | bytearray | memoryview, off: int) -> int:
    return struct.unpack_from("<H", buf, off)[0]


def u32(buf: bytes | bytearray | memoryview, off: int) -> int:
    return struct.unpack_from("<I", buf, off)[0]


def u64(buf: bytes | bytearray | memoryview, off: int) -> int:
    return struct.unpack_from("<Q", buf, off)[0]


def s8(value: int) -> int:
    return value - 0x100 if value & 0x80 else value


def s32(buf: bytes | bytearray | memoryview, off: int) -> int:
    return struct.unpack_from("<i", buf, off)[0]


@dataclasses.dataclass(frozen=True)
class Section:
    name: str
    vaddr: int
    vsize: int
    rawptr: int
    rawsize: int

    def contains_rva(self, rva: int) -> bool:
        return self.vaddr <= rva < self.vaddr + max(self.vsize, self.rawsize)


class PE:
    def __init__(self, data: bytes | mmap.mmap):
        self.data = data
        if data[:2] != b"MZ":
            raise ValueError("not a PE/MZ image")
        self.peoff = u32(data, 0x3C)
        if data[self.peoff : self.peoff + 4] != b"PE\0\0":
            raise ValueError("not a PE image")
        self.machine = u16(data, self.peoff + 4)
        self.nsects = u16(data, self.peoff + 6)
        self.opt_size = u16(data, self.peoff + 20)
        self.opt_off = self.peoff + 0x18
        self.magic = u16(data, self.opt_off)
        if self.magic == 0x20B:
            self.image_base = u64(data, self.opt_off + 0x18)
            self.entry_rva = u32(data, self.opt_off + 0x10)
            self.dd_off = self.opt_off + 0x70
        elif self.magic == 0x10B:
            self.image_base = u32(data, self.opt_off + 0x1C)
            self.entry_rva = u32(data, self.opt_off + 0x10)
            self.dd_off = self.opt_off + 0x60
        else:
            raise ValueError(f"unsupported PE optional header magic {self.magic:#x}")
        self.sections: list[Section] = []
        sect_off = self.opt_off + self.opt_size
        for i in range(self.nsects):
            off = sect_off + i * 40
            name = bytes(data[off : off + 8]).split(b"\0", 1)[0].decode("ascii", "replace")
            vsize, vaddr, rawsize, rawptr = struct.unpack_from("<IIII", data, off + 8)
            self.sections.append(Section(name, vaddr, vsize, rawptr, rawsize))

    def data_dir(self, index: int) -> tuple[int, int]:
        off = self.dd_off + 8 * index
        return u32(self.data, off), u32(self.data, off + 4)

    def rva_to_off(self, rva: int) -> int:
        for sec in self.sections:
            if sec.rawsize and sec.vaddr <= rva < sec.vaddr + sec.rawsize:
                return sec.rawptr + (rva - sec.vaddr)
        raise ValueError(f"RVA not mapped: {rva:#x}")

    def read_rva(self, rva: int, size: int) -> bytes:
        off = self.rva_to_off(rva)
        return bytes(self.data[off : off + size])

    def cstr_rva(self, rva: int) -> str:
        off = self.rva_to_off(rva)
        end = off
        data = self.data
        while end < len(data) and data[end] != 0:
            end += 1
        return bytes(data[off:end]).decode("ascii", "replace")

    def exports(self) -> dict[str, int]:
        rva, size = self.data_dir(0)
        if not rva:
            return {}
        off = self.rva_to_off(rva)
        base = u32(self.data, off + 16)
        num_funcs = u32(self.data, off + 20)
        num_names = u32(self.data, off + 24)
        funcs_rva = u32(self.data, off + 28)
        names_rva = u32(self.data, off + 32)
        ords_rva = u32(self.data, off + 36)
        funcs_off = self.rva_to_off(funcs_rva)
        names_off = self.rva_to_off(names_rva)
        ords_off = self.rva_to_off(ords_rva)
        out: dict[str, int] = {}
        for i in range(num_names):
            name_rva = u32(self.data, names_off + 4 * i)
            name = self.cstr_rva(name_rva)
            ordinal = u16(self.data, ords_off + 2 * i)
            if ordinal < num_funcs:
                out[name] = u32(self.data, funcs_off + 4 * ordinal)
        return out

    def imports(self) -> list[tuple[str, list[str]]]:
        rva, size = self.data_dir(1)
        if not rva:
            return []
        out: list[tuple[str, list[str]]] = []
        desc = self.rva_to_off(rva)
        ptr_size = 8 if self.magic == 0x20B else 4
        while True:
            oft, tds, fwd, name_rva, ft = struct.unpack_from("<IIIII", self.data, desc)
            if not any((oft, tds, fwd, name_rva, ft)):
                break
            dll = self.cstr_rva(name_rva)
            thunk_rva = oft or ft
            thunk_off = self.rva_to_off(thunk_rva)
            names: list[str] = []
            idx = 0
            while True:
                if ptr_size == 8:
                    val = u64(self.data, thunk_off + idx * 8)
                    ord_flag = 0x8000000000000000
                else:
                    val = u32(self.data, thunk_off + idx * 4)
                    ord_flag = 0x80000000
                if not val:
                    break
                if val & ord_flag:
                    names.append(f"#{val & 0xFFFF}")
                else:
                    names.append(self.cstr_rva(val + 2))
                idx += 1
            out.append((dll, names))
            desc += 20
        return out


class ResourceView:
    def __init__(self, exe_path: pathlib.Path = EXE):
        self.fp = exe_path.open("rb")
        self.mm = mmap.mmap(self.fp.fileno(), 0, access=mmap.ACCESS_READ)
        self.pe = PE(self.mm)
        self.res_rva, self.res_size = self.pe.data_dir(2)
        self.res_off = self.pe.rva_to_off(self.res_rva)
        self.rcdata_index: dict[int, tuple[int, int]] | None = None

    def close(self) -> None:
        self.mm.close()
        self.fp.close()

    def _dir_entries(self, rel: int) -> list[tuple[int, bool, bool, int]]:
        off = self.res_off + rel
        named = u16(self.mm, off + 12)
        ids = u16(self.mm, off + 14)
        entries: list[tuple[int, bool, bool, int]] = []
        for i in range(named + ids):
            entry = off + 16 + i * 8
            ident_raw = u32(self.mm, entry)
            target_raw = u32(self.mm, entry + 4)
            entries.append(
                (
                    ident_raw & 0x7FFFFFFF,
                    bool(ident_raw & 0x80000000),
                    bool(target_raw & 0x80000000),
                    target_raw & 0x7FFFFFFF,
                )
            )
        return entries

    def iter_rcdata(self) -> Iterator[tuple[int, int, int, int]]:
        for typ, _is_name, is_dir, target in self._dir_entries(0):
            if typ != 10 or not is_dir:
                continue
            for resid, _name, name_is_dir, name_target in self._dir_entries(target):
                if not name_is_dir:
                    continue
                langs = self._dir_entries(name_target)
                if len(langs) != 1:
                    raise ValueError(f"resource {resid} has {len(langs)} languages")
                lang, _lname, lang_is_dir, data_rel = langs[0]
                if lang_is_dir:
                    raise ValueError(f"resource {resid} language points at directory")
                data_entry = self.res_off + data_rel
                data_rva = u32(self.mm, data_entry)
                size = u32(self.mm, data_entry + 4)
                yield resid, lang, self.pe.rva_to_off(data_rva), size

    def get_resource(self, resid: int) -> bytes:
        if self.rcdata_index is None:
            self.rcdata_index = {cur: (off, size) for cur, _lang, off, size in self.iter_rcdata()}
        try:
            off, size = self.rcdata_index[resid]
        except KeyError:
            raise KeyError(resid) from None
        return bytes(self.mm[off : off + size])


class AplibBits:
    def __init__(self, src: bytes):
        self.src = src
        self.pos = 1
        self.bits = 0
        self.tag = 0

    def bit(self) -> int:
        if self.bits == 0:
            if self.pos >= len(self.src):
                raise EOFError("aplib bitstream exhausted")
            self.tag = self.src[self.pos]
            self.pos += 1
            self.bits = 0x80
        out = 1 if (self.tag & 0x80) else 0
        self.tag = (self.tag << 1) & 0xFF
        self.bits >>= 1
        return out

    def byte(self) -> int:
        if self.pos >= len(self.src):
            raise EOFError("aplib byte stream exhausted")
        out = self.src[self.pos]
        self.pos += 1
        return out

    def gamma(self) -> int:
        out = 1
        while True:
            out = (out << 1) | self.bit()
            if self.bit() == 0:
                return out


def aplib_decompress(src: bytes, expected_size: int | None = None) -> bytes:
    if not src:
        return b""
    bits = AplibBits(src)
    dst = bytearray([src[0]])
    last_offset = -1
    lwm = 3
    while True:
        if bits.bit() == 0:
            dst.append(bits.byte())
            lwm = 3
            continue

        if bits.bit() == 1:
            if bits.bit() == 0:
                packed = bits.byte()
                if packed == 0:
                    break
                offset = packed >> 1
                length = 2 + (packed & 1)
                last_offset = offset
                lwm = 2
                copy_from = len(dst) - offset
                if copy_from < 0:
                    raise ValueError("invalid aplib short match offset")
                for _ in range(length):
                    dst.append(dst[copy_from])
                    copy_from += 1
            else:
                offset = 0
                for _ in range(4):
                    offset = (offset << 1) | bits.bit()
                lwm = 3
                if offset:
                    copy_from = len(dst) - offset
                    if copy_from < 0:
                        raise ValueError("invalid aplib tiny match offset")
                    dst.append(dst[copy_from])
                else:
                    dst.append(0)
            continue

        gamma = bits.gamma()
        offset = gamma - lwm
        if offset < 0:
            offset = last_offset
            length = bits.gamma()
        else:
            offset = (offset << 8) | bits.byte()
            length = bits.gamma()
            if offset <= 127 or offset > 31999:
                length += 2
            elif offset > 1279:
                length += 1
            last_offset = offset
        lwm = 2
        copy_from = len(dst) - offset
        if offset <= 0 or copy_from < 0:
            raise ValueError("invalid aplib long match offset")
        for _ in range(length):
            dst.append(dst[copy_from])
            copy_from += 1
        if expected_size is not None and len(dst) > expected_size:
            raise ValueError("aplib output exceeded expected size")

    out = bytes(dst)
    if expected_size is not None and len(out) != expected_size:
        raise ValueError(f"aplib size mismatch: got {len(out)}, expected {expected_size}")
    return out


def module_image(res: ResourceView, resid: int) -> bytes:
    blob = res.get_resource(resid)
    try:
        import aplib  # type: ignore

        return aplib.decompress(blob)
    except Exception:
        return aplib_decompress(blob)


class DotnetAplibServer:
    def __init__(self, exe_path: pathlib.Path = EXE, server_dll: pathlib.Path = APLIB_SERVER_DLL):
        if not server_dll.exists():
            raise FileNotFoundError(server_dll)
        self.proc = subprocess.Popen(
            ["dotnet", str(server_dll), str(exe_path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def _read_exact(self, size: int) -> bytes:
        assert self.proc.stdout is not None
        data = self.proc.stdout.read(size)
        if len(data) != size:
            stderr = b""
            if self.proc.stderr is not None:
                try:
                    stderr = self.proc.stderr.read()
                except Exception:
                    stderr = b""
            raise RuntimeError(
                f"native decompressor returned {len(data)}/{size} bytes"
                + (f": {stderr.decode('utf-8', 'replace')}" if stderr else "")
            )
        return data

    def image(self, resid: int) -> bytes:
        if self.proc.poll() is not None:
            raise RuntimeError(f"native decompressor exited with {self.proc.returncode}")
        assert self.proc.stdin is not None
        self.proc.stdin.write(f"{resid}\n".encode("ascii"))
        self.proc.stdin.flush()
        size = struct.unpack("<I", self._read_exact(4))[0]
        return self._read_exact(size)

    def close(self) -> None:
        if self.proc.stdin is not None:
            try:
                self.proc.stdin.close()
            except Exception:
                pass
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.terminate()
            self.proc.wait(timeout=5)


def target_counters(exe_path: pathlib.Path = EXE) -> list[int]:
    with exe_path.open("rb") as fp:
        mm = mmap.mmap(fp.fileno(), 0, access=mmap.ACCESS_READ)
        try:
            pe = PE(mm)
            # unk_1400CC000 is at image RVA 0xCC000 and is compared with size 0x9C40.
            off = pe.rva_to_off(0xCC000)
            return list(struct.unpack_from("<10000I", mm, off))
        finally:
            mm.close()


def numeric_import_deps(pe: PE) -> list[int]:
    deps: set[int] = set()
    for dll, _names in pe.imports():
        stem = dll.split(".", 1)[0]
        if len(stem) == 4 and stem.isdigit():
            deps.add(int(stem))
    return sorted(deps)


def _deps_worker(args: tuple[int, int, list[tuple[int, int, int]]]) -> tuple[int, list[list[int]]]:
    start, stop, entries = args
    import aplib  # type: ignore

    with EXE.open("rb") as fp:
        mm = mmap.mmap(fp.fileno(), 0, access=mmap.ACCESS_READ)
        try:
            out: list[list[int]] = []
            for resid in range(start, stop):
                _rid, off, size = entries[resid]
                img = aplib.decompress(bytes(mm[off : off + size]))
                out.append(numeric_import_deps(PE(img)))
            return start, out
        finally:
            mm.close()


def extract_deps(workers: int = 0) -> list[list[int]]:
    res = ResourceView()
    try:
        entries = [(rid, off, size) for rid, _lang, off, size in res.iter_rcdata()]
    finally:
        res.close()
    entries.sort()
    if [rid for rid, _off, _size in entries] != list(range(10000)):
        raise ValueError("resource IDs are not the expected 0..9999 range")

    if workers <= 0:
        workers = max(1, min((os.cpu_count() or 4) - 1, 8))
    chunk = (len(entries) + workers - 1) // workers
    tasks = []
    for start in range(0, len(entries), chunk):
        tasks.append((start, min(start + chunk, len(entries)), entries))

    t0 = time.time()
    if workers == 1:
        pieces = [_deps_worker(task) for task in tasks]
    else:
        from multiprocessing import Pool

        with Pool(processes=workers) as pool:
            pieces = list(pool.imap_unordered(_deps_worker, tasks))
    deps: list[list[int]] = [[] for _ in range(len(entries))]
    for start, rows in pieces:
        deps[start : start + len(rows)] = rows
    with DEPS_PKL.open("wb") as fp:
        pickle.dump(deps, fp, protocol=pickle.HIGHEST_PROTOCOL)
    with TARGET_PKL.open("wb") as fp:
        pickle.dump(target_counters(), fp, protocol=pickle.HIGHEST_PROTOCOL)
    print(f"wrote {DEPS_PKL} with {len(deps)} rows in {time.time() - t0:.1f}s")
    print(
        "direct deps:",
        f"min={min(map(len, deps))}",
        f"max={max(map(len, deps))}",
        f"avg={sum(map(len, deps))/len(deps):.1f}",
    )
    return deps


def load_deps() -> list[list[int]]:
    if not DEPS_PKL.exists():
        return extract_deps()
    with DEPS_PKL.open("rb") as fp:
        return pickle.load(fp)


def load_target() -> list[int]:
    if TARGET_PKL.exists():
        with TARGET_PKL.open("rb") as fp:
            return pickle.load(fp)
    target = target_counters()
    with TARGET_PKL.open("wb") as fp:
        pickle.dump(target, fp, protocol=pickle.HIGHEST_PROTOCOL)
    return target


def topo_order(deps: list[list[int]]) -> list[int]:
    from collections import deque

    n = len(deps)
    indeg = [0] * n
    for row in deps:
        for dep in row:
            indeg[dep] += 1
    q = deque([i for i, x in enumerate(indeg) if x == 0])
    out: list[int] = []
    while q:
        cur = q.popleft()
        out.append(cur)
        for dep in deps[cur]:
            indeg[dep] -= 1
            if indeg[dep] == 0:
                q.append(dep)
    if len(out) != n:
        raise ValueError("dependency graph contains a cycle")
    return out


def closure_bitsets(deps: list[list[int]], topo: list[int]) -> list[int]:
    closures = [0] * len(deps)
    for node in reversed(topo):
        bits = 1 << node
        for dep in deps[node]:
            bits |= closures[dep]
        closures[node] = bits
    return closures


def solve_order(deps: list[list[int]] | None = None, target: list[int] | None = None) -> tuple[list[int], list[int], list[int]]:
    if ORDER_PKL.exists():
        with ORDER_PKL.open("rb") as fp:
            cached = pickle.load(fp)
        return cached["pos"], cached["order"], cached["closures"]

    if deps is None:
        deps = load_deps()
    if target is None:
        target = load_target()
    topo = topo_order(deps)
    closures = closure_bitsets(deps, topo)
    residual = target[:]
    pos = [-1] * len(deps)
    used = [False] * len(deps)
    for node in topo:
        cur_pos = residual[node]
        if not (0 <= cur_pos < len(deps)):
            raise ValueError(f"node {node} solved to invalid position {cur_pos}")
        if used[cur_pos]:
            raise ValueError(f"duplicate solved position {cur_pos}")
        used[cur_pos] = True
        pos[node] = cur_pos
        bits = closures[node]
        while bits:
            lsb = bits & -bits
            residual[lsb.bit_length() - 1] -= cur_pos
            bits ^= lsb
    if any(residual):
        raise ValueError("order residual did not reduce to zero")
    order = [0] * len(deps)
    for module_id, cur_pos in enumerate(pos):
        order[cur_pos] = module_id
    with ORDER_PKL.open("wb") as fp:
        pickle.dump({"pos": pos, "order": order, "closures": closures}, fp, protocol=pickle.HIGHEST_PROTOCOL)
    return pos, order, closures


def mmul4(a: list[int], b: list[int], mod: int) -> list[int]:
    return [
        sum(a[4 * r + k] * b[4 * k + c] for k in range(4)) % mod
        for r in range(4)
        for c in range(4)
    ]


def mpow4(mat: list[int], exp: int, mod: int) -> list[int]:
    result = [1 if r == c else 0 for r in range(4) for c in range(4)]
    while exp:
        if exp & 1:
            result = mmul4(result, mat, mod)
        mat = mmul4(mat, mat, mod)
        exp >>= 1
    return result


def raw_movabs_stores(code: bytes | bytearray | memoryview) -> dict[int, int]:
    stores: dict[int, int] = {}
    last: dict[int, int] = {}
    i = 0
    limit = len(code) - 10
    while i < limit:
        op0 = code[i]
        op1 = code[i + 1]
        if op0 == 0x48 and op1 in (0xB8, 0xBA):
            # movabs rax/rdx, imm64
            last[op1] = u64(code, i + 2)
            i += 10
            continue
        if op0 == 0x48 and op1 == 0x89 and i + 4 <= len(code):
            op2 = code[i + 2]
            if op2 in (0x45, 0x55):
                # mov qword ptr [rbp+disp8], rax/rdx
                reg = 0xB8 if op2 == 0x45 else 0xBA
                if reg in last:
                    stores[s8(code[i + 3])] = last[reg]
                i += 4
                continue
            if op2 in (0x85, 0x95) and i + 7 <= len(code):
                # mov qword ptr [rbp+disp32], rax/rdx
                reg = 0xB8 if op2 == 0x85 else 0xBA
                if reg in last:
                    stores[s32(code, i + 3)] = last[reg]
                i += 7
                continue
        i += 1
    return stores


def raw_movabs_values(code: bytes | bytearray | memoryview) -> list[int]:
    data = bytes(code)
    values: list[int] = []
    i = 0
    while True:
        pos = data.find(b"\x48", i)
        if pos < 0 or pos + 10 > len(data):
            return values
        op = data[pos + 1]
        if op == 0xB8 or op == 0xBA:
            values.append(u64(data, pos + 2))
            i = pos + 10
        else:
            i = pos + 1


def raw_counter_index(code: bytes | bytearray | memoryview) -> int:
    pos = bytes(code[:96]).find(b"\x48\x8b\x05")
    if pos < 0:
        raise ValueError("counter pointer load not found")
    pos += 7
    offset = 0
    if code[pos : pos + 2] == b"\x48\x05":
        offset += u32(code, pos + 2)
        pos += 6
    elif code[pos : pos + 3] == b"\x48\x83\xc0":
        offset += s8(code[pos + 3])
        pos += 4
    elif code[pos : pos + 3] == b"\x48\x83\xe8":
        offset -= s8(code[pos + 3])
        pos += 4
    if code[pos : pos + 2] == b"\x8b\x00":
        pass
    elif code[pos : pos + 2] == b"\x8b\x80":
        offset += u32(code, pos + 2)
    elif code[pos : pos + 2] == b"\x8b\x40":
        offset += s8(code[pos + 2])
    else:
        raise ValueError("counter dword load not found")
    if offset % 4:
        raise ValueError("counter offset is not dword-aligned")
    return offset // 4


def matrix_stage_bytes(img: bytes, pe: PE) -> bytes:
    check_rva = pe.exports()["_Z5checkPh"]
    check_off = pe.rva_to_off(check_rva)
    stores = raw_movabs_stores(img[check_off : check_off + 0x6000])
    prime = stores.get(0x540)
    exponent = stores.get(0x538)
    init = {(off - 0x410) // 0x10: value for off, value in stores.items() if 0x410 <= off <= 0x508 and (off - 0x410) % 0x10 == 0}
    target = {(off - 0x10) // 0x10: value for off, value in stores.items() if 0x10 <= off <= 0x100 and (off - 0x10) % 0x10 == 0}
    if prime is None or exponent is None or len(init) != 16 or len(target) != 16:
        raise ValueError("failed to extract matrix constants")
    order = 1
    for i in range(4):
        order *= prime**4 - prime**i
    inv_exp = pow(exponent, -1, order)
    root = mpow4([target[i] for i in range(16)], inv_exp, prime)
    words: list[int] = []
    for col in range(4):
        value = root[col] ^ init[col]
        for row in range(4):
            idx = 4 * row + col
            if (root[idx] ^ init[idx]) != value:
                raise ValueError("matrix root does not match the repeated-column input pattern")
        words.append(value)
    return b"".join(word.to_bytes(8, "little") for word in words)


@dataclasses.dataclass(frozen=True)
class Helper:
    kind: str
    counter_index: int
    data: bytes | int


class ModuleAnalyzer:
    def __init__(self, res: ResourceView, decomp: DotnetAplibServer | None = None):
        self.res = res
        self.decomp = decomp
        self.images: dict[int, bytes] = {}
        self.pes: dict[int, PE] = {}
        self.helper_cache: dict[tuple[int, str], Helper] = {}
        self.helper_cache_by_rva: dict[tuple[int, int], Helper] = {}
        self.check_cache: dict[int, list[tuple[int, str]]] = {}
        self.stage_cache: dict[int, bytes] = {}
        self.export_cache: dict[int, dict[str, int]] = {}
        self.export_rvas_cache: dict[int, list[int]] = {}

    def image(self, module_id: int) -> bytes:
        img = self.images.get(module_id)
        if img is None:
            if self.decomp is None:
                img = module_image(self.res, module_id)
            else:
                img = self.decomp.image(module_id)
            self.images[module_id] = img
        return img

    def pe(self, module_id: int) -> PE:
        pe = self.pes.get(module_id)
        if pe is None:
            pe = PE(self.image(module_id))
            self.pes[module_id] = pe
        return pe

    def import_slots(self, module_id: int) -> dict[int, tuple[int, str]]:
        pe = self.pe(module_id)
        data = pe.data
        rva, _size = pe.data_dir(1)
        if not rva:
            return {}
        slots: dict[int, tuple[int, str]] = {}
        desc = pe.rva_to_off(rva)
        while True:
            oft, _tds, _fwd, name_rva, ft = struct.unpack_from("<IIIII", data, desc)
            if not any((oft, name_rva, ft)):
                break
            dll = pe.cstr_rva(name_rva)
            stem = dll.split(".", 1)[0]
            thunk_rva = oft or ft
            thunk_off = pe.rva_to_off(thunk_rva)
            idx = 0
            while True:
                val = u64(data, thunk_off + idx * 8)
                if not val:
                    break
                if len(stem) == 4 and stem.isdigit() and not (val & 0x8000000000000000):
                    slots[ft + idx * 8] = (int(stem), pe.cstr_rva(val + 2))
                idx += 1
            desc += 20
        return slots

    def check_calls(self, module_id: int) -> list[tuple[int, str]]:
        cached = self.check_cache.get(module_id)
        if cached is not None:
            return cached
        from capstone import Cs, CS_ARCH_X86, CS_MODE_64
        from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_OP_REG, X86_REG_RAX, X86_REG_RBP

        pe = self.pe(module_id)
        img = self.image(module_id)
        check_rva = pe.exports()["_Z5checkPh"]
        check_off = pe.rva_to_off(check_rva)
        slot_map = self.import_slots(module_id)
        md = Cs(CS_ARCH_X86, CS_MODE_64)
        md.detail = True
        calls: list[tuple[int, str]] = []
        last_rax_slot: int | None = None
        for ins in md.disasm(img[check_off : check_off + 0x6000], pe.image_base + check_rva):
            if (
                ins.mnemonic == "mov"
                and len(ins.operands) == 2
                and ins.operands[0].type == X86_OP_MEM
                and ins.operands[0].mem.base == X86_REG_RBP
                and ins.operands[0].mem.disp == 0x540
                and ins.operands[1].type == X86_OP_REG
                and ins.operands[1].reg == X86_REG_RAX
            ):
                break
            if (
                ins.mnemonic == "mov"
                and len(ins.operands) == 2
                and ins.operands[0].type == X86_OP_REG
                and ins.operands[0].reg == X86_REG_RAX
                and ins.operands[1].type == X86_OP_MEM
                and ins.operands[1].mem.base
            ):
                last_rax_slot = ins.address + ins.size + ins.operands[1].mem.disp - pe.image_base
                continue
            if ins.mnemonic != "call":
                continue
            op = ins.operands[0]
            if op.type == X86_OP_IMM:
                calls.append((module_id, f"@{op.imm - pe.image_base:x}"))
            elif op.type == X86_OP_REG and op.reg == X86_REG_RAX and last_rax_slot is not None:
                try:
                    calls.append(slot_map[last_rax_slot])
                except KeyError as exc:
                    raise ValueError(f"unresolved IAT slot {last_rax_slot:#x} in module {module_id}") from exc
            else:
                raise ValueError(f"unsupported call in module {module_id}: {ins.mnemonic} {ins.op_str}")
        if not calls:
            raise ValueError(f"no checker calls extracted for module {module_id}")
        self.check_cache[module_id] = calls
        return calls

    def helper(self, module_id: int, symbol: str) -> Helper:
        if symbol.startswith("@"):
            key_rva = (module_id, int(symbol[1:], 16))
            cached_rva = self.helper_cache_by_rva.get(key_rva)
            if cached_rva is not None:
                return cached_rva
            helper = self._parse_helper_rva(module_id, key_rva[1])
            self.helper_cache_by_rva[key_rva] = helper
            return helper
        key = (module_id, symbol)
        cached = self.helper_cache.get(key)
        if cached is not None:
            return cached
        rva = self.exports(module_id)[symbol]
        helper = self._parse_helper_rva(module_id, rva)
        self.helper_cache[key] = helper
        return helper

    def exports(self, module_id: int) -> dict[str, int]:
        cached = self.export_cache.get(module_id)
        if cached is None:
            cached = self.pe(module_id).exports()
            self.export_cache[module_id] = cached
            self.export_rvas_cache[module_id] = sorted(cached.values())
        return cached

    def stage(self, module_id: int) -> bytes:
        cached = self.stage_cache.get(module_id)
        if cached is not None:
            return cached
        value = matrix_stage_bytes(self.image(module_id), self.pe(module_id))
        self.stage_cache[module_id] = value
        return value

    def function_bytes(self, module_id: int, rva: int, fallback_max: int = 0x1000) -> bytes:
        pe = self.pe(module_id)
        img = self.image(module_id)
        rvas = self.export_rvas_cache.get(module_id)
        if rvas is None:
            self.exports(module_id)
            rvas = self.export_rvas_cache[module_id]
        idx = bisect.bisect_right(rvas, rva)
        max_len = rvas[idx] - rva if idx < len(rvas) else fallback_max
        max_len = max(1, min(max_len, fallback_max))
        off = pe.rva_to_off(rva)
        return img[off : off + max_len]

    def _parse_helper_rva(self, module_id: int, rva: int) -> Helper:
        code = self.function_bytes(module_id, rva)
        counter_index = raw_counter_index(code)
        values = raw_movabs_values(code)
        if len(values) >= 32:
            for start in range(len(values) - 31):
                table = bytearray()
                for value in values[start : start + 32]:
                    table.extend(value.to_bytes(8, "little"))
                if sorted(table) == list(range(256)):
                    inv = bytearray(256)
                    for i, value in enumerate(table):
                        inv[value] = i
                    return Helper("sbox", counter_index, bytes(inv))

        if len(values) >= 4 and b"\x48\x89\x45\xd0" in code[:128]:
            for start in range(len(values) - 3):
                table = bytearray()
                for value in values[start : start + 4]:
                    table.extend(value.to_bytes(8, "little"))
                if sorted(table) == list(range(32)):
                    inv = bytearray(32)
                    for out_idx, in_idx in enumerate(table):
                        inv[in_idx] = out_idx
                    return Helper("perm", counter_index, bytes(inv))

        if len(values) >= 4 and b"\x48\x89\x45\xa0" in code[:128]:
            mem: dict[int, int] = {}
            stores = raw_movabs_stores(code)
            exp_values = [stores.get(off2) for off2 in (-0x60, -0x58, -0x51, -0x49)]
            if any(value is None for value in exp_values):
                exp_values = values[:4]
            for off2, imm in zip((-0x60, -0x58, -0x51, -0x49), exp_values):
                assert imm is not None
                for idx, b in enumerate(imm.to_bytes(8, "little")):
                    mem[off2 + idx] = b
            exp_bytes = bytes(mem[-0x60 + i] for i in range(31))
            exp = int.from_bytes(exp_bytes, "little")
            if exp % 2 == 0:
                raise ValueError(f"power exponent is not odd in module {module_id}:{rva:#x}")
            return Helper("pow", counter_index, pow(exp, -1, ODD_GROUP_EXP))

        raise ValueError(f"unknown helper shape in module {module_id}:{rva:#x}")


def xor_counter(data: bytearray, counter: int) -> None:
    value = int.from_bytes(data[:4], "little") ^ (counter & 0xFFFFFFFF)
    data[:4] = value.to_bytes(4, "little")


def invert_helper(data: bytearray, helper: Helper, counter: int) -> None:
    if helper.kind == "sbox":
        table = helper.data
        assert isinstance(table, bytes)
        data[:] = bytes(table[b] for b in data)
    elif helper.kind == "perm":
        inv = helper.data
        assert isinstance(inv, bytes)
        old = bytes(data)
        for in_idx, out_idx in enumerate(inv):
            data[in_idx] = old[out_idx]
    elif helper.kind == "pow":
        inv_exp = helper.data
        assert isinstance(inv_exp, int)
        old_lsb = data[0] & 1
        y = int.from_bytes(data, "little")
        odd_y = y if old_lsb else (y ^ 1)
        odd_x = pow(odd_y, inv_exp, MOD256)
        x = odd_x if old_lsb else (odd_x & ~1)
        data[:] = x.to_bytes(32, "little")
    else:
        raise ValueError(helper.kind)
    xor_counter(data, counter)


def apply_helper(data: bytearray, helper: Helper, counter: int) -> None:
    xor_counter(data, counter)
    if helper.kind == "sbox":
        inv = helper.data
        assert isinstance(inv, bytes)
        table = bytearray(256)
        for out, inp in enumerate(inv):
            table[inp] = out
        data[:] = bytes(table[b] for b in data)
    elif helper.kind == "perm":
        inv = helper.data
        assert isinstance(inv, bytes)
        old = bytes(data)
        for in_idx, out_idx in enumerate(inv):
            data[out_idx] = old[in_idx]
    elif helper.kind == "pow":
        # Forward verification is only used in diagnostics; the original exponent
        # is not kept after parsing, so skip it.
        raise ValueError("forward pow verification is unavailable")
    else:
        raise ValueError(helper.kind)


def solve_block(analyzer: ModuleAnalyzer, module_id: int, counters: list[int]) -> bytes:
    data = bytearray(analyzer.stage(module_id))
    for helper_module, symbol in reversed(analyzer.check_calls(module_id)):
        helper = analyzer.helper(helper_module, symbol)
        invert_helper(data, helper, counters[helper.counter_index])
    return bytes(data)


def cmd_probe(args: argparse.Namespace) -> None:
    res = ResourceView()
    try:
        entries = list(res.iter_rcdata())
        print(f"resources: {len(entries)}")
        print(f"first: {entries[:3]}")
        print(f"last: {entries[-3:]}")
        for resid in args.ids:
            blob = res.get_resource(resid)
            img = aplib_decompress(blob)
            pe = PE(img)
            print(
                f"id={resid} compressed={len(blob)} decompressed={len(img)} "
                f"sha256={hashlib.sha256(img).hexdigest()[:16]} "
                f"entry={pe.entry_rva:#x} sections={[s.name for s in pe.sections]}"
            )
            print("  exports", pe.exports())
            print("  imports", pe.imports()[:10])
            print("  header", img[:16].hex())
    finally:
        res.close()


def cmd_extract_deps(args: argparse.Namespace) -> None:
    extract_deps(args.workers)


def closure_sets(deps: list[list[int]]) -> list[set[int]]:
    n = len(deps)
    closures: list[set[int] | None] = [None] * n

    def dfs(i: int, visiting: set[int]) -> set[int]:
        cached = closures[i]
        if cached is not None:
            return cached
        if i in visiting:
            raise ValueError(f"dependency cycle involving {i}")
        visiting.add(i)
        cur = {i}
        for d in deps[i]:
            cur.update(dfs(d, visiting))
        visiting.remove(i)
        closures[i] = cur
        return cur

    return [dfs(i, set()) for i in range(n)]


def cmd_graph_stats(args: argparse.Namespace) -> None:
    deps = load_deps()
    target = load_target()
    print(f"target: min={min(target)} max={max(target)} sum={sum(target)}")
    print(
        "direct deps:",
        f"min={min(map(len, deps))}",
        f"max={max(map(len, deps))}",
        f"avg={sum(map(len, deps))/len(deps):.1f}",
    )
    t0 = time.time()
    closures = closure_sets(deps)
    print(f"closures built in {time.time()-t0:.1f}s")
    print(
        "closure sizes:",
        f"min={min(map(len, closures))}",
        f"max={max(map(len, closures))}",
        f"avg={sum(map(len, closures))/len(closures):.1f}",
    )
    rev_count = [0] * len(deps)
    for s in closures:
        for j in s:
            rev_count[j] += 1
    print(
        "reverse closure counts:",
        f"min={min(rev_count)}",
        f"max={max(rev_count)}",
        f"avg={sum(rev_count)/len(rev_count):.1f}",
    )


def cmd_solve(args: argparse.Namespace) -> None:
    pos, order, closures = solve_order()
    out_path = pathlib.Path(args.output)
    counters = [0] * 10000
    license_blocks: list[bytes] = []
    limit = args.limit or len(order)
    if not (0 < limit <= len(order)):
        raise ValueError(f"invalid limit: {args.limit}")
    res = ResourceView()
    decomp: DotnetAplibServer | None = None
    if not args.no_native_decomp and APLIB_SERVER_DLL.exists():
        decomp = DotnetAplibServer()
        print(f"using native decompressor: {APLIB_SERVER_DLL}", flush=True)
    analyzer = ModuleAnalyzer(res, decomp)
    t0 = time.time()
    last = t0
    try:
        for position, module_id in enumerate(order[:limit]):
            block = solve_block(analyzer, module_id, counters)
            license_blocks.append(struct.pack("<H", module_id) + block)
            bits = closures[module_id]
            while bits:
                lsb = bits & -bits
                counters[lsb.bit_length() - 1] += position
                bits ^= lsb
            if args.progress and (position + 1) % args.progress == 0:
                now = time.time()
                print(
                    f"generated {position + 1}/10000",
                    f"elapsed={now - t0:.1f}s",
                    f"interval={now - last:.1f}s",
                    f"images={len(analyzer.images)}",
                    f"helpers={len(analyzer.helper_cache) + len(analyzer.helper_cache_by_rva)}",
                    flush=True,
                )
                last = now
    finally:
        if decomp is not None:
            decomp.close()
        res.close()
    blob = b"".join(license_blocks)
    if limit != len(order):
        print(f"generated partial license prefix: {limit} records ({len(blob)} bytes) in {time.time() - t0:.1f}s")
        return
    if len(blob) != 340000:
        raise ValueError(f"license has wrong size: {len(blob)}")
    out_path.write_bytes(blob)
    print(f"wrote {out_path} ({len(blob)} bytes) sha256={hashlib.sha256(blob).hexdigest()}")
    if args.run:
        result = subprocess.run([str(EXE)], cwd=str(ROOT), text=True, capture_output=True, timeout=args.timeout)
        print("--- stdout ---")
        print(result.stdout, end="")
        print("--- stderr ---")
        print(result.stderr, end="")
        print(f"exit code: {result.returncode}")


def decrypt_final_message(license_path: pathlib.Path) -> tuple[bytes, bytes]:
    try:
        from Crypto.Cipher import AES
    except ModuleNotFoundError as exc:
        raise RuntimeError("install pycryptodome in the venv first: python -m pip install pycryptodome") from exc

    key = hashlib.sha256(license_path.read_bytes()).digest()
    with EXE.open("rb") as fp:
        mm = mmap.mmap(fp.fileno(), 0, access=mmap.ACCESS_READ)
        try:
            pe = PE(mm)
            ct_off = pe.rva_to_off(0xD5C40)
            iv_off = pe.rva_to_off(0xD93A0)
            ciphertext = bytes(mm[ct_off : ct_off + 80])
            iv = bytes(mm[iv_off : iv_off + 16])
        finally:
            mm.close()

    plaintext = AES.new(key, AES.MODE_CBC, iv).decrypt(ciphertext)
    pad = plaintext[-1]
    if not (1 <= pad <= 16 and plaintext[-pad:] == bytes([pad]) * pad):
        raise ValueError("decrypted plaintext has invalid PKCS#7 padding")
    return key, plaintext[:-pad]


def cmd_decrypt(args: argparse.Namespace) -> None:
    license_path = pathlib.Path(args.license)
    key, plaintext = decrypt_final_message(license_path)
    print(f"license_sha256={key.hex()}")
    print(plaintext.decode("utf-8", "replace"))


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    probe = sub.add_parser("probe")
    probe.add_argument("ids", nargs="*", type=int, default=[0, 1, 9999])
    probe.set_defaults(func=cmd_probe)
    extract = sub.add_parser("extract-deps")
    extract.add_argument("--workers", type=int, default=0)
    extract.set_defaults(func=cmd_extract_deps)
    stats = sub.add_parser("graph-stats")
    stats.set_defaults(func=cmd_graph_stats)
    solve = sub.add_parser("solve")
    solve.add_argument("--output", default=str(ROOT / "license.bin"))
    solve.add_argument("--progress", type=int, default=100)
    solve.add_argument("--limit", type=int, default=0)
    solve.add_argument("--no-native-decomp", action="store_true")
    solve.add_argument("--run", action="store_true")
    solve.add_argument("--timeout", type=int, default=120)
    solve.set_defaults(func=cmd_solve)
    decrypt = sub.add_parser("decrypt")
    decrypt.add_argument("--license", default=str(ROOT / "license.bin"))
    decrypt.set_defaults(func=cmd_decrypt)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
