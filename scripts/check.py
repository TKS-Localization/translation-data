import json
import re
from pathlib import Path


def check_json_files(directory):
    # 定义正则表达式
    # ^第\d+话  : 以"第"开头，中间数字，以"话"结尾
    # .+       : 中间任意内容
    # [BP]$    : 以 B 或 P 结尾
    pattern = re.compile(r"^第\d+话,.+,[BP]$")

    # 将字符串路径转换为 Path 对象
    root_path = Path(directory)

    if not root_path.exists():
        print(f"错误: 目录不存在 -> {directory}")
        return

    print(f"开始检查目录 (Pathlib): {root_path.resolve()} ...\n")

    error_count = 0
    file_count = 0

    # 使用 rglob("*.json") 递归查找所有 json 文件
    # 如果你只想找当前层级（不包含子目录），可以用 glob("*.json")
    for file_path in root_path.rglob("*.json"):
        file_count += 1

        try:
            # pathlib 的 open 写法
            with file_path.open("r", encoding="utf-8") as f:
                data = json.load(f)

                if not isinstance(data, list):
                    print(f"[警告] 文件不是列表格式: {file_path.name}")
                    continue

                for index, item in enumerate(data):
                    if item.get("name") == "Title":
                        message = item.get("message", "")

                        if not pattern.match(message):
                            print(f"[格式错误] 文件: {file_path}")
                            print(f"    --> 位置: 第 {index + 1} 个对象")
                            print(f"    --> 内容: {message}")
                            print("-" * 30)
                            error_count += 1

        except json.JSONDecodeError:
            print(f"[JSON损坏] 无法解析: {file_path}")
        except Exception as e:
            print(f"[未知错误] {file_path}: {e}")

    print(f"\n检查完成。共扫描 {file_count} 个文件，发现 {error_count} 个格式错误。")


if __name__ == "__main__":
    # --- 配置区域 ---
    target_directory = "out/3_Translated"
    # ---------------

    check_json_files(target_directory)
