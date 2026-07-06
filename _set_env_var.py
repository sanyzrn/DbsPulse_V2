"""
Small helper used by setup_and_run.bat to safely set (or insert) a single
KEY=VALUE line inside a .env file, without disturbing any other lines.

Usage:
    python _set_env_var.py <path_to_env_file> <KEY> <VALUE>
"""
import io
import sys


def main() -> int:
    if len(sys.argv) != 4:
        print("Usage: python _set_env_var.py <env_file> <KEY> <VALUE>")
        return 1

    env_path, key, value = sys.argv[1], sys.argv[2], sys.argv[3]
    target_line = f"{key}={value}"

    try:
        with io.open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        lines = []

    found = False
    for i, line in enumerate(lines):
        if line.strip().startswith(f"{key}="):
            lines[i] = target_line + "\n"
            found = True
            break

    if not found:
        if lines and not lines[-1].endswith("\n"):
            lines[-1] += "\n"
        lines.append(target_line + "\n")

    with io.open(env_path, "w", encoding="utf-8") as f:
        f.writelines(lines)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
