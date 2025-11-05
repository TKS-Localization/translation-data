import argparse
import json
import os
import shutil
import copy
from pathlib import Path
from typing import Any

# --- 配置常量 ---
MASTER_CHAPTER_FILE = "Adventure/Master.chapter.json"
CHARACTER_TABLE_SUFFIX = ":Character"
CHARACTER_ID_COL_INDEX = 1
CHARACTER_NAME_COL_INDEX = 2
DIALOGUE_SPEAKER_ID_COL_NAME = "Arg1"
DIALOGUE_TEXT_COL_NAME = "Text"
OUT_DIR = "out"
FOR_TRANSLATION_DIR = os.path.join(OUT_DIR, "1_For_Translation")
READY_FOR_TRANSLATION_DIR = os.path.join(OUT_DIR, "2_Ready_For_Translation")
TRANSLATED_DIR = os.path.join(OUT_DIR, "3_Translated")
PLUGIN_DATA_DIR = os.path.join(OUT_DIR, "4_Plugin_Data")
MASTER_CHARACTERS_FILE = os.path.join(OUT_DIR, "master_characters.json")
NAMES_MAP_FILE = os.path.join(OUT_DIR, "names.json")
EXCLUDE_NAMES_FILE = "exclude_names.json"


# --- 辅助函数 ---
def read_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def handle_extraction(args):
    """
    执行提取操作。
    1. 提取 Master 文件中的角色 ID -> 角色名映射，用于阶段二。
    2. 遍历所有 book.json，提取对话文本。
    3. 会跳过在 '3_Translated' 目录中已存在的文件。
    4. 对 names.json 进行增量更新，保留已存在的条目。
    5. 会读取 'out/exclude_names.json' 文件，排除其中列出的角色名。
    """
    print("--- 阶段一：开始提取 ---")
    input_dir = Path(args.input_dir)
    output_dir = Path(FOR_TRANSLATION_DIR)
    translated_dir = Path(TRANSLATED_DIR)

    if args.force and output_dir.exists():
        print(f"警告：使用 --force 标志，将清空并重新创建目录 '{output_dir}'。")
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    translated_dir.mkdir(parents=True, exist_ok=True)

    # 步骤 1: 提取 Master 文件中的角色映射
    master_file_path = input_dir / MASTER_CHAPTER_FILE
    if not master_file_path.exists():
        print(f"错误: 未找到 Master 文件: {master_file_path}")
        return

    master_data = read_json(master_file_path)
    character_map = {}
    for grid in master_data.get("settingList", []):
        if grid.get("name", "").endswith(CHARACTER_TABLE_SUFFIX):
            for row in grid.get("rows", [])[1:]:
                strings = row.get("strings", [])
                if len(strings) > max(CHARACTER_ID_COL_INDEX, CHARACTER_NAME_COL_INDEX):
                    char_id, char_name = (
                        strings[CHARACTER_ID_COL_INDEX],
                        strings[CHARACTER_NAME_COL_INDEX],
                    )
                    if char_id and char_name:
                        character_map[char_id] = char_name
            break
    write_json(Path(MASTER_CHARACTERS_FILE), character_map)
    print(
        f"成功提取 {len(character_map)} 个角色（用于预处理），已保存至 '{MASTER_CHARACTERS_FILE}'"
    )

    # 步骤 2 & 3: 提取对话并收集所有角色ID
    print("正在扫描并提取所有 book.json 文件...")
    book_files = list(input_dir.glob("**/*.book.json"))
    extracted_count = 0
    skipped_count = 0
    all_speaker_ids = set()

    for book_file in book_files:
        relative_path = book_file.relative_to(input_dir)
        book_data = read_json(book_file)

        for grid in book_data.get("importGridList", []):
            grid_name = grid["name"]
            rows = grid.get("rows", [])
            if not rows:
                continue

            header = rows[0].get("strings", [])
            try:
                speaker_col_idx = header.index(DIALOGUE_SPEAKER_ID_COL_NAME)
                text_col_idx = header.index(DIALOGUE_TEXT_COL_NAME)
            except ValueError:
                continue

            dialogues = []
            for row in rows[1:]:
                strings = row.get("strings", [])
                if len(strings) > max(speaker_col_idx, text_col_idx):
                    speaker_id, dialogue_text = (
                        strings[speaker_col_idx],
                        strings[text_col_idx],
                    )

                    if speaker_id:
                        is_ascii_only = True
                        try:
                            speaker_id.encode("ascii")
                        except UnicodeEncodeError:
                            is_ascii_only = False

                        if not is_ascii_only:
                            all_speaker_ids.add(speaker_id)

                    if dialogue_text:
                        dialogues.append({"name": speaker_id, "message": dialogue_text})

            if dialogues:
                grid_id = grid_name.split(":")[-1]
                relative_file_path = relative_path.with_suffix("") / f"{grid_id}.json"

                translated_version_path = translated_dir / relative_file_path
                if not args.force and translated_version_path.exists():
                    skipped_count += 1
                    continue

                output_file = output_dir / relative_file_path
                write_json(output_file, dialogues)
                extracted_count += 1

    excluded_names_set = set()
    exclude_file_path = Path(EXCLUDE_NAMES_FILE)
    if exclude_file_path.exists():
        try:
            excluded_list = read_json(exclude_file_path)
            if isinstance(excluded_list, list):
                excluded_names_set = set(excluded_list)
                print(
                    f"已加载 {len(excluded_names_set)} 个排除项，来自 '{EXCLUDE_NAMES_FILE}'。"
                )
            else:
                print(
                    f"警告: '{EXCLUDE_NAMES_FILE}' 格式不正确，应为一个 JSON 列表。已忽略。"
                )
        except json.JSONDecodeError:
            print(f"警告: '{EXCLUDE_NAMES_FILE}' 文件格式错误，无法解析。已忽略。")
    else:
        print(
            f"提示: 未找到排除文件 '{EXCLUDE_NAMES_FILE}'。如需排除特定名称，请创建该文件。"
        )

    names_map_path = Path(NAMES_MAP_FILE)
    existing_names = {}
    if names_map_path.exists():
        print(f"找到已存在的 '{NAMES_MAP_FILE}'，将进行增量更新。")
        try:
            existing_names = read_json(names_map_path)
        except json.JSONDecodeError:
            print(f"警告: '{NAMES_MAP_FILE}' 文件格式错误，将创建新文件。")
            existing_names = {}
    else:
        print(f"未找到 '{NAMES_MAP_FILE}'，将创建新文件。")

    unique_display_names = set()
    for speaker_id in all_speaker_ids:
        display_name = character_map.get(speaker_id, speaker_id)
        if display_name:
            unique_display_names.add(display_name)

    new_names_added = 0
    for name in sorted(list(unique_display_names)):
        if name not in existing_names and name not in excluded_names_set:
            existing_names[name] = name
            new_names_added += 1

    write_json(names_map_path, existing_names)

    if new_names_added > 0:
        print(f"成功向 '{NAMES_MAP_FILE}' 中新增 {new_names_added} 个待翻译的角色名。")
    else:
        print(f"'{NAMES_MAP_FILE}' 无需更新，未发现新角色名。")
    print(f"文件中当前共有 {len(existing_names)} 个角色名。")

    print("--- 提取完成 ---")
    print(f"  - 新提取 {extracted_count} 个对话文件。")
    if not args.force:
        print(f"  - 跳过 {skipped_count} 个已翻译的文件。")
    print(f"文件已输出到 '{output_dir}' 目录。")


# --- 阶段二：映射与预处理 ---
def handle_mapping(args):
    """执行映射操作，会跳过在 '3_Translated' 目录中已存在的文件。"""
    print("--- 阶段二：开始映射与预处理 ---")
    input_dir = Path(FOR_TRANSLATION_DIR)
    output_dir = Path(READY_FOR_TRANSLATION_DIR)
    translated_dir = Path(TRANSLATED_DIR)
    char_map_file = Path(MASTER_CHARACTERS_FILE)

    if not input_dir.exists() or not char_map_file.exists():
        print(
            f"错误: 必需的输入 '{input_dir}' 或 '{char_map_file}' 不存在。请先执行提取操作。"
        )
        return

    if args.force and output_dir.exists():
        print(f"警告：使用 --force 标志，将清空并重新创建目录 '{output_dir}'。")
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    translated_dir.mkdir(parents=True, exist_ok=True)

    character_map = read_json(char_map_file)
    print(f"已加载 {len(character_map)} 个角色映射。")

    dialogue_files = list(input_dir.glob("**/*.json"))
    mapped_count = 0
    skipped_count = 0
    for dialogue_file in dialogue_files:
        relative_path = dialogue_file.relative_to(input_dir)

        translated_version_path = translated_dir / relative_path
        if not args.force and translated_version_path.exists():
            skipped_count += 1
            continue

        dialogues = read_json(dialogue_file)
        mapped_dialogues = []
        for item in dialogues:
            speaker_id = item["name"]
            speaker_name = character_map.get(speaker_id, speaker_id)
            mapped_dialogues.append({"name": speaker_name, "message": item["message"]})

        output_path = output_dir / relative_path
        write_json(output_path, mapped_dialogues)
        mapped_count += 1

    print("--- 映射完成 ---")
    print(f"  - 新映射 {mapped_count} 个对话文件。")
    if not args.force:
        print(f"  - 跳过 {skipped_count} 个已翻译的文件。")
    print(f"文件已输出到 '{output_dir}' 目录。")


# --- 阶段四：打包 ---
def handle_packaging(args):
    """
    【已简化】执行打包操作。
    仅将 3_Translated 目录中的对话文本回填到原始游戏文件结构中。
    不再处理 Master 文件或角色名。
    """
    print("--- 阶段四：开始打包 ---")
    original_dir = Path(args.input_dir)
    translated_dir = Path(TRANSLATED_DIR)
    output_dir = Path(PLUGIN_DATA_DIR)

    if not original_dir.exists() or not translated_dir.exists():
        print(f"错误: 必需的输入目录 '{original_dir}' 或 '{translated_dir}' 不存在。")
        return

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("正在打包对话...")
    original_book_files = list(original_dir.glob("**/*.book.json"))
    package_count = 0
    for original_file_path in original_book_files:
        relative_path = original_file_path.relative_to(original_dir)
        translated_book_dir = translated_dir / relative_path.with_suffix("")
        if not translated_book_dir.is_dir():
            continue

        original_data = read_json(original_file_path)
        modified_data = copy.deepcopy(original_data)
        is_modified = False

        for grid in modified_data.get("importGridList", []):
            grid_name = grid["name"]
            rows = grid.get("rows", [])
            if not rows:
                continue

            grid_id = grid_name.split(":")[-1]
            translated_file = translated_book_dir / f"{grid_id}.json"
            if not translated_file.exists():
                continue

            try:
                header = rows[0].get("strings", [])
                text_col_idx = header.index(DIALOGUE_TEXT_COL_NAME)
            except ValueError:
                continue

            translated_dialogues = read_json(translated_file)
            dialogue_iterator = iter(translated_dialogues)

            for row in rows[1:]:
                strings = row.get("strings", [])
                original_text = (
                    strings[text_col_idx] if len(strings) > text_col_idx else ""
                )
                if original_text:
                    try:
                        translated_item = next(dialogue_iterator)
                        strings[text_col_idx] = translated_item["message"]
                        is_modified = True
                    except StopIteration:
                        print(
                            f"警告: 在 {relative_path} 的 '{grid_name}' 中，翻译条目少于原文，可能部分未翻译。"
                        )
                        break

        if is_modified:
            plugin_book_data = {
                grid["name"]: [row["strings"] for row in grid["rows"]]
                for grid in modified_data.get("importGridList", [])
            }
            str_path = str(output_dir / relative_path)
            str_path = str_path.replace("CharaScenario", "")
            output_book_path = Path(str_path.replace(".book.json", ".chapter.json"))
            write_json(output_book_path, plugin_book_data)
            package_count += 1

    print(f"  - 共打包 {package_count} 个包含已翻译对话的文件。")
    print(f"--- 打包完成，插件数据已输出到 '{output_dir}' 目录 ---")


def main():
    os.makedirs("out", exist_ok=True)
    parser = argparse.ArgumentParser(description="游戏汉化工作流工具")
    subparsers = parser.add_subparsers(
        dest="command", required=True, help="可执行的命令"
    )

    parser_extract = subparsers.add_parser(
        "extract", help="阶段一：提取文本和所有角色ID。会跳过已翻译的文件。"
    )
    parser_extract.add_argument(
        "input_dir", type=str, help="包含解包后游戏JSON文件的根目录。"
    )
    parser_extract.add_argument(
        "--force", action="store_true", help="强制重新提取所有文本，忽略已翻译的文件。"
    )
    parser_extract.set_defaults(func=handle_extraction)

    parser_map = subparsers.add_parser(
        "map", help="阶段二：映射文本为友好格式。会跳过已翻译的文件。"
    )
    parser_map.add_argument(
        "--force", action="store_true", help="强制重新映射所有文本，忽略已翻译的文件。"
    )
    parser_map.set_defaults(func=handle_mapping)

    parser_package = subparsers.add_parser(
        "package", help="阶段四：将翻译后的对话文本打包成插件格式。"
    )
    parser_package.add_argument(
        "input_dir", type=str, help="包含原始游戏JSON文件的根目录（用作模板）。"
    )
    parser_package.set_defaults(func=handle_packaging)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
