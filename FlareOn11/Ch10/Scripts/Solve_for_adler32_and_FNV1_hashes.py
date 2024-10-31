from z3 import *  
  
def reverse_combined(desired_checksum, desired_accumulator):  
    # Initialize solver  
    solver = Solver()
    # Variables for bytes b0 to b15  
    b = [BitVec(f'b{i}', 8) for i in range(16)]  
    # Add constraints that each byte is between 0 and 255  
    for byte in b:  
        solver.add(byte >= 30, byte <= 123)
    # Set the first 8 bytes to the known values b"VerYDumB"
    # From DJB2 hash brute-force result
    solver.add(b[0] == ord('V'))
    solver.add(b[1] == ord('e'))
    solver.add(b[2] == ord('r'))
    solver.add(b[3] == ord('Y'))
    # From rotate-and-add hash brute-force result
    solver.add(b[4] == ord('D'))
    solver.add(b[5] == ord('u'))
    solver.add(b[6] == ord('m'))
    solver.add(b[7] == ord('B'))
    # --- Adler-32 Computation for bytes b8 to b15 ---  
    MOD_ADLER = 65521
    A = 1  
    B = 0
    for byte in b[8:16]:  
        A = (A + ZeroExt(24, byte)) % MOD_ADLER  
        B = (B + A) % MOD_ADLER  
    computed_checksum = (B << 16) | A
    # Add constraint for Adler-32 checksum  
    solver.add(computed_checksum == desired_checksum)  
    # --- Last FNV Hash of size 32 Computation ---
    fnv_prime     = BitVecVal(0x1000193, 32)   # FNV prime
    # in out code we have mod with 1 the multiplication result,
    # but for real FNV-1 hash there is no mod operation https://en.wikipedia.org/wiki/Fowler%E2%80%93Noll%E2%80%93Vo_hash_function#FNV-1_hash
    exponent      = BitVecVal(1, 32)
    fnv_hash      = BitVecVal(0x811c9dc5, 32)  # FNV offset basis
    # Compute the FNV-1 hash of the bytes b0 to b15
    for byte in b:  
        fnv_hash = (fnv_hash * fnv_prime) # % exponent # According to the code.
        fnv_hash = fnv_hash ^ ZeroExt(24, byte)  
        fnv_hash = fnv_hash & 0xFFFFFFFF  # Ensure 32-bit value
    # Add constraint for FNV-1 checksum
    solver.add(fnv_hash == desired_accumulator)  
    # Check if the constraints are solvable
    if solver.check() == sat:  
        model = solver.model()  
        byte_values = [model[byte].as_long() for byte in b]  
        return byte_values  
    else:  
        return None  

expected_adler32_hash = 261161844
expected_fnv1_hash    = 837814738
result = reverse_combined(expected_adler32_hash, expected_fnv1_hash)  

if result:  
    print("Bytes b0 to b15:", result)  
    print("As Test:", "".join([chr(b) for b in result]))  
else:
    print("No solution found.")  
