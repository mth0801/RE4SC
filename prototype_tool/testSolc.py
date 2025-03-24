import sys
import solcx
import json
import pyevmasm
import re

def func_solc(Automata_contract):
    solcx.install_solc("0.4.24")
    solcx.set_solc_version("0.4.24")
    current_version = solcx.get_solc_version()
    print(f"当前使用的Solidity编译器版本: {current_version}")

    compiled_sol = solcx.compile_source(
        Automata_contract, output_values=["abi", "bin", "bin-runtime"]
    )

    contracts_bytecode = {}
    for contract_id, contract_interface in compiled_sol.items():
        abi = contract_interface["abi"]
        full_bytecode = contract_interface["bin"]
        runtime_bytecode = contract_interface["bin-runtime"]

        print(f"Contract: {contract_id}")
        print("ABI:", json.dumps(abi, indent=2))
        print("full_bytecode:", full_bytecode)
        print("runtime_bytecode:", runtime_bytecode)

        contracts_bytecode[contract_id] = (full_bytecode, runtime_bytecode)

    return contracts_bytecode


def bytecode_to_opcodes(_bytecode):
    instructions = list(pyevmasm.disassemble_all(_bytecode))
    opcodes = []
    for instr in instructions:
        if instr.operand is not None:
            opcodes.append(f"{instr.mnemonic}")
            opcodes.append(f"0x{instr.operand:x}")
        else:
            opcodes.append(instr.mnemonic)
    return opcodes


def main():
    with open(
        ".../REEVM/test_smartcontract_dataset/Elysium_positive_reentrant_contracts_dataset/modifier_reentrancy.sol",
        "r",
    ) as file:
        Automata_contract = file.read()

    contracts_bytecode = func_solc(Automata_contract)

    # # 将真实库地址替换未链接状态下的占位符
    # for key in contracts_bytecode.keys():
    #     the_tuple_key_mapping_to = contracts_bytecode[key]
    #     index = 0
    #     while index < len(the_tuple_key_mapping_to):
    #         pattern = r"__<stdin>:ECTools_______________________"  # 具体占位符
    #         replacement = (
    #             "cb107c7d2a93e638b20342f46b10b9b6d81377bf"  # 用于替换占位符的具体库地址
    #         )
    #         # 使用 re.sub 函数进行替换
    #         new_bytecode = re.sub(pattern, replacement, the_tuple_key_mapping_to[index])
    #         the_list_key_mapping_to = list(the_tuple_key_mapping_to)
    #         the_list_key_mapping_to[index] = new_bytecode
    #         the_tuple_key_mapping_to = tuple(the_list_key_mapping_to)
    #         index += 1
    #     contracts_bytecode[key] = the_tuple_key_mapping_to

    for contract_id, (full_bytecode, runtime_bytecode) in contracts_bytecode.items():
        full_opcode = bytecode_to_opcodes(bytes.fromhex(full_bytecode))
        runtime_opcode = bytecode_to_opcodes(bytes.fromhex(runtime_bytecode))

        print(f"{contract_id} full_opcode: {full_opcode}")
        print(f"{contract_id} runtime_opcode: {runtime_opcode}")

    contract_id = "<stdin>:ModifierEntrancy"  # 需要指定当前.sol的具体合约
    current_full_bytecode, current_runtime_bytecode = contracts_bytecode[contract_id]

    runtime_opcode_without_metadatahash = current_runtime_bytecode[:-88]  # [:-88]可去除
    runtime_opcode = bytecode_to_opcodes(
        bytes.fromhex(runtime_opcode_without_metadatahash)
    )

    with open("/Users/miaohuidong/demos/REEVM/test_txt/bytecode2.txt", "w") as f:
        for opcode in runtime_opcode:
            f.write(opcode + "\n")
    print("target bytecode has been written into bytecode2.txt")


if __name__ == "__main__":
    main()
