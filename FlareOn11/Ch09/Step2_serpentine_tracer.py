import ida_allins as iins
import idaapi as ia
import ida_dbg as idbg

srt_addr = 0x140097AF0 # get_name_ea(0, "code")
va_base_addr = ia.get_qword(get_name_ea(0, "lpAddress"))
int_b = lambda a:int.from_bytes(a, "little")

if not idbg.is_debugger_on():
    print(f"Debugger is not running")
    exit(1)

def Handle_Exception(exception_addr):
    """
    Get the next address to jump to after exception
    """
    exc_ofst = exception_addr - va_base_addr
    exp_addr = srt_addr + exc_ofst
    end_addr = exp_addr + 1
    unw_addr = int_b(get_bytes(end_addr, 1)) + (end_addr - srt_addr) + 1
    unw_addr = unw_addr + (unw_addr & 1 != 0)
    # Get UnWind header (4-bytes)
    unw_info = get_bytes(srt_addr + unw_addr, 4)
    # 3rd bytes is count of codes
    unw_cofc = unw_info[2]
    # skip the header
    skp_addr = 4
    # Skip unwind_code bytes if any
    if unw_cofc > 0:
        # count of bytes * 2 (each code is 2 bytes)
        skp_addr += unw_cofc * 2
        skp_addr += (unw_cofc % 2) * 2
    # Get the next address
    nxt_addr = 0
    runtime_va = va_base_addr
    nxt_addr = runtime_va + int_b(get_bytes(srt_addr + unw_addr + skp_addr, 4))
    create_insn(nxt_addr)
    return add_bpt(nxt_addr)

def get_operand_actual_value(pc, idx, ins):
    op_value = None
    # if operand 1 is of type 1, then it's a register
    if ins.ops[idx].type == ia.o_reg:
        reg_name = ia.get_reg_name(ins.ops[idx].reg, 8)
        op_value = idbg.get_reg_val(reg_name)
    # else if operand type is 4, then it's a memory address
    elif ins.ops[idx].type == ia.o_displ:
        # GEt the register name
        #read_dbg_qword(get_reg_value(ia.get_reg_name(ins.ops[0].reg, 8))+get_operand_value(get_screen_ea(), 0))
        reg_name = ia.get_reg_name(ins.ops[idx].reg, 8)
        offset = get_operand_value(pc, idx)
        op_value = read_dbg_qword(get_reg_value(reg_name) + offset)
    return op_value

# Initialize some variables
ins   = ia.insn_t()
ins_n = ia.insn_t()
excpt_cnt = 0
threshold = 90
ah_opv = 0
ah_set = False
# Importantly, this is the address of the function that we want to reach
pc            = 0x00000000
final_pc      = 0x1400011F0 # get_name_ea(0,"PrintWrongKey")
final_success = 0x1400011B0
mon_instr = [iins.NN_mul, iins.NN_add, iins.NN_sub, iins.NN_xor, iins.NN_shl]

new_block = True
mul_state = False
shl_state = False
transform_check_requ = True
curr_prod_t_check_requ = True
mul_count = 0
shl_reg = None
data_table = dict()
data_table[0] = {"pc": 0, "key_byte": 0, "constant": 0, "curr_prod": 0, "prev_prod":0, "curr_prod_t": 0, "curr_prod_t_op": None, "transform_op": None, "final_prod": 0}

data_table_test = {}
# data_table_test[1] = {}
# data_table_test[1]["pc"] = 0
# data_table_test[1]["key_byte"] = 0x4E
# data_table_test[1]["constant"] = 0x640BA9
# data_table_test[1]["curr_prod"] = 0x1E7B8D7E
# data_table_test[1]["prev_prod"] = None
# data_table_test[1]["curr_prod_t"] = None
# data_table_test[1]["curr_prod_t_op"] = None
# data_table_test[1]["transform_op"] = 'add'
# data_table_test[1]["final_prod"] = 0

# data_table_test[2] = {}
# data_table_test[2]["pc"] = 0
# data_table_test[2]["key_byte"] = 0x61
# data_table_test[2]["constant"] = 0xF1D9E5
# data_table_test[2]["curr_prod"] = 0x5BA38FC5
# data_table_test[2]["prev_prod"] = 0x6FE807DA
# data_table_test[2]["curr_prod_t"] = 0x14447815
# data_table_test[2]["curr_prod_t_op"] = 'sub'
# data_table_test[2]["transform_op"] = 'add'
# data_table_test[2]["final_prod"] = 0

# while pc != final_pc and excpt_cnt <= threshold:
while pc != final_pc and pc != final_success:
    # get current PC
    pc = idbg.get_ip_val()
    # get current instruction
    ins_sz = ia.decode_insn(ins, pc)
    # ins.get_canon_mnem() => get the canonical mnemonic of the instruction
    curr_instr = ins.itype
    if curr_instr in mon_instr:
        # print all states
        # print(f"PC={pc:x}, new_block={new_block}, mul_state={mul_state}, shl_state={shl_state}, transform_check_requ={transform_check_requ}, curr_prod_t_check_requ={curr_prod_t_check_requ}")
        # processing => mul qword ptr ss:[rsp]
        if curr_instr == iins.NN_mul:
            mul_count += 1
            data_table[mul_count] = {"pc":pc, "key_byte": None, "constant": None, "curr_prod": None, "prev_prod":None, "curr_prod_t": None, "curr_prod_t_op": None, "transform_op": None, "final_prod": 0}
            mul_state = True
            shl_state = False
            curr_prod_t_check_requ = True
            transform_check_requ = True
            if iins.NN_mov not in mon_instr:
                mon_instr.append(iins.NN_mov)
            # here rax has the key byte and the value at [rsp] is the constant
            key_byte = idbg.get_reg_val("rax")
            constant = read_dbg_qword(get_reg_value("rsp"))
            data_table[mul_count]["key_byte"] = key_byte
            data_table[mul_count]["constant"] = constant
            # memory_at_rsp = read_dbg_qword(get_reg_value("rsp")+get_operand_value(get_screen_ea(), 0))
            idbg.step_into()
            idbg.wait_for_next_event(idbg.WFNE_SUSP, -1)
            # Collect the multiplication result
            mul_result = idbg.get_reg_val("rax")
            data_table[mul_count]["curr_prod"] = mul_result
            # Test the values obtained against the test result else break
            # if mul_count in data_table_test:
            #     if not data_table_test[mul_count]["curr_prod"] == mul_result:
            #         print(f"Test failed at {pc:x} for mul_count={mul_count}, curr_prod={mul_result:x} and expected={data_table_test[mul_count]['curr_prod']:x}")
            #         break
            #     if data_table_test[mul_count]["key_byte"] != key_byte:
            #         print(f"Test failed at {pc:x} for mul_count={mul_count}, key_byte={key_byte:x} and expected={data_table_test[mul_count]['key_byte']:x}")
            #         break
            #     if data_table_test[mul_count]["constant"] != constant:
            #         print(f"Test failed at {pc:x} for mul_count={mul_count}, constant={constant:x} and expected={data_table_test[mul_count]['constant']:x}")
            #         break
        # processing => sub rdi,qword ptr ds:[r10+E0]
        elif not new_block and curr_instr in [iins.NN_add, iins.NN_sub, iins.NN_xor] and mul_state and curr_prod_t_check_requ:
            op1_value = None
            op2_value = None
            # mul_state is set accordingly down in the code based on certain conditions
            # get the values from both operands based on their type
            #ia.get_reg_name(ins.ops[1].reg, 8) => get the register name
            op1_value = get_operand_actual_value(pc, 0, ins)
            op2_value = get_operand_actual_value(pc, 1, ins)
            # now check if any of the operand is the result of the previous multiplication
            if mul_count in data_table:
                this_mul = data_table[mul_count].get("curr_prod", None)
                if this_mul:
                    # get the result of the previous multiplication and the index of the operand which will contain the transformed value
                    match_prev_result = False
                    if this_mul == op1_value:
                        data_table[mul_count]["prev_prod"] = op2_value
                        match_prev_result = True
                    elif this_mul == op2_value:
                        data_table[mul_count]["prev_prod"] = op1_value
                        match_prev_result = True
                    # Check if this instruction does operation on the result of the current multiplication
                    if match_prev_result:
                        mul_state = False
                        curr_prod_t_check_requ = False
                        # Step into to get the result of the transofrmation
                        idbg.step_into()
                        idbg.wait_for_next_event(idbg.WFNE_SUSP, -1)
                        # Get the transformation result
                        result = get_operand_actual_value(pc, 0, ins)
                        data_table[mul_count]["curr_prod_t"] = result
                        # get the operation that was performed on the result
                        data_table[mul_count]["curr_prod_t_op"] = ins.get_canon_mnem()
                        # Test the values obtained against the test result else break
                        # if mul_count in data_table_test:
                        #     if not data_table_test[mul_count]["curr_prod_t"] == result:
                        #         print(f"Test failed at {pc:x} for mul_count={mul_count}, curr_prod_t={result:x} and expected={data_table_test[mul_count]['curr_prod_t']:x}")
                        #         print(data_table)
                        #         break
                        #     if data_table_test[mul_count]["prev_prod"] != data_table[mul_count]["prev_prod"]:
                        #         print(f"Test failed at {pc:x} for mul_count={mul_count}, prev_prod={data_table[mul_count]['prev_prod']:x} and expected={data_table_test[mul_count]['prev_prod']:x}")
                        #         print(data_table)
                        #         break
                        #     if data_table_test[mul_count]["curr_prod_t_op"] != data_table[mul_count]["curr_prod_t_op"]:
                        #         print(f"Test failed at {pc:x} for mul_count={mul_count}, curr_prod_t_op={data_table[mul_count]['curr_prod_t_op']} and expected={data_table_test[mul_count]['curr_prod_t_op']}")
                        #         print(data_table)
                        #         break
            idbg.step_into()
            idbg.wait_for_next_event(idbg.WFNE_SUSP, -1)
        elif curr_instr == iins.NN_shl and ins.Op2.__get_value64__() == 8 and transform_check_requ and not shl_state:
            new_block = False
            mul_state = False
            shl_state = True # We are setting that shl operation is performed
            # print(f"Shl operation is performed at {pc:x}")
            shl_reg = ia.get_reg_name(ins.Op1.__get_reg_phrase__(), 8)
            idbg.step_into()
            idbg.wait_for_next_event(idbg.WFNE_SUSP, -1)
            # Step into to get the
        elif curr_instr in [iins.NN_add, iins.NN_sub] and shl_state and transform_check_requ and shl_reg == ia.get_reg_name(ins.Op2.__get_reg_phrase__(), 8):
            transform_check_requ = False
            shl_state = False
            shl_reg = None
            # print(f"Add or Sub operation is performed at {pc:x}")
            data_table[mul_count]["transform_op"] = ins.get_canon_mnem()
            idbg.step_into()
            idbg.wait_for_next_event(idbg.WFNE_SUSP, -1)
        # handle instruction like this mov rdx,FF to tell if transformation op is found or not
        elif curr_instr == iins.NN_mov and transform_check_requ and ins.Op2.__get_value64__() == 0xFF:
            new_block = False
            mul_state = False
            transform_check_requ = False
            if iins.NN_mov in mon_instr:
                mon_instr.remove(iins.NN_mov)
            data_table[mul_count]["transform_op"] = "xor"
            # Check if the shl state is still true, if so it mean no shl operation was performed and thus the transformation operation is xor
            if shl_state: # Shl state is still true so it means no add or sub operation was performed
                data_table[mul_count]["transform_op"] = "xor_shl"
            # do the test here
            # if mul_count in data_table_test:
            #     if not data_table_test[mul_count]["transform_op"] == data_table[mul_count]["transform_op"]:
            #         print(f"Test failed at {pc:x} for mul_count={mul_count}, transform_op={data_table[mul_count]['transform_op']} and expected={data_table_test[mul_count]['transform_op']}")
            #         print(data_table)
            #         break
            idbg.step_into()
            idbg.wait_for_next_event(idbg.WFNE_SUSP, -1)
        else:
            idbg.step_into()
            idbg.wait_for_next_event(idbg.WFNE_SUSP, -1)
    # if this is a pop instruction then runto pc + 33
    elif curr_instr == iins.NN_pop:
        idbg.run_to(pc + 34) # Skip all nops
        idbg.wait_for_next_event(idbg.WFNE_SUSP, -1)
    # if this is a nop instruction then runto pc + 9
    elif curr_instr == iins.NN_nop:
        idbg.step_until_ret() # step till return
        idbg.wait_for_next_event(idbg.WFNE_SUSP, -1)
    elif curr_instr == iins.NN_jmp:
        # if hlt instruction is found continue to run
        ## ia.decode_insn(ins, get_operand_value(get_screen_ea(), 0))
        jump_addr = get_operand_value(pc, 0)
        _ = ia.decode_insn(ins_n, jump_addr)
        if ins_n.itype == iins.NN_hlt:
            excpt_cnt += 1
            hlt_addr = jump_addr
            bpt_status = Handle_Exception(hlt_addr)
            if not bpt_status:
                break
            idbg.continue_process()
            idbg.wait_for_next_event(idbg.WFNE_SUSP, -1)
        else:
            idbg.step_into()
            idbg.wait_for_next_event(idbg.WFNE_SUSP, -1)
    elif curr_instr == iins.NN_test and ins.ops[0].type == ia.o_reg:
        new_block = True
        data_table[mul_count]["final_prod"] = get_operand_actual_value(pc, 0, ins)
        reg_name = ia.get_reg_name(get_operand_value(pc, 0), 8)
        idbg.set_reg_val(reg_name, 0)
        idbg.step_into()
        idbg.wait_for_next_event(idbg.WFNE_SUSP, -1)
    else:
        idbg.step_into()
        idbg.wait_for_next_event(idbg.WFNE_SUSP, -1)

print(data_table)
print(f"Done for {excpt_cnt} exceptions and mul_count={mul_count}")
