#!/usr/bin/env python3
"""
自动导入依赖的脚本：
- 读取 requirements.txt
- 检测缺失包
- 自动执行 pip install -r requirements.txt

用法：
  python scripts/ensure_dependencies.py
"""

from __future__ import annotations

import importlib.util
import pathlib
import subprocess
import sys


def load_requirements(requirements_path: pathlib.Path) -> list[str]:
    return [
        line.strip()
        for line in requirements_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def requirement_to_module(requirement: str) -> str:
    name = requirement.split("==")[0].split(">=")[0].split("<=")[0].strip()
    return name.replace("-", "_")


def is_installed(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def main() -> None:
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    requirements_path = repo_root / "requirements.txt"
    if not requirements_path.exists():
        raise SystemExit("requirements.txt 不存在")

    requirements = load_requirements(requirements_path)
    missing = [req for req in requirements if not is_installed(requirement_to_module(req))]

    if not missing:
        print("所有依赖已安装，无需处理。")
        return

    print(f"检测到缺失依赖：{missing}")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", str(requirements_path)],
        check=True,
    )


if __name__ == "__main__":
    main()
