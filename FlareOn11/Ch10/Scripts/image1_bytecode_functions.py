memory = [0] * 32
  
memory[0] = 48042  # 0xBB2A  
memory[1] = 56780  # 0xDDD6  
memory[2] = 65518  # 0xFFFE  
memory[3] = 44510  # 0xADF2  
memory[4] = 61374  # 0xEFFE  
memory[5] = 65226  # 0xFEFA  
memory[6] = 48826  # 0xBF1A  
memory[7] = 52651  # 0xCDDB  
  
memory[8]  = (ord('a') << 8) | ord('D')       # 'aD'  
memory[9]  = (ord('u') << 8) | ord('4')       # 'u4'  
memory[10] = 26978                            # 0x6952  
memory[11] = (ord('l') << 8) | ord('c')       # 'lc'  
memory[12] = (ord('1') << 8) | ord('e')       # '1e'  
memory[13] = (ord('f') << 8) | ord('i')       # 'fi'  
memory[14] = 25189                            # 0x6265  
memory[15] = (ord('b') << 8) | ord('0')       # 'b0'  

# Function to split a 16-bit integer into two bytes  
def split_into_bytes(value):  
    high_byte = (value >> 8) & 0xFF  
    low_byte = value & 0xFF  
    return [low_byte, high_byte]  
  
# Extract bytes from memory[0] to memory[7] (user input)  
user_input_bytes = []  
for i in range(0, 8):  
    user_input_bytes.extend(split_into_bytes(memory[i]))  
  
# Extract bytes from memory[8] to memory[15] (constants)  
constant_bytes = []  
for i in range(8, 16):  
    constant_bytes.extend(split_into_bytes(memory[i]))  

# Initialize variables  
success_count = 0
needed_bytes = list()
  
for index in range(16):  
    byte_from_input = user_input_bytes[index]  
    byte_from_constant = constant_bytes[index]  
  
    if index == 2:  
        byte_from_constant = ((byte_from_constant << 4) | (byte_from_constant >> 4)) & 0xFF  
    elif index == 9:  
        byte_from_constant = ((byte_from_constant >> 2) | (byte_from_constant << 6)) & 0xFF  
    elif index == 13 or index == 15:  
        byte_from_constant = ((byte_from_constant << 7) | (byte_from_constant >> 1)) & 0xFF

    needed_bytes.append(byte_from_constant)
  
    if byte_from_input == byte_from_constant:  
        success_count += 1  
    # else:  
    #     break  # Exit early if a mismatch is found

print("".join([chr(i) for i in needed_bytes]))
# Final check  
if success_count == 16:  
    result = 1  
else:  
    result = 0  

print("Validation result:", "Success" if result == 1 else "Failure")  
