import json
import re
from pathlib import Path


def get_replacement_table():
    """
    定义字符替换表。
    规则：日语半角符号/ASCII符号 -> 中文全角符号
    注意：特意【不包含】英文逗号 ','，因为它在 Title 中用作分隔符。
    """
    return str.maketrans(
        {
            "　": " ",
        }
    )


def process_json_files(directory):
    # 正则表达式：匹配 第x话,任意内容,B或P
    title_pattern = re.compile(r"^第\d+话,.+,[BP]$")

    # 获取替换表
    trans_table = get_replacement_table()

    root_path = Path(directory)
    if not root_path.exists():
        print(f"错误: 目录不存在 -> {directory}")
        return

    print(f"开始处理目录: {root_path.resolve()}\n")
    print("逻辑: 1. 全局格式化符号  2. 检查 Title 格式\n" + "-" * 40)

    stats = {"files_scanned": 0, "files_modified": 0, "format_errors": 0}

    # 使用 rglob 递归查找所有 json
    for file_path in root_path.rglob("*.json"):
        stats["files_scanned"] += 1
        file_changed = False

        try:
            with file_path.open("r", encoding="utf-8") as f:
                data = json.load(f)

            if not isinstance(data, list):
                continue

            # 遍历 JSON 列表中的每一项
            for index, item in enumerate(data):
                original_message = item.get("message")

                # 如果 message 字段存在且是字符串，则进行处理
                if original_message and isinstance(original_message, str):
                    # --- 步骤 1: 对【所有】消息进行格式化 ---
                    new_message = original_message.translate(trans_table)

                    # 如果内容发生了改变
                    if new_message != original_message:
                        print(f"[自动修复符号] 文件: {file_path.name}")
                        print(
                            f"   位置: 第 {index + 1} 项 (Name: {item.get('name', 'Unknown')})"
                        )
                        print(f"   原: {original_message}")
                        print(f"   新: {new_message}")
                        print("-" * 20)

                        # 更新数据
                        item["message"] = new_message
                        file_changed = True

                    # --- 步骤 2: 仅对 Name 为 Title 的消息进行格式检查 ---
                    if item.get("name") == "Title":
                        # 检查的是可能已经被修复过的内容
                        if not title_pattern.match(new_message):
                            print(f"!!! [Title格式错误] 文件: {file_path}")
                            print(f"    位置: 第 {index + 1} 项")
                            print(f"    内容: {new_message}")
                            print("    期待: 第x话,标题,B (或P)")
                            print("=" * 40)
                            stats["format_errors"] += 1

            # 如果该文件有任何修改，保存回磁盘
            if file_changed:
                with file_path.open("w", encoding="utf-8") as f:
                    # ensure_ascii=False 保证中文可读，indent=4 保持缩进
                    json.dump(data, f, ensure_ascii=False, indent=4)
                stats["files_modified"] += 1

        except json.JSONDecodeError:
            print(f"[Error] JSON 损坏: {file_path}")
        except Exception as e:
            print(f"[Error] {file_path}: {e}")

    print("\n" + "=" * 40)
    print("处理完成。")
    print(f"扫描文件数: {stats['files_scanned']}")
    print(f"修改文件数: {stats['files_modified']}")
    print(f"Title错误数: {stats['format_errors']}")


if __name__ == "__main__":
    target_directory = "out/3_Translated"

    process_json_files(target_directory)
