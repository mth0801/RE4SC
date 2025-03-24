import z3
from z3 import Solver, BitVec, is_bv, simplify
from testSolc import func_solc, bytecode_to_opcodes
import re

# from graphviz import Digraph

name_to_value = {}


class SymbolicVariableGenerator:
    def __init__(self):
        self.counter = 0

    def get_new_variable(self, name=None):
        if name is None:
            name = f"v{self.counter}"
            self.counter += 1
        var = BitVec(name, 256)
        # 此处可以考虑不添加非"0x"起始的情况
        name_to_value[var] = (
            int(name, 16)
            if name.startswith("0x") and "*" not in name and "&" not in name
            else name  # ???
        )
        return var


def convert_to_symbolic_bytecode(bytecode):
    symbolic_bytecode = []
    generator = SymbolicVariableGenerator()

    i = 0
    while i < len(bytecode):
        opcode = bytecode[i]
        if opcode.lower().startswith("push"):
            if opcode.lower() == "push0":
                symbolic_bytecode.append(opcode)
                i += 1  # 跳过操作码
            else:
                value = generator.get_new_variable(bytecode[i + 1])  # 也许合理？
                symbolic_bytecode.append(opcode)
                symbolic_bytecode.append(value)
                i += 2
        else:
            symbolic_bytecode.append(opcode)
            i += 1

    return symbolic_bytecode


class OpcodeHandlers:
    def __init__(self, executor, generator):
        self.executor = executor
        self.generator = generator

    def stop(self):
        self.executor.bytecode_list_index = len(self.executor.symbolic_bytecode)

    def add(self):
        a = self.executor.stack.pop()
        b = self.executor.stack.pop()
        self.executor.stack.append(a + b)
        self.executor.bytecode_list_index += 1

    def mul(self):
        a = self.executor.stack.pop()
        b = self.executor.stack.pop()
        # self.executor.stack.append(a * b)
        self.executor.stack.append(self.generator.get_new_variable(f"{a}*{b}"))
        self.executor.bytecode_list_index += 1

    def sub(self):
        a = self.executor.stack.pop()
        b = self.executor.stack.pop()
        self.executor.stack.append(a - b)
        self.executor.bytecode_list_index += 1

    def div(self):
        a = self.executor.stack.pop()
        b = self.executor.stack.pop()
        if b == 0:
            self.executor.stack.append(0)  # 按照 EVM 的规则，除以 0 结果为 0
        else:
            self.executor.stack.append(a / b)
        self.executor.bytecode_list_index += 1

    def sdiv(self):
        a = self.executor.stack.pop()
        b = self.executor.stack.pop()
        if b == 0:
            self.executor.stack.append(0)  # 按照 EVM 的规则，除以 0 结果为 0
        else:
            self.executor.stack.append(a / b)
        self.executor.bytecode_list_index += 1

    def mod(self):
        a = self.executor.stack.pop()
        b = self.executor.stack.pop()
        if b == 0:
            self.executor.stack.append(0)  # 按照 EVM 的规则，模 0 结果为 0
        else:
            self.executor.stack.append(a % b)
        self.executor.bytecode_list_index += 1

    def smod(self):
        a = self.executor.stack.pop()
        b = self.executor.stack.pop()
        if b == 0:
            self.executor.stack.append(0)  # 按照 EVM 的规则，模 0 结果为 0
        else:
            self.executor.stack.append(a % b)
        self.executor.bytecode_list_index += 1

    def addmod(self):
        a = self.executor.stack.pop()
        b = self.executor.stack.pop()
        c = self.executor.stack.pop()
        self.executor.stack.append((a + b) % c)
        self.executor.bytecode_list_index += 1

    def mulmod(self):
        a = self.executor.stack.pop()
        b = self.executor.stack.pop()
        c = self.executor.stack.pop()
        self.executor.stack.append((a * b) % c)
        self.executor.bytecode_list_index += 1

    def exp(self):  # 存疑
        base = self.executor.stack.pop()
        exponent = self.executor.stack.pop()
        y = self.generator.get_new_variable(f"exp({base},{exponent})")
        self.executor.stack.append(y)
        self.executor.bytecode_list_index += 1

    def signextend(self):
        b = self.executor.stack.pop()
        x = self.executor.stack.pop()
        y = self.generator.get_new_variable(f"SIGNEXTEND({x},{b})")
        self.executor.stack.append(y)
        self.executor.bytecode_list_index += 1

    def lt(self):
        a = self.executor.stack.pop()
        b = self.executor.stack.pop()
        self.executor.stack.append(a < b)
        self.executor.bytecode_list_index += 1

    def gt(self):
        a = self.executor.stack.pop()
        b = self.executor.stack.pop()
        self.executor.stack.append(a > b)
        self.executor.bytecode_list_index += 1

    def slt(self):  # 模拟执行版，实际执行需要修改该方法
        a = self.executor.stack.pop()
        b = self.executor.stack.pop()
        self.executor.stack.append(a < b)
        self.executor.bytecode_list_index += 1

    def sgt(self):  # 模拟执行版，实际执行需要修改该方法
        a = self.executor.stack.pop()
        b = self.executor.stack.pop()
        self.executor.stack.append(a > b)
        self.executor.bytecode_list_index += 1

    def eq(self):
        a = self.executor.stack.pop()
        b = self.executor.stack.pop()
        self.executor.stack.append(a == b)
        self.executor.bytecode_list_index += 1

    def iszero(self):
        a = self.executor.stack.pop()
        self.executor.stack.append(a == False)
        self.executor.bytecode_list_index += 1

    def and_op(self):
        a = self.executor.stack.pop()
        b = self.executor.stack.pop()
        self.executor.stack.append(a & b)
        self.executor.bytecode_list_index += 1

    def or_op(self):
        a = self.executor.stack.pop()
        b = self.executor.stack.pop()
        self.executor.stack.append(a | b)
        self.executor.bytecode_list_index += 1

    def xor_op(self):
        a = self.executor.stack.pop()
        b = self.executor.stack.pop()
        self.executor.stack.append(a ^ b)
        self.executor.bytecode_list_index += 1

    def not_op(self):
        a = self.executor.stack.pop()
        self.executor.stack.append(~a)
        self.executor.bytecode_list_index += 1

    def byte_op(self):
        n = self.executor.stack.pop()
        x = self.executor.stack.pop()
        y = (x >> (248 - n * 8)) & 0xFF
        self.executor.stack.append(y)
        self.executor.bytecode_list_index += 1

    def shl(self):
        shift = self.executor.stack.pop()
        value = self.executor.stack.pop()
        self.executor.stack.append(value << shift)
        self.executor.bytecode_list_index += 1

    def shr(self):
        shift = self.executor.stack.pop()
        value = self.executor.stack.pop()
        self.executor.stack.append(value >> shift)
        self.executor.bytecode_list_index += 1

    def sar(self):  # 存疑
        shift = self.executor.stack.pop()
        value = self.executor.stack.pop()
        self.executor.stack.append(value >> shift)
        self.executor.bytecode_list_index += 1

    def sha3(self):
        offset = self.executor.stack.pop()
        length = self.executor.stack.pop()
        hash = self.generator.get_new_variable(
            f"keccak256(memory[{offset}:{offset}+{length}])"
        )
        self.executor.stack.append(hash)
        self.executor.bytecode_list_index += 1

    def address(self):
        address = self.generator.get_new_variable("address(this)")
        self.executor.stack.append(address)
        self.executor.bytecode_list_index += 1

    def balance(self):
        a = self.executor.stack.pop()
        balance = self.generator.get_new_variable(f"address({a}).balance")
        self.executor.stack.append(balance)
        self.executor.bytecode_list_index += 1

    def origin(self):
        origin = self.generator.get_new_variable("tx.origin")
        self.executor.stack.append(origin)
        self.executor.bytecode_list_index += 1

    def caller(self):
        caller = self.generator.get_new_variable("msg.caller")
        self.executor.stack.append(caller)
        self.executor.bytecode_list_index += 1

    def callvalue(self):
        callvalue = self.generator.get_new_variable("msg.value")
        self.executor.stack.append(callvalue)
        self.executor.bytecode_list_index += 1

    def calldataload(self):
        a = self.executor.stack.pop()
        callvalue = self.generator.get_new_variable(f"msg.data[{a}:{a}+32]")
        self.executor.stack.append(callvalue)
        self.executor.bytecode_list_index += 1

    def calldatasize(self):
        calldatasize = self.generator.get_new_variable("msg.data.size")
        self.executor.stack.append(calldatasize)
        self.executor.bytecode_list_index += 1

    def calldatacopy(self):  #
        dest = self.executor.stack.pop()
        offset = self.executor.stack.pop()
        length = self.executor.stack.pop()
        self.executor.bytecode_list_index += 1

    def codesize(self):
        size = self.generator.get_new_variable("address(this).code.size")
        self.executor.stack.append(size)
        self.executor.bytecode_list_index += 1

    def codecopy(self):
        dest = self.executor.stack.pop()
        offset = self.executor.stack.pop()
        length = self.executor.stack.pop()
        self.executor.bytecode_list_index += 1

    def gasprice(self):
        price = self.generator.get_new_variable("tx.gasprice")
        self.executor.stack.append(price)
        self.executor.bytecode_list_index += 1

    def extcodesize(self):
        address = self.executor.stack.pop()
        size = self.generator.get_new_variable(f"address({address}).code.size")
        self.executor.stack.append(size)
        self.executor.bytecode_list_index += 1

    def extcodecopy(self):
        self.executor.stack.pop()
        self.executor.stack.pop()
        self.executor.stack.pop()
        self.executor.stack.pop()
        self.executor.bytecode_list_index += 1

    def returndatasize(self):
        size = self.generator.get_new_variable("size_RETURNDATASIZE()")
        self.executor.stack.append(size)
        self.executor.bytecode_list_index += 1

    def returndatacopy(self):
        self.executor.stack.pop()
        self.executor.stack.pop()
        self.executor.stack.pop()
        self.executor.bytecode_list_index += 1

    def extcodehash(self):
        address = self.executor.stack.pop()
        hash_val = self.generator.get_new_variable(f"extcodehash_{address}")
        self.executor.stack.append(hash_val)
        self.executor.bytecode_list_index += 1

    def blockhash(self):
        block_number = self.executor.stack.pop()
        hash_val = self.generator.get_new_variable(f"blockhash_{block_number}")
        self.executor.stack.append(hash_val)
        self.executor.bytecode_list_index += 1

    def coinbase(self):
        coinbase = self.generator.get_new_variable("block.coinbase")
        self.executor.stack.append(coinbase)
        self.executor.bytecode_list_index += 1

    def timestamp(self):
        timestamp = self.generator.get_new_variable("block.timestamp")
        self.executor.stack.append(timestamp)
        self.executor.bytecode_list_index += 1

    def number(self):
        number = self.generator.get_new_variable("block.number")
        self.executor.stack.append(number)
        self.executor.bytecode_list_index += 1

    def difficulty(self):
        difficulty = self.generator.get_new_variable("block.difficulty")
        self.executor.stack.append(difficulty)
        self.executor.bytecode_list_index += 1

    def gaslimit(self):
        gaslimit = self.generator.get_new_variable("block.gaslimit")
        self.executor.stack.append(gaslimit)
        self.executor.bytecode_list_index += 1

    def chainid(self):
        chainid = self.generator.get_new_variable("chain_id")
        self.executor.stack.append(chainid)
        self.executor.bytecode_list_index += 1

    def selfbalance(self):
        balance = self.generator.get_new_variable("address(this).balance")
        self.executor.stack.append(balance)
        self.executor.bytecode_list_index += 1

    def basefee(self):
        basefee = self.generator.get_new_variable("base_fee")
        self.executor.stack.append(basefee)
        self.executor.bytecode_list_index += 1

    def blobhash(self):
        blob_index = self.executor.stack.pop()
        blobhash = self.generator.get_new_variable(
            f"tx.blob_versioned_hashes[{blob_index}]"
        )
        self.executor.stack.append(blobhash)
        self.executor.bytecode_list_index += 1

    def blobbasefee(self):
        blobbasefee = self.generator.get_new_variable("blob_base_fee")
        self.executor.stack.append(blobbasefee)
        self.executor.bytecode_list_index += 1

    def pop(self):
        self.executor.stack.pop()
        self.executor.bytecode_list_index += 1

    def mload(self):
        offset = self.executor.stack.pop()
        value = self.generator.get_new_variable(f"memory[{offset}:{offset}+32]")
        self.executor.stack.append(value)
        self.executor.bytecode_list_index += 1

    def mstore(self):
        address = self.executor.stack.pop()
        value = self.executor.stack.pop()
        self.executor.bytecode_list_index += 1

    def mstore8(self):
        address = self.executor.stack.pop()
        value = self.executor.stack.pop()
        self.executor.bytecode_list_index += 1

    def sload(self):
        key = self.executor.stack.pop()
        value = self.generator.get_new_variable(f"storage[{key}]")
        self.executor.stack.append(value)
        self.executor.bytecode_list_index += 1

    def sstore(self):
        key = self.executor.stack.pop()
        value = self.executor.stack.pop()
        self.executor.bytecode_list_index += 1

    def jump(self, jump_address_index):  # cunyi
        target = self.executor.stack.pop()
        if isinstance(jump_address_index, int):

            self.executor.add_control_flow_edge(
                self.executor.bytecode_list_index, jump_address_index
            )  # 记录CFG相关

            self.executor.bytecode_list_index = jump_address_index
        else:
            raise ValueError("Invalid jump target")

    def jumpi(self, jumpi_address_index, jumpi_condition):  # cunyi
        self.executor.stack.pop()
        self.executor.stack.pop()

        if isinstance(jumpi_address_index, int):
            print(f"jumpi_condition: {jumpi_condition}")
            print(type(jumpi_condition))

            self.executor.solver.push()
            self.executor.solver.add(jumpi_condition != True)
            if self.executor.solver.check() == z3.sat:
                self.executor.execution_paths.append(
                    (jumpi_address_index, self.executor.stack.copy())
                )
            self.executor.solver.pop()

            self.executor.add_control_flow_edge(
                self.executor.bytecode_list_index, jumpi_address_index
            )  # 记录CFG相关

            self.executor.solver.push()
            self.executor.solver.add(jumpi_condition == True)
            if self.executor.solver.check() == z3.sat:
                self.executor.execution_paths.append(
                    (
                        self.executor.bytecode_list_index + 1,
                        self.executor.stack.copy(),
                    )
                )
            self.executor.solver.pop()

            self.executor.add_control_flow_edge(
                self.executor.bytecode_list_index, self.executor.bytecode_list_index + 1
            )  # 记录CFG相关

        else:
            raise ValueError("Invalid jumpi target")

    def pc(self):  # 应当改为真正的pc
        pc = self.generator.get_new_variable("PC")
        self.executor.stack.append(pc)
        self.executor.bytecode_list_index += 1

    def msize(self):
        msize = self.generator.get_new_variable("size_MSIZE()")
        self.executor.stack.append(msize)
        self.executor.bytecode_list_index += 1

    def gas(self):
        gas = self.generator.get_new_variable("gasRemaining")
        self.executor.stack.append(gas)
        self.executor.bytecode_list_index += 1

    def jumpdest(self):
        self.executor.bytecode_list_index += 1

    def tload(self):
        key = self.executor.stack.pop()
        value = self.generator.get_new_variable(f"transient[{key}]")
        self.executor.stack.append(value)
        self.executor.bytecode_list_index += 1

    def tstore(self):
        address = self.executor.stack.pop()
        value = self.executor.stack.pop()
        self.executor.bytecode_list_index += 1

    def mcopy(self):
        dest = self.executor.stack.pop()
        src = self.executor.stack.pop()
        length = self.executor.stack.pop()
        self.executor.bytecode_list_index += 1

    def push0(self):
        value = self.generator.get_new_variable("0")
        self.executor.stack.append(value)
        self.executor.bytecode_list_index += 1

    def push1(self, value):
        self.executor.stack.append(value)
        self.executor.bytecode_list_index += 2

    def push2(self, value):
        self.executor.stack.append(value)
        self.executor.bytecode_list_index += 2

    def push3(self, value):
        self.executor.stack.append(value)
        self.executor.bytecode_list_index += 2

    def push4(self, value):
        self.executor.stack.append(value)
        self.executor.bytecode_list_index += 2

    def push5(self, value):
        self.executor.stack.append(value)
        self.executor.bytecode_list_index += 2

    def push6(self, value):
        self.executor.stack.append(value)
        self.executor.bytecode_list_index += 2

    def push7(self, value):
        self.executor.stack.append(value)
        self.executor.bytecode_list_index += 2

    def push8(self, value):
        self.executor.stack.append(value)
        self.executor.bytecode_list_index += 2

    def push9(self, value):
        self.executor.stack.append(value)
        self.executor.bytecode_list_index += 2

    def push10(self, value):
        self.executor.stack.append(value)
        self.executor.bytecode_list_index += 2

    def push11(self, value):
        self.executor.stack.append(value)
        self.executor.bytecode_list_index += 2

    def push12(self, value):
        self.executor.stack.append(value)
        self.executor.bytecode_list_index += 2

    def push13(self, value):
        self.executor.stack.append(value)
        self.executor.bytecode_list_index += 2

    def push14(self, value):
        self.executor.stack.append(value)
        self.executor.bytecode_list_index += 2

    def push15(self, value):
        self.executor.stack.append(value)
        self.executor.bytecode_list_index += 2

    def push16(self, value):
        self.executor.stack.append(value)
        self.executor.bytecode_list_index += 2

    def push17(self, value):
        self.executor.stack.append(value)
        self.executor.bytecode_list_index += 2

    def push18(self, value):
        self.executor.stack.append(value)
        self.executor.bytecode_list_index += 2

    def push19(self, value):
        self.executor.stack.append(value)
        self.executor.bytecode_list_index += 2

    def push20(self, value):
        self.executor.stack.append(value)
        self.executor.bytecode_list_index += 2

    def push21(self, value):
        self.executor.stack.append(value)
        self.executor.bytecode_list_index += 2

    def push22(self, value):
        self.executor.stack.append(value)
        self.executor.bytecode_list_index += 2

    def push23(self, value):
        self.executor.stack.append(value)
        self.executor.bytecode_list_index += 2

    def push24(self, value):
        self.executor.stack.append(value)
        self.executor.bytecode_list_index += 2

    def push25(self, value):
        self.executor.stack.append(value)
        self.executor.bytecode_list_index += 2

    def push26(self, value):
        self.executor.stack.append(value)
        self.executor.bytecode_list_index += 2

    def push27(self, value):
        self.executor.stack.append(value)
        self.executor.bytecode_list_index += 2

    def push28(self, value):
        self.executor.stack.append(value)
        self.executor.bytecode_list_index += 2

    def push29(self, value):
        self.executor.stack.append(value)
        self.executor.bytecode_list_index += 2

    def push30(self, value):
        self.executor.stack.append(value)
        self.executor.bytecode_list_index += 2

    def push31(self, value):
        self.executor.stack.append(value)
        self.executor.bytecode_list_index += 2

    def push32(self, value):
        self.executor.stack.append(value)
        self.executor.bytecode_list_index += 2

    def dup1(self):
        self.executor.stack.append(self.executor.stack[-1])
        self.executor.bytecode_list_index += 1

    def dup2(self):
        self.executor.stack.append(self.executor.stack[-2])
        self.executor.bytecode_list_index += 1

    def dup3(self):
        self.executor.stack.append(self.executor.stack[-3])
        self.executor.bytecode_list_index += 1

    def dup4(self):
        self.executor.stack.append(self.executor.stack[-4])
        self.executor.bytecode_list_index += 1

    def dup5(self):
        self.executor.stack.append(self.executor.stack[-5])
        self.executor.bytecode_list_index += 1

    def dup6(self):
        self.executor.stack.append(self.executor.stack[-6])
        self.executor.bytecode_list_index += 1

    def dup7(self):
        self.executor.stack.append(self.executor.stack[-7])
        self.executor.bytecode_list_index += 1

    def dup8(self):
        self.executor.stack.append(self.executor.stack[-8])
        self.executor.bytecode_list_index += 1

    def dup9(self):
        self.executor.stack.append(self.executor.stack[-9])
        self.executor.bytecode_list_index += 1

    def dup10(self):
        self.executor.stack.append(self.executor.stack[-10])
        self.executor.bytecode_list_index += 1

    def dup11(self):
        self.executor.stack.append(self.executor.stack[-11])
        self.executor.bytecode_list_index += 1

    def dup12(self):
        self.executor.stack.append(self.executor.stack[-12])
        self.executor.bytecode_list_index += 1

    def dup13(self):
        self.executor.stack.append(self.executor.stack[-13])
        self.executor.bytecode_list_index += 1

    def dup14(self):
        self.executor.stack.append(self.executor.stack[-14])
        self.executor.bytecode_list_index += 1

    def dup15(self):
        self.executor.stack.append(self.executor.stack[-15])
        self.executor.bytecode_list_index += 1

    def dup16(self):
        self.executor.stack.append(self.executor.stack[-16])
        self.executor.bytecode_list_index += 1

    def swap1(self):
        self.executor.stack[-1], self.executor.stack[-2] = (
            self.executor.stack[-2],
            self.executor.stack[-1],
        )
        self.executor.bytecode_list_index += 1

    def swap2(self):
        self.executor.stack[-1], self.executor.stack[-3] = (
            self.executor.stack[-3],
            self.executor.stack[-1],
        )
        self.executor.bytecode_list_index += 1

    def swap3(self):
        self.executor.stack[-1], self.executor.stack[-4] = (
            self.executor.stack[-4],
            self.executor.stack[-1],
        )
        self.executor.bytecode_list_index += 1

    def swap4(self):
        self.executor.stack[-1], self.executor.stack[-5] = (
            self.executor.stack[-5],
            self.executor.stack[-1],
        )
        self.executor.bytecode_list_index += 1

    def swap5(self):
        self.executor.stack[-1], self.executor.stack[-6] = (
            self.executor.stack[-6],
            self.executor.stack[-1],
        )
        self.executor.bytecode_list_index += 1

    def swap6(self):
        self.executor.stack[-1], self.executor.stack[-7] = (
            self.executor.stack[-7],
            self.executor.stack[-1],
        )
        self.executor.bytecode_list_index += 1

    def swap7(self):
        self.executor.stack[-1], self.executor.stack[-8] = (
            self.executor.stack[-8],
            self.executor.stack[-1],
        )
        self.executor.bytecode_list_index += 1

    def swap8(self):
        self.executor.stack[-1], self.executor.stack[-9] = (
            self.executor.stack[-9],
            self.executor.stack[-1],
        )
        self.executor.bytecode_list_index += 1

    def swap9(self):
        self.executor.stack[-1], self.executor.stack[-10] = (
            self.executor.stack[-10],
            self.executor.stack[-1],
        )
        self.executor.bytecode_list_index += 1

    def swap10(self):
        self.executor.stack[-1], self.executor.stack[-11] = (
            self.executor.stack[-11],
            self.executor.stack[-1],
        )
        self.executor.bytecode_list_index += 1

    def swap11(self):
        self.executor.stack[-1], self.executor.stack[-12] = (
            self.executor.stack[-12],
            self.executor.stack[-1],
        )
        self.executor.bytecode_list_index += 1

    def swap12(self):
        self.executor.stack[-1], self.executor.stack[-13] = (
            self.executor.stack[-13],
            self.executor.stack[-1],
        )
        self.executor.bytecode_list_index += 1

    def swap13(self):
        self.executor.stack[-1], self.executor.stack[-14] = (
            self.executor.stack[-14],
            self.executor.stack[-1],
        )
        self.executor.bytecode_list_index += 1

    def swap14(self):
        self.executor.stack[-1], self.executor.stack[-15] = (
            self.executor.stack[-15],
            self.executor.stack[-1],
        )
        self.executor.bytecode_list_index += 1

    def swap15(self):
        self.executor.stack[-1], self.executor.stack[-16] = (
            self.executor.stack[-16],
            self.executor.stack[-1],
        )
        self.executor.bytecode_list_index += 1

    def swap16(self):
        self.executor.stack[-1], self.executor.stack[-17] = (
            self.executor.stack[-17],
            self.executor.stack[-1],
        )
        self.executor.bytecode_list_index += 1

    def log0(self):
        data = self.executor.stack.pop()
        data = self.executor.stack.pop()
        self.executor.bytecode_list_index += 1

    def log1(self):
        data = self.executor.stack.pop()
        data = self.executor.stack.pop()
        data = self.executor.stack.pop()
        self.executor.bytecode_list_index += 1

    def log2(self):
        data = self.executor.stack.pop()
        data = self.executor.stack.pop()
        data = self.executor.stack.pop()
        data = self.executor.stack.pop()
        self.executor.bytecode_list_index += 1

    def log3(self):
        data = self.executor.stack.pop()
        data = self.executor.stack.pop()
        data = self.executor.stack.pop()
        data = self.executor.stack.pop()
        data = self.executor.stack.pop()
        self.executor.bytecode_list_index += 1

    def log4(self):
        data = self.executor.stack.pop()
        data = self.executor.stack.pop()
        data = self.executor.stack.pop()
        data = self.executor.stack.pop()
        data = self.executor.stack.pop()
        data = self.executor.stack.pop()
        self.executor.bytecode_list_index += 1

    def create(self):
        value = self.executor.stack.pop()
        offset = self.executor.stack.pop()
        length = self.executor.stack.pop()
        address = self.generator.get_new_variable(
            f"new_memory[{offset}:{offset}+{length}].value({value})"
        )
        self.executor.stack.append(address)
        self.executor.bytecode_list_index += 1

    def call(self):
        gas = self.executor.stack.pop()
        address = self.executor.stack.pop()
        value = self.executor.stack.pop()
        argsOffset = self.executor.stack.pop()
        argsLength = self.executor.stack.pop()
        retOffset = self.executor.stack.pop()
        retLength = self.executor.stack.pop()
        success = self.generator.get_new_variable("call_success")
        self.executor.stack.append(success)
        self.executor.bytecode_list_index += 1

    def callcode(self):
        gas = self.executor.stack.pop()
        address = self.executor.stack.pop()
        value = self.executor.stack.pop()
        argsOffset = self.executor.stack.pop()
        argsLength = self.executor.stack.pop()
        retOffset = self.executor.stack.pop()
        retLength = self.executor.stack.pop()
        success = self.generator.get_new_variable("callcode_success")
        self.executor.stack.append(success)
        self.executor.bytecode_list_index += 1

    def return_op(self):
        self.executor.stack.pop()
        self.executor.stack.pop()
        self.executor.bytecode_list_index = len(self.executor.symbolic_bytecode)

    def delegatecall(self):
        gas = self.executor.stack.pop()
        address = self.executor.stack.pop()
        argsOffset = self.executor.stack.pop()
        argsLength = self.executor.stack.pop()
        retOffset = self.executor.stack.pop()
        retLength = self.executor.stack.pop()
        success = self.generator.get_new_variable("delegatecall_success")
        self.executor.stack.append(success)
        self.executor.bytecode_list_index += 1

    def create2(self):
        value = self.executor.stack.pop()
        offset = self.executor.stack.pop()
        length = self.executor.stack.pop()
        salt = self.executor.stack.pop()
        address = self.generator.get_new_variable(
            f"new_memory[{offset}:{offset}+{length}].value({value})"
        )
        self.executor.stack.append(address)
        self.executor.bytecode_list_index += 1

    def staticcall(self):
        gas = self.executor.stack.pop()
        address = self.executor.stack.pop()
        argsOffset = self.executor.stack.pop()
        argsLength = self.executor.stack.pop()
        retOffset = self.executor.stack.pop()
        retLength = self.executor.stack.pop()
        success = self.generator.get_new_variable("staticcall_success")
        self.executor.stack.append(success)
        self.executor.bytecode_list_index += 1

    def revert(self):
        self.executor.stack.pop()
        self.executor.stack.pop()
        self.executor.bytecode_list_index = len(self.executor.symbolic_bytecode)

    def selfdestruct(self):
        address = self.executor.stack.pop()
        self.executor.bytecode_list_index = len(self.executor.symbolic_bytecode)

    def invalid(self):
        self.executor.bytecode_list_index += 1
        # raise ValueError("Invalid opcode")


class BytecodeExecutor:
    def __init__(self, symbolic_bytecode, real_bytecode):
        self.symbolic_bytecode = symbolic_bytecode
        self.real_bytecode = real_bytecode
        self.stack = []
        self.bytecode_list_index = 0
        self.generator = SymbolicVariableGenerator()
        self.handlers = OpcodeHandlers(self, self.generator)
        self.index_mapping_pc, self.pc_mapping_index = (
            self.create_mapping()
        )  # 创建PC映射关系
        self.solver = Solver()
        self.execution_paths = []
        self.paths = []  # 添加路径记录列表
        self.smartcontract_functions_index_position = []
        self.smartcontract_functions_index_range = []
        self.stack_snapshots = {}  # 新增堆栈快照记录
        self.control_flow_graph = {}  # 新增，存储每个位置的跳转目标
        self.visited_nodes_index_by_jumpi = {}
        self.exist_loop_node_by_jumpi = set()
        self.jump_structure_info = []  # 暂时未用
        self.opcodeindex_to_stack = {}
        self.all_jump_index_related_to_Call = set()
        self.contract_start_index = []
        self.the_first_contract_end_index = 0

    def create_mapping(self):
        index_mapping_pc = {}
        pc_mapping_index = {}
        pc = 0
        index = 0
        while index < len(self.symbolic_bytecode):
            print(self.symbolic_bytecode[index])  #
            opcode = self.symbolic_bytecode[index].lower()
            index_mapping_pc[index] = pc
            pc_mapping_index[pc] = index
            pc += 1  # 每个操作码占用一个PC位置
            if opcode.startswith("push") and not opcode.startswith("push0"):
                # 提取推入的数据字节数
                push_bytes = int(opcode[4:])
                pc += push_bytes  # 加上操作数所占用的PC位置
                index += 1  # 跳过操作数
            index += 1
        return index_mapping_pc, pc_mapping_index

    def get_pc_position(self, index):
        return self.index_mapping_pc.get(index, None)

    def get_index_position(self, pc):
        return self.pc_mapping_index.get(pc, None)

    def get_max_stop_return_index(self):
        # 防止跨合约的情况,也就是编译后一份合约后还尾随着其他合约
        contract_start_index = []
        index = 0
        while index < len(self.real_bytecode):
            if (
                self.real_bytecode[index].startswith("PUSH")
                and self.real_bytecode[index] != "PUSH0"
                and self.real_bytecode[index + 1] == "0x80"
                and self.real_bytecode[index + 2].startswith("PUSH")
                and self.real_bytecode[index + 2] != "PUSH0"
                and self.real_bytecode[index + 3] == "0x40"
                and self.real_bytecode[index + 4] == "MSTORE"
            ):
                contract_start_index.append(index)
            index += 1
        self.contract_start_index = contract_start_index
        print(f"contract_start_index: {contract_start_index}")

        if len(contract_start_index) >= 2:
            print("111")
            stop_return_indices = []
            index1 = 0
            while index1 < len(self.real_bytecode):
                if (
                    self.real_bytecode[index1] == "STOP"
                    or self.real_bytecode[index1] == "RETURN"
                ) and index1 < contract_start_index[1]:
                    stop_return_indices.append(index1)
                    print(f"stop_return_indices: {stop_return_indices}")
                index1 += 1
            stop_return_indices.pop()
            dispatcher_boundary = max(stop_return_indices)
            self.the_first_contract_end_index = contract_start_index[1] - 2
        else:
            stop_return_indices = [
                index1
                for index1, opcode in enumerate(self.real_bytecode)
                if opcode.lower() == "stop" or opcode.lower() == "return"
            ]
            dispatcher_boundary = max(stop_return_indices)
            self.the_first_contract_end_index = len(self.real_bytecode) - 1

        print(f"self.the_first_contract_end_index: {self.the_first_contract_end_index}")
        print(f"stop_return_indices: {stop_return_indices}")
        print(f"dispatcher_boundary: {dispatcher_boundary}")
        return dispatcher_boundary

    def record_stack_snapshot(self):
        self.stack_snapshots[self.bytecode_list_index] = len(self.stack)

    def record_stack(self):
        self.opcodeindex_to_stack[self.bytecode_list_index] = self.stack.copy()
        # 终于找到问题所在，self.stack应改为self.stack.copy()，因为用self.stack会将指针也指向self.opcodeindex_to_stack[self.bytecode_list_index]，这意味着self.stack改变也会引起self.opcodeindex_to_stack[self.bytecode_list_index]的改变，而用self.stack.copy()取代self.stack则不会将指针指过去，两者独立

    def add_control_flow_edge(self, source, target):
        if source in self.control_flow_graph:
            if target not in self.control_flow_graph[source]:
                self.control_flow_graph[source].append(target)
        else:
            self.control_flow_graph[source] = [target]

    def create_control_flow_graph(self):
        print(f"control_flow_graph: {self.control_flow_graph}")
        return self.control_flow_graph
        # dot = Digraph()

        # for source, targets in self.control_flow_graph.items():
        #     for target in targets:
        #         dot.edge(f"PC {source}", f"PC {target}")
        # return dot

    def execute(self):
        dispatcher_boundary = self.get_max_stop_return_index()
        self.execution_paths = [(self.bytecode_list_index, self.stack.copy())]
        all_stacks = []
        self.smartcontract_functions_index_position.append(dispatcher_boundary + 1)
        while self.execution_paths:
            self.bytecode_list_index, self.stack = self.execution_paths.pop()  #
            while self.bytecode_list_index < len(self.real_bytecode):  # 天然的合约隔阂
                print(f"index:{self.bytecode_list_index}")
                print(f"stack:{self.stack}")
                opcode = self.symbolic_bytecode[self.bytecode_list_index]
                print(opcode)
                handler_name = opcode.lower()
                handler = getattr(self.handlers, handler_name, None)
                self.record_stack_snapshot()  # 记录当前堆栈快照
                self.record_stack()  # 记录当前堆栈 ????????
                # print(
                #     f"self.opcodeindex_to_stack[self.bytecode_list_index]: {self.opcodeindex_to_stack[self.bytecode_list_index]}"
                # )

                if opcode.lower().startswith("push") and opcode.lower() != "push0":
                    value = self.symbolic_bytecode[self.bytecode_list_index + 1]
                    handler(value)
                elif opcode.lower() == "jump":
                    jump_address_symbol = self.stack[-1]

                    # 存在对跳转地址取掩码的情况
                    if "&" not in str(jump_address_symbol):
                        jump_address_pc = name_to_value[jump_address_symbol]
                    else:
                        parts = str(jump_address_symbol).split("&")
                        # 取出 & 后的部分，去除多余的空格
                        result = parts[1].strip()
                        jump_address_pc = name_to_value[BitVec(result, 256)]

                    jump_address_index = self.get_index_position(jump_address_pc)
                    print(name_to_value)
                    print(f"jump address pc: {self.stack[-1]}")
                    print(type(self.stack[-1]))
                    print(f"jump address pc: {jump_address_pc}")
                    print(f"jump address index: {jump_address_index}")

                    # 需要修改，无法分辨internal函数！！！并且有函数边界index重复的情况？？？
                    if jump_address_index <= dispatcher_boundary:
                        # 补丁,防止dispatcher_boundary之前出现类似调用结构而使函数边界向前越过dispatcher_boundary
                        if self.bytecode_list_index + 1 > dispatcher_boundary + 2:
                            if (
                                self.bytecode_list_index + 1
                                not in self.smartcontract_functions_index_position
                            ):
                                self.smartcontract_functions_index_position.append(
                                    self.bytecode_list_index + 1
                                )
                                print(
                                    f"self.smartcontract_functions_index_position: {self.smartcontract_functions_index_position}"
                                )

                    handler(jump_address_index)

                    # exist another way
                elif opcode.lower() == "jumpi":
                    print(f"happen branch jumpi in index {self.bytecode_list_index}")
                    jumpi_address_symbol = self.stack[-1]
                    jumpi_condition = self.stack[-2]
                    jumpi_address_pc = name_to_value[jumpi_address_symbol]
                    jumpi_address_index = self.get_index_position(jumpi_address_pc)

                    # 防止字节码路径无限回路,但可能不是因为循环的存在而多次经过某些JUMPI,如果统计不充分可能会导致部分路径不被模拟导致控制流图的缺失
                    # 需要优化对循环结构判断的逻辑,具体来说就是可能需要在超过重复次数阈值之后开始记录去往某个被重复经过的index的跳转源地址以及其跳往该index的次数,因此,在超过重复次数阈值之前照常模拟执行,在超过重复次数阈值之后就需要考察源地址跳往该index的次数是否大于等于1,如果是则不再执行,如果不是则继续执行
                    # 理论上来说,跳转深度越浅,相应地某处的重复次数阈值应当越少,跳转深度越深,相应地某处的重复次数阈值应当越多
                    # 也就是不建议设定一个总重复次数阈值来限制所有的重复点,因为这样可能会导致过度重复执行某些区域造成计算资源浪费,或是缺乏执行某些区域导致跳转信息缺失而CFG不完整.而是每个重复点都应当根据其对应的跳转深度而建立自身对应的重复次数阈值
                    # 再补充一些模糊概念,也许可以从这样的角度来解决,跳转深度越深的重复点被重新打开被执行的权限更高,跳转深度越浅的重复点被重新打开被执行的权限更低
                    # 这部分还会影响后续对循环结构的判断,可能会导致对循环结构的漏判或是对循环结构的误判,但是循环结构的核心在于究竟是从重复JUMPDEST的上一个操作码经过后再经过JUMPDEST还是从跳转到JUMPDEST的某个源JUMP经过后再经过JUMPDEST
                    # 不对,就目前来看,即使用一个或大或小的总重复次数阈值来限制所有的重复点,也绝不会导致循环结构的漏判,但有可能误判,这时就要判断JUMPI所对应条件为假时候的目标地址的上一个操作码是否为JUMP,以及即使是JUMP则其对应的跳转地址是否在index上小于JUMPI的地址
                    # 所以目前还是要稍稍放大一点总重复次数阈值,但关键在于对于真正的循环结构,需要在新的外部调用后经过其时又打开模拟执行其的权限
                    if self.bytecode_list_index in self.visited_nodes_index_by_jumpi:
                        # 暂定4为重复次数阈值
                        if (
                            self.visited_nodes_index_by_jumpi[self.bytecode_list_index]
                            <= 4
                        ):
                            self.visited_nodes_index_by_jumpi[
                                self.bytecode_list_index
                            ] += 1
                            handler(jumpi_address_index, jumpi_condition)
                        else:
                            print(
                                f"Exist Loop!!! Exist Loop!!! Exist Loop!!! in PC {self.bytecode_list_index}"
                            )
                            # 由于在条件分支时优先模拟执行分支内容，所以理论上所有的循环体jumpi都会被n次经过
                            self.exist_loop_node_by_jumpi.add(self.bytecode_list_index)

                            # # test!!!没什么用,还会加重循环的冗重
                            # self.visited_nodes_index_by_jumpi[
                            #     self.bytecode_list_index
                            # ] = 1

                            break
                    else:
                        self.visited_nodes_index_by_jumpi.update(
                            {self.bytecode_list_index: 0}
                        )
                        handler(jumpi_address_index, jumpi_condition)

                    break  # ???
                elif (
                    opcode.lower() == "return"
                ):  # .startswith("return")误导太多,因为还有RETURNDATASIZE,RETURNDATACOPY等操作码
                    handler_name = "return_op"
                    handler = getattr(self.handlers, handler_name, None)
                    handler()
                elif opcode.lower().startswith("and"):  # 。。。
                    handler_name = "and_op"
                    handler = getattr(self.handlers, handler_name, None)
                    handler()
                elif opcode.lower() == "or":  # 。。。
                    handler_name = "or_op"
                    handler = getattr(self.handlers, handler_name, None)
                    handler()
                elif opcode.lower() == "xor":  # 。。。
                    handler_name = "xor_op"
                    handler = getattr(self.handlers, handler_name, None)
                    handler()
                elif opcode.lower() == "not":  # 。。。
                    handler_name = "not_op"
                    handler = getattr(self.handlers, handler_name, None)
                    handler()
                elif opcode.lower() == "byte":  # 。。。
                    handler_name = "byte_op"
                    handler = getattr(self.handlers, handler_name, None)
                    handler()
                else:
                    handler()

                if handler is None:
                    raise ValueError(f"Unknown opcode: {opcode}")

            all_stacks.append(self.stack.copy())

        self.control_flow_graph = dict(sorted(self.control_flow_graph.items()))
        print(f"self.control_flow_graph: {self.control_flow_graph}")

        # 获取函数体信息

        # 补充internal类型的函数边界
        all_target_jumpdest_index = []
        for key in self.control_flow_graph.keys():
            all_target_jumpdest_index.extend(self.control_flow_graph[key])
        all_target_jumpdest_index = set(all_target_jumpdest_index)
        all_target_jumpdest_index = list(all_target_jumpdest_index)
        all_target_jumpdest_index = sorted(all_target_jumpdest_index)
        print(f"all_target_jumpdest_index: {all_target_jumpdest_index}")

        exist_internal_function_boundrys_index = set()
        index = dispatcher_boundary + 1  # 注意dispatcher_boundary
        while index <= self.the_first_contract_end_index:
            if (
                self.real_bytecode[index] == "JUMP"
                and self.real_bytecode[index - 2].startswith("PUSH")
                and self.real_bytecode[index - 2] != "PUSH0"
                and self.real_bytecode[index + 1] == "JUMPDEST"
            ):
                print(f"new turn!!!")
                repeated_jump_nodes = set()
                passed_paths_range_list = []
                possible_search_index = []
                possible_search_index.append(index)
                while possible_search_index:
                    current_index = possible_search_index.pop()
                    current_index_target_address_index_list = self.control_flow_graph[
                        current_index
                    ]
                    print(
                        f"current_index_target_address_index_list: {current_index_target_address_index_list}"
                    )
                    if current_index in repeated_jump_nodes:
                        continue
                    else:
                        repeated_jump_nodes.add(current_index)

                    for target_address_index in current_index_target_address_index_list:
                        keep_go_signal = True
                        next_jump_or_jumpi_index = min(
                            [
                                key
                                for key in self.control_flow_graph.keys()
                                if key > target_address_index
                            ]
                        )
                        for index1 in range(
                            target_address_index + 1, next_jump_or_jumpi_index
                        ):
                            if (
                                self.real_bytecode[index1] == "RETURN"
                                or self.real_bytecode[index1] == "STOP"
                                or self.real_bytecode[index1] == "REVERT"
                                or self.real_bytecode[index1] == "INVALID"
                                or self.real_bytecode[index1] == "SELFDESTRUCT"
                            ):
                                keep_go_signal = False
                                break
                        if keep_go_signal:
                            possible_search_index.append(next_jump_or_jumpi_index)
                            passed_paths_range_list.append(
                                [target_address_index, next_jump_or_jumpi_index]
                            )
                    print(f"passed_paths_range_list: {passed_paths_range_list}")
                print(f"repeated_jump_nodes: {repeated_jump_nodes}")
                for path in passed_paths_range_list:
                    if index + 1 in range(path[0], path[1] + 1):
                        print("111")
                        print(f"index+1: {index + 1}")
                        for key in self.control_flow_graph.keys():
                            if (
                                index + 1 in self.control_flow_graph[key]
                                and self.real_bytecode[key] == "JUMP"
                            ):
                                print("222")
                                self.all_jump_index_related_to_Call.add(index)
                                exist_internal_function_boundrys_index.add(key + 1)

            index += 1

        print(
            f"self.all_jump_index_related_to_Call: {self.all_jump_index_related_to_Call}"
        )
        print(
            f"exist_internal_function_boundrys_index: {exist_internal_function_boundrys_index}"
        )

        for index in list(exist_internal_function_boundrys_index):
            if index not in self.smartcontract_functions_index_position:
                self.smartcontract_functions_index_position.append(index)

        self.smartcontract_functions_index_position = sorted(
            self.smartcontract_functions_index_position
        )

        i = 0
        while i < len(self.smartcontract_functions_index_position) and i + 1 < len(
            self.smartcontract_functions_index_position
        ):
            self.smartcontract_functions_index_range.append(
                [
                    self.smartcontract_functions_index_position[i],
                    self.smartcontract_functions_index_position[i + 1] - 1,
                ]
            )
            i += 1
        print(self.smartcontract_functions_index_position)
        print(f"函数体有{len(self.smartcontract_functions_index_range)}个")
        print(
            f"self.smartcontract_functions_index_range: {self.smartcontract_functions_index_range}"
        )

        # 补丁,应对合约中只有一个函数并且其结尾具有return的情况,执行该函数最终不会返回函数包装器中,而在函数末尾以RETURN操作码就彻底结束
        if (
            len(self.smartcontract_functions_index_range) == 1
            and self.real_bytecode[-1] == "RETURN"
        ):
            self.smartcontract_functions_index_range[0][0] = (
                self.smartcontract_functions_index_range[0][0] + 2
            )
            print(
                f"final self.smartcontract_functions_index_range: {self.smartcontract_functions_index_range}"
            )

        return all_stacks


class SymbolicBytecodeExecutor(BytecodeExecutor):
    def __init__(self, symbolic_bytecode, real_bytecode):
        super().__init__(symbolic_bytecode, real_bytecode)
        self.handlers = OpcodeHandlers(self, self.generator)


# 堆栈快照分析
class Analysis1FunctionBodyOffChain:
    def __init__(self, executor):
        self.executor = executor
        self.special_stack_snapshot_index = []  # 暂时未用

    def count_consecutive_push_0_push_60_dup1(self, function_body_index):
        issuccess = False
        index = self.executor.smartcontract_functions_index_range[function_body_index][
            0
        ]
        temporary_variable_quantity = 0
        while (
            index
            <= self.executor.smartcontract_functions_index_range[function_body_index][1]
        ):
            print(
                f"self.executor.real_bytecode[index + 1]: {self.executor.real_bytecode[index + 1].lower()}"
            )
            if self.executor.real_bytecode[index + 1].lower().startswith("push"):
                if self.executor.real_bytecode[index + 1].lower() == "push0":
                    temporary_variable_quantity += 1
                elif (
                    self.executor.real_bytecode[index + 2].lower() == "0x0"
                    or self.executor.real_bytecode[index + 2].lower() == "0x60"
                ):
                    temporary_variable_quantity += 1
                    index += 1
                else:
                    break
            elif self.executor.real_bytecode[index + 1].lower() == "dup1":
                temporary_variable_quantity += 1
            else:
                break
            index += 1

        while issuccess is False:
            issuccess, temporary_variable_quantity, index_list = (
                self.examine_is_temporary_variable_quantity_right(
                    function_body_index,
                    temporary_variable_quantity,
                    1,  # 检测前后的额度暂定为1
                )
            )

        return temporary_variable_quantity, index_list

    def examine_is_temporary_variable_quantity_right(
        self, function_body_index, temporary_variable_quantity, check_indicator
    ):
        index_list = []
        index = self.executor.smartcontract_functions_index_range[function_body_index][
            0
        ]
        while (
            index
            <= self.executor.smartcontract_functions_index_range[function_body_index][1]
        ):
            if (
                self.executor.real_bytecode[index].lower().startswith("push")
                and self.executor.real_bytecode[index + 1].lower() != "push0"
            ):
                if (
                    self.executor.stack_snapshots[index]
                    == self.executor.stack_snapshots[
                        self.executor.smartcontract_functions_index_range[
                            function_body_index
                        ][0]
                    ]
                    + temporary_variable_quantity
                ):
                    index_list.append(index)
                index += 1
            else:
                if (
                    self.executor.stack_snapshots[index]
                    == self.executor.stack_snapshots[
                        self.executor.smartcontract_functions_index_range[
                            function_body_index
                        ][0]
                    ]
                    + temporary_variable_quantity
                ):
                    index_list.append(index)
            index += 1

        j = 0
        possible_temporary_variable_quantity_list = []
        while j < len(index_list):
            print("111")
            print(index_list)
            if j != 0 and j != len(index_list) - 1:
                k = index_list[j] - check_indicator
                print("222")
                print(
                    f"self.executor.real_bytecode[k].lower(): {self.executor.real_bytecode[k].lower()}"
                )
                print(f"k: {k}")
                # 补丁 k <= self.executor.smartcontract_functions_index_range[function_body_index][1]
                while (
                    k <= index_list[j] + check_indicator
                    and k
                    <= self.executor.smartcontract_functions_index_range[
                        function_body_index
                    ][1]
                ):
                    if self.executor.real_bytecode[k].lower().startswith("0x"):
                        pass
                    else:
                        print(
                            f"self.executor.stack_snapshots[k]: {self.executor.stack_snapshots[k]}"
                        )
                        if (
                            self.executor.stack_snapshots[k]
                            < self.executor.stack_snapshots[index_list[j]]
                        ):
                            possible_temporary_variable_quantity_list.append(
                                self.executor.stack_snapshots[k]
                                - self.executor.stack_snapshots[
                                    self.executor.smartcontract_functions_index_range[
                                        function_body_index
                                    ][0]
                                ]
                            )
                    k += 1
                print(
                    f"possible_temporary_variable_quantity_list: {possible_temporary_variable_quantity_list}"
                )
            j += 1

        if len(possible_temporary_variable_quantity_list) == 0:
            issuccess = True
            minvalue = temporary_variable_quantity
        else:
            issuccess = False
            minvalue = min(possible_temporary_variable_quantity_list)

        return issuccess, minvalue, index_list


# 跳转结构分析
class Analysis2FunctionBodyOffChain:
    def __init__(self, executor, special_stack_snapshots_index, function_body_index):
        self.executor = executor
        self.special_stack_snapshots_index = special_stack_snapshots_index
        self.jump_structure_info = []

        self.function_body_index = function_body_index

    # 有待进一步加工
    def record_jump_structure_info(
        self,
        jump_structure_type,
        jump_structure_depth,
        jump_structure_index_range,
        jump_structure_in_the_PC_detecting_range,
        jump_structure_parent,
        jump_structure_children,
    ):
        one_jump_structure_info = {
            "jump_structure_type": jump_structure_type,
            "jump_structure_depth": jump_structure_depth,
            "jump_structure_index_range": jump_structure_index_range,
            "jump_structure_in_the_PC_detecting_range": jump_structure_in_the_PC_detecting_range,
            "jump_structure_parent": jump_structure_parent,
            "jump_structure_children": jump_structure_children,
        }  # 跳转结构信息表
        self.jump_structure_info.append(one_jump_structure_info)

    def next_jumpi(self, current_index, max_index):
        next_jumpi_index = 0
        while next_jumpi_index == 0 and current_index < max_index:
            if self.executor.real_bytecode[current_index + 1].lower() == "jumpi":
                next_jumpi_index = current_index + 1
            current_index += 1
        if current_index == max_index and next_jumpi_index == 0:  # ?
            return False, next_jumpi_index
        else:
            return True, next_jumpi_index

    def notIsInTheSameBranchStructure(self, temporary_index, index):
        counter = 0
        for i in self.special_stack_snapshots_index:
            if (
                i >= self.executor.control_flow_graph[temporary_index][0] + 2
                and i <= index
            ):
                counter += 1
        if counter != 0:
            return True
        else:
            return False

    def traverse_designated_function_bytecode(
        self, parent, PC_detecting_range, current_jump_depth=0
    ):
        index = PC_detecting_range[0]
        C = [0, -1]  # ▷ PC detected range

        while index <= PC_detecting_range[1]:
            if index > C[1]:
                if self.executor.real_bytecode[index].lower() == "jump" and index >= 2:
                    if (
                        self.executor.real_bytecode[index - 2]
                        .lower()
                        .startswith("push")
                        and self.executor.real_bytecode[index - 2].lower() != "push0"
                        and self.executor.real_bytecode[index + 1].lower() == "jumpdest"
                    ):
                        if (
                            self.executor.control_flow_graph[index][0]
                            not in range(
                                self.executor.smartcontract_functions_index_range[
                                    self.function_body_index
                                ][0],
                                self.executor.smartcontract_functions_index_range[
                                    self.function_body_index
                                ][1]
                                + 1,
                            )
                            and self.executor.control_flow_graph[index][0]
                            >= self.executor.smartcontract_functions_index_range[0][0]
                        ):
                            print(
                                f"self.executor.control_flow_graph[index][0]: {self.executor.control_flow_graph[index][0]}"
                            )
                            print(f"PC_detecting_range[0]: {PC_detecting_range[0]}")
                            print(f"PC_detecting_range[1]: {PC_detecting_range[1]}")

                            # new part
                            temporary_list1 = []
                            for snapshot in self.special_stack_snapshots_index:
                                if snapshot < index:
                                    temporary_list1.append(snapshot)
                            call_structure_start = max(temporary_list1)

                            temporary_list2 = []
                            for snapshot in self.special_stack_snapshots_index:
                                if snapshot >= (index + 1) + 1:
                                    temporary_list2.append(snapshot)
                            call_structure_end = min(temporary_list2)
                            call_structure_end -= 1

                            self.record_jump_structure_info(
                                "Call",
                                current_jump_depth,
                                [call_structure_start, call_structure_end],
                                PC_detecting_range,
                                parent,
                                [],
                            )

                            C = [PC_detecting_range[0], index + 1]
                elif (
                    self.executor.real_bytecode[index].lower() == "jumpi" and index >= 2
                ):
                    if (
                        self.executor.real_bytecode[index - 2]
                        .lower()
                        .startswith("push")
                        and self.executor.real_bytecode[index - 2].lower() != "push0"
                    ):
                        if index in self.executor.exist_loop_node_by_jumpi:
                            D = self.executor.control_flow_graph[index][0]
                            E = self.executor.control_flow_graph[D - 1][0]

                            # new part
                            temporary_list3 = []
                            for snapshot in self.special_stack_snapshots_index:
                                if snapshot < E:
                                    temporary_list3.append(snapshot)
                            loop_structure_start = max(temporary_list3)

                            temporary_list4 = []
                            for snapshot in self.special_stack_snapshots_index:
                                if snapshot >= D + 1:
                                    temporary_list4.append(snapshot)
                            loop_structure_end = min(temporary_list4)
                            loop_structure_end -= 1

                            self.record_jump_structure_info(
                                "Loop",
                                current_jump_depth,
                                [loop_structure_start, loop_structure_end],
                                PC_detecting_range,
                                parent,
                                [[index + 1, D - 1]],
                            )

                            self.traverse_designated_function_bytecode(
                                [loop_structure_start, loop_structure_end],
                                [index + 1, D - 1],
                                current_jump_depth + 1,
                            )
                            C = [PC_detecting_range[0], D]
                        else:
                            # 当前条件分支结构中的所有分支块
                            branch_blocks = []
                            # 当前条件分支结构中的所有分支块的跳出index位置
                            branch_blocks_target_pc_address = []
                            temporary_index = 0
                            initial_index = index

                            while True:
                                D = self.executor.control_flow_graph[index][0]
                                branch_blocks.append([index + 1, D - 1])
                                if self.executor.real_bytecode[D - 1].lower() == "jump":
                                    branch_blocks_target_pc_address.append(
                                        self.executor.control_flow_graph[D - 1][0]
                                    )
                                temporary_index = index
                                isexist, index = self.next_jumpi(
                                    D, PC_detecting_range[1]
                                )
                                if not isexist:
                                    index = temporary_index
                                    break
                                else:
                                    if self.notIsInTheSameBranchStructure(
                                        temporary_index, index
                                    ):
                                        index = temporary_index
                                        break

                            if len(branch_blocks_target_pc_address) != 0:
                                F = max(branch_blocks_target_pc_address)
                            else:
                                F = self.executor.control_flow_graph[index][0]

                            # new part
                            temporary_list5 = []
                            for snapshot in self.special_stack_snapshots_index:
                                if snapshot < initial_index - 2:
                                    temporary_list5.append(snapshot)
                            conditionbranch_structure_start = max(temporary_list5)

                            temporary_list6 = []
                            for snapshot in self.special_stack_snapshots_index:
                                if snapshot >= F + 1:  # 临时F + 1改为F
                                    temporary_list6.append(snapshot)
                            print(
                                f"self.special_stack_snapshots_index: {self.special_stack_snapshots_index}"
                            )
                            print(f"F + 1: {F + 1}")
                            conditionbranch_structure_end = min(temporary_list6)
                            conditionbranch_structure_end -= 1

                            branch_children = branch_blocks
                            if len(branch_blocks_target_pc_address) != 0:
                                branch_children.append(
                                    [
                                        self.executor.control_flow_graph[index][0] + 1,
                                        min(branch_blocks_target_pc_address) - 1,
                                    ]
                                )

                            self.record_jump_structure_info(
                                "ConditionBranch",
                                current_jump_depth,
                                [
                                    conditionbranch_structure_start,
                                    conditionbranch_structure_end,
                                ],
                                PC_detecting_range,
                                parent,
                                branch_children,
                            )

                            for block in branch_blocks:
                                self.traverse_designated_function_bytecode(
                                    [
                                        conditionbranch_structure_start,
                                        conditionbranch_structure_end,
                                    ],
                                    block,
                                    current_jump_depth + 1,
                                )

                            if branch_children != branch_blocks:
                                self.traverse_designated_function_bytecode(
                                    [
                                        conditionbranch_structure_start,
                                        conditionbranch_structure_end,
                                    ],
                                    [
                                        self.executor.control_flow_graph[index][0] + 1,
                                        min(branch_blocks_target_pc_address) - 1,
                                    ],
                                    current_jump_depth
                                    + 1,  # 理论上此处的current_jump_depth + 1应为current_jump_depth
                                )

                            C = [PC_detecting_range[0], F]

            index += 1
        return self.jump_structure_info


# 分块
class Analysis3FunctionBodyOffChain:
    def __init__(
        self,
        executor,
        special_stack_snapshots_index,
        function_body_index,
        jump_structure_info,
    ):
        self.executor = executor
        self.special_stack_snapshots_index = special_stack_snapshots_index
        self.function_body_index = function_body_index
        self.jump_structure_info = jump_structure_info

    def bytecode_ByteDance_granularity_segmentation_by_jump_depth(self):
        temporary_list7 = []  # 暂时无用
        temporary_list8 = []  # 需要进一步分块的detecing区域
        temporary_list12 = []  # 用于维护跳转深度
        temporary_list13 = []  # 用于记录父跳转结构
        temporary_list14 = []  # 用于记录父跳转结构的类型
        temporary_list8.append(
            self.executor.smartcontract_functions_index_range[self.function_body_index]
        )
        temporary_list12.append(0)
        temporary_list13.append(
            self.executor.smartcontract_functions_index_range[self.function_body_index]
        )
        temporary_list14.append("Call")
        for info in self.jump_structure_info:
            # temporary_list7.append(info["jump_structure_depth"])
            print(f"info[jump_structure_children]: {info['jump_structure_children']}")
            for jsc in info["jump_structure_children"]:
                if jsc not in temporary_list8:
                    temporary_list8.append(jsc)
                    temporary_list12.append(info["jump_structure_depth"] + 1)
                    temporary_list13.append(info["jump_structure_index_range"])
                    temporary_list14.append(info["jump_structure_type"])
        # max_jump_structure_depth = max(temporary_list7)
        print(f"temporary_list8: {temporary_list8}")
        print(f"temporary_list12: {temporary_list12}")
        print(f"temporary_list13: {temporary_list13}")
        print(f"temporary_list14: {temporary_list14}")

        temporary_list9 = []  # 按detecting区域一致所分类出的跳转结构
        i = 0
        while i < len(temporary_list8):
            temporary_list9.append([])
            i += 1
        print(f"step1 temporary_list9: {temporary_list9}")

        index = 0
        for therange in temporary_list8:
            for info in self.jump_structure_info:
                if info["jump_structure_in_the_PC_detecting_range"] == therange:
                    temporary_list9[index].append(info)
            index += 1

        print(f"step2 temporary_list9: {temporary_list9}")

        j = 0
        while j < len(temporary_list9):
            current_range = temporary_list8[j]
            current_jump_depth = temporary_list12[j]
            current_jump_structure_parent = temporary_list13[j]
            current_jump_structure_parent_type = temporary_list14[j]

            k = 0
            temporary_list10 = []  # 单独分析关于某一detecting区域的跳转结构
            while k < len(temporary_list9[j]):
                temporary_list10.append(
                    temporary_list9[j][k]["jump_structure_index_range"]
                )
                k += 1

            print(f"temporary_list10: {temporary_list10}")
            print(f"current_range: {current_range}")
            print(f"current_jump_depth: {current_jump_depth}")
            print(f"current_jump_structure_parent: {current_jump_structure_parent}")
            print(
                f"current_jump_structure_parent_type: {current_jump_structure_parent_type}"
            )

            if len(temporary_list10) == 0:
                temporary_list11 = []  # 存放在detecting范围内的特殊堆栈快照
                for l in self.special_stack_snapshots_index:
                    # current_range[1] + 1 ???
                    if (
                        l >= current_range[0] and l <= current_range[1] + 1
                    ):  # 重要改动current_range[1]为current_range[1] + 1
                        temporary_list11.append(l)
                        print(f"l: {l}")

                # # 担心没有增量部分而注释掉
                # if current_jump_structure_parent_type == "Loop":
                #     temporary_list11.pop()
                #     temporary_list11.pop()

                m = 0
                while m < len(temporary_list11) - 1:
                    if [
                        temporary_list11[m],
                        temporary_list11[m + 1] - 1,
                    ] not in temporary_list10:
                        new_jump_structure_info = {
                            "jump_structure_type": "order",
                            "jump_structure_depth": current_jump_depth,
                            "jump_structure_index_range": [
                                temporary_list11[m],
                                temporary_list11[m + 1] - 1,
                            ],
                            "jump_structure_in_the_PC_detecting_range": current_range,
                            "jump_structure_parent": current_jump_structure_parent,
                            "jump_structure_children": [],
                        }  # 跳转结构信息表
                        self.jump_structure_info.append(new_jump_structure_info)
                        print(f"self.jump_structure_info: {self.jump_structure_info}")
                    m += 1
            else:
                temporary_list11 = []  # 存放在detecting范围内的特殊堆栈快照
                for l in self.special_stack_snapshots_index:
                    # current_range[1] + 1 ???
                    if (
                        l >= current_range[0]
                        and l <= current_range[1] + 1
                        and not any(
                            start <= l <= end + 1 for start, end in temporary_list10
                        )
                    ):  # 重要改动current_range[1]为current_range[1] + 1
                        temporary_list11.append(l)
                        print(f"l: {l}")

                for start, end in temporary_list10:
                    if start not in temporary_list11:
                        temporary_list11.append(start)
                    if end + 1 not in temporary_list11:
                        temporary_list11.append(end + 1)

                temporary_list11 = sorted(temporary_list11)

                print(
                    f"同一detecting范围中具有跳转结构时的temporary_list11: {temporary_list11}"
                )

                if current_jump_structure_parent_type == "Loop":
                    temporary_list11.pop()
                    temporary_list11.pop()
                # 万一return对象多，那可能会多删掉一个0级粒度块，所以默认可以多一个不准确的粒度块，但不能少一个准确的粒度块

                m = 0
                while m < len(temporary_list11) - 1:
                    if [
                        temporary_list11[m],
                        temporary_list11[m + 1] - 1,
                    ] not in temporary_list10:
                        new_jump_structure_info = {
                            "jump_structure_type": "order",
                            "jump_structure_depth": current_jump_depth,
                            "jump_structure_index_range": [
                                temporary_list11[m],
                                temporary_list11[m + 1] - 1,
                            ],
                            "jump_structure_in_the_PC_detecting_range": current_range,
                            "jump_structure_parent": current_jump_structure_parent,
                            "jump_structure_children": [],
                        }  # 跳转结构信息表
                        self.jump_structure_info.append(new_jump_structure_info)
                        print(f"self.jump_structure_info: {self.jump_structure_info}")
                    m += 1

            j += 1
        return self.jump_structure_info


# 查询关键状态变量赋值与转帐操作的父跳转结构或自身（包括两者）之间的所有传播项和被赋值项
class Analysis4FunctionBodyOffChain:
    def __init__(
        self,
        executor,
        special_stack_snapshots_index,
        function_body_index,
        jump_structure_info,
        temporary_variable_quantity,
    ):
        self.executor = executor
        self.special_stack_snapshots_index = special_stack_snapshots_index
        self.function_body_index = function_body_index
        self.jump_structure_info = jump_structure_info
        self.temporary_variable_quantity = temporary_variable_quantity

        self.transfer_accounts_opcodes_index_list = []
        self.critical_state_variable_assigned_value_opcodes_index_list = []
        self.all_create_opcodes_index_list = []

        self.step1_can_reorder_or_not = bool()
        self.final_jump_structure1 = {}
        self.final_jump_structure2 = {}

        self.critical_propagation_items = []
        self.critical_assigned_items = []
        self.middle_propagation_items = []
        self.middle_assigned_items = []

        self.the_number_of_stack_operands_in_special_stack_snapshot = (
            self.executor.stack_snapshots[self.special_stack_snapshots_index[0]]
        )

        self.index_mapping_to_critical_propagation_items = {}
        self.index_mapping_to_critical_assigned_items = {}
        self.index_mapping_to_middle_propagation_items = {}
        self.index_mapping_to_middle_assigned_items = {}

    # 为修复基于构造的重入漏洞,需要找出当前函数中的所有CREATE操作码
    def search_all_create_opcode(self):
        all_create_opcodes_index_list = []
        for index in range(
            self.executor.smartcontract_functions_index_range[self.function_body_index][
                0
            ],
            self.executor.smartcontract_functions_index_range[self.function_body_index][
                1
            ]
            + 1,
        ):
            if self.executor.real_bytecode[index] == "CREATE":
                all_create_opcodes_index_list.append(index)
        self.all_create_opcodes_index_list = all_create_opcodes_index_list
        print(
            f"self.all_create_opcodes_index_list: {self.all_create_opcodes_index_list}"
        )
        return all_create_opcodes_index_list

    # gasRemaining,直接找到CALL或DELEGATECALL操作码,否则通过迭代寻找所有调用结构中是否存在CALL或DELEGATECALL操作码,为鉴别委托调用
    def search_transfer_accounts_opcode(
        self, current_start_index, current_end_index, transfer_accounts_opcodes_index=-1
    ):
        for index in range(
            current_start_index,
            current_end_index + 1,
        ):
            if (
                self.executor.real_bytecode[index] == "CALL"
                # or self.executor.real_bytecode[index] == "CALLCODE"
                or self.executor.real_bytecode[index] == "DELEGATECALL"
                # or self.executor.real_bytecode[index] == "STATICCALL"
                and self.executor.opcodeindex_to_stack[index][-1]
                == BitVec("gasRemaining", 256)
            ):
                print(
                    f"self.executor.opcodeindex_to_stack[{index}][-1]: {self.executor.opcodeindex_to_stack[index][-1]}"
                )
                print(type(self.executor.opcodeindex_to_stack[index][-1]))
                if index in range(
                    self.executor.smartcontract_functions_index_range[
                        self.function_body_index
                    ][0],
                    self.executor.smartcontract_functions_index_range[
                        self.function_body_index
                    ][1]
                    + 1,
                ):
                    self.transfer_accounts_opcodes_index_list.append(index)
                else:
                    self.transfer_accounts_opcodes_index_list.append(
                        transfer_accounts_opcodes_index
                    )
                print(
                    f"step self.transfer_accounts_opcodes_index_list: {self.transfer_accounts_opcodes_index_list}"
                )

        # 判断嵌套下一层的转帐委托
        for index in range(
            current_start_index,
            current_end_index + 1,
        ):
            if self.executor.real_bytecode[index] == "JUMP":
                print("there is jump")
                print(f"current jump index: {index}")
                if index in self.executor.all_jump_index_related_to_Call:
                    print("there is critical jump")
                    if index in range(
                        self.executor.smartcontract_functions_index_range[
                            self.function_body_index
                        ][0],
                        self.executor.smartcontract_functions_index_range[
                            self.function_body_index
                        ][1]
                        + 1,
                    ):
                        transfer_accounts_opcodes_index = index
                    for key in self.executor.control_flow_graph.keys():
                        if (
                            index + 1 in self.executor.control_flow_graph[key]
                            and self.executor.real_bytecode[key] == "JUMP"
                        ):
                            next_end_index = key
                    next_start_index = self.executor.control_flow_graph[index][0]
                    print(f"next_start_index: {next_start_index}")
                    print(f"next_end_index: {next_end_index}")
                    self.search_transfer_accounts_opcode(
                        next_start_index,
                        next_end_index,
                        transfer_accounts_opcodes_index,
                    )

        self.transfer_accounts_opcodes_index_list = sorted(
            self.transfer_accounts_opcodes_index_list
        )
        potential_transfer_accounts_opcodes = self.transfer_accounts_opcodes_index_list
        return potential_transfer_accounts_opcodes

    # 找出当前函数内的在转帐或者创建新合约之后的所有状态变量赋值index,此法可弥补跨函数重入漏洞
    def search_all_critical_state_variable_assigned_value_opcode(self):
        all_state_variable_assigned_value_opcodes_index_list = []

        if len(self.all_create_opcodes_index_list) != 0:
            target_transfer_accounts_index = min(
                [
                    self.transfer_accounts_opcodes_index_list[0],
                    self.all_create_opcodes_index_list[0],
                ]
            )
        else:
            target_transfer_accounts_index = self.transfer_accounts_opcodes_index_list[
                0
            ]

        for index in range(
            target_transfer_accounts_index + 1,
            self.executor.smartcontract_functions_index_range[self.function_body_index][
                1
            ]
            + 1,
        ):
            if self.executor.real_bytecode[index] == "SSTORE":
                all_state_variable_assigned_value_opcodes_index_list.append(index)
        self.critical_state_variable_assigned_value_opcodes_index_list = (
            all_state_variable_assigned_value_opcodes_index_list
        )
        print(
            f"self.critical_state_variable_assigned_value_opcodes_index_list: {self.critical_state_variable_assigned_value_opcodes_index_list}"
        )
        return all_state_variable_assigned_value_opcodes_index_list

    # 通过关键条件分支结构找出关键状态变量赋值index,但此法无法弥补跨函数重入漏洞
    def search_critical_state_variable_assigned_value_opcode_by_critical_branch_jump_structure(
        self,
    ):
        info_index = 0
        critical_branch_jump_structure_children = []
        while info_index < len(self.jump_structure_info):
            if (
                self.jump_structure_info[info_index]["jump_structure_type"]
                == "ConditionBranch"
            ):
                critical_branch_PC_range = self.jump_structure_info[info_index][
                    "jump_structure_index_range"
                ]
                critical_branch_jump_structure_children = self.jump_structure_info[
                    info_index
                ]["jump_structure_children"]
                break
            else:
                raise UnboundLocalError(
                    "The function does not have conditional branch jump structure!"
                )
            info_index += 1
        print(f"critical_branch_PC_range: {critical_branch_PC_range}")
        print(
            f"critical_branch_jump_structure_children: {critical_branch_jump_structure_children}"
        )

        temporary_list1 = []  # 记录特殊jumpi的index
        for index in range(
            critical_branch_PC_range[0], critical_branch_PC_range[1] + 1
        ):
            if self.executor.real_bytecode[index] == "JUMPI" and not any(
                start <= index <= end
                for start, end in critical_branch_jump_structure_children
            ):
                temporary_list1.append(index)
                print(f"step1 temporary_list1: {temporary_list1}")
        max_jumpi_index_in_critical_branch_PC_range = max(temporary_list1)
        critical_branch_search_PC_range = [
            critical_branch_PC_range[0],
            self.executor.control_flow_graph[
                max_jumpi_index_in_critical_branch_PC_range
            ][0],
        ]
        print(f"critical_branch_search_PC_range: {critical_branch_search_PC_range}")

        temporary_list2 = []  # 记录特殊jumpi的所对应条件为假的跳转PC位置
        for index in temporary_list1:
            temporary_list2.append(self.executor.control_flow_graph[index][0])
        print(f"step1 temporary_list2: {temporary_list2}")
        temporary_list2.pop()
        print(f"step2 temporary_list2: {temporary_list2}")

        temporary_list1.extend(temporary_list2)
        temporary_list1.append(critical_branch_search_PC_range[0])
        temporary_list1 = sorted(temporary_list1)
        print(f"step2 temporary_list1: {temporary_list1}")

        i = 0
        temporary_list3 = []  # 记录多个条件分支前置准备的范围
        while i < len(temporary_list1) - 1:
            temporary_list3.append([temporary_list1[i], temporary_list1[i + 1]])
            i += 2
        print(f"temporary_list3: {temporary_list3}")

        # 记录多个条件分支前置准备范围中的堆栈顶为关键状态变量所对应的index位置
        temporary_list4 = []
        for start, end in temporary_list3:
            print(f"start, end: {start}, {end}")
            for index in range(start, end + 1):
                print(
                    f"self.executor.real_bytecode[index]: {self.executor.real_bytecode[index]}"
                )
                if self.executor.real_bytecode[index] == "SLOAD":
                    temporary_list4.append(index)
        print(f"temporary_list4: {temporary_list4}")

        # 记录关键状态变量被赋值时的index位置
        # 单个关键状态变量的情形
        temporary_list5 = []
        if len(temporary_list4) == 1:
            for j in range(
                temporary_list4[0] + 1,
                self.executor.smartcontract_functions_index_range[
                    self.function_body_index
                ][1]
                + 1,
            ):
                if (
                    self.executor.real_bytecode[j] == "SSTORE"
                    and self.executor.opcodeindex_to_stack[j][-1]
                    == self.executor.opcodeindex_to_stack[temporary_list4[0]][-1]
                ):
                    temporary_list5.append(j)
        else:
            pass  # 多个关键状态变量的情形

        print(f"temporary_list5: {temporary_list5}")
        self.critical_state_variable_assigned_value_opcodes_index_list = temporary_list5
        return temporary_list5

    def search_parent_jump_structure_in_the_same_deepest_detecting_range(
        self, which_critical_state_variable_assigned_value_opcodes_index=0
    ):
        index = 0
        temporary_list6 = []
        temporary_list7 = []

        if len(self.all_create_opcodes_index_list) != 0:
            target_transfer_accounts_index = min(
                [
                    self.transfer_accounts_opcodes_index_list[0],
                    self.all_create_opcodes_index_list[0],
                ]
            )
        else:
            target_transfer_accounts_index = self.transfer_accounts_opcodes_index_list[
                0
            ]

        while index < len(self.jump_structure_info):
            if target_transfer_accounts_index in range(
                self.jump_structure_info[index]["jump_structure_index_range"][0],
                self.jump_structure_info[index]["jump_structure_index_range"][1] + 1,
            ):
                temporary_list6.append(self.jump_structure_info[index])
            if self.critical_state_variable_assigned_value_opcodes_index_list[
                which_critical_state_variable_assigned_value_opcodes_index
            ] in range(
                self.jump_structure_info[index]["jump_structure_index_range"][0],
                self.jump_structure_info[index]["jump_structure_index_range"][1] + 1,
            ):
                temporary_list7.append(self.jump_structure_info[index])
            index += 1
        print(f"temporary_list6: {temporary_list6}")
        print(f"temporary_list7: {temporary_list7}")

        initial_jump_structure1 = temporary_list6[0]
        for info in temporary_list6:
            if (
                info["jump_structure_depth"]
                > initial_jump_structure1["jump_structure_depth"]
            ):
                initial_jump_structure1 = info
        print(f"initial_jump_structure1: {initial_jump_structure1}")

        initial_jump_structure2 = temporary_list7[0]
        for info in temporary_list7:
            if (
                info["jump_structure_depth"]
                > initial_jump_structure2["jump_structure_depth"]
            ):
                initial_jump_structure2 = info
        print(f"initial_jump_structure2: {initial_jump_structure2}")

        final_jump_structure1 = initial_jump_structure1
        final_jump_structure2 = initial_jump_structure2
        while (
            final_jump_structure1["jump_structure_in_the_PC_detecting_range"]
            != final_jump_structure2["jump_structure_in_the_PC_detecting_range"]
        ):
            if (
                final_jump_structure1["jump_structure_depth"]
                != final_jump_structure2["jump_structure_depth"]
            ):
                if (
                    final_jump_structure1["jump_structure_depth"]
                    > final_jump_structure2["jump_structure_depth"]
                ):
                    for info in temporary_list6:
                        if (
                            info["jump_structure_depth"]
                            == final_jump_structure2["jump_structure_depth"]
                        ):
                            final_jump_structure1 = info
                            break
                else:
                    for info in temporary_list7:
                        if (
                            info["jump_structure_depth"]
                            == final_jump_structure1["jump_structure_depth"]
                        ):
                            final_jump_structure2 = info
                            break

                if (
                    final_jump_structure1["jump_structure_in_the_PC_detecting_range"]
                    == final_jump_structure2["jump_structure_in_the_PC_detecting_range"]
                ):
                    break

            print(f"step1 final_jump_structure1: {final_jump_structure1}")
            print(f"step1 final_jump_structure2: {final_jump_structure2}")

            for info in temporary_list6:
                if (
                    info["jump_structure_depth"]
                    == final_jump_structure1["jump_structure_depth"] - 1
                ):
                    final_jump_structure1 = info
                    break
            for info in temporary_list7:
                if (
                    info["jump_structure_depth"]
                    == final_jump_structure2["jump_structure_depth"] - 1
                ):
                    final_jump_structure2 = info
                    break

            if (
                final_jump_structure1["jump_structure_depth"] == 0
                and final_jump_structure2["jump_structure_depth"] == 0
            ):
                break

        print(f"step2 final_jump_structure1: {final_jump_structure1}")
        print(f"step2 final_jump_structure2: {final_jump_structure2}")
        if (
            final_jump_structure1["jump_structure_in_the_PC_detecting_range"]
            == final_jump_structure2["jump_structure_in_the_PC_detecting_range"]
            and final_jump_structure1["jump_structure_index_range"][0]
            < final_jump_structure2["jump_structure_index_range"][0]
        ):  # 情况必须为状态变量赋值在转帐操作之后执行
            self.step1_can_reorder_or_not = True
        else:
            self.step1_can_reorder_or_not = False
        self.final_jump_structure1 = final_jump_structure1
        self.final_jump_structure2 = final_jump_structure2
        print(f"self.step1_can_reorder_or_not: {self.step1_can_reorder_or_not}")

        # 准备深入判断
        if (
            self.step1_can_reorder_or_not == False
            and self.final_jump_structure1 == self.final_jump_structure2
            and which_critical_state_variable_assigned_value_opcodes_index + 1
            < len(self.critical_state_variable_assigned_value_opcodes_index_list)
        ):
            self.search_parent_jump_structure_in_the_same_deepest_detecting_range(
                which_critical_state_variable_assigned_value_opcodes_index + 1
            )

        return self.final_jump_structure1.copy(), self.final_jump_structure2.copy()

    def search_parent_jump_structure_in_the_adjacent_deepest_detecting_range(self):
        index = 0
        temporary_list6 = []
        temporary_list7 = []

        if len(self.all_create_opcodes_index_list) != 0:
            target_transfer_accounts_index = min(
                [
                    self.transfer_accounts_opcodes_index_list[0],
                    self.all_create_opcodes_index_list[0],
                ]
            )
        else:
            target_transfer_accounts_index = self.transfer_accounts_opcodes_index_list[
                0
            ]

        while index < len(self.jump_structure_info):
            if (
                target_transfer_accounts_index
                in range(
                    self.jump_structure_info[index]["jump_structure_index_range"][0],
                    self.jump_structure_info[index]["jump_structure_index_range"][1]
                    + 1,
                )
                and self.jump_structure_info[index]["jump_structure_type"]
                == "ConditionBranch"
            ):
                temporary_list6.append(self.jump_structure_info[index])
            if self.critical_state_variable_assigned_value_opcodes_index_list[
                0
            ] in range(
                self.jump_structure_info[index]["jump_structure_index_range"][0],
                self.jump_structure_info[index]["jump_structure_index_range"][1] + 1,
            ):
                temporary_list7.append(self.jump_structure_info[index])
            index += 1
        print(f"temporary_list6: {temporary_list6}")
        print(f"temporary_list7: {temporary_list7}")

        if len(temporary_list6) == 0:
            self.step1_can_reorder_or_not = False
        else:
            initial_jump_structure1 = temporary_list6[0]
            for info in temporary_list6:
                if (
                    info["jump_structure_depth"]
                    > initial_jump_structure1["jump_structure_depth"]
                ):
                    initial_jump_structure1 = info
            print(f"initial_jump_structure1: {initial_jump_structure1}")

            initial_jump_structure2 = temporary_list7[0]
            for info in temporary_list7:
                if (
                    info["jump_structure_depth"]
                    > initial_jump_structure2["jump_structure_depth"]
                ):
                    initial_jump_structure2 = info
            print(f"initial_jump_structure2: {initial_jump_structure2}")

            final_jump_structure1 = initial_jump_structure1
            final_jump_structure2 = initial_jump_structure2

            for info in temporary_list7:
                if (
                    info["jump_structure_depth"]
                    == final_jump_structure1["jump_structure_depth"] + 1
                ):
                    final_jump_structure2 = info
                    break

            # 转帐操作必须要在第一分支条件判断中
            if (
                target_transfer_accounts_index
                < final_jump_structure1["jump_structure_children"][0][0]
            ):
                print(f"transfer in the first branch judgment")
                self.step1_can_reorder_or_not = True
            else:
                # print(target_transfer_accounts_index)
                # print(final_jump_structure1["jump_structure_children"][0][0])
                print(f"transfer not in the first branch judgment")
                self.step1_can_reorder_or_not = False

            # 状态变量赋值块必须在第一分支中
            if self.step1_can_reorder_or_not == True:
                if (
                    final_jump_structure2["jump_structure_index_range"][0]
                    >= final_jump_structure1["jump_structure_children"][0][0]
                    and final_jump_structure2["jump_structure_index_range"][1]
                    <= final_jump_structure1["jump_structure_children"][0][1]
                ):
                    print(f"state in the first branch")
                    self.step1_can_reorder_or_not = True
                else:
                    # print(final_jump_structure1["jump_structure_children"][0][0])
                    # print(final_jump_structure1["jump_structure_children"][0][1])
                    # print(final_jump_structure2["jump_structure_index_range"][0])
                    # print(final_jump_structure2["jump_structure_index_range"][1])
                    print(f"state not in the first branch")
                    self.step1_can_reorder_or_not = False

            print(f"step3 final_jump_structure1: {final_jump_structure1}")
            print(f"step3 final_jump_structure2: {final_jump_structure2}")
            self.final_jump_structure1 = final_jump_structure1
            self.final_jump_structure2 = final_jump_structure2

        # 不能只存在一条分支
        if self.step1_can_reorder_or_not == True:
            if len(final_jump_structure1["jump_structure_children"]) <= 1:
                print(f"there is only one branch")
                self.step1_can_reorder_or_not = False

        # 仅有转帐操作相关的那条分支中可以出现状态变量赋值,否则不可通过
        if self.step1_can_reorder_or_not == True:
            for index in self.critical_state_variable_assigned_value_opcodes_index_list:
                for child_range in final_jump_structure1["jump_structure_children"]:
                    if (
                        index in child_range
                        and index
                        not in final_jump_structure1["jump_structure_children"][0]
                    ):
                        print(f"other branches have state")
                        self.step1_can_reorder_or_not = False
                        break

        # 检查转帐操作所在的跳转深度最大的那个条件分支结构中是否存在REVERT,这一定程度上决定了self.step1_can_reorder_or_not的值
        if self.step1_can_reorder_or_not == True:
            for child_range in final_jump_structure1["jump_structure_children"]:
                for index in range(
                    child_range[0],
                    child_range[1] + 1,
                ):
                    if index not in range(
                        final_jump_structure1["jump_structure_children"][0][0],
                        final_jump_structure1["jump_structure_children"][0][1] + 1,
                    ):
                        if self.executor.real_bytecode[index] == "REVERT":
                            print(f"There is a REVERT in index {index}!!!")
                            self.step1_can_reorder_or_not = True
                            break
                        else:
                            self.step1_can_reorder_or_not = False
        print(f"final self.step1_can_reorder_or_not: {self.step1_can_reorder_or_not}")

        return self.final_jump_structure1.copy(), self.final_jump_structure2.copy()

    # 存在那种情况，映射式的不同状态变量地址在堆栈中的表现形式一致，这是因为不同点保存在内存的同一块位置所导致的，反向探索或许可以解决这一点，模拟内存和存储或许也可以解决这一点
    def record_critical_propagation_items_and_assigned_items(
        self, range_start, range_end
    ):
        print(
            f"self.the_number_of_stack_operands_in_special_stack_snapshot: {self.the_number_of_stack_operands_in_special_stack_snapshot}"
        )
        # 先检查关键状态变量赋值块中的被赋值项和传播项
        for index in range(
            range_start,
            range_end + 1,
        ):
            if (
                self.executor.real_bytecode[index] == "SLOAD"
                and ["storage", self.executor.opcodeindex_to_stack[index][-1]]
                not in self.critical_propagation_items
            ):
                self.critical_propagation_items.append(
                    ["storage", self.executor.opcodeindex_to_stack[index][-1]]
                )
                self.index_mapping_to_critical_propagation_items.update(
                    {index: ["storage", self.executor.opcodeindex_to_stack[index][-1]]}
                )
            elif (
                self.executor.real_bytecode[index] == "MLOAD"
                and ["memory", self.executor.opcodeindex_to_stack[index][-1]]
                not in self.critical_propagation_items
            ):
                self.critical_propagation_items.append(
                    ["memory", self.executor.opcodeindex_to_stack[index][-1]]
                )
                self.index_mapping_to_critical_propagation_items.update(
                    {index: ["memory", self.executor.opcodeindex_to_stack[index][-1]]}
                )
            elif self.executor.real_bytecode[index].startswith("DUP"):
                if (
                    self.executor.stack_snapshots[index]
                    - int(self.executor.real_bytecode[index][3:])
                    + 1
                    <= self.the_number_of_stack_operands_in_special_stack_snapshot
                ) and [
                    "stack",
                    self.executor.stack_snapshots[index]
                    - int(self.executor.real_bytecode[index][3:]),
                ] not in self.critical_propagation_items:
                    self.critical_propagation_items.append(
                        [
                            "stack",
                            self.executor.stack_snapshots[index]
                            - int(self.executor.real_bytecode[index][3:]),
                        ]
                    )  # 记录了dup*所用的堆栈的索引位置，而不是dup*所用的堆栈的长度位置
                    self.index_mapping_to_critical_propagation_items.update(
                        {
                            index: [
                                "stack",
                                self.executor.stack_snapshots[index]
                                - int(self.executor.real_bytecode[index][3:]),
                            ]
                        }
                    )
            elif (
                self.executor.real_bytecode[index] == "SSTORE"
                and ["storage", self.executor.opcodeindex_to_stack[index][-1]]
                not in self.critical_assigned_items
            ):
                self.critical_assigned_items.append(
                    ["storage", self.executor.opcodeindex_to_stack[index][-1]]
                )
                self.index_mapping_to_critical_assigned_items.update(
                    {index: ["storage", self.executor.opcodeindex_to_stack[index][-1]]}
                )
            elif (
                self.executor.real_bytecode[index] == "MSTORE"
                and ["memory", self.executor.opcodeindex_to_stack[index][-1]]
                not in self.critical_assigned_items
            ):
                self.critical_assigned_items.append(
                    ["memory", self.executor.opcodeindex_to_stack[index][-1]]
                )
                self.index_mapping_to_critical_assigned_items.update(
                    {index: ["memory", self.executor.opcodeindex_to_stack[index][-1]]}
                )
            elif self.executor.real_bytecode[index].startswith("SWAP"):
                if (
                    self.executor.stack_snapshots[index]
                    - int(self.executor.real_bytecode[index][4:])
                    <= self.the_number_of_stack_operands_in_special_stack_snapshot
                ) and [
                    "stack",
                    self.executor.stack_snapshots[index]
                    - int(self.executor.real_bytecode[index][4:])
                    - 1,
                ] not in self.critical_assigned_items:
                    self.critical_assigned_items.append(
                        [
                            "stack",
                            self.executor.stack_snapshots[index]
                            - int(self.executor.real_bytecode[index][4:])
                            - 1,
                        ]
                    )
                    self.index_mapping_to_critical_assigned_items.update(
                        {
                            index: [
                                "stack",
                                self.executor.stack_snapshots[index]
                                - int(self.executor.real_bytecode[index][4:])
                                - 1,
                            ]
                        }
                    )
            elif self.executor.real_bytecode[index] == "JUMP":
                if index in self.executor.all_jump_index_related_to_Call:
                    for key in self.executor.control_flow_graph.keys():
                        if (
                            index + 1 in self.executor.control_flow_graph[key]
                            and self.executor.real_bytecode[key] == "JUMP"
                        ):
                            next_end_index = key
                    next_start_index = self.executor.control_flow_graph[index][0]
                    print(f"next_start_index: {next_start_index}")
                    print(f"next_end_index: {next_end_index}")
                    self.record_critical_propagation_items_and_assigned_items(
                        next_start_index,
                        next_end_index,
                    )

        # print(f"self.critical_propagation_items: {self.critical_propagation_items}")
        # print(f"self.critical_assigned_items: {self.critical_assigned_items}")
        critical_propagation_items = self.critical_propagation_items.copy()
        critical_assigned_items = self.critical_assigned_items.copy()
        index_mapping_to_critical_propagation_items = (
            self.index_mapping_to_critical_propagation_items.copy()
        )
        index_mapping_to_critical_assigned_items = (
            self.index_mapping_to_critical_assigned_items.copy()
        )
        return (
            critical_propagation_items,
            critical_assigned_items,
            index_mapping_to_critical_propagation_items,
            index_mapping_to_critical_assigned_items,
        )

    # 存在那种情况，映射式的不同状态变量地址在堆栈中的表现形式一致，这是因为不同点保存在内存的同一块位置所导致的，反向探索或许可以解决这一点，模拟内存和存储或许也可以解决这一点
    def record_middle_propagation_items_and_assigned_items(
        self,
        range_start,
        range_end,
    ):
        print(
            f"self.the_number_of_stack_operands_in_special_stack_snapshot: {self.the_number_of_stack_operands_in_special_stack_snapshot}"
        )
        # 再检查中间部分中的被赋值项和传播项
        for index in range(
            range_start,
            range_end,
        ):
            if (
                self.executor.real_bytecode[index] == "SLOAD"
                and ["storage", self.executor.opcodeindex_to_stack[index][-1]]
                not in self.middle_propagation_items
            ):
                self.middle_propagation_items.append(
                    ["storage", self.executor.opcodeindex_to_stack[index][-1]]
                )
                self.index_mapping_to_middle_propagation_items.update(
                    {index: ["storage", self.executor.opcodeindex_to_stack[index][-1]]}
                )
            elif (
                self.executor.real_bytecode[index] == "MLOAD"
                and ["memory", self.executor.opcodeindex_to_stack[index][-1]]
                not in self.middle_propagation_items
            ):
                self.middle_propagation_items.append(
                    ["memory", self.executor.opcodeindex_to_stack[index][-1]]
                )
                self.index_mapping_to_middle_propagation_items.update(
                    {index: ["memory", self.executor.opcodeindex_to_stack[index][-1]]}
                )
            elif self.executor.real_bytecode[index].startswith("DUP"):
                if (
                    self.executor.stack_snapshots[index]
                    - int(self.executor.real_bytecode[index][3:])
                    + 1
                    <= self.the_number_of_stack_operands_in_special_stack_snapshot
                ) and [
                    "stack",
                    self.executor.stack_snapshots[index]
                    - int(self.executor.real_bytecode[index][3:]),
                ] not in self.middle_propagation_items:
                    self.middle_propagation_items.append(
                        [
                            "stack",
                            self.executor.stack_snapshots[index]
                            - int(self.executor.real_bytecode[index][3:]),
                        ]
                    )  # 记录了dup*所用的堆栈的索引位置，而不是dup*所用的堆栈的长度位置
                    self.index_mapping_to_middle_propagation_items.update(
                        {
                            index: [
                                "stack",
                                self.executor.stack_snapshots[index]
                                - int(self.executor.real_bytecode[index][3:]),
                            ]
                        }
                    )
            elif (
                self.executor.real_bytecode[index] == "SSTORE"
                and ["storage", self.executor.opcodeindex_to_stack[index][-1]]
                not in self.middle_assigned_items
            ):
                self.middle_assigned_items.append(
                    ["storage", self.executor.opcodeindex_to_stack[index][-1]]
                )
                self.index_mapping_to_middle_assigned_items.update(
                    {index: ["storage", self.executor.opcodeindex_to_stack[index][-1]]}
                )
            elif (
                self.executor.real_bytecode[index] == "MSTORE"
                and ["memory", self.executor.opcodeindex_to_stack[index][-1]]
                not in self.middle_assigned_items
            ):
                self.middle_assigned_items.append(
                    ["memory", self.executor.opcodeindex_to_stack[index][-1]]
                )
                self.index_mapping_to_middle_assigned_items.update(
                    {index: ["memory", self.executor.opcodeindex_to_stack[index][-1]]}
                )
            elif self.executor.real_bytecode[index].startswith("SWAP"):
                if (
                    self.executor.stack_snapshots[index]
                    - int(self.executor.real_bytecode[index][4:])
                    + 1
                    <= self.the_number_of_stack_operands_in_special_stack_snapshot
                ) and [
                    "stack",
                    self.executor.stack_snapshots[index]
                    - int(self.executor.real_bytecode[index][4:])
                    - 1,
                ] not in self.middle_assigned_items:
                    self.middle_assigned_items.append(
                        [
                            "stack",
                            self.executor.stack_snapshots[index]
                            - int(self.executor.real_bytecode[index][4:])
                            - 1,
                        ]
                    )
                    self.index_mapping_to_middle_assigned_items.update(
                        {
                            index: [
                                "stack",
                                self.executor.stack_snapshots[index]
                                - int(self.executor.real_bytecode[index][4:])
                                - 1,
                            ]
                        }
                    )
            elif self.executor.real_bytecode[index] == "JUMP":
                if index in self.executor.all_jump_index_related_to_Call:
                    for key in self.executor.control_flow_graph.keys():
                        if (
                            index + 1 in self.executor.control_flow_graph[key]
                            and self.executor.real_bytecode[key] == "JUMP"
                        ):
                            next_end_index = key
                    next_start_index = self.executor.control_flow_graph[index][0]
                    print(f"next_start_index: {next_start_index}")
                    print(f"next_end_index: {next_end_index}")
                    self.record_middle_propagation_items_and_assigned_items(
                        next_start_index,
                        next_end_index,
                    )

        # print(f"self.middle_propagation_items: {self.middle_propagation_items}")
        # print(f"self.middle_assigned_items: {self.middle_assigned_items}")
        middle_propagation_items = self.middle_propagation_items.copy()
        middle_assigned_items = self.middle_assigned_items.copy()
        index_mapping_to_middle_propagation_items = (
            self.index_mapping_to_middle_propagation_items.copy()
        )
        index_mapping_to_middle_assigned_items = (
            self.index_mapping_to_middle_assigned_items.copy()
        )
        return (
            middle_propagation_items,
            middle_assigned_items,
            index_mapping_to_middle_propagation_items,
            index_mapping_to_middle_assigned_items,
        )


class Analysis5FunctionBodyOffChain:
    def __init__(
        self,
        executor,
        special_stack_snapshots_index,
        function_body_index,
        jump_structure_info,
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
    ):
        self.executor = executor
        self.special_stack_snapshots_index = special_stack_snapshots_index
        self.function_body_index = function_body_index
        self.jump_structure_info = jump_structure_info
        self.temporary_variable_quantity = temporary_variable_quantity
        self.critical_propagation_items = critical_propagation_items
        self.critical_assigned_items = critical_assigned_items
        self.middle_propagation_items = middle_propagation_items
        self.middle_assigned_items = middle_assigned_items
        self.final_jump_structure1 = final_jump_structure1
        self.final_jump_structure2 = final_jump_structure2
        self.index_mapping_to_critical_propagation_items = (
            index_mapping_to_critical_propagation_items
        )
        self.index_mapping_to_critical_assigned_items = (
            index_mapping_to_critical_assigned_items
        )
        self.index_mapping_to_middle_propagation_items = (
            index_mapping_to_middle_propagation_items
        )
        self.index_mapping_to_middle_assigned_items = (
            index_mapping_to_middle_assigned_items
        )

        self.step2_can_reorder_or_not = bool()
        self.reorder_function_real_bytecode = []
        self.reorder_real_bytecode = []

    def determine_whether_the_consistency_of_data_dependency_relationships_is_met(
        self,
        is_or_not_determine_whether_the_consistency_of_data_dependency_relationships_is_met,
    ):
        if is_or_not_determine_whether_the_consistency_of_data_dependency_relationships_is_met:
            for item1 in self.critical_propagation_items:
                if item1 in self.middle_assigned_items:
                    step2_can_reorder_or_not = False
                    break
                else:
                    step2_can_reorder_or_not = True

            for item2 in self.critical_assigned_items:
                if item2 in self.middle_propagation_items:
                    step2_can_reorder_or_not = False
                    break
                else:
                    step2_can_reorder_or_not = True
        self.step2_can_reorder_or_not = step2_can_reorder_or_not
        print(f"step2_can_reorder_or_not: {step2_can_reorder_or_not}")

        # if is_or_not_determine_whether_the_consistency_of_data_dependency_relationships_is_met:
        #     # step1
        #     index1 = 0
        #     while index1 < len(self.critical_propagation_items):
        #         # test
        #         if self.critical_propagation_items[index1][0] == "storage":
        #             if (
        #                 self.critical_propagation_items[index1]
        #                 not in self.middle_assigned_items
        #             ):
        #                 step2_can_reorder_or_not = True
        #             else:
        #                 for key in self.index_mapping_to_middle_assigned_items.keys():
        #                     if (
        #                         self.index_mapping_to_middle_assigned_items[key]
        #                         == self.critical_propagation_items[index1]
        #                     ):
        #                         key1 = key
        #                 for (
        #                     key
        #                 ) in self.index_mapping_to_critical_propagation_items.keys():
        #                     if (
        #                         self.index_mapping_to_critical_propagation_items[key]
        #                         == self.critical_propagation_items[index1]
        #                     ):
        #                         key2 = key
        #                 if key1 > key2:
        #                     range_for_diff = [key2, key1]
        #                 else:
        #                     range_for_diff = [key1, key2]
        #                 print(f"step1 range_for_diff: {range_for_diff}")

        #                 index2 = 0
        #                 while index2 < len(self.critical_assigned_items):
        #                     if self.critical_assigned_items[index2][0] == "memory":
        #                         # 逻辑可优化str...str
        #                         match = re.search(
        #                             r"memory\[(.*?)\]",
        #                             str(self.critical_propagation_items[index1][1]),
        #                         )
        #                         if match:
        #                             memory_content = match.group(1)
        #                             if (
        #                                 str(self.critical_assigned_items[index2][1])
        #                                 in memory_content
        #                             ):
        #                                 for (
        #                                     key
        #                                 ) in (
        #                                     self.index_mapping_to_critical_assigned_items.keys()
        #                                 ):
        #                                     if (
        #                                         self.index_mapping_to_critical_assigned_items[
        #                                             key
        #                                         ]
        #                                         == self.critical_assigned_items[index2]
        #                                     ):
        #                                         key3 = key
        #                                         print(f"step1 key3: {key3}")
        #                                 if key3 in range(
        #                                     range_for_diff[0], range_for_diff[1] + 1
        #                                 ):
        #                                     step2_can_reorder_or_not = True
        #                                     break
        #                             else:
        #                                 step2_can_reorder_or_not = False
        #                         else:
        #                             step2_can_reorder_or_not = False
        #                     index2 += 1

        #                 index3 = 0
        #                 while index3 < len(self.middle_assigned_items):
        #                     if self.middle_assigned_items[index3][0] == "memory":
        #                         # 逻辑可优化str...str
        #                         match = re.search(
        #                             r"memory\[(.*?)\]",
        #                             str(self.critical_propagation_items[index1][1]),
        #                         )
        #                         if match:
        #                             memory_content = match.group(1)
        #                             if (
        #                                 str(self.middle_assigned_items[index3][1])
        #                                 in memory_content
        #                             ):
        #                                 for (
        #                                     key
        #                                 ) in (
        #                                     self.index_mapping_to_middle_assigned_items.keys()
        #                                 ):
        #                                     if (
        #                                         self.index_mapping_to_middle_assigned_items[
        #                                             key
        #                                         ]
        #                                         == self.middle_assigned_items[index3]
        #                                     ):
        #                                         key3 = key
        #                                         print(f"step1 key3: {key3}")
        #                                 if key3 in range(
        #                                     range_for_diff[0], range_for_diff[1] + 1
        #                                 ):
        #                                     step2_can_reorder_or_not = True
        #                                     break
        #                             else:
        #                                 step2_can_reorder_or_not = False
        #                         else:
        #                             step2_can_reorder_or_not = False
        #                     index3 += 1
        #                 if step2_can_reorder_or_not == False:
        #                     break
        #         else:
        #             if (
        #                 self.critical_propagation_items[index1]
        #                 in self.middle_assigned_items
        #             ):
        #                 step2_can_reorder_or_not = False
        #                 break
        #             else:
        #                 step2_can_reorder_or_not = True

        #         index1 += 1

        #     # step2
        #     index1 = 0
        #     while index1 < len(self.middle_propagation_items):
        #         # test
        #         if self.middle_propagation_items[index1][0] == "storage":
        #             if (
        #                 self.middle_propagation_items[index1]
        #                 not in self.critical_assigned_items
        #             ):
        #                 step2_can_reorder_or_not = True
        #             else:
        #                 for key in self.index_mapping_to_critical_assigned_items.keys():
        #                     if (
        #                         self.index_mapping_to_critical_assigned_items[key]
        #                         == self.middle_propagation_items[index1]
        #                     ):
        #                         key1 = key
        #                 for (
        #                     key
        #                 ) in self.index_mapping_to_middle_propagation_items.keys():
        #                     if (
        #                         self.index_mapping_to_middle_propagation_items[key]
        #                         == self.middle_propagation_items[index1]
        #                     ):
        #                         key2 = key
        #                 if key1 > key2:
        #                     range_for_diff = [key2, key1]
        #                 else:
        #                     range_for_diff = [key1, key2]
        #                 print(f"step2 range_for_diff: {range_for_diff}")

        #                 index2 = 0
        #                 while index2 < len(self.middle_assigned_items):
        #                     if self.middle_assigned_items[index2][0] == "memory":
        #                         # 逻辑可优化str...str
        #                         match = re.search(
        #                             r"memory\[(.*?)\]",
        #                             str(self.middle_propagation_items[index1][1]),
        #                         )
        #                         if match:
        #                             memory_content = match.group(1)
        #                             if (
        #                                 str(self.middle_assigned_items[index2][1])
        #                                 in memory_content
        #                             ):
        #                                 for (
        #                                     key
        #                                 ) in (
        #                                     self.index_mapping_to_middle_assigned_items.keys()
        #                                 ):
        #                                     if (
        #                                         self.index_mapping_to_middle_assigned_items[
        #                                             key
        #                                         ]
        #                                         == self.middle_assigned_items[index2]
        #                                     ):
        #                                         key3 = key
        #                                         print(f"step2 key3: {key3}")
        #                                 if key3 in range(
        #                                     range_for_diff[0], range_for_diff[1] + 1
        #                                 ):
        #                                     step2_can_reorder_or_not = True
        #                                     break
        #                             else:
        #                                 step2_can_reorder_or_not = False
        #                         else:
        #                             step2_can_reorder_or_not = False
        #                     index2 += 1

        #                 index3 = 0
        #                 while index3 < len(self.critical_assigned_items):
        #                     if self.critical_assigned_items[index3][0] == "memory":
        #                         # 逻辑可优化str...str
        #                         match = re.search(
        #                             r"memory\[(.*?)\]",
        #                             str(self.middle_propagation_items[index1][1]),
        #                         )
        #                         if match:
        #                             memory_content = match.group(1)
        #                             if (
        #                                 str(self.critical_assigned_items[index3][1])
        #                                 in memory_content
        #                             ):
        #                                 for (
        #                                     key
        #                                 ) in (
        #                                     self.index_mapping_to_critical_assigned_items.keys()
        #                                 ):
        #                                     if (
        #                                         self.index_mapping_to_critical_assigned_items[
        #                                             key
        #                                         ]
        #                                         == self.critical_assigned_items[index3]
        #                                     ):
        #                                         key3 = key
        #                                         print(f"step2 key3: {key3}")
        #                                 if key3 in range(
        #                                     range_for_diff[0], range_for_diff[1] + 1
        #                                 ):
        #                                     step2_can_reorder_or_not = True
        #                                     break
        #                             else:
        #                                 step2_can_reorder_or_not = False
        #                         else:
        #                             step2_can_reorder_or_not = False
        #                     index3 += 1
        #                 if step2_can_reorder_or_not == False:
        #                     break
        #         else:
        #             if (
        #                 self.middle_propagation_items[index1]
        #                 in self.critical_assigned_items
        #             ):
        #                 step2_can_reorder_or_not = False
        #                 break
        #             else:
        #                 step2_can_reorder_or_not = True

        #         index1 += 1
        # self.step2_can_reorder_or_not = step2_can_reorder_or_not
        # print(f"step2_can_reorder_or_not: {step2_can_reorder_or_not}")

        return step2_can_reorder_or_not

    def reorder_key_granularity_bytecode_blocks(self, adjacent_or_same_signal):
        real_bytecode = self.executor.real_bytecode.copy()
        print(real_bytecode)

        final_jump_structure1_index_range = self.final_jump_structure1[
            "jump_structure_index_range"
        ]
        final_jump_structure2_index_range = self.final_jump_structure2[
            "jump_structure_index_range"
        ]
        print(f"final_jump_structure1_index_range: {final_jump_structure1_index_range}")
        print(f"final_jump_structure2_index_range: {final_jump_structure2_index_range}")

        more_unchanged_real_bytecode_list1 = real_bytecode[
            0 : self.executor.smartcontract_functions_index_range[
                self.function_body_index
            ][0]
        ]
        unchanged_real_bytecode_list1 = real_bytecode[
            self.executor.smartcontract_functions_index_range[self.function_body_index][
                0
            ] : final_jump_structure1_index_range[0]
        ]
        middle_real_bytecode_list = real_bytecode[
            final_jump_structure1_index_range[0] : final_jump_structure2_index_range[0]
        ]
        reorder_real_bytecode_list = real_bytecode[
            final_jump_structure2_index_range[0] : final_jump_structure2_index_range[1]
            + 1
        ]
        unchanged_real_bytecode_list2 = real_bytecode[
            final_jump_structure2_index_range[1]
            + 1 : self.executor.smartcontract_functions_index_range[
                self.function_body_index
            ][1]
            + 1
        ]
        more_unchanged_real_bytecode_list2 = real_bytecode[
            self.executor.smartcontract_functions_index_range[self.function_body_index][
                1
            ]
            + 1 : len(real_bytecode)
        ]
        print(
            f"step1 more_unchanged_real_bytecode_list1: {more_unchanged_real_bytecode_list1}"
        )
        print(
            f"{0}:{self.executor.smartcontract_functions_index_range[self.function_body_index][0]-1}"
        )
        print(f"step1 unchanged_real_bytecode_list1: {unchanged_real_bytecode_list1}")
        print(
            f"{self.executor.smartcontract_functions_index_range[self.function_body_index][0]}:{final_jump_structure1_index_range[0]-1}"
        )
        print(f"step1 middle_real_bytecode_list: {middle_real_bytecode_list}")
        print(
            f"{final_jump_structure1_index_range[0]}:{final_jump_structure2_index_range[0]-1}"
        )
        print(f"step1 reorder_real_bytecode_list: {reorder_real_bytecode_list}")
        print(
            f"{final_jump_structure2_index_range[0]}:{final_jump_structure2_index_range[1]}"
        )
        print(f"step1 unchanged_real_bytecode_list2: {unchanged_real_bytecode_list2}")
        print(
            f"{final_jump_structure2_index_range[1]+1}:{self.executor.smartcontract_functions_index_range[self.function_body_index][1]}"
        )
        print(
            f"step1 more_unchanged_real_bytecode_list2: {more_unchanged_real_bytecode_list2}"
        )
        print(
            f"{self.executor.smartcontract_functions_index_range[self.function_body_index][1] + 1}:{len(real_bytecode)-1}"
        )

        # 获取final_jump_structure1中的相关跳转地址
        the_number_of_stack_operands_in_special_stack_snapshot = (
            self.executor.stack_snapshots[self.special_stack_snapshots_index[0]]
        )
        related_jump_and_jumpi_address_in_final_jump_structure1_index_range = set()
        unrelated_jump_address_in_final_jump_structure1_index_range = set()
        index = 0
        while index < len(middle_real_bytecode_list):
            if (
                middle_real_bytecode_list[index] == "JUMPI"
                or middle_real_bytecode_list[index] == "JUMP"
            ):
                related_jump_and_jumpi_address_in_final_jump_structure1_index_range.add(
                    self.executor.opcodeindex_to_stack[
                        index
                        + self.executor.smartcontract_functions_index_range[
                            self.function_body_index
                        ][0]
                        + len(unchanged_real_bytecode_list1)
                    ][-1]
                )

            if middle_real_bytecode_list[index] == "JUMP":
                if (
                    index
                    + self.executor.smartcontract_functions_index_range[
                        self.function_body_index
                    ][0]
                    + len(unchanged_real_bytecode_list1)
                    in self.executor.all_jump_index_related_to_Call
                ):
                    unrelated_jump_address_in_final_jump_structure1_index_range.add(
                        self.executor.opcodeindex_to_stack[
                            index
                            + self.executor.smartcontract_functions_index_range[
                                self.function_body_index
                            ][0]
                            + len(unchanged_real_bytecode_list1)
                        ][-1]
                    )
                    # 对此进行修改，因为即使不是函数调用也可能出现PUSH JUMP JUMPDEST的连接关系
                    for key in self.executor.control_flow_graph.keys():
                        if (
                            index
                            + 1
                            + self.executor.smartcontract_functions_index_range[
                                self.function_body_index
                            ][0]
                            + len(unchanged_real_bytecode_list1)
                            in self.executor.control_flow_graph[key]
                            and self.executor.real_bytecode[key] == "JUMP"
                        ):
                            related_jump_and_jumpi_address_in_final_jump_structure1_index_range.add(
                                self.executor.opcodeindex_to_stack[key][-1]
                            )

                # for info in self.jump_structure_info:
                #     if info[
                #         "jump_structure_type"
                #     ] == "Call" and index + self.executor.smartcontract_functions_index_range[
                #         self.function_body_index
                #     ][
                #         0
                #     ] + len(
                #         unchanged_real_bytecode_list1
                #     ) in range(
                #         info["jump_structure_index_range"][0],
                #         info["jump_structure_index_range"][1] + 1,
                #     ):
                #         unrelated_jump_address_in_final_jump_structure1_index_range.add(
                #             self.executor.opcodeindex_to_stack[
                #                 index
                #                 + self.executor.smartcontract_functions_index_range[
                #                     self.function_body_index
                #                 ][0]
                #                 + len(unchanged_real_bytecode_list1)
                #             ][-1]
                #         )
                #         # 对此进行修改，因为即使不是函数调用也可能出现PUSH JUMP JUMPDEST的连接关系
                #         related_jump_and_jumpi_address_in_final_jump_structure1_index_range.add(
                #             self.executor.opcodeindex_to_stack[
                #                 index
                #                 + self.executor.smartcontract_functions_index_range[
                #                     self.function_body_index
                #                 ][0]
                #                 + len(unchanged_real_bytecode_list1)
                #             ][
                #                 the_number_of_stack_operands_in_special_stack_snapshot
                #                 - 1
                #                 + 1
                #             ][-1]
                #         )

            index += 1

        # 相邻深度的情况下,需要把关于条件分支结构的并且在状态变量赋值块之前index最大的JUMPI的索引位置找出并从调整位置集合中移除
        if adjacent_or_same_signal == 0:
            jumpi_index_in_branch = []  # 记录特殊jumpi的index
            for index in range(
                self.final_jump_structure1["jump_structure_index_range"][0],
                self.final_jump_structure1["jump_structure_index_range"][1] + 1,
            ):
                if (
                    self.executor.real_bytecode[index] == "JUMPI"
                    and not any(
                        start <= index <= end
                        for start, end in self.final_jump_structure1[
                            "jump_structure_children"
                        ]
                    )
                    and index
                    < self.final_jump_structure2["jump_structure_index_range"][0]
                ):
                    jumpi_index_in_branch.append(index)
                    print(f"jumpi_index_in_branch: {jumpi_index_in_branch}")
            max_jumpi_index_in_branch = max(jumpi_index_in_branch)
            unrelated_jump_address_in_final_jump_structure1_index_range.add(
                self.executor.opcodeindex_to_stack[max_jumpi_index_in_branch][-1]
            )

        print(
            f"unrelated_jump_address_in_final_jump_structure1_index_range: {unrelated_jump_address_in_final_jump_structure1_index_range}"
        )
        print(
            f"step1 related_jump_and_jumpi_address_in_final_jump_structure1_index_range: {related_jump_and_jumpi_address_in_final_jump_structure1_index_range}"
        )
        related_jump_and_jumpi_address_in_final_jump_structure1_index_range = (
            related_jump_and_jumpi_address_in_final_jump_structure1_index_range
            - unrelated_jump_address_in_final_jump_structure1_index_range
        )
        print(
            f"step2 related_jump_and_jumpi_address_in_final_jump_structure1_index_range: {related_jump_and_jumpi_address_in_final_jump_structure1_index_range}"
        )

        # 获取final_jump_structure2中的相关跳转地址
        related_jump_and_jumpi_address_in_final_jump_structure2_index_range = set()
        unrelated_jump_address_in_final_jump_structure2_index_range = set()
        index = 0
        while index < len(reorder_real_bytecode_list):
            if (
                reorder_real_bytecode_list[index] == "JUMPI"
                or reorder_real_bytecode_list[index] == "JUMP"
            ):
                related_jump_and_jumpi_address_in_final_jump_structure2_index_range.add(
                    self.executor.opcodeindex_to_stack[
                        index
                        + self.executor.smartcontract_functions_index_range[
                            self.function_body_index
                        ][0]
                        + len(unchanged_real_bytecode_list1)
                        + len(middle_real_bytecode_list)
                    ][-1]
                )

            if reorder_real_bytecode_list[index] == "JUMP":
                if (
                    index
                    + self.executor.smartcontract_functions_index_range[
                        self.function_body_index
                    ][0]
                    + len(unchanged_real_bytecode_list1)
                    + len(middle_real_bytecode_list)
                    in self.executor.all_jump_index_related_to_Call
                ):
                    unrelated_jump_address_in_final_jump_structure2_index_range.add(
                        self.executor.opcodeindex_to_stack[
                            index
                            + self.executor.smartcontract_functions_index_range[
                                self.function_body_index
                            ][0]
                            + len(unchanged_real_bytecode_list1)
                            + len(middle_real_bytecode_list)
                        ][-1]
                    )
                    # 对此进行修改，因为即使不是函数调用也可能出现PUSH JUMP JUMPDEST的连接关系
                    for key in self.executor.control_flow_graph.keys():
                        if (
                            index
                            + 1
                            + self.executor.smartcontract_functions_index_range[
                                self.function_body_index
                            ][0]
                            + len(unchanged_real_bytecode_list1)
                            + len(middle_real_bytecode_list)
                            in self.executor.control_flow_graph[key]
                            and self.executor.real_bytecode[key] == "JUMP"
                        ):
                            related_jump_and_jumpi_address_in_final_jump_structure2_index_range.add(
                                self.executor.opcodeindex_to_stack[key][-1]
                            )

                # for info in self.jump_structure_info:
                #     if info[
                #         "jump_structure_type"
                #     ] == "Call" and index + self.executor.smartcontract_functions_index_range[
                #         self.function_body_index
                #     ][
                #         0
                #     ] + len(
                #         unchanged_real_bytecode_list1
                #     ) + len(
                #         middle_real_bytecode_list
                #     ) in range(
                #         info["jump_structure_index_range"][0],
                #         info["jump_structure_index_range"][1] + 1,
                #     ):
                #         unrelated_jump_address_in_final_jump_structure2_index_range.add(
                #             self.executor.opcodeindex_to_stack[
                #                 index
                #                 + self.executor.smartcontract_functions_index_range[
                #                     self.function_body_index
                #                 ][0]
                #                 + len(unchanged_real_bytecode_list1)
                #                 + len(middle_real_bytecode_list)
                #             ][-1]
                #         )
                #         related_jump_and_jumpi_address_in_final_jump_structure2_index_range.add(
                #             self.executor.opcodeindex_to_stack[
                #                 index
                #                 + self.executor.smartcontract_functions_index_range[
                #                     self.function_body_index
                #                 ][0]
                #                 + len(unchanged_real_bytecode_list1)
                #                 + len(middle_real_bytecode_list)
                #             ][
                #                 the_number_of_stack_operands_in_special_stack_snapshot
                #                 - 1
                #                 + 1
                #             ][-1]
                #         )

            index += 1

        print(
            f"step1 related_jump_and_jumpi_address_in_final_jump_structure2_index_range: {related_jump_and_jumpi_address_in_final_jump_structure2_index_range}"
        )
        related_jump_and_jumpi_address_in_final_jump_structure2_index_range = (
            related_jump_and_jumpi_address_in_final_jump_structure2_index_range
            - unrelated_jump_address_in_final_jump_structure2_index_range
        )
        print(
            f"step2 related_jump_and_jumpi_address_in_final_jump_structure2_index_range: {related_jump_and_jumpi_address_in_final_jump_structure2_index_range}"
        )

        # 根据final_jump_structure1中的相关跳转地址,获取push进相关跳转地址的操作数index位置,后续根据index偏移量进行修正
        related_jump_and_jumpi_address_index_in_final_jump_structure1_index_range = (
            set()
        )
        index = 0
        while index < len(middle_real_bytecode_list):
            if (
                middle_real_bytecode_list[index].startswith("PUSH")
                and middle_real_bytecode_list[index] != "PUSH0"
            ):
                if (
                    self.executor.opcodeindex_to_stack[
                        index
                        + self.executor.smartcontract_functions_index_range[
                            self.function_body_index
                        ][0]
                        + len(unchanged_real_bytecode_list1)
                        + 2  # +2 ???
                    ][-1]
                    in related_jump_and_jumpi_address_in_final_jump_structure1_index_range
                ):
                    related_jump_and_jumpi_address_index_in_final_jump_structure1_index_range.add(
                        index + 1
                    )
            index += 1
        print(
            f"related_jump_and_jumpi_address_index_in_final_jump_structure1_index_range: {related_jump_and_jumpi_address_index_in_final_jump_structure1_index_range}"
        )

        # 根据final_jump_structure2中的相关跳转地址,获取push进相关跳转地址的操作数index位置,并直接重置之
        related_jump_and_jumpi_address_index_in_final_jump_structure2_index_range = (
            set()
        )
        index = 0
        while index < len(reorder_real_bytecode_list):
            if (
                reorder_real_bytecode_list[index].startswith("PUSH")
                and reorder_real_bytecode_list[index] != "PUSH0"
            ):
                if (
                    self.executor.opcodeindex_to_stack[
                        index
                        + self.executor.smartcontract_functions_index_range[
                            self.function_body_index
                        ][0]
                        + len(unchanged_real_bytecode_list1)
                        + len(middle_real_bytecode_list)
                        + 2  # +2 ???
                    ][-1]
                    in related_jump_and_jumpi_address_in_final_jump_structure2_index_range
                ):
                    related_jump_and_jumpi_address_index_in_final_jump_structure2_index_range.add(
                        index + 1
                    )
            index += 1
        print(
            f"related_jump_and_jumpi_address_index_in_final_jump_structure2_index_range: {related_jump_and_jumpi_address_index_in_final_jump_structure2_index_range}"
        )

        # 重构pc和index映射关系
        temporary_reorder_real_bytecode = (
            unchanged_real_bytecode_list1
            + reorder_real_bytecode_list
            + middle_real_bytecode_list
            + unchanged_real_bytecode_list2
        )
        new_index_mapping_pc = {}
        new_pc_mapping_index = {}
        pc = 0
        index = 0
        while index < len(temporary_reorder_real_bytecode):
            opcode = temporary_reorder_real_bytecode[index].lower()
            new_index_mapping_pc[index] = pc
            new_pc_mapping_index[pc] = index
            pc += 1  # 每个操作码占用一个PC位置
            if opcode.startswith("push") and not opcode.startswith("push0"):
                # 提取推入的数据字节数
                push_bytes = int(opcode[4:])
                pc += push_bytes  # 加上操作数所占用的PC位置
                index += 1  # 跳过操作数
            index += 1
        print(f"new_index_mapping_pc: {new_index_mapping_pc}")
        print(f"new_pc_mapping_index: {new_pc_mapping_index}")

        # 计算两个PC偏移量
        print(
            f"{0+ self.executor.smartcontract_functions_index_range[self.function_body_index][0]+ len(unchanged_real_bytecode_list1)+ len(middle_real_bytecode_list)}"
        )
        print(
            f"{len(reorder_real_bytecode_list)- 1+ self.executor.smartcontract_functions_index_range[self.function_body_index][0]+ len(unchanged_real_bytecode_list1)+ len(middle_real_bytecode_list)}"
        )
        print(
            f"{0+ self.executor.smartcontract_functions_index_range[self.function_body_index][0]+ len(unchanged_real_bytecode_list1)}"
        )
        print(
            f"{len(middle_real_bytecode_list)- 1+ self.executor.smartcontract_functions_index_range[self.function_body_index][0]+ len(unchanged_real_bytecode_list1)}"
        )
        decimalism_PC_offset1_amount = (
            self.executor.index_mapping_pc[
                len(reorder_real_bytecode_list)
                - 1
                + self.executor.smartcontract_functions_index_range[
                    self.function_body_index
                ][0]
                + len(unchanged_real_bytecode_list1)
                + len(middle_real_bytecode_list)
            ]
            - self.executor.index_mapping_pc[
                0
                + self.executor.smartcontract_functions_index_range[
                    self.function_body_index
                ][0]
                + len(unchanged_real_bytecode_list1)
                + len(middle_real_bytecode_list)
            ]
            + 1  # 很微妙的一个点，+1的原因是漏了最前面的pc长度，但是恒定为1的原因是最开始的操作码的上两个操作码不可能为PUSH*
        )
        print(f"decimalism_PC_offset1_amount: {decimalism_PC_offset1_amount}")
        hexadecimal_PC_offset1_amount = hex(decimalism_PC_offset1_amount)
        print(f"hexadecimal_PC_offset1_amount: {hexadecimal_PC_offset1_amount}")

        decimalism_PC_offset2_amount = (
            self.executor.index_mapping_pc[
                len(middle_real_bytecode_list)
                - 1
                + self.executor.smartcontract_functions_index_range[
                    self.function_body_index
                ][0]
                + len(unchanged_real_bytecode_list1)
            ]
            - self.executor.index_mapping_pc[
                0
                + self.executor.smartcontract_functions_index_range[
                    self.function_body_index
                ][0]
                + len(unchanged_real_bytecode_list1)
            ]
            + 1  # 很微妙的一个点，+1的原因是漏了最前面的pc长度，但是恒定为1的原因是最开始的操作码的上两个操作码不可能为PUSH*
        )
        print(f"decimalism_PC_offset2_amount: {decimalism_PC_offset2_amount}")
        hexadecimal_PC_offset2_amount = hex(decimalism_PC_offset2_amount)
        print(f"hexadecimal_PC_offset2_amount: {hexadecimal_PC_offset2_amount}")

        # 更新middle_real_bytecode_list中的相关的跳转地址
        for (
            index
        ) in related_jump_and_jumpi_address_index_in_final_jump_structure1_index_range:
            middle_real_bytecode_list[index] = hex(
                int(middle_real_bytecode_list[index], 16)
                + int(hexadecimal_PC_offset1_amount, 16)
            )
            print(
                f"middle_real_bytecode_list[{index}]: {middle_real_bytecode_list[index]}"
            )

        # 更新reorder_real_bytecode_list中的相关的跳转地址
        for (
            index
        ) in related_jump_and_jumpi_address_index_in_final_jump_structure2_index_range:
            reorder_real_bytecode_list[index] = hex(
                int(reorder_real_bytecode_list[index], 16)
                - int(hexadecimal_PC_offset2_amount, 16)
            )
            print(
                f"reorder_real_bytecode_list[{index}]: {reorder_real_bytecode_list[index]}"
            )

        print(f"step2 middle_real_bytecode_list: {middle_real_bytecode_list}")
        print(f"step2 reorder_real_bytecode_list: {reorder_real_bytecode_list}")

        reorder_function_real_bytecode = (
            unchanged_real_bytecode_list1
            + reorder_real_bytecode_list
            + middle_real_bytecode_list
            + unchanged_real_bytecode_list2
        )
        reorder_real_bytecode = (
            more_unchanged_real_bytecode_list1
            + unchanged_real_bytecode_list1
            + reorder_real_bytecode_list
            + middle_real_bytecode_list
            + unchanged_real_bytecode_list2
            + more_unchanged_real_bytecode_list2
        )
        print(f"reorder_function_real_bytecode: {reorder_function_real_bytecode}")
        print(f"reorder_real_bytecode: {reorder_real_bytecode}")
        self.reorder_function_real_bytecode = reorder_function_real_bytecode
        self.reorder_real_bytecode = reorder_real_bytecode
        return reorder_function_real_bytecode, reorder_real_bytecode


# 之前的实验代码中，并没有防范出现循环的情况，那就是如果字节码中有循环结构，那么可能就会不停地执行下去，并且这样的话字节码路径也会不断增多，这种情况应该怎么修改代码逻辑来处理这种情形呢？（已完成）
# 明晰public类型的函数范围以及internal类型的函数范围（已完成）
# 跨合约的界限分割（待完成）
# 目前可以模拟执行所有的字节码路径（已完成），进一步需要维护所有可行的字节码路径结构（已完成）
# 区分每个函数的PC范围(已完成)
# 模拟执行时取堆栈快照（已完成）
# 指定特殊堆栈快照，以单个函数体为操作对象（已完成）
# 明晰跳转结构，跳转深度（已完成）
# 分块（已完成）
# 静态反向搜索，或是直接查询关键状态变量（已完成）
# 数据依赖关系一致性分析（已完成）
# 重新排序,条件分支结构和循环结构所用的跳转地址的相对迁移;调用结构中的跳出地址不变,跳回地址相对迁移（已完成）

# 多状态变量赋值迁移到转帐块之前 (已完成)
# 跨函数重入修复,即:无前置检测的重入修复（已完成）
# 基于构造重入修复（已完成）
# 委托重入修复（已完成）取决于CFG的完整度
# 包含函数调用那部分的数据依赖关系一致性分析(已完成)


# exist another way
# if (
#     self.real_bytecode[self.bytecode_list_index - 2]
#     .lower()
#     .startswith("push")
#     and self.real_bytecode[self.bytecode_list_index - 2].lower()
#     != "push0"
# ):
#     print(
#         f"self.real_bytecode[self.pc - 1]:{int(self.real_bytecode[self.bytecode_list_index - 1], 16)}"
#     )
#     print(
#         f"related pc {int(self.real_bytecode[self.bytecode_list_index - 1], 16)} mapping to index {self.get_index_position(int(self.real_bytecode[self.bytecode_list_index - 1], 16))}"
#     )
#     handler(
#         self.get_index_position(
#             int(self.real_bytecode[self.bytecode_list_index - 1], 16)
#         )
#     )
#     # 这里不应该直接把int(self.real_bytecode[self.bytecode_list_index - 1]放入handler第一参数位置，因为这个跳转地址实际上是pc位置而不是index.
#     # 所以我们要把int(self.real_bytecode[self.bytecode_list_index - 1]所对应的操作码的index地址放入handler第一参数位置
# else:
#     raise RuntimeError("not explicit address")  # 待改善
