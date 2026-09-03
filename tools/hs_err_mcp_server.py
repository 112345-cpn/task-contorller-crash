#!/usr/bin/env python3
"""MCP server for HotSpot hs_err log analysis and JBS correlation.

Exposes the hs-err-jbs-analyzer workflow as Model Context Protocol tools so
any MCP client (WorkBuddy, Claude Code, ...) can call it directly:

  parse_hs_err      - parse one hs_err_pid*.log into structured fields
  search_jbs        - query bugs.openjdk.org (JBS) for known issues
  analyze_hs_err    - full pipeline: parse + JBS correlation + advice report

Transport: stdio (default for MCP servers). Run with:

  python3.10 tools/hs_err_mcp_server.py

The server depends on parse_hs_err.py in the same directory. Requires
Python >= 3.10 and the `mcp` Python package (pip install "mcp>=2.0").

Example client config (e.g. WorkBuddy ~/.workbuddy/mcp.json):

  {
    "mcpServers": {
      "hs-err-jbs-analyzer": {
        "command": "<path to a Python >= 3.10 with mcp installed>",
        "args": ["<repo>/task-controlled-crash/tools/hs_err_mcp_server.py"]
      }
    }
  }
"""

from __future__ import annotations

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

try:
    from parse_hs_err import parse_log
except ModuleNotFoundError:  # Run from anywhere.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from parse_hs_err import parse_log

from mcp.server.mcpserver import MCPServer

JBS_REST = "https://bugs.openjdk.org/rest/api/2/search"
JBS_ISSUE_URL = "https://bugs.openjdk.org/browse/"

mcp = MCPServer("hs-err-jbs-analyzer")


def _query_jbs(jql: str, limit: int, timeout: int = 30) -> list[dict[str, Any]]:
    """Query the JBS REST API and return candidate issues (best effort)."""
    params = {
        "jql": jql,
        "maxResults": limit,
        "fields": "summary,status,resolution,fixVersions,components",
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
                "components": [c["name"] for c in (fields.get("components") or [])],
                "url": JBS_ISSUE_URL + issue.get("key", ""),
            }
        )
    return issues


@mcp.tool()
def parse_hs_err(file_path: str) -> dict[str, Any]:
    """Parse a HotSpot fatal error log (hs_err_pid*.log) into structured fields.

    Returns error kind/signal, direct cause, problematic frame, crash thread,
    fault address, assert message, java version and JBS search hints. For
    real-world logs (no controlledCrash marker) the direct cause is inferred
    and a jbs_search object with Jira JQL urls is included.
    """
    result = parse_log(file_path)
    result["file"] = str(Path(file_path).resolve())
    return result


@mcp.tool()
def search_jbs(
    query: str, version: str | None = None, max_results: int = 5
) -> dict[str, Any]:
    """Search bugs.openjdk.org (JBS) for known issues matching a keyword.

    Args:
        query: keyword, typically the crash-site function name (e.g.
            "JavaThread::is_lock_owned") or an assert message (e.g.
            "bad AD file").
        version: optional JDK version for the affectedVersion constraint
            (e.g. "21", "11.0.20"). Strongly recommended: constraining by
            the version from the log narrows noisy keyword matches to the
            actual bug.
        max_results: max issues to return (default 5).

    Returns {"query", "version", "count", "results"} where results is a list
    of issues with key/summary/status/resolution/fixVersions/url.
    """
    jql = f'text ~ "{query}"'
    if version:
        jql += f' AND affectedVersion = "{version}"'
    issues = _query_jbs(jql, max_results)
    return {"query": query, "version": version, "count": len(issues), "results": issues}


@mcp.tool()
def analyze_hs_err(file_path: str, max_results: int = 5) -> str:
    """Full analysis of one hs_err log: parse, correlate with JBS, advise.

    Runs the whole hs-err-jbs-analyzer pipeline and returns a Markdown
    report: basic info, key evidence, crash stack, JBS candidate issues
    (queried live, version-constrained), and upgrade/mitigation advice.
    """
    result = parse_log(file_path)
    result["file"] = str(Path(file_path).resolve())
    candidates: list[dict[str, Any]] | None = None
    search = result.get("jbs_search")
    if isinstance(search, dict):
        jql = None
        for key in ("url_version", "url"):
            url = search.get(key)
            if not url:
                continue
            qs = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
            if "jql" in qs:
                jql = qs["jql"][0]
                break
        if jql:
            candidates = _query_jbs(jql, max_results)
    return _render_report(result, candidates)


def _render_report(result: dict[str, Any], candidates: list[dict[str, Any]] | None) -> str:
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
        fa = result["fault_address"]
        if isinstance(fa, int):
            lines.append(f"- 故障地址：`0x{fa:x}`")
        else:
            lines.append(f"- 故障地址：`{fa}`")
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
            lines.append("> 未做联机检索。")
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
        if fixed and fixed[0]["fixVersions"]:
            newest = max(fixed[0]["fixVersions"])
            if newest and result.get("java_version") and newest != result["java_version"]:
                lines.extend(["", "## 建议", "", f"- 已知问题，修复版本为 **{newest}**：建议升级到该版本或更高。", "- 若无法升级：参照 issue 描述临时规避（如关闭触发路径、调整 GC/编译器参数）。"])
            else:
                lines.extend(["", "## 建议", "", "- JBS 已有同类型 issue，建议跟踪其修复进度并保持 JDK 更新。"])
    lines.extend(["", "---", "", "由 `hs-err-jbs-analyzer` MCP server 自动生成。"])
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run()
