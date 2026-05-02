# 10000.exe solution

Flag:

```text
Its_l1ke_10000_spooO0o0O0oOo0o0O0O0OoOoOOO00o0o0Ooons@flare-on.com
```

Generated license:

```text
license.bin
size:   340000 bytes
sha256: 600abf28e03c73471a73bb909210dc2d2b4e98c7577d6b71299d2e54d693d14d
```

## Files

```text
solve_10000.py            solver and final decrypt script
requirements_10000.txt    Python dependencies
AplibServer\              .NET aPLib resource decompressor used for speed
```

Expected challenge files are outside this folder in `FlareOn12\Ch9`:

```text
..\10000.exe              original challenge binary
..\10000.exe.c            Hex-Rays decompilation used for analysis
..\license.bin            optional generated valid license
```

## Reproduce

From this folder in PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .\requirements_10000.txt
dotnet build .\AplibServer\AplibServer.csproj -c Release --nologo
```

If `license.bin` is already present, recover the flag directly:

```powershell
.\.venv\Scripts\python.exe .\solve_10000.py decrypt
```

To regenerate the license from the embedded modules:

```powershell
.\.venv\Scripts\python.exe .\solve_10000.py solve --progress 250
.\.venv\Scripts\python.exe .\solve_10000.py decrypt
```

`solve_10000.py` starts `AplibServer` automatically when this file exists:

```text
AplibServer\bin\Release\net8.0\AplibServer.dll
```

You normally do not run `AplibServer` by hand. If you do, the command is:

```powershell
dotnet .\AplibServer\bin\Release\net8.0\AplibServer.dll ..\10000.exe
```

It expects resource IDs on stdin, one per line, for example `0`, `1`, or `7476`. For each requested ID it writes binary data to stdout as:

```text
4-byte little-endian decompressed length || decompressed PE bytes
```

That means direct terminal output will look like binary garbage; the Python solver is the intended client.

`solve_artifacts\deps.pkl`, `target.pkl`, and `order.pkl` are generated cache files. They are not included in this upload to avoid committing generated artifacts. The script rebuilds them with:

```powershell
.\.venv\Scripts\python.exe .\solve_10000.py extract-deps
```

## Cache file formats

The cache files are Python `pickle` files. They are binary Python serializations, not JSON. Only load them if you trust the files.

`solve_artifacts\deps.pkl` stores the direct module dependency graph:

```python
list[list[int]]
```

The index is the module ID, and the value is the list of directly imported numeric DLLs:

```python
deps[module_id] = [direct_dependency_module_id, ...]
```

For example, if module `1234` imports `0042.dll` and `0777.dll`, then:

```python
deps[1234] == [42, 777]
```

Quick inspection:

```powershell
@'
import pickle
from pathlib import Path

deps = pickle.loads(Path(r"solve_artifacts\deps.pkl").read_bytes())
print(type(deps), len(deps))
print("module 0 deps:", deps[0])
'@ | .\.venv\Scripts\python.exe -
```

Other cache files:

| File | Python object | Meaning |
|---|---|---|
| `solve_artifacts\deps.pkl` | `list[list[int]]` | Direct numeric-import dependencies for modules `0..9999` |
| `solve_artifacts\target.pkl` | `list[int]` | 10,000 expected final counter dwords extracted from the main EXE |
| `solve_artifacts\order.pkl` | `dict` | Solved ordering data: `pos`, `order`, and `closures` |

`order.pkl` contains:

```python
{
    "pos": list[int],       # pos[module_id] = record position
    "order": list[int],     # order[position] = module_id
    "closures": list[int],  # integer bitset closure for each module
}
```

Each closure is stored as one Python integer bitset. If bit `k` is set, module `k` is in that module's recursive dependency closure.

## Analysis summary

The main routine in `10000.exe.c` opens `license.bin`, requires it to be exactly `340000` bytes, and treats it as 10,000 records of 34 bytes:

```text
uint16 module_id
byte   block[32]
```

For each record, the binary loads an embedded PE module from RCDATA resources, resolves `_Z5checkPh`, and checks the 32-byte block. After a successful check it adds the current record position to a 10,000-entry counter table for every module currently loaded through the custom loader. At the end it compares that counter table with the embedded target table at `unk_1400CC000`. If everything matches, it hashes the whole license with SHA-256 and uses that 32-byte hash as the AES key to decrypt the final message.

The efficient solution avoids brute force:

1. Parse the PE resource tree and enumerate the 10,000 RCDATA entries.
2. Decompress each entry as an aPLib stream; each decompressed entry is another PE module.
3. Extract numeric imports such as `0231.dll`; these are dependencies on other embedded modules.
4. Build each module closure: the module plus every recursively imported module.
5. Solve the global record order from the target counter equation:

```text
target[j] = sum(position[m] for every module m whose closure contains j)
```

The dependency graph is a DAG. Processing nodes in topological order gives each module position directly from the remaining residual target value, then subtracts that position from every member of its closure. This yields a unique permutation of positions `0..9999`.

Each module checker is generated code with the same structure:

1. It runs hundreds of helper transforms on the 32-byte block.
2. Each helper first XORs the first dword with one current global counter entry.
3. Helpers are one of three reversible forms:
   - 256-byte S-box substitution.
   - 32-byte byte permutation.
   - Odd exponentiation of a 256-bit integer modulo `2^256`.
4. The final check interprets the result as four 64-bit words and verifies a 4x4 matrix exponentiation over a 64-bit prime field.

For each record, the solver:

1. Computes the required final 32 bytes by taking the matrix root. The exponent is invertible modulo the order of `GL(4, p)`, so this is deterministic.
2. Walks the helper call list in reverse.
3. Applies each inverse transform and then undoes the counter XOR using the current simulated counter table.
4. Writes `module_id || solved_block`.
5. Updates the simulated counter table for the module closure at that position.

After writing `license.bin`, the final message is recovered by reproducing the executable's last step:

```text
key = SHA256(license.bin)
plaintext = AES-256-CBC-decrypt(embedded_ciphertext, key, embedded_iv)
```

The executable's full validation path is slow because it dynamically loads and runs all 10,000 generated modules. The `decrypt` command is equivalent after the license has been generated because it uses the same embedded ciphertext, IV, and license hash.

## Why this solver is faster

The fastest route was to avoid materializing large intermediate artifacts. The staged approach many writeups use is:

```text
extract 10000 DLLs -> dump closures JSON -> dump per-DLL transform JSON -> dump XOR snapshots NDJSON -> recover payload NDJSON -> build license
```

This solver uses a shorter pipeline:

```text
read 10000 resources from 10000.exe -> solve graph/order in memory -> invert checkers directly -> write license.bin
```

The main performance decisions are:

1. **Direct PE resource parsing**

   The solver parses the resource tree in `10000.exe` and reads each RCDATA entry directly. It does not require a directory of `0.dll` through `9999.dll`.

2. **O(1) resource lookup**

   `ResourceView` builds an index once:

   ```python
   rcdata_index: dict[int, tuple[int, int]]
   ```

   This maps:

   ```text
   resource_id -> (file_offset, compressed_size)
   ```

   Without this, every module load would rescan the whole 10,000-entry resource tree.

3. **Native aPLib decompression**

   The embedded modules are aPLib-compressed. Pure Python decompression worked but was slow. `AplibServer` is a small .NET helper that keeps `10000.exe` open, accepts resource IDs on stdin, and returns decompressed module bytes on stdout:

   ```text
   request:  "7476\n"
   response: uint32_le decompressed_size || decompressed PE bytes
   ```

   This made the first 10-record benchmark drop from about 126 seconds to about 7 seconds.

4. **Compact dependency cache**

   Only direct numeric imports are cached in `deps.pkl`. The script does not write each decompressed PE to disk and does not dump huge JSON metadata for every module.

5. **Topological residual order solve**

   The executable's final counter equation is:

   ```text
   target[j] = sum(position[m] for every module m whose closure contains j)
   ```

   Because the dependency graph is a DAG, the solver processes modules in topological order. For each node, the current residual at that node is the module's position:

   ```python
   for node in topo:
       cur_pos = residual[node]
       pos[node] = cur_pos
       for dep in closure[node]:
           residual[dep] -= cur_pos
   ```

   This solves the 10,000-record order directly. No brute force and no dense matrix solve are needed.

6. **Integer bitset closures**

   Transitive closures are stored as Python integers rather than JSON arrays or Python sets:

   ```python
   closures[module_id] = bitset
   ```

   Counter updates use bit operations:

   ```python
   bits = closures[module_id]
   while bits:
       lsb = bits & -bits
       counters[lsb.bit_length() - 1] += position
       bits ^= lsb
   ```

   This is compact and avoids repeatedly parsing large closure lists.

7. **No XOR snapshot files**

   The EXE maintains a 10,000-dword counter table. Instead of writing one snapshot per iteration to NDJSON and reading it later, the solver keeps the live table in memory:

   ```python
   counters = [0] * 10000
   ```

   At the moment each record is solved, `counters` already matches the executable's current global counter table.

8. **Parse only used checker helpers**

   Each `_Z5checkPh` calls hundreds of generated helper functions. The solver follows the actual call list and parses only those helpers. It does not classify every unused export.

   Parsed helper metadata is cached in memory:

   ```python
   check_cache
   helper_cache
   helper_cache_by_rva
   stage_cache
   export_cache
   ```

9. **Precomputed inverse helper forms**

   During parsing, the solver converts helper constants directly into inverse-ready data:

   ```text
   S-box helper       -> inverse 256-byte table
   permutation helper -> inverse 32-byte permutation
   exponent helper    -> inverse exponent modulo 2^254
   ```

   That avoids rebuilding inverse tables or recomputing modular inverses while generating records.

10. **Simple matrix-root shortcut**

    The final checker step verifies:

    ```text
    M^e == target_matrix
    ```

    over a 64-bit prime field. Since `e` is invertible modulo the order of `GL(4, p)`, the solver computes:

    ```python
    order = 1
    for i in range(4):
        order *= prime**4 - prime**i

    inv_exp = pow(exponent, -1, order)
    root = matrix_pow(target_matrix, inv_exp, prime)
    ```

    This avoids characteristic-polynomial factoring, SymPy, FLINT, and per-matrix factor caches.

11. **Direct license writing**

    The solver writes each final record directly:

    ```python
    struct.pack("<H", module_id) + solved_32_byte_block
    ```

    It does not write recovered blocks to NDJSON and then convert them in a second script.

12. **Direct final decrypt**

    Once `license.bin` is generated, the final EXE step is:

    ```text
    key = SHA256(license.bin)
    plaintext = AES-256-CBC-decrypt(embedded_ciphertext, key, embedded_iv)
    ```

    Running the original EXE has to revalidate all 10,000 records and can take a long time. The `decrypt` command reproduces the same final cryptographic step immediately after the license is generated.

