import os
import shutil
import time
from pathlib import Path

# ================= 配置区域 =================

CACHE_PATH = "C:/Users/jhq223/AppData/LocalLow/Unity/FANZAGAMES_twinkle_starknightsX"

# 【安全开关】
# True = 模拟运行（只列出会被删除的文件，不执行删除）
# False = 实际运行（真的会删除文件，请谨慎！）
DRY_RUN = False

# ===========================================


def get_dir_size(path):
    """计算文件夹大小"""
    total = 0
    try:
        for entry in os.scandir(path):
            if entry.is_file():
                total += entry.stat().st_size
            elif entry.is_dir():
                total += get_dir_size(entry.path)
    except Exception:
        pass
    return total


def format_size(size):
    """格式化文件大小显示"""
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} TB"


def clean_unity_cache():
    root = Path(CACHE_PATH)

    if not root.exists():
        print(f"[错误] 路径不存在: {CACHE_PATH}")
        return

    print(f"正在扫描目录: {CACHE_PATH}")
    print(
        f"当前模式: {'【模拟运行 - 不会删除文件】' if DRY_RUN else '【执行模式 - 将删除旧文件】'}"
    )
    print("-" * 60)

    cleaned_count = 0
    freed_space = 0
    bundles_checked = 0

    # 1. 遍历第一层目录 (AssetBundle ID)
    for bundle_dir in root.iterdir():
        if not bundle_dir.is_dir():
            continue

        bundles_checked += 1

        # 2. 寻找该ID下的所有版本目录
        # 过滤条件：必须是文件夹，且里面包含 __data 文件
        version_dirs = []
        for v_dir in bundle_dir.iterdir():
            if v_dir.is_dir() and (v_dir / "__data").exists():
                version_dirs.append(v_dir)

        # 如果只有一个版本或没有版本，跳过
        if len(version_dirs) <= 1:
            continue

        # 3. 对比时间，找出最新的
        # 创建列表: [(时间戳, 文件夹路径), ...]
        versions_with_time = []
        for v_dir in version_dirs:
            data_file = v_dir / "__data"
            mtime = data_file.stat().st_mtime
            versions_with_time.append((mtime, v_dir))

        # 按时间降序排序 (最新的在第一个)
        versions_with_time.sort(key=lambda x: x[0], reverse=True)

        latest_version = versions_with_time[0][1]
        old_versions = versions_with_time[1:]

        print(f"[发现重复] 资源包: {bundle_dir.name}")
        print(
            f"   - 保留最新: {latest_version.name} ({time.ctime(versions_with_time[0][0])})"
        )

        # 4. 处理旧版本
        for _, old_dir in old_versions:
            size = get_dir_size(old_dir)
            freed_space += size
            cleaned_count += 1

            if DRY_RUN:
                print(
                    f"   - [模拟删除] 过期版本: {old_dir.name} (大小: {format_size(size)})"
                )
            else:
                try:
                    shutil.rmtree(old_dir)
                    print(
                        f"   - [已删除] 过期版本: {old_dir.name} (大小: {format_size(size)})"
                    )
                except Exception as e:
                    print(f"   - [删除失败] {old_dir.name}: {e}")
        print("-" * 40)

    # 总结
    print("=" * 60)
    print("扫描完成。")
    print(f"检查了 {bundles_checked} 个资源包。")
    if DRY_RUN:
        print(f"如果关闭 DRY_RUN，将删除 {cleaned_count} 个旧文件夹。")
        print(f"预计释放空间: {format_size(freed_space)}")
        print("\n请将代码中的 DRY_RUN = True 改为 False 以执行清理。")
    else:
        print(f"成功删除了 {cleaned_count} 个旧文件夹。")
        print(f"共释放空间: {format_size(freed_space)}")


if __name__ == "__main__":
    clean_unity_cache()
