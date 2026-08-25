import tempfile
import unittest
from pathlib import Path
from urllib.parse import unquote

try:
    from tools.parse_hs_err import parse_log
except ModuleNotFoundError:  # Supports direct execution from the repository root.
    from parse_hs_err import parse_log


class ParseHsErrTest(unittest.TestCase):
    def parse(self, text: str, name: str = "controlled-crash-1.log") -> dict[str, object]:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / name
            path.write_text(text, encoding="utf-8")
            return parse_log(path)

    def test_internal_error(self) -> None:
        result = self.parse(
            """#  Internal Error (/src/hotspot/share/prims/whitebox.cpp:193), pid=10, tid=11
#  fatal error: controlled crash requested through WhiteBox (type 1)
# JRE version: OpenJDK Runtime Environment (25.0.4) (fastdebug build test)
# Java VM: OpenJDK 64-Bit Server VM (fastdebug test)
# Problematic frame:
# V  [libjvm.so+0x10]  VM_ControlledCrash::doit()+0x1
Current thread (0x1):  VMThread \"VM Thread\"          [id=11, stack(0x2,0x3)]
Native frames: (J=compiled Java code, j=interpreted, Vv=VM code, C=native code)
V  [libjvm.so+0x10]  VM_ControlledCrash::doit()+0x1
VM_Operation (0x4): ControlledCrash, mode: safepoint, requested by thread 0x5
"""
        )
        self.assertEqual(result["crash_type"], 1)
        self.assertEqual(result["error_kind"], "Internal Error")
        self.assertEqual(result["source_line"], 193)
        self.assertEqual(result["source_file"], "/src/hotspot/share/prims/whitebox.cpp")
        self.assertEqual(result["direct_cause"], "WhiteBox 主动调用 fatal")
        self.assertEqual(result["vm_operation"]["name"], "ControlledCrash")
        self.assertEqual(result["current_thread"]["name"], "VMThread \"VM Thread\"")
        self.assertEqual(len(result["native_frames"]), 1)

    def test_signal(self) -> None:
        result = self.parse(
            """#  SIGSEGV (0xb) at pc=0x10, pid=20, tid=21
# JRE version: test
# Java VM: test vm
# Problematic frame:
# C  [libc.so+0x1]
Current thread (0x1): VMThread \"VM Thread\" [id=21, stack(0x2,0x3)]
VM_Operation (0x4): ControlledCrash, mode: safepoint, requested by thread 0x5
siginfo: si_signo: 11 (SIGSEGV), si_code: 1 (SEGV_MAPERR), si_addr: 0x400
Native frames:
C  [libc.so+0x1]  VM_ControlledCrash::doit()+0x1
""",
            name="controlled-crash-4.log",
        )
        self.assertEqual(result["signal"], "SIGSEGV")
        self.assertEqual(result["error_kind"], "Signal")
        self.assertEqual(result["crash_type"], 4)
        self.assertEqual(result["signal_number"], "0xb")
        self.assertIn("SEGV_MAPERR", result["siginfo"])
        self.assertEqual(result["direct_cause"], "非法地址访问导致 SIGSEGV")
        self.assertEqual(result["error_reporting_frames"], [])

    def test_real_world_jbs_log(self) -> None:
        result = self.parse(
            """#  SIGSEGV (0xb) at pc=0x00007f2b1eb8e363, pid=3558129, tid=1440504
#
# JRE version: Java(TM) SE Runtime Environment (21.0+35) (build 21+35-LTS-2513)
# Java VM: Java HotSpot(TM) 64-Bit Server VM (21+35-LTS-2513, mixed mode, z gc, linux-amd64)
# Problematic frame:
# V  [libjvm.so+0x8f9363]  JavaThread::is_lock_owned(unsigned char*) const+0x23
Current thread (0x00007f23f09ba260):  JavaThread "Thread-1833141" daemon [_thread_in_vm, id=1440504, stack(0x1,0x2)]
siginfo: si_signo: 11 (SIGSEGV), si_code: 1 (SEGV_MAPERR), si_addr: 0x0000000000000000
Native frames: (J=compiled Java code, j=interpreted, Vv=VM code, C=native code)
V  [libjvm.so+0x8f9363]  JavaThread::is_lock_owned(unsigned char*) const+0x23  (monitorChunk.hpp:40)
V  [libjvm.so+0xea3a84]  Threads::owning_thread_from_monitor(ThreadsList*, ObjectMonitor*)+0xd4
""",
            name="hs_err_pid3558129.log",
        )
        self.assertIsNone(result["crash_type"])
        self.assertEqual(result["error_kind"], "Signal")
        self.assertEqual(result["java_version"], "21")
        self.assertEqual(result["current_thread"]["state"], "_thread_in_vm")
        self.assertIn("is_lock_owned", result["problematic_frame"])
        self.assertIn("空指针解引用", result["direct_cause"])
        self.assertIn("is_lock_owned", result["direct_cause"])
        self.assertEqual(result["error_reporting_frames"], [])
        search = result["jbs_search"]
        self.assertIsNotNone(search)
        self.assertIn("JavaThread::is_lock_owned", search["keywords"])
        self.assertIn("gc", search["subsystems"])
        self.assertIn('text ~ "JavaThread::is_lock_owned"', unquote(search["url"]))
        self.assertIn('affectedVersion = "21"', unquote(search["url_version"]))

    def test_reporting_failure_is_separate(self) -> None:
        result = self.parse(
            """#  Out of Memory Error (/src/hotspot/share/prims/whitebox.cpp:199), pid=30, tid=31
# JRE version: test
# Java VM: test vm
Native frames:
V  [libjvm.so+0x1]  VMError::report_and_die()+0x1
V  [libjvm.so+0x2]  DwarfFile::DebugAranges::find_compilation_unit_offset()+0x1
V  [libjvm.so+0x3]  VM_ControlledCrash::doit()+0x1
""",
            name="controlled-crash-3.log",
        )
        self.assertEqual(len(result["native_frames"]), 1)
        self.assertIn("VM_ControlledCrash", result["native_frames"][0])
        self.assertEqual(len(result["error_reporting_frames"]), 2)
        self.assertNotIn("VM_ControlledCrash", "\n".join(result["error_reporting_frames"]))


if __name__ == "__main__":
    unittest.main()
