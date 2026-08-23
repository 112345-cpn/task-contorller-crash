#!/usr/bin/env python3
"""Extract stable diagnostic fields from a HotSpot hs_err log.

The parser is deliberately conservative. It reports text that is present in
the log and uses the controlledCrash message only to label the known sample
type. It does not claim that a log matches a Java bug.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Iterable


ERROR_RE = re.compile(
    r"^#\s+(?P<kind>Internal Error|Out of Memory Error)\s+"
    r"\((?P<source>.*):(?P<line>\d+)\),\s+pid=(?P<pid>\d+),\s+tid=(?P<tid>\d+)"
)
SIGNAL_RE = re.compile(
    r"^#\s+(?P<signal>SIG[A-Z0-9]+)\s+\((?P<number>[^)]+)\) at "
    r"pc=(?P<pc>[^,]+),\s+pid=(?P<pid>\d+),\s+tid=(?P<tid>\d+)"
)
TYPE_RE = re.compile(r"controlled crash requested through WhiteBox \(type (?P<type>[1-5])\)")
FILE_TYPE_RE = re.compile(r"controlled-crash-(?P<type>[1-5])\.log$")
CURRENT_THREAD_RE = re.compile(
    r"^Current thread \((?P<address>[^)]+)\):\s+(?P<name>.*?)\s+\[id=(?P<id>\d+),"
)
VM_OPERATION_RE = re.compile(
    r"^VM_Operation \([^)]*\):\s+(?P<name>[^,]+)"
    r"(?:, mode: (?P<mode>[^,]+))?"
)
SIGINFO_RE = re.compile(r"^siginfo:\s+(?P<value>.*)$")
FRAME_RE = re.compile(r"^[VvJjCc]\s+")


def _without_log_prefix(line: str) -> str:
    return line[2:] if line.startswith("# ") else line


def _first_match(lines: list[str], pattern: re.Pattern[str]) -> re.Match[str] | None:
    return next((match for line in lines if (match := pattern.search(line))), None)


def _native_sections(lines: list[str]) -> list[list[str]]:
    sections: list[list[str]] = []
    for index, line in enumerate(lines):
        if not line.startswith("Native frames:"):
            continue
        frames: list[str] = []
        for candidate in lines[index + 1 :]:
            if candidate.startswith("Native frames:") or candidate.startswith("Registers:"):
                break
            if candidate.startswith("---------------") or candidate.startswith("Java frames:"):
                break
            if FRAME_RE.match(candidate):
                frames.append(candidate)
        if frames:
            sections.append(frames)
    return sections


def _direct_cause(lines: list[str], signal: str | None, error_kind: str | None) -> str | None:
    text = "\n".join(lines[:40]).lower()
    if signal == "SIGSEGV":
        return "非法地址访问导致 SIGSEGV"
    if signal == "SIGFPE":
        return "整数除零导致 SIGFPE"
    if error_kind == "Out of Memory Error":
        return "WhiteBox 主动请求 native OOM"
    if "guarantee(false) failed" in text:
        return "guarantee 检查失败"
    if "fatal error: controlled crash requested" in text:
        return "WhiteBox 主动调用 fatal"
    return None


def _redact_source(path: str | None) -> str | None:
    if path is None:
        return None
    marker = "/TencentKona-25-master/"
    if marker in path:
        return "<kona>/" + path.split(marker, 1)[1]
    return path


def parse_log(path: str | Path) -> dict[str, object]:
    """Parse one log and return JSON-serializable stable fields."""

    path = Path(path)
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    error_match = _first_match(lines, ERROR_RE)
    signal_match = _first_match(lines, SIGNAL_RE)
    type_match = _first_match(lines, TYPE_RE)
    file_type_match = FILE_TYPE_RE.search(path.name)
    thread_match = _first_match(lines, CURRENT_THREAD_RE)
    operation_match = _first_match(lines, VM_OPERATION_RE)
    siginfo_match = _first_match(lines, SIGINFO_RE)

    problematic_frame: str | None = None
    for index, line in enumerate(lines):
        if line.strip() == "# Problematic frame:":
            for candidate in lines[index + 1 :]:
                candidate = _without_log_prefix(candidate).strip()
                if candidate:
                    problematic_frame = candidate
                    break
            break

    if error_match:
        error_kind = error_match.group("kind")
        source_file = error_match.group("source")
        source_line = int(error_match.group("line"))
        pid = int(error_match.group("pid"))
        tid = int(error_match.group("tid"))
    else:
        error_kind = "Signal" if signal_match else None
        source_file = None
        source_line = None
        pid = int(signal_match.group("pid")) if signal_match else None
        tid = int(signal_match.group("tid")) if signal_match else None

    signal = signal_match.group("signal") if signal_match else None
    signal_number = signal_match.group("number") if signal_match else None
    native_sections = _native_sections(lines)
    native_frames = max(
        native_sections,
        key=lambda section: (any("VM_ControlledCrash" in frame for frame in section), len(section)),
        default=[],
    )

    result: dict[str, object] = {
        "file": path.name,
        "crash_type": int(type_match.group("type")) if type_match else (
            int(file_type_match.group("type")) if file_type_match else None
        ),
        "error_kind": error_kind,
        "signal": signal,
        "signal_number": signal_number,
        "siginfo": siginfo_match.group("value") if siginfo_match else None,
        "source_file": _redact_source(source_file),
        "source_line": source_line,
        "pid": pid,
        "tid": tid,
        "jre_version": next(
            (_without_log_prefix(line)[len("JRE version: ") :] for line in lines if line.startswith("# JRE version: ")),
            None,
        ),
        "java_vm": next(
            (_without_log_prefix(line)[len("Java VM: ") :] for line in lines if line.startswith("# Java VM: ")),
            None,
        ),
        "current_thread": {
            "name": thread_match.group("name") if thread_match else None,
            "id": int(thread_match.group("id")) if thread_match else None,
        },
        "problematic_frame": problematic_frame,
        "vm_operation": {
            "name": operation_match.group("name").strip() if operation_match else None,
            "mode": operation_match.group("mode").strip() if operation_match and operation_match.group("mode") else None,
        },
        "native_frames": native_frames,
        "direct_cause": _direct_cause(lines, signal, error_kind),
    }
    return result


def _paths(args: argparse.Namespace) -> Iterable[Path]:
    if args.directory:
        yield from sorted(args.directory.glob("controlled-crash-*.log"))
    yield from (Path(path) for path in args.logs)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("logs", nargs="*", help="hs_err log files")
    parser.add_argument("--directory", type=Path, help="parse controlled-crash-*.log in this directory")
    parser.add_argument("-o", "--output", type=Path, help="write JSON to this file instead of stdout")
    args = parser.parse_args()
    paths = list(_paths(args))
    if not paths:
        parser.error("provide log files or --directory")
    output = json.dumps([parse_log(path) for path in paths], ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
