/*
 * Copyright (c) 2026, Tencent. All rights reserved.
 * DO NOT ALTER OR REMOVE COPYRIGHT NOTICES OR THIS FILE HEADER.
 *
 * This code is free software; you can redistribute it and/or modify it
 * under the terms of the GNU General Public License version 2 only, as
 * published by the Free Software Foundation.
 */

/*
 * @test ControlledCrash
 * @summary Exercise the WhiteBox controlledCrash API and produce analyzable hs_err logs
 * @requires vm.flagless
 * @library /test/lib
 * @build jdk.test.whitebox.WhiteBox
 * @run driver jdk.test.lib.helpers.ClassFileInstaller -jar whitebox.jar jdk.test.whitebox.WhiteBox
 * @run main ControlledCrash
 */

import java.io.File;
import java.util.stream.Collectors;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;

import jdk.test.lib.process.OutputAnalyzer;
import jdk.test.lib.process.ProcessTools;

public class ControlledCrash {
    private static final String[] TYPES = { "1", "2", "3", "4", "5" };

    public static void main(String[] args) throws Exception {
        if (args.length == 1) {
            jdk.test.whitebox.WhiteBox.getWhiteBox().controlledCrash(Integer.parseInt(args[0]));
            throw new AssertionError("controlledCrash returned unexpectedly");
        }

        for (String type : TYPES) {
            Path log = Paths.get("controlled-crash-" + type + ".log").toAbsolutePath();
            ProcessBuilder pb = ProcessTools.createLimitedTestJavaProcessBuilder(
                    "-XX:-CreateCoredumpOnCrash",
                    "-XX:ErrorFile=" + log,
                    "-Xbootclasspath/a:" + new File("whitebox.jar").getAbsolutePath(),
                    "-XX:+UnlockDiagnosticVMOptions",
                    "-XX:+WhiteBoxAPI",
                    ControlledCrash.class.getName(), type);

            OutputAnalyzer output = new OutputAnalyzer(pb.start());
            output.shouldNotHaveExitValue(0);
            if (!Files.exists(log)) {
                throw new AssertionError("Missing error log for crash type " + type + ": " + log);
            }

            String errorLog = Files.readAllLines(log).stream().collect(Collectors.joining(System.lineSeparator()));
            if (!errorLog.contains("VM_ControlledCrash")) {
                throw new AssertionError("Error log does not identify VM_ControlledCrash for type " + type);
            }
            Files.deleteIfExists(log);
        }
    }
}
