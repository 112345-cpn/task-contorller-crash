#!/usr/bin/env python3
"""End-to-end MCP client smoke test for hs_err_mcp_server.py (stdio transport)."""
import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

TOOLS_DIR = Path(__file__).resolve().parent
PYTHON = r"C:/Users/lenovo/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
SAMPLES = Path(r"C:/Users/lenovo/AppData/Local/Temp/jbs-test")


def text_of(result) -> str:
    parts = []
    for block in result.content:
        parts.append(block.text if hasattr(block, "text") else str(block))
    return "\n".join(parts)


def is_error(result) -> bool:
    return bool(getattr(result, "is_error", getattr(result, "isError", False)))


async def main() -> int:
    params = StdioServerParameters(
        command=PYTHON,
        args=[str(TOOLS_DIR / "hs_err_mcp_server.py")],
        cwd=str(TOOLS_DIR),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # 1. tools/list
            tools = await session.list_tools()
            names = [t.name for t in tools.tools]
            print("=== tools/list ===")
            for t in tools.tools:
                print(f"  {t.name}: {t.description.splitlines()[0][:60]}")
            assert "parse_hs_err" in names and "search_jbs" in names and "analyze_hs_err" in names

            # 2. call parse_hs_err
            print("\n=== call parse_hs_err (jdk-8314225.log) ===")
            res = await session.call_tool("parse_hs_err", {"file_path": str(SAMPLES / "jdk-8314225.log")})
            data = json.loads(text_of(res))
            print("  direct_cause:", data["direct_cause"])
            print("  java_version:", data["java_version"])
            assert data["jbs_search"]["url_version"], "url_version missing"

            # 3. call search_jbs with version constraint
            print("\n=== call search_jbs (JavaThread::is_lock_owned, v21) ===")
            res = await session.call_tool(
                "search_jbs",
                {"query": "JavaThread::is_lock_owned", "version": "21", "max_results": 3},
            )
            payload = json.loads(text_of(res))
            cands = payload["results"]
            for c in cands:
                print(f"  {c['key']} | {c['summary'][:45]} | fix: {','.join(c['fixVersions'])}")
            assert cands[0]["key"] == "JDK-8314225", f"unexpected top hit: {cands[0]['key']}"

            # 4. call analyze_hs_err
            print("\n=== call analyze_hs_err (jdk-8312741.log) ===")
            res = await session.call_tool("analyze_hs_err", {"file_path": str(SAMPLES / "jdk-8312741.log")})
            report = text_of(res)
            assert "JDK-8312741" in report or "8238812" in report
            for ln in report.splitlines():
                if ln.startswith(("- 直接原因", "- 断言消息", "## 建议", "- 已知问题", "- [")):
                    print(" ", ln[:95])
            print("\nALL E2E TOOLS OK")
            return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
