needed_bytes = list()

# Function to split a 16-bit integer into two bytes  
def split_into_bytes(value):  
    high_byte = (value >> 8) & 0xFF  
    low_byte = value & 0xFF  
    return [low_byte, high_byte]  

def start():  
    memory = [0] * 32
    
    memory[0] = 48042  # 0xBB2A  
    memory[1] = 56780  # 0xDDD6  
    memory[2] = 65518  # 0xFFFE  
    memory[3] = 44510  # 0xADF2  
    memory[4] = 61374  # 0xEFFE  
    memory[5] = 65226  # 0xFEFA  
    memory[6] = 48826  # 0xBF1A  
    memory[7] = 52651  # 0xCDDB

    memory[8]  = 41049
    memory[9]  = 27213
    memory[10] = 56867
    memory[11] = 9408
    memory[12] = 25826
    memory[13] = 22961
    memory[14] = 29191
    memory[15] = 32604

    # Extract bytes from memory[0] to memory[7] (user input)  
    input_bytes = []  
    for i in range(0, 8):  
        input_bytes.extend(split_into_bytes(memory[i]))  
    
    # Extract bytes from memory[8] to memory[15] (constants)  
    constants = []  
    for i in range(8, 16):  
        constants.extend(split_into_bytes(memory[i]))  
  
    # 3. Initialize the Linear Congruential Generator (LCG) parameters  
    lcg_multiplier = 214013  
    lcg_increment = 2531011  
    lcg_modulus = 0x80000000  # 2^31  
    lcg_seed = 4919  
  
    # 4. Initialize loop control variables  
    valid_byte_count = 0  
  
    # 5. Main validation loop  
    for i in range(16):  
        # Extract the input byte and the corresponding constant byte  
        input_byte = input_bytes[i]  
        constant_byte = constants[i]  
  
        # Update the random number generator  
        lcg_seed = (lcg_multiplier * lcg_seed + lcg_increment) % lcg_modulus  
  
        # Extract a byte from the random number generator based on current position  
        mem6_2 = (lcg_seed >> (8 * (i % 4))) & 0xFF
  
        # Compute XOR between the input byte and the random number byte  
        mem8 = input_byte ^ mem6_2
        needed_bytes.append((constant_byte ^ mem6_2) & 0xFF)
  
        # Validation check  
        if mem8 != constant_byte:  
            # # Validation failed  
            # print("Validation failed.")  
            # return
            pass
        else:  
            valid_byte_count += 1  
  
    # 6. Final validation  
    if valid_byte_count == 16:  
        print("Validation successful.")  
    else:  
        print("Validation failed.")  

start()
print("".join([chr(i) for i in needed_bytes]))
