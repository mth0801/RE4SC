def read_file_lines(file_path):
    # 读取文件的所有行，并去掉每行的换行符和多余的空白
    with open(file_path, "r") as file:
        lines = [line.strip() for line in file.readlines()]
    return lines


def compare_files(file1, file2):
    # 读取两个文件的内容
    file1_lines = read_file_lines(file1)
    file2_lines = read_file_lines(file2)

    # 比较两者内容
    if file1_lines == file2_lines:
        print("the contents of two files are same")
    else:
        print("the contents of two files are not same")

        # 找出不同的地方
        min_length = min(len(file1_lines), len(file2_lines))
        for i in range(min_length):
            if file1_lines[i] != file2_lines[i]:
                print(f"the {i + 1} line is different:")
                print(f"  file1: {file1_lines[i]}")
                print(f"  file2: {file2_lines[i]}")

        # 如果文件长度不同，显示多出的部分
        if len(file1_lines) > len(file2_lines):
            print("\nthe content of file1 more than file2's:")
            for line in file1_lines[min_length:]:
                print(f"  {line}")
        elif len(file2_lines) > len(file1_lines):
            print("\nthe content of file2 more than file1's:")
            for line in file2_lines[min_length:]:
                print(f"  {line}")


# 文件路径
file1 = ".../REEVM/test_txt/bytecode1.txt"  # 第一个文件
file2 = ".../REEVM/test_txt/bytecode2.txt"  # 第二个文件

# 调用函数比较两个文件
compare_files(file1, file2)





