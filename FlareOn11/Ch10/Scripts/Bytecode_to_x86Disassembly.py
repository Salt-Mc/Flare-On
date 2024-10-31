# VM to x86 Disassembler  
# Author: rtiwari  
# Description: Disassembles VM bytecode into x86 assembly code  
  
from typing import List  
  
OPCODES = {  
    0x00: 'EXIT',
    0x01: 'PUSH',
    0x02: 'LOAD',
    0x03: 'ADD_MEM',
    0x04: 'STORE',
    0x05: 'LOAD_IND',
    0x06: 'STORE_IND',
    0x07: 'DUP',
    0x08: 'POP',
    0x09: 'ADD',
    0x0A: 'ADD_IMM',
    0x0B: 'SUB',
    0x0C: 'DIV',
    0x0D: 'MUL',
    0x0E: 'JMP',
    0x0F: 'JNZ',
    0x10: 'JZ',
    0x11: 'CMP_EQ',
    0x12: 'CMP_LT',
    0x13: 'CMP_LE',
    0x14: 'CMP_GT',
    0x15: 'CMP_GE',
    0x16: 'CMP_IMM_GE',
    0x17: 'POP_TO_VALID',
    0x18: 'EXIT_OK',
    0x19: 'RESERVED',
    0x1A: 'XOR',
    0x1B: 'OR',
    0x1C: 'AND',
    0x1D: 'MOD',
    0x1E: 'SHL',
    0x1F: 'SHR',
    0x20: 'ROL32',
    0x21: 'ROR32',
    0x22: 'ROL16',
    0x23: 'ROR16',
    0x24: 'ROL8',
    0x25: 'ROR8',
    0x26: 'PUTCHAR',
}  
 
class VMDisassembler:  
    def __init__(self, bytecode: bytes):  
        self.bytecode = bytecode  
        self.pc = 0       # Program counter  
        self.output = []  # Disassembled instructions  
        self.labels = {}  # For generating labels in control flow  
  
    def read_byte(self):  
        if self.pc < len(self.bytecode):  
            byte = self.bytecode[self.pc]  
            self.pc += 1  
            return byte  
        else:  
            raise IndexError("Attempted to read past end of bytecode.")  
  
    def read_word(self):  
        """Reads a 2-byte word (big-endian) from the bytecode."""  
        high_byte = self.read_byte()  
        low_byte = self.read_byte()  
        word = (high_byte << 8) | low_byte  
        return word  
  
    def disassemble(self):  
        while self.pc < len(self.bytecode):  
            addr = self.pc  
            opcode = self.read_byte()  
            instruction = OPCODES.get(opcode, f'UNKNOWN_OPCODE_{opcode:#02x}')  
  
            if instruction == 'EXIT_ERROR':  
                self.output.append(f"{addr:04x}: EXIT_ERROR")  
            elif instruction == 'PUSH':  
                immediate = self.read_word()  
                self.output.append(f"{addr:04x}: PUSH 0x{immediate:04x}")  
            elif instruction == 'LOAD':  
                address = self.read_word()  
                self.output.append(f"{addr:04x}: LOAD 0x{address:04x}")  
            elif instruction == 'ADD':  
                self.output.append(f"{addr:04x}: ADD")  
            elif instruction == 'ADD_IMM':  
                immediate = self.read_word()  
                self.output.append(f"{addr:04x}: ADD_IMM 0x{immediate:04x}")  
            elif instruction == 'ADD_MEM':  
                address = self.read_word()  
                self.output.append(f"{addr:04x}: ADD_MEM 0x{address:04x}")  
            elif instruction == 'SUB':  
                self.output.append(f"{addr:04x}: SUB")  
            elif instruction == 'MUL':  
                self.output.append(f"{addr:04x}: MUL")  
            elif instruction == 'DIV':  
                self.output.append(f"{addr:04x}: DIV")  
            elif instruction == 'MOD':  
                self.output.append(f"{addr:04x}: MOD")  
            elif instruction == 'SHL':  
                self.output.append(f"{addr:04x}: SHL")  
            elif instruction == 'SHR':  
                self.output.append(f"{addr:04x}: SHR")  
            elif instruction == 'JMP':  
                address = self.read_word()  
                self.output.append(f"{addr:04x}: JMP 0x{address:04x}")  
                self.labels[address] = f"label_{address:04x}"  
            elif instruction == 'JNZ':  
                address = self.read_word()  
                self.output.append(f"{addr:04x}: JNZ 0x{address:04x}")  
                self.labels[address] = f"label_{address:04x}"  
            elif instruction == 'JZ':  
                address = self.read_word()  
                self.output.append(f"{addr:04x}: JZ 0x{address:04x}")  
                self.labels[address] = f"label_{address:04x}"  
            elif instruction == 'CMP_EQ':  
                self.output.append(f"{addr:04x}: CMP_EQ")  
            elif instruction == 'CMP_GT':  
                self.output.append(f"{addr:04x}: CMP_GT")  
            elif instruction == 'CMP_GE':  
                self.output.append(f"{addr:04x}: CMP_GE")  
            elif instruction == 'CMP_LT':  
                self.output.append(f"{addr:04x}: CMP_LT")  
            elif instruction == 'CMP_LE':  
                self.output.append(f"{addr:04x}: CMP_LE")  
            elif instruction == 'DUP':  
                self.output.append(f"{addr:04x}: DUP")  
            elif instruction == 'POP':  
                self.output.append(f"{addr:04x}: POP")  
            elif instruction == 'STORE':  
                address = self.read_word()  
                self.output.append(f"{addr:04x}: STORE 0x{address:04x}")  
            elif instruction == 'LOAD_IND':  
                self.output.append(f"{addr:04x}: LOAD_IND")  
            elif instruction == 'STORE_IND':  
                self.output.append(f"{addr:04x}: STORE_IND")  
            elif instruction == 'ROL32':  
                self.output.append(f"{addr:04x}: ROL32")  
            elif instruction == 'ROR32':  
                self.output.append(f"{addr:04x}: ROR32")  
            elif instruction == 'ROL16':  
                self.output.append(f"{addr:04x}: ROL16")  
            elif instruction == 'ROR16':  
                self.output.append(f"{addr:04x}: ROR16")  
            elif instruction == 'ROL8':  
                self.output.append(f"{addr:04x}: ROL8")  
            elif instruction == 'ROR8':  
                self.output.append(f"{addr:04x}: ROR8")  
            elif instruction == 'XOR':  
                self.output.append(f"{addr:04x}: XOR")  
            elif instruction == 'OR':  
                self.output.append(f"{addr:04x}: OR")  
            elif instruction == 'AND':  
                self.output.append(f"{addr:04x}: AND")  
            elif instruction == 'PUTCHAR':  
                self.output.append(f"{addr:04x}: PUTCHAR")  
            elif instruction == 'EXIT_OK':  
                self.output.append(f"{addr:04x}: EXIT_OK")  
            else:  
                self.output.append(f"{addr:04x}: {instruction} (Unhandled)")  
        return self.output  
  
    def translate_to_x86(self):  
        """Translates the disassembled VM instructions to x86 assembly code."""  
        x86_instructions = []  
        # Map for labels based on addresses  
        labels_map = {addr: label for addr, label in self.labels.items()}  
  
        # Collect all addresses that are jump targets for labels  
        jump_targets = set(self.labels.keys())  
  
        # First pass: establish labels  
        addr_line_map = {}  
        for idx, line in enumerate(self.output):  
            addr = int(line.split(':')[0], 16)  
            addr_line_map[addr] = idx  
  
        # Second pass: translate instructions  
        for idx, line in enumerate(self.output):  
            addr_instr = line.split(': ', 1)  
            if len(addr_instr) != 2:  
                continue  
            addr = int(addr_instr[0], 16)  
            instr_line = addr_instr[1]  
            if addr in jump_targets:  
                label = labels_map[addr]  
                x86_instructions.append(f"{label}:")  
            parts = instr_line.strip().split()  
            if not parts:  
                continue  
            mnemonic = parts[0]  
            operands = parts[1:] if len(parts) > 1 else []  
  
            # Translate VM instructions to x86 assembly code  
            if mnemonic == 'EXIT_ERROR':  
                x86_instructions.append(f"    mov eax, 4")  
                x86_instructions.append(f"    ; exit with code 4")  
                x86_instructions.append(f"    ; Implement OS-specific exit syscall")  
            elif mnemonic == 'EXIT_OK':  
                x86_instructions.append(f"    mov eax, 0")  
                x86_instructions.append(f"    ; exit with code 0")  
                x86_instructions.append(f"    ; Implement OS-specific exit syscall")  
            elif mnemonic == 'PUSH':  
                immediate = operands[0]  
                x86_instructions.append(f"    mov eax, {immediate}")  
                x86_instructions.append(f"    push eax")  
            elif mnemonic == 'POP':  
                x86_instructions.append(f"    pop eax")  
            elif mnemonic == 'DUP':  
                x86_instructions.append(f"    mov eax, [esp]")  
                x86_instructions.append(f"    push eax")  
            elif mnemonic == 'LOAD':  
                address = operands[0]  
                x86_instructions.append(f"    mov eax, [memory + {address}]")  
                x86_instructions.append(f"    push eax")  
            elif mnemonic == 'LOAD_IND':  
                x86_instructions.append(f"    pop eax                ; Load address from stack")  
                x86_instructions.append(f"    mov ebx, [memory + eax]")  
                x86_instructions.append(f"    push ebx")  
            elif mnemonic == 'STORE':  
                address = operands[0]  
                x86_instructions.append(f"    pop eax")  
                x86_instructions.append(f"    mov [memory + {address}], eax")  
            elif mnemonic == 'STORE_IND':  
                x86_instructions.append(f"    pop eax                ; Value to store")  
                x86_instructions.append(f"    pop ebx                ; Address")  
                x86_instructions.append(f"    mov [memory + ebx], eax")  
            elif mnemonic == 'ADD':  
                x86_instructions.append(f"    pop eax")  
                x86_instructions.append(f"    pop ebx")  
                x86_instructions.append(f"    add eax, ebx")  
                x86_instructions.append(f"    push eax")  
            elif mnemonic == 'ADD_IMM':  
                immediate = operands[0]  
                x86_instructions.append(f"    pop eax")  
                x86_instructions.append(f"    add eax, {immediate}")  
                x86_instructions.append(f"    push eax")  
            elif mnemonic == 'ADD_MEM':  
                address = operands[0]  
                x86_instructions.append(f"    pop eax")  
                x86_instructions.append(f"    mov ebx, [memory + {address}]")  
                x86_instructions.append(f"    add eax, ebx")  
                x86_instructions.append(f"    push eax")  
            elif mnemonic == 'SUB':  
                x86_instructions.append(f"    pop ebx")  
                x86_instructions.append(f"    pop eax")  
                x86_instructions.append(f"    sub eax, ebx")  
                x86_instructions.append(f"    push eax")  
            elif mnemonic == 'MUL':  
                x86_instructions.append(f"    pop eax")  
                x86_instructions.append(f"    pop ebx")  
                x86_instructions.append(f"    imul eax, ebx")  
                x86_instructions.append(f"    push eax")  
            elif mnemonic == 'DIV':  
                x86_instructions.append(f"    xor edx, edx")  
                x86_instructions.append(f"    pop ebx")  
                x86_instructions.append(f"    pop eax")  
                x86_instructions.append(f"    idiv ebx")  
                x86_instructions.append(f"    push eax")  # Push quotient  
            elif mnemonic == 'MOD':  
                x86_instructions.append(f"    xor edx, edx")  
                x86_instructions.append(f"    pop ebx")  
                x86_instructions.append(f"    pop eax")  
                x86_instructions.append(f"    idiv ebx")  
                x86_instructions.append(f"    push edx")  # Push remainder  
            elif mnemonic == 'SHL':  
                x86_instructions.append(f"    pop ecx")  # Shift count  
                x86_instructions.append(f"    pop eax")  
                x86_instructions.append(f"    shl eax, cl")  
                x86_instructions.append(f"    push eax")  
            elif mnemonic == 'SHR':  
                x86_instructions.append(f"    pop ecx")  # Shift count  
                x86_instructions.append(f"    pop eax")  
                x86_instructions.append(f"    shr eax, cl")  
                x86_instructions.append(f"    push eax")  
            elif mnemonic == 'ROL32':  
                x86_instructions.append(f"    pop ecx")  # Rotate count  
                x86_instructions.append(f"    pop eax")  
                x86_instructions.append(f"    rol eax, cl")  
                x86_instructions.append(f"    push eax")  
            elif mnemonic == 'ROR32':  
                x86_instructions.append(f"    pop ecx")  # Rotate count  
                x86_instructions.append(f"    pop eax")  
                x86_instructions.append(f"    ror eax, cl")  
                x86_instructions.append(f"    push eax")  
            elif mnemonic == 'ROL16':  
                x86_instructions.append(f"    pop ecx")  
                x86_instructions.append(f"    pop eax")  
                x86_instructions.append(f"    rol ax, cl")  
                x86_instructions.append(f"    push eax")  
            elif mnemonic == 'ROR16':  
                x86_instructions.append(f"    pop ecx")  
                x86_instructions.append(f"    pop eax")  
                x86_instructions.append(f"    ror ax, cl")  
                x86_instructions.append(f"    push eax")  
            elif mnemonic == 'ROL8':  
                x86_instructions.append(f"    pop ecx")  
                x86_instructions.append(f"    pop eax")  
                x86_instructions.append(f"    rol al, cl")  
                x86_instructions.append(f"    push eax")  
            elif mnemonic == 'ROR8':  
                x86_instructions.append(f"    pop ecx")  
                x86_instructions.append(f"    pop eax")  
                x86_instructions.append(f"    ror al, cl")  
                x86_instructions.append(f"    push eax")  
            elif mnemonic == 'XOR':  
                x86_instructions.append(f"    pop eax")  
                x86_instructions.append(f"    pop ebx")  
                x86_instructions.append(f"    xor eax, ebx")  
                x86_instructions.append(f"    push eax")  
            elif mnemonic == 'OR':  
                x86_instructions.append(f"    pop eax")  
                x86_instructions.append(f"    pop ebx")  
                x86_instructions.append(f"    or eax, ebx")  
                x86_instructions.append(f"    push eax")  
            elif mnemonic == 'AND':  
                x86_instructions.append(f"    pop eax")  
                x86_instructions.append(f"    pop ebx")  
                x86_instructions.append(f"    and eax, ebx")  
                x86_instructions.append(f"    push eax")  
            elif mnemonic == 'CMP_EQ':  
                x86_instructions.append(f"    pop eax")  
                x86_instructions.append(f"    pop ebx")  
                x86_instructions.append(f"    cmp eax, ebx")  
                x86_instructions.append(f"    sete al")  
                x86_instructions.append(f"    movzx eax, al")  
                x86_instructions.append(f"    push eax")  
            elif mnemonic == 'CMP_GT':  
                x86_instructions.append(f"    pop ebx")  # Second operand  
                x86_instructions.append(f"    pop eax")  # First operand  
                x86_instructions.append(f"    cmp eax, ebx")  
                x86_instructions.append(f"    setg al")  
                x86_instructions.append(f"    movzx eax, al")  
                x86_instructions.append(f"    push eax")  
            elif mnemonic == 'CMP_GE':  
                x86_instructions.append(f"    pop ebx")  
                x86_instructions.append(f"    pop eax")  
                x86_instructions.append(f"    cmp eax, ebx")  
                x86_instructions.append(f"    setge al")  
                x86_instructions.append(f"    movzx eax, al")  
                x86_instructions.append(f"    push eax")  
            elif mnemonic == 'CMP_LT':  
                x86_instructions.append(f"    pop ebx")  
                x86_instructions.append(f"    pop eax")  
                x86_instructions.append(f"    cmp eax, ebx")  
                x86_instructions.append(f"    setl al")  
                x86_instructions.append(f"    movzx eax, al")  
                x86_instructions.append(f"    push eax")  
            elif mnemonic == 'CMP_LE':  
                x86_instructions.append(f"    pop ebx")  
                x86_instructions.append(f"    pop eax")  
                x86_instructions.append(f"    cmp eax, ebx")  
                x86_instructions.append(f"    setle al")  
                x86_instructions.append(f"    movzx eax, al")  
                x86_instructions.append(f"    push eax")  
            elif mnemonic == 'JMP':  
                address = int(operands[0], 16)  
                label = labels_map.get(address, f"label_{address:04x}")  
                x86_instructions.append(f"    jmp {label}")  
            elif mnemonic == 'JNZ':  
                address = int(operands[0], 16)  
                label = labels_map.get(address, f"label_{address:04x}")  
                x86_instructions.append(f"    pop eax")  
                x86_instructions.append(f"    cmp eax, 0")  
                x86_instructions.append(f"    jne {label}")  
            elif mnemonic == 'JZ':  
                address = int(operands[0], 16)  
                label = labels_map.get(address, f"label_{address:04x}")  
                x86_instructions.append(f"    pop eax")  
                x86_instructions.append(f"    cmp eax, 0")  
                x86_instructions.append(f"    je {label}")  
            elif mnemonic == 'PUTCHAR':  
                x86_instructions.append(f"    pop eax")  
                x86_instructions.append(f"    mov ebx, 1         ; stdout file descriptor")  
                x86_instructions.append(f"    mov ecx, eax       ; character to write")  
                x86_instructions.append(f"    mov edx, 1         ; number of bytes")  
                x86_instructions.append(f"    mov eax, 4         ; sys_write")  
                x86_instructions.append(f"    int 0x80           ; make syscall")  
            else:  
                # Handle other instructions or mark as unimplemented  
                x86_instructions.append(f"    ; Unhandled instruction: {instr_line}")  
  
        return x86_instructions  
  
def main():
    # Validate1
    code = "01 00 00 01 BB AA 06 01 00 01 01 DD CC 06 01 00 02 01 FF EE 06 01 00 03 01 AD DE 06 01 00 04 01 EF BE 06 01 00 05 01 FE CA 06 01 00 06 01 BE BA 06 01 00 07 01 CD AB 06 01 00 0A 01 61 44 06 01 00 0B 01 75 34 06 01 00 0C 01 69 62 06 01 00 0D 01 6C 63 06 01 00 0E 01 31 65 06 01 00 0F 01 66 69 06 01 00 10 01 62 65 06 01 00 11 01 62 30 06 01 00 08 01 00 03 05 01 00 30 1E 01 00 02 05 01 00 20 1E 1B 01 00 01 05 01 00 10 1E 1B 01 00 00 05 1B 06 01 00 09 01 00 07 05 01 00 30 1E 01 00 06 05 01 00 20 1E 1B 01 00 05 05 01 00 10 1E 1B 01 00 04 05 1B 06 01 00 12 01 00 0D 05 01 00 30 1E 01 00 0C 05 01 00 20 1E 1B 01 00 0B 05 01 00 10 1E 1B 01 00 0A 05 1B 06 01 00 13 01 00 11 05 01 00 30 1E 01 00 10 05 01 00 20 1E 1B 01 00 0F 05 01 00 10 1E 1B 01 00 0E 05 1B 06 01 00 14 01 00 00 06 01 00 18 01 00 01 06 01 00 17 01 00 00 06 01 00 19 01 00 00 06 01 00 18 05 01 00 01 11 10 02 41 01 00 14 05 01 00 08 12 10 01 50 01 00 15 01 00 08 05 01 00 08 01 00 14 05 0D 1F 06 01 00 16 01 00 12 05 01 00 08 01 00 14 05 0D 1F 06 01 00 14 05 01 00 07 14 10 01 7D 01 00 15 01 00 09 05 01 00 08 01 00 14 05 0D 1F 06 01 00 16 01 00 13 05 01 00 08 01 00 14 05 0D 1F 06 01 00 15 01 00 15 05 01 00 FF 1C 06 01 00 16 01 00 16 05 01 00 FF 1C 06 01 00 14 05 01 00 02 11 10 01 AC 01 00 16 01 00 16 05 01 00 04 24 06 01 00 14 05 01 00 09 11 10 01 C3 01 00 16 01 00 16 05 01 00 02 25 06 01 00 14 05 01 00 0D 11 10 01 DA 01 00 16 01 00 16 05 01 00 07 24 06 01 00 14 05 01 00 0F 11 10 01 F1 01 00 16 01 00 16 05 01 00 07 24 06 01 00 15 05 01 00 16 05 11 01 00 00 11 10 02 08 01 00 18 01 00 00 06 01 00 15 05 01 00 16 05 11 10 02 20 01 00 17 01 00 17 05 01 00 01 09 06 01 00 14 01 00 14 05 01 00 01 09 06 01 00 14 05 01 00 0F 14 10 02 3E 01 00 18 01 00 00 06 0E 01 18 01 00 17 05 01 00 10 11 10 02 53 01 00 19 01 00 01 06 01 00 19 05 19 18"
    # validate2
    code = "01 00 00 01 BB AA 06 01 00 01 01 DD CC 06 01 00 02 01 FF EE 06 01 00 03 01 AD DE 06 01 00 04 01 EF BE 06 01 00 05 01 FE CA 06 01 00 06 01 BE BA 06 01 00 07 01 CD AB 06 01 00 0A 01 A0 59 06 01 00 0B 01 6A 4D 06 01 00 0C 01 DE 23 06 01 00 0D 01 24 C0 06 01 00 0E 01 64 E2 06 01 00 0F 01 59 B1 06 01 00 10 01 72 07 06 01 00 11 01 7F 5C 06 01 00 08 01 00 03 05 01 00 30 1E 01 00 02 05 01 00 20 1E 1B 01 00 01 05 01 00 10 1E 1B 01 00 00 05 1B 06 01 00 09 01 00 07 05 01 00 30 1E 01 00 06 05 01 00 20 1E 1B 01 00 05 05 01 00 10 1E 1B 01 00 04 05 1B 06 01 00 12 01 00 0D 05 01 00 30 1E 01 00 0C 05 01 00 20 1E 1B 01 00 0B 05 01 00 10 1E 1B 01 00 0A 05 1B 06 01 00 13 01 00 11 05 01 00 30 1E 01 00 10 05 01 00 20 1E 1B 01 00 0F 05 01 00 10 1E 1B 01 00 0E 05 1B 06 01 00 14 01 00 00 06 01 00 15 01 00 01 06 01 00 16 01 00 00 06 01 00 17 01 00 00 06 01 00 1C 01 43 FD 01 00 03 01 00 10 1E 1B 06 01 00 1D 01 9E C3 01 00 26 01 00 10 1E 1B 06 01 00 1B 01 00 01 01 00 1F 1E 06 01 00 1E 01 13 37 06 01 00 15 05 01 00 01 11 10 02 62 01 00 14 05 01 00 08 12 10 01 80 01 00 18 01 00 08 05 01 00 08 01 00 14 05 0D 1F 06 01 00 19 01 00 12 05 01 00 08 01 00 14 05 0D 1F 06 01 00 14 05 01 00 07 14 10 01 AD 01 00 18 01 00 09 05 01 00 08 01 00 14 05 0D 1F 06 01 00 19 01 00 13 05 01 00 08 01 00 14 05 0D 1F 06 01 00 18 01 00 18 05 01 00 FF 1C 06 01 00 19 01 00 19 05 01 00 FF 1C 06 01 00 1E 01 00 1C 05 01 00 1E 05 0D 01 00 1D 05 09 01 00 1B 05 1D 06 01 00 1A 01 00 1E 05 06 01 00 1A 01 00 1E 05 01 00 08 01 00 14 05 01 00 04 1D 0D 1F 06 01 00 1F 01 00 1A 05 01 00 FF 1C 06 01 00 20 01 00 18 05 01 00 1F 05 1A 06 01 00 20 05 01 00 19 05 11 01 00 00 11 10 02 29 01 00 15 01 00 00 06 01 00 20 05 01 00 19 05 11 10 02 41 01 00 16 01 00 16 05 01 00 01 09 06 01 00 14 01 00 14 05 01 00 01 09 06 01 00 14 05 01 00 0F 14 10 02 5F 01 00 15 01 00 00 06 0E 01 48 01 00 16 05 01 00 10 11 10 02 74 01 00 17 01 00 01 06 01 00 16 05 01 00 10 11 01 00 00 11 10 02 8A 01 00 17 01 00 00 06 01 00 17 05 19 18"
    # validate3
    code = "01 00 00 01 BB AA 06 01 00 01 01 DD CC 06 01 00 02 01 FF EE 06 01 00 03 01 AD DE 06 01 00 04 01 EF BE 06 01 00 05 01 FE CA 06 01 00 06 01 BE BA 06 01 00 07 01 CD AB 06 01 00 08 01 00 03 05 01 00 30 1E 01 00 02 05 01 00 20 1E 1B 01 00 01 05 01 00 10 1E 1B 01 00 00 05 1B 06 01 00 09 01 00 07 05 01 00 30 1E 01 00 06 05 01 00 20 1E 1B 01 00 05 05 01 00 10 1E 1B 01 00 04 05 1B 06 01 00 1E 01 FF FF 06 01 00 1D 01 00 1E 05 06 01 00 1E 01 00 1E 05 01 00 10 1E 01 00 1D 05 1B 06 01 00 1B 01 00 00 06 01 00 1F 01 00 00 06 01 00 20 01 00 00 06 01 00 13 01 15 05 06 01 00 1B 05 01 00 04 12 10 01 0F 01 00 1C 01 00 08 05 01 00 08 01 00 1B 05 0D 1F 06 01 00 1C 01 00 1C 05 01 00 FF 1C 06 01 00 1D 01 00 13 05 06 01 00 13 01 00 13 05 01 00 05 1E 01 00 1D 05 09 01 00 1C 05 09 06 01 00 1B 01 00 1B 05 01 00 01 09 06 0E 00 BA 01 00 13 01 00 13 05 01 00 1E 05 1C 06 01 00 14 01 7C 8D 01 00 10 1E 01 F4 CB 1B 06 01 00 14 05 01 00 13 05 11 10 01 43 01 00 1F 01 00 1F 05 01 00 01 09 06 01 00 1F 05 01 00 00 14 10 01 D9 01 00 15 01 00 00 06 01 00 1B 05 01 00 08 12 10 01 A5 01 00 1C 01 00 08 05 01 00 08 01 00 1B 05 0D 1F 06 01 00 1C 01 00 1C 05 01 00 FF 1C 06 01 00 15 01 00 15 05 01 00 0D 21 06 01 00 15 01 00 15 05 01 00 1C 05 09 06 01 00 1B 01 00 1B 05 01 00 01 09 06 0E 01 55 01 00 15 01 00 15 05 01 00 1E 05 1C 06 01 00 16 01 8B 68 01 00 10 1E 01 1D 82 1B 06 01 00 16 05 01 00 15 05 11 10 01 D9 01 00 1F 01 00 1F 05 01 00 01 09 06 01 00 1F 05 01 00 01 14 10 02 9E 01 00 11 01 00 01 06 01 00 12 01 00 00 06 01 00 17 01 00 00 06 01 00 1B 01 00 00 06 01 00 1B 05 01 00 08 12 10 02 59 01 00 1C 01 00 09 05 01 00 08 01 00 1B 05 0D 1F 06 01 00 1C 01 00 1C 05 01 00 FF 1C 06 01 00 11 01 00 11 05 01 00 1C 05 09 01 FF F1 1D 06 01 00 12 01 00 12 05 01 00 11 05 09 01 FF F1 1D 06 01 00 1B 01 00 1B 05 01 00 01 09 06 0E 02 00 01 00 17 01 00 12 05 01 00 10 1E 01 00 11 05 1B 06 01 00 17 01 00 17 05 01 00 1E 05 1C 06 01 00 18 01 0F 91 01 00 10 1E 01 03 74 1B 06 01 00 18 05 01 00 17 05 11 10 02 9E 01 00 1F 01 00 1F 05 01 00 01 09 06 01 00 1F 05 01 00 02 14 10 03 B2 01 00 0A 01 01 93 06 01 00 0B 01 01 00 06 01 00 0C 01 00 0B 05 01 00 10 1E 01 00 0A 05 1B 06 01 00 0D 01 9D C5 06 01 00 0E 01 81 1C 06 01 00 0F 01 00 0E 05 01 00 10 1E 01 00 0D 05 1B 06 01 00 10 01 00 01 01 00 20 1E 06 01 00 19 01 00 0F 05 06 01 00 1B 01 00 00 06 01 00 1B 05 01 00 10 12 10 03 7E 01 00 1B 05 01 00 08 12 10 03 28 01 00 1C 01 00 08 05 01 00 08 01 00 1B 05 0D 1F 06 01 00 1B 05 01 00 07 14 10 03 44 01 00 1C 01 00 09 05 01 00 08 01 00 1B 05 0D 1F 06 01 00 1C 01 00 1C 05 01 00 FF 1C 06 01 00 19 01 00 19 05 01 00 0C 05 0D 01 00 10 05 1D 06 01 00 19 01 00 19 05 01 00 1C 05 1A 06 01 00 1B 01 00 1B 05 01 00 01 09 06 0E 03 01 01 00 19 01 00 19 05 01 00 1E 05 1C 06 01 00 1A 01 31 F0 01 00 10 1E 01 09 D2 1B 06 01 00 1A 05 01 00 19 05 11 10 03 B2 01 00 1F 01 00 1F 05 01 00 01 09 06 01 00 1F 05 01 00 04 11 10 03 C4 01 00 20 01 00 01 06 01 00 20 05 19 18"
    
    code = bytearray(bytes.fromhex(code.replace(" ", "")))
  
    disassembler = VMDisassembler(code)  
    disassembler_output = disassembler.disassemble()  
  
    print("Disassembled VM Instructions:")  
    for line in disassembler_output:  
        print(line)  
  
    x86_code = disassembler.translate_to_x86()  
  
    print("\nTranslated x86 Assembly Code:")  
    for line in x86_code:  
        print(line)  
  
if __name__ == "__main__":  
    main()
