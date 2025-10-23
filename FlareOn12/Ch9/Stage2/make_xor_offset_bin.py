# build_ndjson_index.py
import struct

def build_index(ndjson_path: str, index_path: str):
    offsets = []
    offset = 0
    with open(ndjson_path, "rb") as f:
        while True:
            line = f.readline()
            if not line:
                break
            offsets.append(offset)
            offset += len(line)

    with open(index_path, "wb") as out:
        for off in offsets:
            out.write(struct.pack("<Q", off))  # uint64 little-endian

if __name__ == "__main__":
    build_index("snapshots.ndjson", "offsets.bin")
    print("Index built: offsets.bin")