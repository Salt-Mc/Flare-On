#!/usr/bin/env python3
"""
Optimised transformations module:
- Exponentiation-based transform (forward/inverse)
- S-box substitution transform (forward/inverse)
- Permutation-based transform (forward/inverse)
Includes reusable helpers for parsing constants, XOR operations, and inverse mapping.
"""
import os
from typing import Any, List, Dict, Sequence
from sympy import Matrix, symbols, factor_list
from functools import reduce, lru_cache
from math import gcd
from operator import xor
from pathlib import Path
import json
import time, random

# Optional gmpy2 acceleration
try:
    import gmpy2
    GMPY2_OK = True
except ImportError:
    GMPY2_OK = False

# Optional FLINT acceleration (python-flint)
try:
    import flint
    from flint import nmod_mat  # matrix over Z/pZ
    FLINT_OK = True
except ImportError:
    FLINT_OK = False

# -----------------------------
# Generic Helpers
# -----------------------------

def parse_hex_chunks(hex_list: Sequence[str], chunk_size: int, total_bytes: int) -> bytes:
    """
    Convert a list of hex strings into little-endian chunks and return total_bytes.
    """
    buf = bytearray()
    for hx in hex_list:
        val = int(hx, 0) & 0xFFFFFFFFFFFFFFFF
        buf.extend(val.to_bytes(chunk_size, 'little'))
    if len(buf) < total_bytes:
        raise ValueError(f"Not enough data: got {len(buf)} bytes, need {total_bytes}")
    return bytes(buf[:total_bytes])


def xor_first_dword(data: bytearray, key32: int):
    """
    XOR the first 4 bytes of data with key32 (32-bit).
    """
    key32 &= 0xFFFFFFFF
    d0 = int.from_bytes(data[0:4], 'little') ^ key32
    data[0:4] = d0.to_bytes(4, 'little')


def build_inverse_mapping(seq: Sequence[int], size: int, strict=True) -> List[int]:
    """
    Build inverse mapping for a sequence of indices or table values.
    """
    inv = [-1] * size
    for pos, val in enumerate(seq):
        if val >= size:
            raise ValueError(f"Value {val} out of range")
        if inv[val] != -1 and strict:
            raise ValueError(f"Duplicate mapping for {val}")
        if inv[val] == -1:
            inv[val] = pos
    for i in range(size):
        if inv[i] == -1:
            inv[i] = 0
    return inv

# -----------------------------
# Exponentiation Transform
# -----------------------------

# ---------- Memoized parsers ----------
@lru_cache(maxsize=512)
def parse_exponent_constants_tuple(raw_constants_tuple):
    # raw_constants_tuple: tuple of (index, value_str)
    exp_bytes = bytearray(31)
    for idx, value_str in raw_constants_tuple:
        val = int(value_str, 0) & 0xFFFFFFFFFFFFFFFF
        chunk = val.to_bytes(8, 'little')
        end = min(idx + 8, 31)
        exp_bytes[idx:end] = chunk[:end - idx]
    return bytes(exp_bytes)

def parse_exponent_constants(raw_constants: List[Dict]) -> bytes:
    key = tuple((int(item['index']), item['value']) for item in raw_constants)
    return parse_exponent_constants_tuple(key)

def forward_exponent(x_bytes: bytes, exp_bytes: bytes, check_byte: int) -> bytes:
    """
    Forward exponentiation transform.
    """
    E = int.from_bytes(exp_bytes, 'little')
    X = int.from_bytes(x_bytes, 'little')

    X ^= check_byte
    v7 = X & 1
    X |= 1

    Y = pow(X, E, 1 << 256)
    Y ^= (v7 ^ 1)

    return Y.to_bytes(32, 'little')


def inverse_exponent(y_bytes: bytes, exp_bytes: bytes, check_byte: int) -> bytes:
    """
    Inverse exponentiation transform.
    """
    E = int.from_bytes(exp_bytes, 'little')
    D = pow(E, -1, 1 << 254)

    Y = int.from_bytes(y_bytes, 'little')
    Z = Y | 1
    S = pow(Z, D, 1 << 256)

    v7 = Y & 1
    S = (S & ~1) | v7
    S ^= check_byte

    return S.to_bytes(32, 'little')

# -----------------------------
# S-box Transform
# -----------------------------

def parse_sbox_constants(v2_constants: Sequence[str]) -> bytes:
    """
    Parse S-box constants into 256-byte table.
    """
    return parse_hex_chunks(v2_constants, 8, 256)


def forward_sbox(x_bytes: bytes, key32: int, table_bytes: bytes) -> bytes:
    """
    Forward S-box substitution transform.
    """
    y = bytearray(x_bytes)
    xor_first_dword(y, key32)
    for i in range(32):
        y[i] = table_bytes[y[i]]
    return bytes(y)


def inverse_sbox(y_bytes: bytes, key32: int, table_bytes: bytes) -> bytes:
    """
    Inverse S-box substitution transform.
    """
    inv = build_inverse_mapping(table_bytes, 256)
    p = bytearray(32)
    for i in range(32):
        p[i] = inv[y_bytes[i]]
    xor_first_dword(p, key32)
    return bytes(p)

# -----------------------------
# Permutation Transform
# -----------------------------

# ---------- Memoized parsers ----------
@lru_cache(maxsize=256)
def parse_permutation_constants_tuple(v3_constants_tuple):
    return parse_hex_chunks(v3_constants_tuple, 8, 32)

def parse_permutation_constants(v3_constants: Sequence[str]) -> bytes:
    return parse_permutation_constants_tuple(tuple(v3_constants))


def forward_permutation(x_bytes: bytes, key32: int, idx_bytes: bytes) -> bytes:
    """
    Forward permutation transform.
    """
    y = bytearray(x_bytes)
    xor_first_dword(y, key32)
    out = bytearray(32)
    for i in range(32):
        out[i] = y[idx_bytes[i]]
    return bytes(out)


def inverse_permutation(y_bytes: bytes, key32: int, idx_bytes: bytes) -> bytes:
    """
    Inverse permutation transform.
    """
    inv = build_inverse_mapping(idx_bytes, 32)
    p = bytearray(32)
    for j in range(32):
        p[j] = y_bytes[inv[j]]
    xor_first_dword(p, key32)
    return bytes(p)

# -----------------------------
# Matrix Helpers for Exponentiation Inversion
# -----------------------------

def lcm_reduce(values):
    """lcm over an iterable of positive integers."""
    def _lcm(a, b):
        return a // gcd(a, b) * b
    return reduce(_lcm, values)

def build_matrix_mod_p(flat: List[int], p: int) -> List[List[int]]:
    """4x4 matrix mod p from row-major flat list of 16 ints."""
    if len(flat) != 16:
        raise ValueError("T_flat must have 16 integers (row-major 4x4).")
    return [[flat[i*4 + j] % p for j in range(4)] for i in range(4)]

# ---------- Unrolled matrix multiply ----------
def mat_mul_mod_p(A: List[List[int]], B: List[List[int]], p: int) -> List[List[int]]:
    # Small 4x4 unrolled multiply with single modulo per cell
    a00,a01,a02,a03 = A[0]; a10,a11,a12,a13 = A[1]; a20,a21,a22,a23 = A[2]; a30,a31,a32,a33 = A[3]
    b00,b01,b02,b03 = B[0]; b10,b11,b12,b13 = B[1]; b20,b21,b22,b23 = B[2]; b30,b31,b32,b33 = B[3]
    r0c0 = (a00*b00 + a01*b10 + a02*b20 + a03*b30) % p
    r0c1 = (a00*b01 + a01*b11 + a02*b21 + a03*b31) % p
    r0c2 = (a00*b02 + a01*b12 + a02*b22 + a03*b32) % p
    r0c3 = (a00*b03 + a01*b13 + a02*b23 + a03*b33) % p
    r1c0 = (a10*b00 + a11*b10 + a12*b20 + a13*b30) % p
    r1c1 = (a10*b01 + a11*b11 + a12*b21 + a13*b31) % p
    r1c2 = (a10*b02 + a11*b12 + a12*b22 + a13*b32) % p
    r1c3 = (a10*b03 + a11*b13 + a12*b23 + a13*b33) % p
    r2c0 = (a20*b00 + a21*b10 + a22*b20 + a23*b30) % p
    r2c1 = (a20*b01 + a21*b11 + a22*b21 + a23*b31) % p
    r2c2 = (a20*b02 + a21*b12 + a22*b22 + a23*b32) % p
    r2c3 = (a20*b03 + a21*b13 + a22*b23 + a23*b33) % p
    r3c0 = (a30*b00 + a31*b10 + a32*b20 + a33*b30) % p
    r3c1 = (a30*b01 + a31*b11 + a32*b21 + a33*b31) % p
    r3c2 = (a30*b02 + a31*b12 + a32*b22 + a33*b32) % p
    r3c3 = (a30*b03 + a31*b13 + a32*b23 + a33*b33) % p
    return [
        [r0c0,r0c1,r0c2,r0c3],
        [r1c0,r1c1,r1c2,r1c3],
        [r2c0,r2c1,r2c2,r2c3],
        [r3c0,r3c1,r3c2,r3c3],
    ]

# Optional GMP acceleration for multiply (toggle via env)
USE_GMP_MUL = os.environ.get("USE_GMP_MUL") == "1" and GMPY2_OK
if USE_GMP_MUL:
    def mat_mul_mod_p(A: List[List[int]], B: List[List[int]], p: int) -> List[List[int]]:
        mp = gmpy2.mpz(p)
        out = [[0]*4 for _ in range(4)]
        for i in range(4):
            for j in range(4):
                s = gmpy2.mpz(0)
                for k in range(4):
                    s += gmpy2.mpz(A[i][k]) * gmpy2.mpz(B[k][j])
                out[i][j] = int(s % mp)
        return out

def mat_pow_mod_p(A: List[List[int]], exp: int, p: int) -> List[List[int]]:
    R = [[1 if i == j else 0 for j in range(4)] for i in range(4)]
    B = [row[:] for row in A]
    e = exp
    while e > 0:
        if e & 1:
            R = mat_mul_mod_p(R, B, p)
        B = mat_mul_mod_p(B, B, p)
        e >>= 1
    return R

def matrix_equal(A: List[List[int]], B: List[List[int]]) -> bool:
    return all(A[i][j] == B[i][j] for i in range(4) for j in range(4))

def recover_W_words(A_flat: List[int], R_const: List[int], p: int) -> List[int]:
    """
    Recover 4 u64 words W0..W3 by intersecting XOR candidates per column.
    For each column k (k=0..3), for the 4 positions with index % 4 == k:
      mval = A_flat[idx], C = R_const[idx],
      candidates are { mval ^ C, (mval + p) ^ C }.
    Intersection across the 4 rows must be a single value.
    """
    if len(A_flat) != 16 or len(R_const) != 16:
        raise ValueError("A_flat and R_const must be 16-long lists.")
    W = [None] * 4
    for k in range(4):
        idxs = [i for i in range(16) if i % 4 == k]
        candidates = None
        for idx in idxs:
            mval = int(A_flat[idx])
            C = int(R_const[idx])
            raw0 = xor(mval, C)
            raw1 = xor(mval + p, C)  # lifted once
            local = {raw0, raw1}
            candidates = local if candidates is None else (candidates & local)
        if not candidates:
            raise ValueError(f"No candidate survived for W[{k}]")
        if len(candidates) != 1:
            raise ValueError(f"Ambiguity for W[{k}]: {candidates}")
        W[k] = next(iter(candidates))
    return W  # 4 integers (intended as 64-bit words)

def split_u64_le(x: int):
    """Return (low32, high32) from a 64-bit word (little-endian)."""
    return x & 0xFFFFFFFF, (x >> 32) & 0xFFFFFFFF

def dwords_to_bytes_le(dw: List[int]) -> List[int]:
    """Convert list of u32 words into little-endian bytes."""
    out = []
    for w in dw:
        for b in range(4):
            out.append((w >> (8 * b)) & 0xFF)
    return out

# -----------------------------
# Charpoly factoring over GF(p)
# -----------------------------

def charpoly_factor_degrees_mod_p_flint(T_flat: List[int], p: int) -> List[int]:
    """
    Use FLINT (nmod_mat) for characteristic polynomial factoring modulo p.
    Returns list of factor degrees with multiplicity.
    """
    if not FLINT_OK:
        raise RuntimeError("FLINT not available")
    # Build 4x4 matrix modulo p
    rows = []
    for i in range(4):
        row = [int(T_flat[i*4 + j] % p) for j in range(4)]
        rows.append(row)
    mat = nmod_mat(rows, p)
    poly = mat.charpoly()          # nmod_poly
    # Factor into irreducibles over GF(p)
    # poly.factor() returns list of (factor, multiplicity)
    try:
        facs = poly.factor()
    except Exception as ex:
        raise RuntimeError(f"FLINT factor failed: {ex}") from ex
    degs: List[int] = []
    for factor, mult in facs:
        deg = int(factor.degree())
        for _ in range(int(mult)):
            degs.append(deg)
    return degs

def charpoly_factor_degrees_mod_p_sympy(T_flat: List[int], p: int) -> List[int]:
    x = symbols('x')
    T_sym = Matrix([[int(T_flat[i*4 + j] % p) for j in range(4)] for i in range(4)])
    char_poly_expr = T_sym.charpoly(x).as_expr()
    coeff, factors = factor_list(char_poly_expr, modulus=p)
    degs = [f.as_poly(x, modulus=p).degree() for (f, _mult) in factors]
    return degs

def charpoly_factor_degrees_mod_p(T_flat: List[int], p: int) -> List[int]:
    """
    Dispatch order:
      1) FLINT (if FLINT_CHARPOLY=1 and available)
      2) SymPy fallback
    """
    if os.environ.get("FLINT_CHARPOLY") == "1" and FLINT_OK:
        try:
            return charpoly_factor_degrees_mod_p_flint(T_flat, p)
        except Exception:
            # Fall through to SymPy
            pass
    else:
        raise NotImplementedError("FLINT_CHARPOLY not enabled or FLINT not available")
    return charpoly_factor_degrees_mod_p_sympy(T_flat, p)

# -----------------------------
# Main inversion routine (dynamic p, e, T_flat, R_const)
# -----------------------------

def invert_matrix_root(p: int, e: int, T_flat: List[int], R_const: List[int]) -> Dict[str, Any]:
    """
    Invert the matrix-power transform:
      - Compute L = lcm(p^deg_i - 1) from irreducible factor degrees of charpoly over GF(p)
      - Compute d_global = e^{-1} mod L
      - A = T^d_global mod p
      - Verify A^e == T
      - Recover W words via XOR intersections and produce 32 bytes (little-endian)
    Returns dict with 'A_root', 'W_words', 'a1_bytes'.
    """
    # 1) Build T mod p
    T = build_matrix_mod_p(T_flat, p)

    # 2) Factor characteristic polynomial over GF(p) to get degrees
    _load_charpoly_cache()
    sig = _matrix_sig(p, T_flat)

    cached_entry = _charpoly_cache.get(sig)
    if cached_entry:
        unique_degs = cached_entry["unique_degs"]
        L = cached_entry["L"]
        d_global = cached_entry["d_global"]
    else:
        # Factor
        deg_list = charpoly_factor_degrees_mod_p(T_flat, p)
        if not deg_list:
            raise RuntimeError("Failed to factor characteristic polynomial over GF(p).")
        unique_degs = sorted(set(deg_list))
        orders = [pow(p, d) - 1 for d in unique_degs]
        L = lcm_reduce(orders)
        g = gcd(e, L)
        if g != 1:
            raise ValueError(f"Exponent e is not invertible modulo L (gcd={g}). e={e}, L={L}")
        d_global = pow(e, -1, L)
        _charpoly_cache[sig] = {
            "unique_degs": unique_degs,
            "L": L,
            "d_global": d_global
        }
        _save_charpoly_cache()

    # 3) Compute L = lcm(p^d - 1) over unique degrees
    # unique_degs = sorted(set(deg_list))
    # orders = [pow(p, d) - 1 for d in unique_degs]
    # L = lcm_reduce(orders)

    # 4) Compute d_global (modular inverse)
    # g = gcd(e, L)
    # if g != 1:
    #     raise ValueError(f"Exponent e is not invertible modulo L (gcd={g}). "
    #                      f"e={e}, L={L}")
    # d_global = pow(e, -1, L)

    # 5) Compute A = T^d_global and verify
    A = mat_pow_mod_p(T, d_global, p)
    if not matrix_equal(mat_pow_mod_p(A, e, p), T):
        # Rare fallback: recompute with original path (defensive)
        deg_list_fallback = charpoly_factor_degrees_mod_p(T_flat, p)
        orders_fb = [pow(p, d) - 1 for d in sorted(set(deg_list_fallback))]
        L_fb = lcm_reduce(orders_fb)
        d_global_fb = pow(e, -1, L_fb)
        A = mat_pow_mod_p(T, d_global_fb, p)
        if not matrix_equal(mat_pow_mod_p(A, e, p), T):
            raise RuntimeError("Verification failed even after fallback")

    # 6) Recover W words
    A_flat = [A[i][j] for i in range(4) for j in range(4)]
    W_words = recover_W_words(A_flat, R_const, p)

    # 7) Convert to bytes (little-endian)
    a1_dwords = []
    for w in W_words:
        lo, hi = split_u64_le(w)
        a1_dwords.extend([lo, hi])
    a1_bytes = dwords_to_bytes_le(a1_dwords)

    return {
        "A_root": A,
        "W_words": W_words,
        "a1_bytes": a1_bytes,
        "deg_list": unique_degs,
        "L": L,
        "d_global": d_global,
    }

# ---------- Order caching ----------
_order_cache: Dict[str, int] = {}

def maybe_refine_order(sig: str, A: List[List[int]], e: int, T: List[List[int]], p: int, L: int) -> int:
    # Attempt to find smaller order; very cheap heuristic
    if sig in _order_cache:
        return _order_cache[sig]
    # Try dividing L by small factors first
    test = L
    # Factor L coarsely (trial division small primes)
    primes = [2,3,5,7,11,13,17,19,23,29]
    for pr in primes:
        while test % pr == 0:
            candidate = test // pr
            # Check if T^candidate == I? Actually we want order of T; test matrix powering of T^candidate
            I = mat_pow_mod_p(T, candidate, p)
            if all(I[i][j] == (1 if i==j else 0) for i in range(4) for j in range(4)):
                test = candidate
            else:
                break
    _order_cache[sig] = test
    return test

# -----------------------------
# Characteristic polynomial caching
# -----------------------------

CHARPOLY_CACHE_FILE = Path(__file__).parent / "charpoly_inversion_cache.json"
_charpoly_cache: Dict[str, Dict[str, int]] = {}
_parent_pid = os.getpid()
_charpoly_batch_mode = False       # NEW
_charpoly_dirty = False            # NEW
_charpoly_save_errors: List[str] = []  # NEW

def enable_charpoly_batch_mode():
    global _charpoly_batch_mode
    _charpoly_batch_mode = True

def flush_charpoly_cache():
    global _charpoly_dirty
    if _charpoly_dirty:
        _save_charpoly_cache(force=True)
        _charpoly_dirty = False
    if _charpoly_save_errors:
        print(f"[charpoly-cache] {len(_charpoly_save_errors)} save error(s) during batch (showing up to 5):")
        for msg in _charpoly_save_errors[:5]:
            print("  -", msg)
        if len(_charpoly_save_errors) > 5:
            print("  ...")

def ensure_charpoly_cache_loaded():
    _load_charpoly_cache()

def _load_charpoly_cache():
    global _charpoly_cache
    if _charpoly_cache:
        return
    if CHARPOLY_CACHE_FILE.exists():
        try:
            _charpoly_cache = json.loads(CHARPOLY_CACHE_FILE.read_text())
        except Exception:
            _charpoly_cache = {}

def _save_charpoly_cache(force: bool = False):
    """
    Robust save:
      - Skip if not parent or cache disabled
      - Defer if batch mode and not force
      - Retry with backoff & unique temp names to dodge transient locks.
    """
    global _charpoly_dirty
    if not _charpoly_cache:
        return
    if os.environ.get("CHARPOLY_CACHE_DISABLE") == "1":
        return
    if os.environ.get("CACHE_WRITE_ROLE") != "parent":
        return
    if os.getpid() != _parent_pid:
        return
    if _charpoly_batch_mode and not force:
        _charpoly_dirty = True
        return

    data = json.dumps(_charpoly_cache, indent=2, sort_keys=True)
    attempts = 5
    for attempt in range(1, attempts + 1):
        # unique temp; avoid reuse collisions
        tmp = CHARPOLY_CACHE_FILE.with_suffix(
            f".tmp.{_parent_pid}.{time.time_ns()}.{random.randint(0,9999)}"
        )
        try:
            tmp.write_text(data)
            os.replace(tmp, CHARPOLY_CACHE_FILE)
            _charpoly_dirty = False
            return
        except Exception as ex:
            _charpoly_save_errors.append(f"attempt={attempt} error={ex}")
            # Best effort cleanup
            try:
                if tmp.exists():
                    tmp.unlink(missing_ok=True)
            except Exception:
                pass
            if attempt < attempts:
                time.sleep(0.05 * attempt)  # incremental backoff
            else:
                return

def _matrix_sig(p: int, T_flat: List[int]) -> str:
    import hashlib
    h = hashlib.sha256()
    h.update(p.to_bytes(8, "little"))
    for x in T_flat:
        h.update(int(x).to_bytes(8, "little", signed=False))
    return h.hexdigest()[:32]

# -----------------------------
# Example Usage
# -----------------------------

if __name__ == "__main__":
    dll_no = 5582
    original = bytes.fromhex('3e892b5d6d872c32f5b12a009eb2317372f470eaaea386b6ba91f0f430ddea1f')
    check_byte = 55
    print(hex(check_byte))
    # Exponentiation example
    raw_constants = [
    {
      "index": 0,
      "value": "0xdcf85964d8e3d025"
    },
    {
      "index": 8,
      "value": "0xd5de8ae8329f7be"
    },
    {
      "index": 15,
      "value": "0xd8fb334308835d0d"
    },
    {
      "index": 23,
      "value": "0x482e79ec5c62666e"
    }
    ]
    a1_prime = original
    exp_bytes = parse_exponent_constants(raw_constants)

    enc = forward_exponent(original, exp_bytes, check_byte)
    dec = inverse_exponent(enc, exp_bytes, check_byte)
    print(f"Exponentiation: {enc.hex()}")
    print("Exponentiation Round-trip OK:", dec == original)

    # S-box example
    v2_constants = [
    "0x3b262b4ce0ae160b",
    "0xac509ddeb637b4fb",
    "0x8f642ff03003a640",
    "0x567de277c5edc0d9",
    "0x6ad11ffdc4453c6e",
    "0x7c2478b28e008df9",
    "0x246205f79d4fe85",
    "0x68e8f19adb361517",
    "0x974dbd8c4f6fa787",
    "0x3fa070a4dfef5110",
    "0xa1ee407767e0d12",
    "0x13aa97ab96386b5",
    "0xd8e7cf5dd7041a49",
    "0xb7e56938caf4255e",
    "0x11297492fab859f8",
    "0x3e557261a24e88ff",
    "0x8b286beccef3c981",
    "0xc1af423357c6beee",
    "0xaa4a84f7ba3914b1",
    "0xe6435c2ea89f6608",
    "0x6c65b0f644e371bf",
    "0xd62a73fc18c21353",
    "0x54dccb270e21a367",
    "0xc35ba1322d0c9e8a",
    "0x313505ab9b91d01b",
    "0x6d75b393eb1cea9c",
    "0x47583dbc1dd3e9d2",
    "0x228998a506098323",
    "0x520ff2f560c8ccda",
    "0x627b9499bb96cd19",
    "0x827fadc74b34dd2c",
    "0xe1804841d590955a"
  ]
    table_bytes = parse_sbox_constants(v2_constants)
    sbox_enc = forward_sbox(enc, check_byte, table_bytes)
    sbox_dec = inverse_sbox(sbox_enc, check_byte, table_bytes)
    print(f"S-box: {sbox_enc.hex()}")
    print("S-box Round-trip OK:", sbox_dec == enc)

    # Permutation example
    v3_constants = ["0x0F14051900160A04", "0x0C171B0E11181C0D", "0x03061D151F13080B", "0x1E1202090710011A"]
    
    original = bytes.fromhex("C47881B193AB4EF23045CEB199CA4BB5CE1FA70FD68AFCBBF21EF4FFCD00D709")

    idx_bytes = parse_permutation_constants(v3_constants)
    perm_enc = forward_permutation(original, check_byte, idx_bytes)
    perm_dec = inverse_permutation(perm_enc, check_byte, idx_bytes)
    print(f"Permutation: {perm_enc.hex()}")
    print("Permutation Round-trip OK:", perm_dec == original)

    # Example inputs (replace with your parsed values)
    # p = 0xD83146B153175933
    # e = 0x559D6E12E849596B
    # T_flat = [
    #     0x1F2CCE278F7F0F03, 0x888A753879E68DAE, 0x5D9239E3618BFF63, 0xC435210FB4402532,
    #     0x2525FDEF8C7D331F, 0x91946D8C60DFB121, 0x2BBD94327DE98D3C, 0x92687B6921C294D9,
    #     0x9B6D2CD527805891, 0xC8B953E0B3259F8A, 0x9940614C1A71E163, 0x3B7509EA3F34B738,
    #     0x8D12A5121B46FC6F, 0x826512EE04D2A7A4, 0x27E7AF737205BC87, 0x33371FE0DE4D083E
    # ]
    # R_const = [
    #     0xF98EFEF9B4D91F6E, 0x9B6A4C80B5B1F2E8, 0x2DF308609A576A8D, 0x2602DC84E56FC8D7,
    #     0x2D73F4FBB5FD9583, 0xBDF9A047BEFDCC6B, 0x59A762C00AEE2BC2, 0x1B3D7791163B4CA4,
    #     0x1C1C29536EE6D72C, 0x7D0887FE75684BCF, 0x34DEDFB47C2283A0, 0x4262F2F39E547F89,
    #     0x2EAC87236B3E6041, 0x4299E4F3195E3695, 0xE77D5389E61F24AC, 0x4D458A85909EA355
    # ]

    p=15578310313468451123
    e=6169208092053035371
    T_flat=[
        2246396983457550083, 9838805221368040878, 6742515240883978083, 14138242956531868978,
        2676824758837654303, 10490129881740849441, 3151838258810948924, 10549817818583569625,
        11199657142342670481, 14463683902820425610, 11042933265801535843, 4284341522200311608,
        10165368806114262127, 9395937011070838692, 2875459797468429447, 3690453470316136510]
    R_const=[
        17982590710571409262, 11198847539098022632, 3310999362046749325, 2738993986737785047,
        3275230715955746179, 13689148772376759403, 6460240767442889666, 1962856477630352548,
        2025539370729527084, 9009600581515889615, 3809728301071762336, 4783652882368200585,
        3363211607931772993, 4799118610693764757, 16680580446586610860, 5568008820575085397]

    result = invert_matrix_root(p, e, T_flat, R_const)
    recovered_original = bytes(result["a1_bytes"])
    print(recovered_original.hex())
    assert recovered_original == a1_prime, "Final inversion did not recover original bytes"
    print("Matrix inversion successful.")