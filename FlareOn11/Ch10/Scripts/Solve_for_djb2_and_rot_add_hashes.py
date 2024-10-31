def reverse_adler32(desired_checksum):  
    MASK_16_BIT = 0xFFFF  
    desired_adler_a = desired_checksum & MASK_16_BIT  
    desired_adler_b = (desired_checksum >> 16) & MASK_16_BIT  
  
    for b8 in range(35, 123):  
        for b9 in range(35, 123):  
            for b10 in range(35, 123):  
                for b11 in range(35, 123):  
                    for b12 in range(35, 123):  
                        for b13 in range(35, 123):  
                            for b14 in range(35, 123):  
                                # Compute adler_a  
                                adler_a = (1 + b8 + b9 + b10 + b11 + b12 + b13 + b14) % 65521  
                                # Compute adler_b  
                                adler_a_values = [1]  
                                bytes_list = [b8, b9, b10, b11, b12, b13, b14]  
                                for byte in bytes_list:  
                                    adler_a_values.append((adler_a_values[-1] + byte) % 65521)  
                                adler_b = sum(adler_a_values) % 65521  
                                # Solve for b15  
                                b15 = (desired_adler_a - adler_a_values[-1]) % 65521  
                                if b15 > 255:  
                                    continue  # b15 must be between 0 and 255  
                                # Update adler_a and adler_b with b15  
                                adler_a = (adler_a + b15) % 65521  
                                adler_b = (adler_b + adler_a) % 65521  
                                if adler_a == desired_adler_a and adler_b == desired_adler_b:  
                                    # Found a solution  
                                    bytes_result = [b8, b9, b10, b11, b12, b13, b14, b15]  
                                    return bytes_result  
    return None  # No solution found  


def reverse_custom_hash(desired_hash):  
    from collections import deque  
    MASK_32_BIT = 0xFFFFFFFF  
      
    for b4 in range(35, 123):  
        hash1 = ((0 >> 13) | (0 << (32 - 13))) & MASK_32_BIT  
        hash1 = (hash1 + b4) & MASK_32_BIT  
        for b5 in range(35, 123):  
            temp_hash = ((hash1 >> 13) | (hash1 << (32 - 13))) & MASK_32_BIT  
            hash2 = (temp_hash + b5) & MASK_32_BIT  
            for b6 in range(35, 123):  
                temp_hash = ((hash2 >> 13) | (hash2 << (32 - 13))) & MASK_32_BIT  
                hash3 = (temp_hash + b6) & MASK_32_BIT  
                for b7 in range(35, 123):  
                    temp_hash = ((hash3 >> 13) | (hash3 << (32 - 13))) & MASK_32_BIT  
                    hash4 = (temp_hash + b7) & MASK_32_BIT  
                    if hash4 == desired_hash:  
                        return [b4, b5, b6, b7]  
    return None  # No combination found  

def reverse_djb2(desired_hash):  
    for b0 in range(35, 122):  
        hash1 = (5381 * 33 + b0) & 0xFFFFFFFF  
        for b1 in range(35, 122):  
            hash2 = (hash1 * 33 + b1) & 0xFFFFFFFF  
            for b2 in range(35, 122):  
                hash3 = (hash2 * 33 + b2) & 0xFFFFFFFF  
                for b3 in range(35, 122):  
                    hash4 = (hash3 * 33 + b3) & 0xFFFFFFFF  
                    if hash4 == desired_hash:  
                        return [b0, b1, b2, b3]  
    return None  # No combination found

# STAGE 1: DJB2 Hash
desired_hash = 2089678027  
result = reverse_djb2(desired_hash)  
if result:  
    print("Found bytes:", result)  
    print("As Test:", " ".join([chr(b) for b in result]))
else:  
    print("No solution found.")

# # STAGE 2: Custom Rotate-and-Add Hash
desired_hash = 2338856322  
result = reverse_custom_hash(desired_hash)  
if result:  
    print("Found bytes:", result)  
    print("As Test:", " ".join([chr(b) for b in result]))
else:  
    print("No solution found.")

## This is solved using Z3
# desired_checksum = 261161844  
# result = reverse_adler32(desired_checksum)  
# if result:  
#     print("Found bytes:", result)  
#     print("As hex:", [hex(b) for b in result])  
# else:  
#     print("No solution found.")  