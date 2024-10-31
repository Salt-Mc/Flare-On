import ida_allins as iins
import idaapi as ia
import ida_dbg as idbg
import ida_bytes as ib
from time import sleep

addr_table = dict() # Holds Exception_address : Exception_handler

srt_addr = 0x140097AF0 # get_name_ea(0, "code")
va_base_addr = ia.get_qword(get_name_ea(0, "lpAddress"))

int_b = lambda a:int.from_bytes(a, "little")

def Handle_Exception(exception_addr):

    exc_ofst = exception_addr - va_base_addr
    exp_addr = srt_addr + exc_ofst
    end_addr = exp_addr + 1
    unw_addr = int_b(get_bytes(end_addr, 1)) + (end_addr - srt_addr) + 1
    unw_addr = unw_addr + (unw_addr & 1 != 0)

    unw_info = get_bytes(srt_addr + unw_addr, 4) # Get UnWind header (4-bytes)
    unw_cofc = unw_info[2]                       # 3rd bytes is count of codes

    skp_addr = 4 # skip the header

    # Skip unwind_code bytes if any
    if unw_cofc > 0:
        # count of bytes * 2 (each code is 2 bytes)
        skp_addr += unw_cofc * 2
        skp_addr += (unw_cofc % 2) * 2
    
    nxt_addr = 0
    runtime_va = va_base_addr
    nxt_addr = runtime_va + int_b(get_bytes(srt_addr + unw_addr + skp_addr, 4))
    create_insn(nxt_addr)
    return add_bpt(nxt_addr)

def can_continue():
    # check if we can query debugger
    sleep(0.2)
    while idbg.dbg_can_query() == False:
        print("Can't query debugger now")
        sleep(0.8)

def check_make_code(ea, sz=1):
    F = ib.get_flags(ea)
    if not ib.is_code(F):
        ib.del_items(ea,sz)
        create_insn(ea)  

if not idbg.is_debugger_on():
    exit(0)

ins = ia.insn_t()
ins_n = ia.insn_t()
excpt_cnt = 0
threshold = 90
ah_opv = 0
ah_set = False
pc            = 0x00000000
final_pc      = 0x1400011F0 # get_name_ea(0,"PrintWrongKey")
final_success = 0x1400011B0

while pc not in [final_pc, final_success]:
    pc = idbg.get_ip_val()
    # get current instruction
    ins_sz = ia.decode_insn(ins, pc)
    curr_instr = ins.itype
    # create code if not at PC
    check_make_code(pc, ins_sz)
    n_pc = 0x00000000
    # get the next address
    n_pc = get_first_cref_from(pc)
    if n_pc == 0xffffffffffffffff:
        n_pc = get_first_cref_from(pc)
    if n_pc == 0xffffffffffffffff:
        n_pc = pc + ins_sz
    # get next instruction size
    ins_sz = ia.decode_insn(ins, n_pc)
    # print("n_pc", hex(n_pc))
    ins_n_sz = ia.decode_insn(ins_n, n_pc + ins_sz)
    # print("n_pc_n", hex(n_pc + ins_sz))
    # check if next instruction is moving bytes to current PC
    if ins.itype == iins.NN_mov:
        # get the first operand which is the offset to move
        op_val = get_operand_value(n_pc, 0)
        # print(f"mov 1st operand {op_val:x} and ah_opv {ah_opv:x}")
        # check if it's equal to pc
        if op_val == pc:
            # print(f"next ip = {hex(n_pc)}")
            # create instruction size times NOP bytes
            patch_byts = b'\x90'*ins_sz
            # Patch the bytes at PC with NOP bytes
            ia.patch_bytes(n_pc, patch_byts)
            ia.patch_bytes(pc-0x1C, b'\x90'*0x1C)
            # Undefine bytes at PC
            ib.del_items(n_pc, 0, ins_sz)
            # Create code at PC
            create_insn(n_pc)
            # Single step
            # idbg.run_to(n_pc + ins_sz + -1) # +1 is for push rax
            idbg.step_until_ret() # step till return
            idbg.wait_for_next_event(idbg.WFNE_SUSP, -1)
        # # Check for patter where instr @PC=MOV, @n_PC=MOV ah and ah is set before
        # elif op_val == 20 and ah_set and curr_instr == iins.NN_mov:
        #     print(f"setting correct value of ah to {ah_opv:x}")
        #     idbg.step_into()
        #     idbg.wait_for_next_event(idbg.WFNE_SUSP, -1)
        #     idbg.step_into()
        #     idbg.wait_for_next_event(idbg.WFNE_SUSP, -1)
        #     idbg.set_reg_val("rax", 0)
        #     idbg.set_reg_val("ah", ah_opv)
        #     ah_set = False
        #     can_continue()
        # # if  lea rax, [rax+n]
        # elif ins_n.itype == iins.NN_lea and get_operand_value(n_pc + ins_sz, 1) <= 5:
        #     lea_bytes = get_operand_value(n_pc + ins_sz, 1)
        #     # This code block will convert the 2 bytes before the return address to NOP
        #     nxt_ptch_addr = get_operand_value(n_pc, 1)
        #     if not ah_set:
        #         ah_opv = nxt_ptch_addr.to_bytes(4, "little")[0]
        #         ah_set = True
        #     print(f"next ah = {ah_opv:x}")
        #     print("Patching with NOP, POP RAX at", hex(nxt_ptch_addr))
        #     ia.patch_bytes(nxt_ptch_addr, b'\x90'*(lea_bytes-1) + b'\x58')
        #     check_make_code(nxt_ptch_addr, lea_bytes)
        #     # This code is to change the 'mov' inst at n_pc to `jmp`
        #     jmp_addr = nxt_ptch_addr + lea_bytes - 1 # to jump to pop rax 
        #     jmp_byts = jmp_addr - (n_pc + 0x5)
        #     jmp_byts = jmp_byts.to_bytes(4, "little", signed=True)
        #     jmp_byts = b'\xe9' + jmp_byts
        #     print("jmp_bytes = ", jmp_byts)
        #     ia.patch_bytes(n_pc, jmp_byts)
        #     # delete previously declared instruction and make again
        #     ib.del_items(n_pc+2)
        #     create_insn(n_pc)
        #     # # idbg.step_until_ret()
        #     idbg.run_to(jmp_addr+1)
        #     idbg.wait_for_next_event(idbg.WFNE_SUSP, -1)
        else:
            idbg.step_into()
            idbg.wait_for_next_event(idbg.WFNE_SUSP, -1)
    elif ins.itype == iins.NN_hlt and curr_instr == iins.NN_jmp:
        # if hlt instruction is found continue to run
        excpt_cnt += 1
        hlt_addr = get_operand_value(pc, 0)
        bpt_status = Handle_Exception(hlt_addr)
        if not bpt_status:
            break
        idbg.continue_process()
        idbg.wait_for_next_event(idbg.WFNE_SUSP, -1)
        # # patch retroaspectively
        # if excpt_follow_addr != -1:
        #     n_jmp_byts = excpt_follow_addr - (pc + 0x5)
        #     n_jmp_byts = n_jmp_byts.to_bytes(4, "little", signed=True)
        #     n_jmp_byts = b'\xe9' + n_jmp_byts
        #     print(f"Patching the jmp at {pc:x} originally to {hlt_addr:x} with next {excpt_follow_addr:x}")
        #     ia.patch_bytes(pc, n_jmp_byts)
        #     # Also path the previous junk of 0x22 bytes
        ia.patch_bytes(pc-0x1C, b'\x90'*0x1C)
    elif curr_instr == iins.NN_test and get_operand_type(pc, 0) == 1:
        print(f"Bypassing the test check at {pc:x}")
        reg_name = ia.get_reg_name(get_operand_value(pc, 0), 8)
        idbg.set_reg_val(reg_name, 0)
        idbg.step_into()
        idbg.wait_for_next_event(idbg.WFNE_SUSP, -1)
    else:
        # step one instruction
        idbg.step_into()
        idbg.wait_for_next_event(idbg.WFNE_SUSP, -1)

print(f"Done for {excpt_cnt} exceptions")
