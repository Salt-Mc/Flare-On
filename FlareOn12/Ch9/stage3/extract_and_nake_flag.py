import argparse
import struct
from pathlib import Path
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

def parse_sections(f, pe_offset):
    f.seek(pe_offset)
    sig = f.read(4)
    if sig != b"PE\0\0":
        raise ValueError("Not a PE signature")
    coff = f.read(20)
    (num_sections,) = struct.unpack_from("<H", coff, 2)
    opt_magic = struct.unpack("<H", f.read(2))[0]
    # Skip rest of optional header based on magic (PE32 vs PE32+)
    if opt_magic == 0x10B:
        # PE32 size: standard 96 + data dirs (16*8) = 224 total
        f.seek(-2, 1)
        optional = f.read(224)
    elif opt_magic == 0x20B:
        f.seek(-2, 1)
        optional = f.read(240)
    else:
        raise ValueError(f"Unknown optional header magic {hex(opt_magic)}")
    sections = []
    for _ in range(num_sections):
        ent = f.read(40)
        name = ent[:8].rstrip(b"\0").decode(errors="ignore")
        vsize, vaddr, size_raw, ptr_raw = struct.unpack_from("<IIII", ent, 8)
        sections.append({
            "name": name,
            "vaddr": vaddr,
            "vsize": vsize,
            "size_raw": size_raw,
            "ptr_raw": ptr_raw
        })
    return sections

def rva_to_file_offset(rva, sections):
    for s in sections:
        start = s["vaddr"]
        end = start + max(s["vsize"], s["size_raw"])
        if start <= rva < end:
            delta = rva - start
            return s["ptr_raw"] + delta
    raise ValueError(f"RVA {hex(rva)} not in any section")

def read_bytes_at(f, offset, length):
    f.seek(offset)
    data = f.read(length)
    if len(data) != length:
        raise ValueError(f"Expected {length} bytes at {hex(offset)}, got {len(data)}")
    return data

def main():
    ap = argparse.ArgumentParser(description="Extract & decrypt flag from PE file.")
    ap.add_argument("pefile", help="Path to PE file")
    ap.add_argument("--key-hex", required=True,
                    help="AES key in hex (16/24/32 bytes)")
    ap.add_argument("--iv-offset", default="0xd93a0", required=False,
                    help="File offset or RVA (hex or int) of 16-byte IV")
    ap.add_argument("--cipher-offset", default="0xd5c40", required=False,
                    help="File offset or RVA (hex or int) of 80-byte ciphertext")
    ap.add_argument("--cipher-len", type=int, default=80,
                    help="Length of encrypted data (default 80)")
    ap.add_argument("--rva", action="store_true",
                    help="Treat offsets as RVAs instead of file offsets")
    ap.add_argument("--mode", choices=["cbc", "ctr"], default="cbc",
                    help="AES mode (cbc uses PKCS#7 unpad; ctr no unpad)")
    args = ap.parse_args()

    pe_path = Path(args.pefile)
    if not pe_path.exists():
        raise FileNotFoundError(pe_path)

    def parse_int(x):
        x = x.lower()
        return int(x, 16) if x.startswith("0x") else int(x)

    iv_off_in = parse_int(args.iv_offset)
    ct_off_in = parse_int(args.cipher_offset)

    key = bytes.fromhex(args.key_hex)
    if len(key) not in (16, 24, 32):
        raise ValueError("Key length must be 16/24/32 bytes")

    with pe_path.open("rb") as f:
        # If RVA mode, build section map and convert
        if args.rva:
            f.seek(0x3C)
            e_lfanew = struct.unpack("<I", f.read(4))[0]
            sections = parse_sections(f, e_lfanew)
            iv_off = rva_to_file_offset(iv_off_in, sections)
            ct_off = rva_to_file_offset(ct_off_in, sections)
        else:
            iv_off = iv_off_in
            ct_off = ct_off_in

        iv = read_bytes_at(f, iv_off, 16)
        ciphertext = read_bytes_at(f, ct_off, args.cipher_len)

    if args.mode == "cbc":
        cipher = AES.new(key, AES.MODE_CBC, iv)
        plaintext = unpad(cipher.decrypt(ciphertext), AES.block_size)
    else:  # ctr
        # PyCryptodome CTR: use initial_value from IV (16 bytes -> 128-bit counter start)
        from Crypto.Util import Counter
        initial = int.from_bytes(iv, "big")
        ctr = Counter.new(128, initial_value=initial)
        cipher = AES.new(key, AES.MODE_CTR, counter=ctr)
        plaintext = cipher.decrypt(ciphertext)

    # Output
    try:
        text = plaintext.decode("utf-8")
    except UnicodeDecodeError:
        text = None

    Path("flag.bin").write_bytes(plaintext)
    print(f"IV @ {hex(iv_off)}: {iv.hex()}")
    print(f"Ciphertext @ {hex(ct_off)} ({len(ciphertext)} bytes)")
    if text:
        print("Flag (UTF-8):")
        print(text)
    else:
        print("Plaintext written to flag.bin (non-UTF8 or binary).")

if __name__ == "__main__":
    main()