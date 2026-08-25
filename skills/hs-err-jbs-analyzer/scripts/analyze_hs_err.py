#!/usr/bin/env python3
"""One-shot hs_err log analysis with JBS correlation.

Parses HotSpot fatal error logs (hs_err_pid*.log / *.txt), infers the direct
cause, and correlates the crash with known Java Bug System (JBS) issues.

Usage:
  analyze_hs_err.py <log> [more logs...]         parse and print JSON
  analyze_hs_err.py <log> --jbs [--limit N]      additionally query JBS for
                                                 candidate issues (online)
  analyze_hs_err.py <log> --report [--out F]     write a Markdown report
  analyze_hs_err.py <log> --json <out.json>      save raw JSON to a file

Examples:
  analyze_hs_err.py hs_err_pid12345.log
  analyze_hs_err.py hs_err_pid12345.log --jbs --limit 5
  analyze_hs_err.py *.log --report
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

try:
    from parse_hs_err import parse_log
except ModuleNotFoundError:  # Runs from anywhere when installed in a skill dir.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from parse_hs_err import parse_log

JBS_REST = "https://bugs.openjdk.org/rest/api/2/search"
JBS_ISSUE_URL = "https://bugs.openjdk.org/browse/"


def _jql_of(search: dict[str, Any] | None) -> str | None:
    """Extract the Jira JQL string from a jbs_search url (prefer version-constrained)."""
    if not search:
        return None
    for key in ("url_version", "url"):
        url = search.get(key)
        if not url:
            continue
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        if "jql" in query:
            return query["jql"][0]
    return None


def _query_jbs(jql: str, limit: int, timeout: int = 30) -> list[dict[str, Any]]:
    """Query the JBS REST API and return candidate issues (best effort)."""
    params = {
        "jql": jql,
        "maxResults": limit,
        "fields": "summary,status,resolution,fixVersions",
    }
    url = JBS_REST + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            data = json.load(resp)
    except Exception as exc:  # Network issues must not break the analysis.
        return [{"_error": f"{type(exc).__name__}: {exc}"}]
    issues: list[dict[str, Any]] = []
    for issue in data.get("issues", []):
        fields = issue.get("fields", {})
        issues.append(
            {
                "key": issue.get("key"),
                "summary": fields.get("summary"),
                "status": (fields.get("status") or {}).get("name"),
                "resolution": (fields.get("resolution") or {}).get("name"),
                "fixVersions": [v["name"] for v in (fields.get("fixVersions") or [])],
                "url": JBS_ISSUE_URL + issue.get("key", ""),
            }
        )
    return issues


def _render_report(result: dict[str, Any], candidates: list[dict[str, Any]] | None = None) -> str:
    """Render a Markdown analysis report for one parsed log."""
    search = result.get("jbs_search")
    thread = result.get("current_thread") or {}
    operation = result.get("vm_operation") or {}
    lines = [
        "# hs_err 崩溃分析报告",
        "",
        "## 基本信息",
        "",
        f"- 日志文件：`{result.get('file')}`",
        f"- JRE 版本：{result.get('jre_version') or '未知'}",
        f"- VM 类型：{result.get('java_vm') or '未知'}",
        f"- 崩溃类型：{result.get('error_kind') or '未知'}"
        + (f"（crash_type={result.get('crash_type')}）" if result.get("crash_type") is not None else ""),
        f"- 直接原因：{result.get('direct_cause') or '未能推断'}",
        f"- Problematic frame：{result.get('problematic_frame') or '未知'}",
        f"- 崩溃线程：{thread.get('name') or '未知'}（state={thread.get('state') or '未知'}）",
        "",
        "## 关键证据",
        "",
    ]
    if result.get("assert_message"):
        lines.append(f"- 断言消息：`{result['assert_message']}`")
    if result.get("fault_address") is not None:
        lines.append(f"- 故障地址：`0x{result['fault_address']:x}`")
    if result.get("segv_code"):
        lines.append(f"- SEGV 码：{result['segv_code']}")
    if operation.get("name"):
        lines.append(f"- VM 操作：{operation['name']}（{operation.get('mode') or '?'}）")
    if result.get("error_reporting_frames"):
        lines.append(f"- 错误报告链帧数：{len(result['error_reporting_frames'])}")
    frames = result.get("native_frames") or []
    if frames:
        lines.extend(["", "### 崩溃栈顶部", ""])
        for frame in frames[:6]:
            lines.append(f"```\n{frame}\n```")
        if len(frames) > 6:
            lines.append(f"（共 {len(frames)} 帧，仅显示前 6 帧）")

    lines.extend(["", "## JBS 已知问题关联", ""])
    if search:
        lines.append(f"- 检索关键词：`{', '.join(search.get('keywords') or [])}`")
        lines.append(f"- 子系统提示：{', '.join(search.get('subsystems') or []) if search.get('subsystems') else '未知'}")
        if search.get("version"):
            lines.append(f"- 日志版本：{search['version']}（用于版本约束检索）")
        lines.append(f"- 关键词检索：{search.get('url')}")
        if search.get("url_version"):
            lines.append(f"- 版本约束检索：{search['url_version']}")
        if candidates is None:
            lines.append("> 未做联机检索。加 `--jbs` 可直接查询 JBS 候选 issue。")
    else:
        lines.append("- 受控样本（含 controlledCrash 标记），不关联 JBS 已知问题。")

    if candidates:
        lines.extend(["", "### JBS 候选 issue", ""])
        for cand in candidates:
            if "_error" in cand:
                lines.append(f"- ⚠ 检索失败：{cand['_error']}")
                continue
            fix = ", ".join(cand["fixVersions"]) or "未发布"
            lines.append(
                f"- [{cand['key']}]({cand['url']}) — {cand['summary']}（{cand['status']}，fix {fix}）"
            )
        fixed = [c for c in candidates if c.get("fixVersions")]
        if fixed:
            newest = max(fixed[0]["fixVersions"]) if fixed[0]["fixVersions"] else None
            if newest and result.get("java_version") and newest != result["java_version"]:
                lines.extend(["", "## 建议", "", f"- 已知问题，修复版本为 **{newest}**：建议升级到该版本或更高。", "- 若无法升级：参照 issue 描述临时规避（如关闭触发路径、调整 GC/编译器参数）。"])
            else:
                lines.extend(["", "## 建议", "", "- JBS 已有同类型 issue，建议跟踪其修复进度并保持 JDK 更新。"])
    lines.extend(["", "---", "", "由 `hs-err-jbs-analyzer` skill 自动生成。"])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("logs", nargs="*", help="hs_err log file(s)")
    parser.add_argument("--jbs", action="store_true", help="query JBS for candidate issues (online)")
    parser.add_argument("--limit", type=int, default=5, help="max JBS candidates per log (default 5)")
    parser.add_argument("--report", action="store_true", help="write a Markdown report")
    parser.add_argument("--json", type=Path, help="save raw JSON to this file")
    parser.add_argument("--out", type=Path, default=Path("hs-err-analysis.md"), help="report output path")
    args = parser.parse_args()

    if not args.logs:
        parser.print_help()
        return 2

    results: list[dict[str, Any]] = []
    for path in args.logs:
        result = parse_log(path)
        result["file"] = str(Path(path).resolve())
        if args.jbs and result.get("jbs_search"):
            jql = _jql_of(result["jbs_search"])
            if jql:
                result["jbs_candidates"] = _query_jbs(jql, args.limit)
        results.append(result)

    if args.json:
        args.json.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.report:
        sections = [_render_report(r, r.get("jbs_candidates") if args.jbs else None) for r in results]
        report = "\n\n---\n\n".join(sections)
        args.out.write_text(report + "\n", encoding="utf-8")
        print(f"report written to {args.out}", file=sys.stderr)
    else:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
