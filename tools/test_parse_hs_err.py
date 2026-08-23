import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
