#!/usr/bin/env python3
"""Extract stable diagnostic fields from a HotSpot hs_err log.

The parser is deliberately conservative. It reports text that is present in
the log and uses the controlledCrash message only to label the known sample
type. It does not claim that a log matches a Java bug.

Logs copied from the Java Bug System (JBS) are supported as well. All header
regexes tolerate the wider spacing produced by JBS attachments and web
copies (for example ``#  JRE version:`` with two spaces), and the
``Current thread`` line is accepted both in the controlled-crash layout
(``[id=...]``) and in the real-world layout that carries thread state
(``daemon [_thread_in_vm, id=...]``).

For real-world logs (no controlledCrash marker) the parser additionally
derives a best-effort direct cause from siginfo and the problematic frame,
and proposes JBS search keywords together with a Jira jql URL. When the
JRE version can be read from the log, a second, version-constrained URL
(``affectedVersion = ...``) is proposed as well: on JBS the keyword alone
often matches hundreds of issues, while the version constraint narrows it
to a handful. These are hints, not claims.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Iterable
from urllib.parse import quote


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
    r"^Current thread \((?P<address>[^)]+)\):\s+(?P<name>.*?)"
    r"\s*\[(?:(?P<state>_thread_\w+),\s*)?id=(?P<id>\d+)"
)
VM_OPERATION_RE = re.compile(
    r"^VM_Operation \([^)]*\):\s+(?P<name>[^,]+)"
    r"(?:, mode: (?P<mode>[^,]+))?"
)
SIGINFO_RE = re.compile(r"^siginfo:\s+(?P<value>.*)$")
FAULT_ADDRESS_RE = re.compile(r"si_addr:\s*(?P<addr>0x[0-9a-fA-F]+)")
SEGV_CODE_RE = re.compile(r"si_code:\s*\d+\s*\((?P<code>[A-Z_]+)\)")
ASSERT_RE = re.compile(
    r"^#\s+(?P<kind>assert|guarantee)\((?P<expr>.*?)\)\s+failed:\s*(?P<msg>.*)$"
)
JRE_VERSION_RE = re.compile(r"^#\s+JRE version:\s*(?P<value>.*)$")
JRE_VERSION_TOKEN_RE = re.compile(r"\((?P<token>\d[\w.+-]*)\)")
JAVA_VM_RE = re.compile(r"^#\s+Java VM:\s*(?P<value>.*)$")
PROBLEMATIC_FRAME_HEADER_RE = re.compile(r"^#\s+Problematic frame:\s*$")
FRAME_RE = re.compile(r"^[VvJjCc]\s+")
FRAME_SYMBOL_RE = re.compile(r"^\s*[VJjCc]\s+\[[^\]]+\]\s+(?P<symbol>[^(]+?)\s*(?=\(|$)")
JBS_SEARCH_URL = "https://bugs.openjdk.org/issues/?jql="


def _without_log_prefix(line: str) -> str:
    return line[2:] if line.startswith("# ") else line


def _first_match(lines: list[str], pattern: re.Pattern[str]) -> re.Match[str] | None:
    return next((match for line in lines if (match := pattern.search(line))), None)


def _group(match: re.Match[str] | None, name: str) -> str | None:
    value = match.group(name) if match else None
    return value.strip() if isinstance(value, str) else value


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


def _split_reporting_frames(frames: list[str]) -> tuple[list[str], list[str]]:
    """Separate the original VM operation from a later reporter failure.

    Real-world logs do not carry the VM_ControlledCrash marker, so the whole
    section is returned as crash frames and the reporting list is empty.
    """
    report_marker = next(
        (
            index for index, frame in enumerate(frames)
            if "VMError::report_and_die" in frame or "report_vm_error" in frame
        ),
        None,
    )
    operation_marker = next(
        (index for index, frame in enumerate(frames) if "VM_ControlledCrash::doit" in frame),
        None,
    )
    if report_marker is None or operation_marker is None or report_marker > operation_marker:
        return frames, []
    return frames[operation_marker:], frames[report_marker:operation_marker]


def _controlled_cause(lines: list[str], signal: str | None, error_kind: str | None) -> str | None:
    """Direct cause of the known controlledCrash samples."""
    if signal == "SIGSEGV":
        return "非法地址访问导致 SIGSEGV"
    if signal == "SIGFPE":
        return "整数除零导致 SIGFPE"
    if error_kind == "Out of Memory Error":
        return "WhiteBox 主动请求 native OOM"
    text = "\n".join(lines[:40]).lower()
    if "guarantee(false) failed" in text:
        return "guarantee 检查失败"
    if "fatal error: controlled crash requested" in text:
        return "WhiteBox 主动调用 fatal"
    return None


def _inferred_cause(
    assert_match: re.Match[str] | None,
    signal: str | None,
    fault_address: str | None,
    segv_code: str | None,
    frame_symbol: str | None,
) -> str | None:
    """Best-effort direct cause for a real-world (non-controlled) log.

    Every clause is grounded in text that is present in the log: the assert
    message, the siginfo si_addr/si_code, and the problematic frame symbol.
    """
    if assert_match:
        kind = assert_match.group("kind")
        expression = assert_match.group("expr").strip()
        message = assert_match.group("msg").strip()
        return f"断言失败: {kind}({expression}) failed: {message}"
    if signal == "SIGSEGV":
        address = int(fault_address, 16) if fault_address else None
        if address == 0:
            cause = f"空指针解引用 (si_addr={fault_address})"
        elif address is not None and address < 0x10000:
            cause = f"低地址解引用，疑似空指针加字段偏移 (si_addr={fault_address})"
        elif segv_code == "SEGV_MAPERR":
            cause = "访问未映射地址 (SEGV_MAPERR)"
        elif segv_code == "SEGV_ACCERR":
            cause = "访问权限冲突 (SEGV_ACCERR)"
        else:
            cause = "非法地址访问 (SIGSEGV)"
        if frame_symbol:
            cause += f"，崩溃点 {frame_symbol}"
        return cause
    if signal == "SIGFPE":
        return "整数运算错误导致 SIGFPE"
    if signal:
        return f"{signal} 信号崩溃"
    return None


def _subsystem_hints(*texts: str | None) -> list[str]:
    text = " ".join(part for part in texts if part).lower()
    hints: list[str] = []
    if "jvmti" in text:
        hints.append("jvmti")
    if any(word in text for word in ("c2", "compile", "matcher", "opto")):
        hints.append("c2-compiler")
    if any(word in text for word in (" gc", "zgc", "zheap", "g1 gc", "shenandoah")):
        hints.append("gc")
    return hints


def _java_version(jre_version: str | None) -> str | None:
    """Best-effort short version like ``21`` or ``11.0.20`` from the JRE line.

    Takes the first parenthesized token that starts with a digit (so
    ``Java(TM)`` is skipped), strips build suffixes such as ``+35`` or
    ``-internal``, and drops a trailing ``.0`` (``21.0`` -> ``21``).
    """
    if jre_version is None:
        return None
    match = JRE_VERSION_TOKEN_RE.search(jre_version)
    if not match:
        return None
    token = match.group("token").split("+")[0].split("-")[0]
    if token.endswith(".0"):
        token = token[: -2]
    return token or None


def _jbs_search(
    frame_symbol: str | None,
    assert_message: str | None,
    signal: str | None,
    thread_name: str | None,
    java_vm: str | None,
    java_version: str | None,
) -> dict[str, object] | None:
    """Propose search keywords for the Java Bug System (best effort)."""
    keywords: list[str] = []
    if frame_symbol:
        keywords.append(frame_symbol)
    if assert_message:
        keywords.append(assert_message)
    if signal:
        keywords.append(signal)
    if not keywords:
        return None
    # assert_message is the most distinctive for an assert crash; otherwise
    # the problematic frame symbol; otherwise the signal name.
    primary = assert_message or frame_symbol or signal
    jql = f'text ~ "{primary}"'
    result: dict[str, object] = {
        "keywords": keywords,
        "subsystems": _subsystem_hints(frame_symbol, thread_name, java_vm) or None,
        "url": JBS_SEARCH_URL + quote(jql),
    }
    if java_version:
        jql_version = f'{jql} AND affectedVersion = "{java_version}"'
        result["version"] = java_version
        result["url_version"] = JBS_SEARCH_URL + quote(jql_version)
    return result


def _redact_source(path: str | None) -> str | None:
    if path is None:
        return None
    marker = "/TencentKona-25-master/"
    if marker in path:
        return "<kona>/" + path.split(marker, 1)[1]
    return path


def _redact_runtime_text(value: str | None) -> str | None:
    if value is None:
        return None
    return re.sub(r"adhoc\.[^, )]+", "adhoc.<local-build>", value)


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
    assert_match = _first_match(lines, ASSERT_RE)

    problematic_frame: str | None = None
    for index, line in enumerate(lines):
        if PROBLEMATIC_FRAME_HEADER_RE.match(line):
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
    siginfo_value = siginfo_match.group("value") if siginfo_match else None
    fault_address_match = FAULT_ADDRESS_RE.search(siginfo_value) if siginfo_value else None
    fault_address = fault_address_match.group("addr") if fault_address_match else None
    segv_code_match = SEGV_CODE_RE.search(siginfo_value) if siginfo_value else None
    segv_code = segv_code_match.group("code") if segv_code_match else None
    frame_symbol_match = FRAME_SYMBOL_RE.match(problematic_frame) if problematic_frame else None
    frame_symbol = _group(frame_symbol_match, "symbol")
    assert_message = _group(assert_match, "msg")
    crash_type = (
        int(type_match.group("type")) if type_match else (
            int(file_type_match.group("type")) if file_type_match else None
        )
    )

    native_sections = _native_sections(lines)
    all_native_frames = max(
        native_sections,
        key=lambda section: (any("VM_ControlledCrash" in frame for frame in section), len(section)),
        default=[],
    )
    native_frames, error_reporting_frames = _split_reporting_frames(all_native_frames)

    thread_name = _group(thread_match, "name")
    java_vm = _group(_first_match(lines, JAVA_VM_RE), "value")
    jre_version = _redact_runtime_text(_group(_first_match(lines, JRE_VERSION_RE), "value"))
    java_version = _java_version(jre_version)

    if crash_type is not None:
        direct_cause = _controlled_cause(lines, signal, error_kind)
    else:
        direct_cause = _inferred_cause(assert_match, signal, fault_address, segv_code, frame_symbol)
    jbs_search = (
        _jbs_search(frame_symbol, assert_message, signal, thread_name, java_vm, java_version)
        if crash_type is None
        else None
    )

    result: dict[str, object] = {
        "file": path.name,
        "crash_type": crash_type,
        "error_kind": error_kind,
        "signal": signal,
        "signal_number": signal_number,
        "siginfo": siginfo_value,
        "fault_address": fault_address,
        "source_file": _redact_source(source_file),
        "source_line": source_line,
        "pid": pid,
        "tid": tid,
        "jre_version": jre_version,
        "java_version": java_version,
        "java_vm": _redact_runtime_text(java_vm),
        "current_thread": {
            "name": thread_name,
            "id": int(thread_match.group("id")) if thread_match else None,
            "state": _group(thread_match, "state"),
        },
        "problematic_frame": problematic_frame,
        "vm_operation": {
            "name": operation_match.group("name").strip() if operation_match else None,
            "mode": operation_match.group("mode").strip() if operation_match and operation_match.group("mode") else None,
        },
        "native_frames": native_frames,
        "error_reporting_frames": error_reporting_frames,
        "source_line_meaning": (
            "line reported by the HotSpot error header; for signal logs the header has no source line"
        ),
        "assert_message": assert_message,
        "direct_cause": direct_cause,
        "jbs_search": jbs_search,
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
