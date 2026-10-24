"""构建 AP01 1.0.2_0031 只读对象树观察固件。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from core.firmware_image import (
    AP01_1_0_2_0031,
    ByteRange,
    load_read_only_baseline,
    refresh_recovery_crc,
    validate_candidate,
)
from core.firmware_payload_space import (
    GIF_DATA_OFFSET,
    OPTIMIZED_SIZE,
    PAYLOAD_CAPACITY,
    PAYLOAD_START,
    inspect_payload_space,
)


MODULE_DIR = Path(__file__).resolve().parent
SOURCE = MODULE_DIR / "object_observer.c"
LINKER = MODULE_DIR / "object_observer.ld"
PAYLOAD_VA = 0xA02465D0
HOOK_HIGH_OFFSET = 0x0B37E4
HOOK_HIGH_OLD = bytes.fromhex("37b50ba0")
HOOK_HIGH_NEW = bytes.fromhex("376524a0")
HOOK_LOW_OFFSET = 0x0B37EE
HOOK_LOW_OLD = bytes.fromhex("1305a55d")
HOOK_LOW_NEW = bytes.fromhex("1305055d")
OUTPUT_NAME = "ap01-1.0.2_0031-dark-skin-object-observer.bin"
EXPECTED_BINUTILS = "2.46.1"
EXPECTED_GCC = "16.1.0"


class ObserverBuildError(RuntimeError):
    pass


def _run(command: list[object], *, capture: bool = False, cwd: Path | None = None) -> str:
    try:
        result = subprocess.run(
            [str(item) for item in command],
            cwd=cwd,
            check=True,
            capture_output=capture,
            text=True,
        )
    except (OSError, subprocess.SubprocessError) as error:
        stderr = getattr(error, "stderr", "") or ""
        raise ObserverBuildError(f"构建命令失败：{Path(str(command[0])).name}\n{stderr}") from error
    return result.stdout if capture else ""


def _tool(name: str) -> Path:
    found = shutil.which(name)
    if not found:
        raise ObserverBuildError(f"缺少构建工具：{name}")
    return Path(found).resolve()


def _version(tool: Path, expected: str) -> str:
    first = _run([tool, "--version"], capture=True).splitlines()[0]
    if expected not in first:
        raise ObserverBuildError(f"工具版本不匹配：{tool.name}: {first}")
    return first


def _symbols(nm: Path, elf: Path) -> dict[str, int]:
    symbols: dict[str, int] = {}
    undefined: list[str] = []
    for line in _run([nm, "-n", elf], capture=True).splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0] == "U":
            undefined.append(parts[1])
        elif len(parts) >= 3:
            try:
                symbols[parts[-1]] = int(parts[0], 16)
            except ValueError:
                pass
    if undefined:
        raise ObserverBuildError("载荷存在未解析符号：" + ", ".join(undefined))
    return symbols


def _git_state(repo: Path, require_clean_commit: bool) -> dict[str, object]:
    commit = _run(["git", "rev-parse", "HEAD"], capture=True, cwd=repo).strip()
    status = _run(["git", "status", "--porcelain"], capture=True, cwd=repo)
    if require_clean_commit and status:
        raise ObserverBuildError("冻结构建要求 Git 工作树无未提交修改")
    return {"commit": commit, "clean": not bool(status), "status": status.splitlines()}


def _write(path: Path, payload: bytes, freeze: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise ObserverBuildError(f"禁止覆盖已有文件：{path}")
    temporary = path.with_name(path.name + ".part")
    with temporary.open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    if freeze:
        path.chmod(0o444)


def build(
    baseline_path: Path,
    build_dir: Path,
    output_dir: Path,
    *,
    freeze: bool,
    require_clean_commit: bool,
) -> dict[str, object]:
    repo = MODULE_DIR.parents[1]
    git = _git_state(repo, require_clean_commit)
    endpoint = os.environ.get("AP01_OBSERVER_URL_PREFIX", "")
    if not endpoint.startswith("http://") or not endpoint.endswith("/ap01-observe?"):
        raise ObserverBuildError(
            "环境变量 AP01_OBSERVER_URL_PREFIX 必须是 http:// 开头并以 /ap01-observe? 结尾"
        )
    if any(character in endpoint for character in ('"', "\\", "\n", "\r")):
        raise ObserverBuildError("观察接收地址包含不允许的字符")
    baseline, baseline_report = load_read_only_baseline(baseline_path)
    if baseline[HOOK_HIGH_OFFSET:HOOK_HIGH_OFFSET + 4] != HOOK_HIGH_OLD:
        raise ObserverBuildError("原厂定时回调高位旧字节不匹配")
    if baseline[HOOK_LOW_OFFSET:HOOK_LOW_OFFSET + 4] != HOOK_LOW_OLD:
        raise ObserverBuildError("原厂定时回调低位旧字节不匹配")

    build_dir.mkdir(parents=True, exist_ok=False)
    optimized_gif = build_dir / "optimized-stock-pet.gif"
    payload_space_report = build_dir / "payload-space-report.json"
    inspect_payload_space(
        baseline_path,
        optimized_gif,
        payload_space_report,
        tool_revision={"git_commit": git["commit"]},
    )
    if optimized_gif.stat().st_size != OPTIMIZED_SIZE:
        raise ObserverBuildError("无损优化动图大小不匹配")

    gcc = _tool("riscv64-elf-gcc")
    linker = _tool("riscv64-elf-ld")
    objcopy = _tool("riscv64-elf-objcopy")
    objdump = _tool("riscv64-elf-objdump")
    readelf = _tool("riscv64-elf-readelf")
    nm = _tool("riscv64-elf-nm")
    versions = {
        "gcc": _version(gcc, EXPECTED_GCC),
        "ld": _version(linker, EXPECTED_BINUTILS),
        "objcopy": _version(objcopy, EXPECTED_BINUTILS),
        "objdump": _version(objdump, EXPECTED_BINUTILS),
        "readelf": _version(readelf, EXPECTED_BINUTILS),
        "nm": _version(nm, EXPECTED_BINUTILS),
    }
    object_path = build_dir / "object-observer.o"
    elf_path = build_dir / "object-observer.elf"
    payload_path = build_dir / "object-observer.bin"
    map_path = build_dir / "object-observer.map"
    _run([
        gcc, "-march=rv32imac", "-mabi=ilp32", "-Os", "-ffreestanding",
        "-fno-builtin", "-fno-pic", "-fno-pie", "-fno-plt",
        "-fno-stack-protector", "-fno-asynchronous-unwind-tables",
        "-fno-unwind-tables", "-fno-jump-tables", "-fno-common",
        "-fno-toplevel-reorder", "-fno-tree-loop-distribute-patterns",
        "-fstack-usage", "-msmall-data-limit=0", "-Wall", "-Wextra", "-Werror",
        f'-DAP01_OBSERVER_URL_PREFIX="{endpoint}"',
        "-c", SOURCE, "-o", object_path,
    ])
    _run([
        linker, "-m", "elf32lriscv", "--no-relax", f"-Map={map_path}",
        "-T", LINKER, "-o", elf_path, object_path,
    ])
    _run([objcopy, "-O", "binary", "-j", ".payload", elf_path, payload_path])
    payload = payload_path.read_bytes()
    if not payload or len(payload) > PAYLOAD_CAPACITY:
        raise ObserverBuildError("观察载荷为空或超过 60,934 字节")
    symbols = _symbols(nm, elf_path)
    required = (
        "ap01_dark_skin_ui_timer_wrapper",
        "ap01_dark_skin_observer_timer",
        "discard_response_sink",
    )
    for name in required:
        if name not in symbols or not PAYLOAD_VA <= symbols[name] < PAYLOAD_VA + len(payload):
            raise ObserverBuildError(f"观察载荷符号缺失或越界：{name}")
    if symbols["ap01_dark_skin_ui_timer_wrapper"] != PAYLOAD_VA:
        raise ObserverBuildError("观察包装入口不在固定地址 0xa02465d0")

    disassembly = _run([objdump, "-d", "-M", "no-aliases", elf_path], capture=True)
    (build_dir / "object-observer.disassembly.txt").write_text(disassembly, encoding="utf-8")
    readelf_text = _run([readelf, "-h", "-S", "-s", "-r", elf_path], capture=True)
    (build_dir / "object-observer.readelf.txt").write_text(readelf_text, encoding="utf-8")
    if "There are no relocations in this file." not in readelf_text:
        raise ObserverBuildError("观察载荷仍有未处理重定位")
    wrapper = disassembly.split("<ap01_dark_skin_ui_timer_wrapper>:", 1)[1]
    wrapper = wrapper.split("\n\n", 1)[0]
    ensure_position = wrapper.find("<ensure_state>")
    stock_position = wrapper.find("<stock_ui_timer>")
    if stock_position < 0 or ensure_position < 0 or ensure_position > stock_position:
        raise ObserverBuildError("包装函数没有先确保独立观察定时器，再调用原厂 UI 定时函数")
    source_text = SOURCE.read_text(encoding="utf-8")
    forbidden = (
        "lv_obj_create", "lv_obj_del", "lv_obj_set_", "lv_obj_add_event_cb",
        "lv_obj_add_flag", "lv_obj_remove_flag", "lv_obj_align", "lv_obj_center",
    )
    if any(name in source_text for name in forbidden):
        raise ObserverBuildError("观察源码包含改变对象的 LVGL 调用")
    if "struct record records[MAX_OBJECTS]" in source_text:
        raise ObserverBuildError("观察状态仍包含完整对象记录数组")
    required_incremental_contract = (
        "#define MAX_PERSISTENT_BYTES 192u",
        "observer_state_must_remain_small",
        "TIMER_BYTES + sizeof(struct observer_state) <= MAX_PERSISTENT_BYTES",
        "state->probe_sent == 0u",
        "state->page = -1",
        "resolve_object((void *)state->root",
        "advance_path((void *)state->root",
    )
    if any(item not in source_text for item in required_incremental_contract):
        raise ObserverBuildError("观察程序缺少低内存增量遍历或启动探针")
    required_webclient_contract = (
        "#define HTTP_RESPONSE_BYTES 4096u",
        "#define HTTP_SINK_OFFSET 60u",
        "#define HTTP_SINK_ARG_OFFSET 64u",
        "(void *)discard_response_sink",
        "context + HTTP_SINK_ARG_OFFSET) = (void *)record",
    )
    if any(item not in source_text for item in required_webclient_contract):
        raise ObserverBuildError("观察程序没有完整复用原厂 webclient 上下文")

    stack_lines = object_path.with_suffix(".su").read_text(encoding="utf-8").splitlines()
    stack_sizes: list[int] = []
    for line in stack_lines:
        parts = line.split("\t")
        if len(parts) != 3 or parts[2] != "static":
            raise ObserverBuildError("设备端存在无法固定的动态栈用量")
        stack_sizes.append(int(parts[1]))

    candidate = bytearray(baseline)
    candidate[HOOK_HIGH_OFFSET:HOOK_HIGH_OFFSET + 4] = HOOK_HIGH_NEW
    candidate[HOOK_LOW_OFFSET:HOOK_LOW_OFFSET + 4] = HOOK_LOW_NEW
    optimized = optimized_gif.read_bytes()
    candidate[GIF_DATA_OFFSET:GIF_DATA_OFFSET + len(optimized)] = optimized
    candidate[PAYLOAD_START:PAYLOAD_START + len(payload)] = payload
    recovery_crc = refresh_recovery_crc(candidate)
    crc_start = AP01_1_0_2_0031.recovery_trailer_offset + 36
    allowed = (
        ByteRange(HOOK_HIGH_OFFSET, HOOK_HIGH_OFFSET + 4),
        ByteRange(HOOK_LOW_OFFSET, HOOK_LOW_OFFSET + 4),
        ByteRange(GIF_DATA_OFFSET, GIF_DATA_OFFSET + len(optimized)),
        ByteRange(PAYLOAD_START, PAYLOAD_START + len(payload)),
        ByteRange(crc_start, crc_start + 4),
    )
    validation = validate_candidate(baseline, bytes(candidate), allowed)
    output = output_dir / OUTPUT_NAME
    manifest = output.with_suffix(".manifest.json")
    report = {
        "schema_version": 1,
        "artifact_type": "ap01-read-only-object-tree-observer",
        "built_at_beijing": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
        "target": {"model": AP01_1_0_2_0031.model, "version": AP01_1_0_2_0031.version},
        "baseline": baseline_report.to_dict(),
        "git": git,
        "tools": versions,
        "payload": {
            "entry": f"0x{symbols['ap01_dark_skin_ui_timer_wrapper']:08x}",
            "size": len(payload),
            "capacity": PAYLOAD_CAPACITY,
            "sha256": hashlib.sha256(payload).hexdigest(),
            "maximum_static_stack_bytes": max(stack_sizes, default=0),
            "unresolved_relocations": 0,
        },
        "approved_changes": [item.to_dict() for item in allowed],
        "validation": validation.to_dict(),
        "recovery_crc": f"0x{recovery_crc:08x}",
        "output": {
            "filename": output.name,
            "size": len(candidate),
            "md5": hashlib.md5(candidate).hexdigest(),
            "sha256": hashlib.sha256(candidate).hexdigest(),
            "read_only": freeze,
        },
        "safety": {
            "observer_timer_ensured_before_stock_ui_timer": True,
            "object_mutation_calls_absent": True,
            "network_timeout_seconds": 2,
            "maximum_objects": 64,
            "maximum_depth": 6,
            "maximum_timer_and_state_bytes": 192,
            "full_record_array_absent": True,
            "startup_probe_page": -1,
            "incremental_object_send": True,
            "installation_authorized": False,
            "receiver_address_stored_in_manifest": False,
            "webclient_response_buffer_bytes": 4096,
            "webclient_response_sink_configured": True,
        },
    }
    _write(output, bytes(candidate), freeze)
    _write(manifest, (json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(), freeze)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--freeze", action="store_true")
    parser.add_argument("--require-clean-commit", action="store_true")
    args = parser.parse_args()
    report = build(
        args.baseline.resolve(), args.build_dir.resolve(), args.output_dir.resolve(),
        freeze=args.freeze, require_clean_commit=args.require_clean_commit,
    )
    print(json.dumps(report["output"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
