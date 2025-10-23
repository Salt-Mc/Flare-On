from hashlib import sha256
import json
from pathlib import Path

SRC = Path("recovered.ndjson")
OUT = Path("license.bin")

def main():
    if not SRC.exists():
        raise FileNotFoundError(f"Input file not found: {SRC}")

    written = 0
    with SRC.open("r", encoding="utf-8") as f, OUT.open("wb") as xf:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                # Each line is a JSON object like: {"7476": "'2b2b...'"}
                obj = json.loads(line)
            except json.JSONDecodeError as ex:
                raise ValueError(f"Bad JSON on line {lineno}: {ex} -> {line[:120]}") from ex

            for k, v in obj.items():
                # Allow decimal or 0x-prefixed keys (int(k,0) handles both)
                try:
                    dll_index = int(k, 0)
                except ValueError as ex:
                    raise ValueError(f"Invalid key (not int) on line {lineno}: {k}") from ex

                # Value has embedded single quotes: "'abcdef...'"

                hex_str = v.strip().strip("'")
                if len(hex_str) % 2 != 0:
                    raise ValueError(f"Odd-length hex string for key {k} on line {lineno}: {hex_str}")

                try:
                    data = bytes.fromhex(hex_str)
                except ValueError as ex:
                    raise ValueError(f"Invalid hex for key {k} on line {lineno}: {hex_str}") from ex

                if len(data) != 32:
                    # Not necessarily fatal—adjust or warn depending on expectations.
                    # Here we enforce length since license components should be 32 bytes.
                    raise ValueError(f"Unexpected data length {len(data)} (expected 32) for key {k} on line {lineno}")

                idx_bytes = dll_index.to_bytes(2, "little", signed=False)
                xf.write(idx_bytes + data)
                written += 1

    digest_hex = sha256(OUT.read_bytes()).hexdigest()
    print(f"Wrote {written} entries to {OUT}.")
    print(f"SHA256 Digest: {digest_hex}")

if __name__ == "__main__":
    main()

