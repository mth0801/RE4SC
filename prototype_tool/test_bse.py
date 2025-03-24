from testSolc import func_solc
from bse_version2 import (
    bytecode_to_opcodes,
    convert_to_symbolic_bytecode,
    SymbolicBytecodeExecutor,
    Analysis1FunctionBodyOffChain,
    Analysis2FunctionBodyOffChain,
    Analysis3FunctionBodyOffChain,
    Analysis4FunctionBodyOffChain,
    Analysis5FunctionBodyOffChain,
)
import time
import re

all_single_part_execution_time = []
all_single_all_execution_time = []


def instantiated_main_body(
    runtime_opcode,
    designated_functions_index_range,
    is_or_not_determine_whether_the_consistency_of_data_dependency_relationships_is_met,
    critical_state_variable_assigned_value_opcodes_number,
):
    if critical_state_variable_assigned_value_opcodes_number == 0:
        raise UnboundLocalError("The function has finished its reorder!")
    else:
        print(f"current runtime_opcode: {runtime_opcode}")
        symbolic_bytecode = convert_to_symbolic_bytecode(runtime_opcode)
        # 执行符号字节码
        print(f"symbolic_bytecode:{symbolic_bytecode}")
        executor = SymbolicBytecodeExecutor(symbolic_bytecode, runtime_opcode)

        all_single_all_execution_time.append(time.time())
        print(f"all_single_all_execution_time: {all_single_all_execution_time}")

        all_stacks = executor.execute()
        # print(all_stacks)  # 输出符号表达式堆栈，例如: [v0 + v1 - v2, pc, msize, gas]

        # function_start_index = executor.get_max_stop_return_index()
        # print(f"function_start_index: {function_start_index}")

        # # 在模拟执行完毕后调用
        # cfg = executor.create_control_flow_graph()
        # print(f"cfg: {cfg}")
        # print(type(cfg))
        # # cfg.render('control_flow_graph', format='png')  # 保存为 PNG 文件
        # # cfg.view()  # 显示控制流图

        # print(executor.visited_nodes_index_by_jumpi)
        # print(type(executor.visited_nodes_index_by_jumpi))
        # print(executor.exist_loop_node_by_jumpi)
        # print(f"executor.exist_loop_node_by_jumpi: {executor.exist_loop_node_by_jumpi}")

        # # 查询指定索引位置的操作码的PC位置
        # test_index = 17  # 替换为你需要查询的索引位置
        # pc_position = executor.get_pc_position(test_index)
        # print(f"索引位置 {test_index} 对应的PC位置是: {pc_position}")

        # # 查询指定PC位置的操作码的索引位置
        # test_pc = 46  # 替换为你需要查询的索引位置
        # index_position = executor.get_index_position(test_pc)
        # print(f"PC位置 {test_pc} 对应的索引位置是: {index_position}")

        executor.stack_snapshots = dict(sorted(executor.stack_snapshots.items()))
        print(f"executor.stack_snapshots: {executor.stack_snapshots}")
        print(f"executor.opcodeindex_to_stack: {executor.opcodeindex_to_stack}")  # ?
        print(
            f"executor.smartcontract_functions_index_range: {executor.smartcontract_functions_index_range}"
        )

        # # print(executor.stack_snapshots[232])
        # # print(executor.stack_snapshots[241])
        # # print(executor.stack_snapshots[276])

        all_single_part_execution_time.append(time.time())
        print(f"all_single_part_execution_time: {all_single_part_execution_time}")

        analysis1_function_body_off_chain_machine = Analysis1FunctionBodyOffChain(
            executor
        )
        temporary_variable_quantity, take_special_stack_snapshots_index = (
            analysis1_function_body_off_chain_machine.count_consecutive_push_0_push_60_dup1(
                designated_functions_index_range
            )
        )
        print(f"temporary_variable_quantity: {temporary_variable_quantity}")
        print(
            f"take_special_stack_snapshots_index: {take_special_stack_snapshots_index}"
        )
        # 现在跳转地址是能够具体确定的，包括显式和隐式都可以确定，我们采用的是获取堆栈顶部操作数的方法来确定的

        analysis2_function_body_off_chain_machine = Analysis2FunctionBodyOffChain(
            executor,
            take_special_stack_snapshots_index,
            designated_functions_index_range,
        )
        old_jump_structure_info = analysis2_function_body_off_chain_machine.traverse_designated_function_bytecode(
            executor.smartcontract_functions_index_range[
                designated_functions_index_range
            ],
            executor.smartcontract_functions_index_range[
                designated_functions_index_range
            ],
            current_jump_depth=0,
        )
        print(f"old_jump_structure_info: {old_jump_structure_info}")

        analysis3_function_body_off_chain_machine = Analysis3FunctionBodyOffChain(
            executor,
            take_special_stack_snapshots_index,
            designated_functions_index_range,
            old_jump_structure_info,
        )
        new_jump_structure_info = (
            analysis3_function_body_off_chain_machine.bytecode_ByteDance_granularity_segmentation_by_jump_depth()
        )

        analysis4_function_body_off_chain_machine = Analysis4FunctionBodyOffChain(
            executor,
            take_special_stack_snapshots_index,
            designated_functions_index_range,
            new_jump_structure_info,
            temporary_variable_quantity,
        )

        all_create_opcodes_index_list = (
            analysis4_function_body_off_chain_machine.search_all_create_opcode()
        )  # 当前函数内的所有CREATE操作码的index位置
        print(f"all_create_opcodes_index_list: {all_create_opcodes_index_list}")

        transfer_accounts_opcodes_index_list = (
            analysis4_function_body_off_chain_machine.search_transfer_accounts_opcode(
                executor.smartcontract_functions_index_range[
                    designated_functions_index_range
                ][0],
                executor.smartcontract_functions_index_range[
                    designated_functions_index_range
                ][1],
            )
        )  # 关键CALL操作码的index位置

        print(
            f"transfer_accounts_opcodes_index_list: {transfer_accounts_opcodes_index_list}"
        )

        # all_single_part_execution_time.append(time.time())
        # print(f"all_single_part_execution_time: {all_single_part_execution_time}")
        # all_single_all_execution_time.append(time.time())
        # print(f"all_single_all_execution_time: {all_single_all_execution_time}")

        if len(transfer_accounts_opcodes_index_list) == 0:
            raise UnboundLocalError("The function does not have transfer money block!")

        # critical_state_variable_assigned_value_opcodes_index_list = (
        #     analysis4_function_body_off_chain_machine.search_critical_state_variable_assigned_value_opcode_by_critical_branch_jump_structure()
        # )  # 当前函数内的关键SSTORE操作码的index位置
        critical_state_variable_assigned_value_opcodes_index_list = (
            analysis4_function_body_off_chain_machine.search_all_critical_state_variable_assigned_value_opcode()
        )  # 当前函数内的转帐之后的所有SSTORE操作码的index位置

        all_single_part_execution_time.append(time.time())
        print(f"all_single_part_execution_time: {all_single_part_execution_time}")
        all_single_all_execution_time.append(time.time())
        print(f"all_single_all_execution_time: {all_single_all_execution_time}")

        if len(critical_state_variable_assigned_value_opcodes_index_list) == 0:
            raise UnboundLocalError(
                "The function does not have status variables assignment block!"
            )

        final_jump_structure1, final_jump_structure2 = (
            analysis4_function_body_off_chain_machine.search_parent_jump_structure_in_the_same_deepest_detecting_range()
        )
        if analysis4_function_body_off_chain_machine.step1_can_reorder_or_not:
            # 先检查关键状态变量赋值块中的被赋值项和传播项
            (
                critical_propagation_items,
                critical_assigned_items,
                index_mapping_to_critical_propagation_items,
                index_mapping_to_critical_assigned_items,
            ) = analysis4_function_body_off_chain_machine.record_critical_propagation_items_and_assigned_items(
                analysis4_function_body_off_chain_machine.final_jump_structure2[
                    "jump_structure_index_range"
                ][0],
                analysis4_function_body_off_chain_machine.final_jump_structure2[
                    "jump_structure_index_range"
                ][1],
            )
            print(f"critical_propagation_items: {critical_propagation_items}")
            print(f"critical_assigned_items: {critical_assigned_items}")

            # 再检查中间部分中的被赋值项和传播项
            (
                middle_propagation_items,
                middle_assigned_items,
                index_mapping_to_middle_propagation_items,
                index_mapping_to_middle_assigned_items,
            ) = analysis4_function_body_off_chain_machine.record_middle_propagation_items_and_assigned_items(
                analysis4_function_body_off_chain_machine.final_jump_structure1[
                    "jump_structure_index_range"
                ][0],
                analysis4_function_body_off_chain_machine.final_jump_structure2[
                    "jump_structure_index_range"
                ][0],
            )
            print(f"middle_propagation_items: {middle_propagation_items}")
            print(f"middle_assigned_items: {middle_assigned_items}")

            analysis5_function_body_off_chain_machine = Analysis5FunctionBodyOffChain(
                executor,
                take_special_stack_snapshots_index,
                designated_functions_index_range,
                new_jump_structure_info,
                temporary_variable_quantity,
                critical_propagation_items,
                critical_assigned_items,
                middle_propagation_items,
                middle_assigned_items,
                final_jump_structure1,
                final_jump_structure2,
                index_mapping_to_critical_propagation_items,
                index_mapping_to_critical_assigned_items,
                index_mapping_to_middle_propagation_items,
                index_mapping_to_middle_assigned_items,
            )
            step2_can_reorder_or_not = analysis5_function_body_off_chain_machine.determine_whether_the_consistency_of_data_dependency_relationships_is_met(
                is_or_not_determine_whether_the_consistency_of_data_dependency_relationships_is_met
            )
            if step2_can_reorder_or_not:
                adjacent_or_same_signal = 1  # 相同深度
                reorder_function_real_bytecode, reorder_real_bytecode = (
                    analysis5_function_body_off_chain_machine.reorder_key_granularity_bytecode_blocks(
                        adjacent_or_same_signal
                    )
                )

                with open(
                    "/Users/miaohuidong/demos/REEVM/test_txt/bytecode1.txt", "w"
                ) as f:
                    for opcode in reorder_real_bytecode:
                        f.write(opcode + "\n")
                print("reorder bytecode has been written into bytecode1.txt")

            else:

                all_single_part_execution_time.append(time.time())
                print(
                    f"all_single_part_execution_time: {all_single_part_execution_time}"
                )
                all_single_all_execution_time.append(time.time())
                print(f"all_single_all_execution_time: {all_single_all_execution_time}")

                raise UnboundLocalError("step2_can_reorder_or_not is False!")
        else:
            final_jump_structure1, final_jump_structure2 = (
                analysis4_function_body_off_chain_machine.search_parent_jump_structure_in_the_adjacent_deepest_detecting_range()
            )
            if analysis4_function_body_off_chain_machine.step1_can_reorder_or_not:
                # 先检查关键状态变量赋值块中的被赋值项和传播项
                (
                    critical_propagation_items,
                    critical_assigned_items,
                    index_mapping_to_critical_propagation_items,
                    index_mapping_to_critical_assigned_items,
                ) = analysis4_function_body_off_chain_machine.record_critical_propagation_items_and_assigned_items(
                    analysis4_function_body_off_chain_machine.final_jump_structure2[
                        "jump_structure_index_range"
                    ][0],
                    analysis4_function_body_off_chain_machine.final_jump_structure2[
                        "jump_structure_index_range"
                    ][1],
                )
                print(f"critical_propagation_items: {critical_propagation_items}")
                print(f"critical_assigned_items: {critical_assigned_items}")

                # 再检查中间部分中的被赋值项和传播项
                (
                    middle_propagation_items,
                    middle_assigned_items,
                    index_mapping_to_middle_propagation_items,
                    index_mapping_to_middle_assigned_items,
                ) = analysis4_function_body_off_chain_machine.record_middle_propagation_items_and_assigned_items(
                    analysis4_function_body_off_chain_machine.final_jump_structure1[
                        "jump_structure_index_range"
                    ][0],
                    analysis4_function_body_off_chain_machine.final_jump_structure2[
                        "jump_structure_index_range"
                    ][0],
                )
                print(f"middle_propagation_items: {middle_propagation_items}")
                print(f"middle_assigned_items: {middle_assigned_items}")

                analysis5_function_body_off_chain_machine = (
                    Analysis5FunctionBodyOffChain(
                        executor,
                        take_special_stack_snapshots_index,
                        designated_functions_index_range,
                        new_jump_structure_info,
                        temporary_variable_quantity,
                        critical_propagation_items,
                        critical_assigned_items,
                        middle_propagation_items,
                        middle_assigned_items,
                        final_jump_structure1,
                        final_jump_structure2,
                        index_mapping_to_critical_propagation_items,
                        index_mapping_to_critical_assigned_items,
                        index_mapping_to_middle_propagation_items,
                        index_mapping_to_middle_assigned_items,
                    )
                )
                step2_can_reorder_or_not = analysis5_function_body_off_chain_machine.determine_whether_the_consistency_of_data_dependency_relationships_is_met(
                    is_or_not_determine_whether_the_consistency_of_data_dependency_relationships_is_met
                )
                if step2_can_reorder_or_not:
                    adjacent_or_same_signal = 0  # 相邻深度
                    reorder_function_real_bytecode, reorder_real_bytecode = (
                        analysis5_function_body_off_chain_machine.reorder_key_granularity_bytecode_blocks(
                            adjacent_or_same_signal
                        )
                    )

                    with open(
                        "/Users/miaohuidong/demos/REEVM/test_txt/bytecode1.txt", "w"
                    ) as f:
                        for opcode in reorder_real_bytecode:
                            f.write(opcode + "\n")
                    print("reorder bytecode has been written into bytecode1.txt")

                else:

                    all_single_part_execution_time.append(time.time())
                    print(
                        f"all_single_part_execution_time: {all_single_part_execution_time}"
                    )
                    all_single_all_execution_time.append(time.time())
                    print(
                        f"all_single_all_execution_time: {all_single_all_execution_time}"
                    )

                    raise UnboundLocalError("step2_can_reorder_or_not is False!")
            else:
                all_single_part_execution_time.append(time.time())
                print(
                    f"all_single_part_execution_time: {all_single_part_execution_time}"
                )
                all_single_all_execution_time.append(time.time())
                print(f"all_single_all_execution_time: {all_single_all_execution_time}")

                raise UnboundLocalError("step1_can_reorder_or_not is False!")

        all_single_part_execution_time.append(time.time())
        print(f"all_single_part_execution_time: {all_single_part_execution_time}")
        all_single_all_execution_time.append(time.time())
        print(f"all_single_all_execution_time: {all_single_all_execution_time}")

    return (
        reorder_real_bytecode,
        len(critical_state_variable_assigned_value_opcodes_index_list) - 1,
    )


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

    designated_functions_index_range = 0  # 需要指定合约中的具体函数

    is_or_not_determine_whether_the_consistency_of_data_dependency_relationships_is_met = (
        1  # 1,0 决定是否开启数据依赖关系一致性判断, 默认1开启数据依赖关系一致性判断
    )

    critical_state_variable_assigned_value_opcodes_number = (
        1  # 一开始默认至少具有一个关键状态变量赋值
    )

    # ???
    while True:
        runtime_opcode, critical_state_variable_assigned_value_opcodes_number = (
            instantiated_main_body(
                runtime_opcode,
                designated_functions_index_range,
                is_or_not_determine_whether_the_consistency_of_data_dependency_relationships_is_met,
                critical_state_variable_assigned_value_opcodes_number,
            )
        )


# print(f"ultimate runtime_opcode: {runtime_opcode}")


if __name__ == "__main__":
    main()
