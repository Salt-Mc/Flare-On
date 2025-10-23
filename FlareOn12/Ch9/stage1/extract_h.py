import argparse
import json
import pefile
from pathlib import Path
import sys

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pe_path", help="Path to challenge binary")
    ap.add_argument("--rva", default="0xCC000", help="RVA of Hardcoded_Expected_Result (hex)")
    ap.add_argument("--count", type=int, default=10000, help="Number of uint32 entries")
    ap.add_argument("--out", default="hardcoded_expected.json", help="Output JSON file for H array")
    args = ap.parse_args()

    pe_path = Path(args.pe_path)
    if not pe_path.is_file():
        print(f"[-] File not found: {pe_path}", file=sys.stderr)
        sys.exit(1)

    rva = int(args.rva, 16)
    count = args.count

    pe = pefile.PE(str(pe_path), fast_load=True)
    try:
        file_offset = pe.get_offset_from_rva(rva)
    except pefile.PEFormatError as e:
        print(f"[-] Could not translate RVA {hex(rva)}: {e}", file=sys.stderr)
        sys.exit(1)

    size_needed = count * 4
    data = pe.__data__[file_offset:file_offset + size_needed]
    if len(data) != size_needed:
        print(f"[-] Not enough bytes at RVA {hex(rva)} (needed {size_needed}, got {len(data)})", file=sys.stderr)
        sys.exit(1)

    import struct
    H = list(struct.unpack("<" + "I"*count, data))

    with open(args.out, "w") as f:
        json.dump(H, f)

    # Quick diagnostics
    unique = len(set(H))
    minv, maxv = min(H), max(H)
    print(f"[+] Extracted {count} uint32 entries to {args.out}")
    print(f"[+] Distinct values: {unique}  Range: [{minv}, {maxv}]")
    if unique == count and set(H) == set(range(count)):
        print("[+] H is a full permutation of 0..9999 (trivial identity case).")
    else:
        print("[*] H is NOT a simple permutation; dependencies overlap (needs system solve).")

if __name__ == "__main__":
    main()