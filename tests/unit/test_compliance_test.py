# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2014-2019, Lars Asplund lars.anders.asplund@gmail.com

"""
Test the compliance test.
"""
from unittest import TestCase
from shutil import rmtree
from os.path import exists, dirname, join, abspath
from os import makedirs
from itertools import product
import re
from vunit.ostools import renew_path
from vunit import ComplianceTest
from vunit.vc.compliance_test import main
from vunit import VUnit
from vunit.vhdl_parser import VHDLDesignFile, VHDLReference
from tests.mock_2or3 import mock


class TestComplianceTest(TestCase):  # pylint: disable=too-many-public-methods
    """Tests the ComplianceTest class."""

    def setUp(self):
        self.tmp_dir = join(dirname(__file__), "vc_tmp")
        renew_path(self.tmp_dir)
        self.vc_contents = """
library ieee
use ieee.std_logic_1164.all;

entity vc is
  generic(vc_h : vc_handle_t);
  port(
    a, b : in std_logic;
    c : in std_logic := '0';
    d, e : inout std_logic;
    f, g : inout std_logic := '1';
    h, i : out std_logic := '0';
    j : out std_logic);

end entity;
"""
        self.vc_path = self.make_file(join(self.tmp_dir, "vc.vhd"), self.vc_contents)

        self.vci_contents = """
package vc_pkg is
  impure function new_vc(
    logger : logger_t := vc_logger;
    actor : actor_t := null_actor;
    checker : checker_t := null_checker;
    fail_on_unexpected_msg_type : boolean := true
  ) return vc_handle_t;
end package;
"""
        self.vci_path = self.make_file(join(self.tmp_dir, "vci.vhd"), self.vci_contents)

        self.ui = VUnit.from_argv([])

        self.vc_lib = self.ui.add_library("vc_lib")
        self.vc_lib.add_source_files(join(self.tmp_dir, "*.vhd"))

    def tearDown(self):
        if exists(self.tmp_dir):
            rmtree(self.tmp_dir)

    def make_file(self, file_name, contents):
        """
        Create a file in the temporary directory with contents
        Returns the absolute path to the file.
        """
        full_file_name = abspath(join(self.tmp_dir, file_name))
        with open(full_file_name, "w") as outfile:
            outfile.write(contents)
        return full_file_name

    def test_not_finding_vc(self):
        self.assertRaises(
            RuntimeError, ComplianceTest, self.vc_lib, "other_vc", "vc_pkg"
        )

    def test_not_finding_vci(self):
        self.assertRaises(
            RuntimeError, ComplianceTest, self.vc_lib, "vc", "other_vc_pkg"
        )

    def test_failing_on_multiple_entities(self):
        vc_contents = """
entity vc1 is
  generic(a : bit);
end entity;

entity vc2 is
  generic(b : bit);
end entity;
"""
        self.vc_lib.add_source_file(
            self.make_file(join(self.tmp_dir, "vc1_2.vhd"), vc_contents)
        )
        self.assertRaises(RuntimeError, ComplianceTest, self.vc_lib, "vc1", "vc_pkg")
        self.assertRaises(RuntimeError, ComplianceTest, self.vc_lib, "vc2", "vc_pkg")

    def test_failing_on_multiple_package(self):
        vci_contents = """
package vc_pkg1 is
end package;

package vc_pkg2 is
end package;
"""
        self.vc_lib.add_source_file(
            self.make_file(join(self.tmp_dir, "vci1_2.vhd"), vci_contents)
        )
        self.assertRaises(RuntimeError, ComplianceTest, self.vc_lib, "vc", "vc_pkg1")
        self.assertRaises(RuntimeError, ComplianceTest, self.vc_lib, "vc", "vc_pkg2")

    def test_evaluating_vc_generics(self):
        vc1_contents = """
entity vc1 is
end entity;
"""
        self.vc_lib.add_source_file(
            self.make_file(join(self.tmp_dir, "vc1.vhd"), vc1_contents)
        )
        self.assertRaises(RuntimeError, ComplianceTest, self.vc_lib, "vc1", "vc_pkg")

        vc2_contents = """
entity vc2 is
  generic(a : bit; b : bit);
end entity;
"""
        self.vc_lib.add_source_file(
            self.make_file(join(self.tmp_dir, "vc2.vhd"), vc2_contents)
        )
        self.assertRaises(RuntimeError, ComplianceTest, self.vc_lib, "vc2", "vc_pkg")

        vc3_contents = """
entity vc3 is
  generic(a, b : bit);
end entity;
"""
        self.vc_lib.add_source_file(
            self.make_file(join(self.tmp_dir, "vc3.vhd"), vc3_contents)
        )
        self.assertRaises(RuntimeError, ComplianceTest, self.vc_lib, "vc3", "vc_pkg")

    def test_failing_with_no_constructor(self):
        vci_contents = """\
package other_vc_pkg is
  impure function create_vc return vc_handle_t;
end package;
"""
        self.vc_lib.add_source_file(
            self.make_file(join(self.tmp_dir, "other_vci.vhd"), vci_contents)
        )
        self.assertRaises(
            RuntimeError, ComplianceTest, self.vc_lib, "vc", "other_vc_pkg"
        )

    def test_failing_with_wrong_constructor_return_type(self):
        vci_contents = """\
package other_vc_pkg is
  impure function new_vc return vc_t;
end package;
"""
        self.vc_lib.add_source_file(
            self.make_file(join(self.tmp_dir, "other_vci.vhd"), vci_contents)
        )
        self.assertRaises(
            RuntimeError, ComplianceTest, self.vc_lib, "vc", "other_vc_pkg"
        )

    def test_failing_on_incorrect_constructor_parameters(self):
        parameters = dict(
            logger=("logger_t", "default_logger"),
            actor=("actor_t", "default_actor"),
            checker=("checker_t", "default_checker"),
            fail_on_unexpected_msg_type=("boolean", "true"),
        )
        reasons_for_failure = [
            "missing_parameter",
            "invalid_type",
            "missing_default_value",
        ]

        for iteration, (invalid_parameter, invalid_reason) in enumerate(
            product(parameters, reasons_for_failure)
        ):
            vci_contents = (
                """\
package other_vc_%d_pkg is
  impure function new_vc(
"""
                % iteration
            )
            for parameter_name, parameter_data in parameters.items():
                if parameter_name != invalid_parameter:
                    vci_contents += "    %s : %s := %s;\n" % (
                        parameter_name,
                        parameter_data[0],
                        parameter_data[1],
                    )
                elif invalid_reason == "invalid_type":
                    vci_contents += "    %s : invalid_type := %s;\n" % (
                        parameter_name,
                        parameter_data[1],
                    )
                elif invalid_reason == "missing_default_value":
                    vci_contents += "    %s : %s;\n" % (
                        parameter_name,
                        parameter_data[0],
                    )

            vci_contents = (
                vci_contents[:-2]
                + """
  ) return vc_handle_t;
end package;
"""
            )
            self.vc_lib.add_source_file(
                self.make_file(
                    join(self.tmp_dir, "other_vci_%d.vhd" % iteration), vci_contents
                )
            )
            self.assertRaises(
                RuntimeError,
                ComplianceTest,
                self.vc_lib,
                "vc",
                "other_vc_%d_pkg" % iteration,
            )

    def test_create_vhdl_testbench_template_references(self):
        vc_contents = """\
library std;
library work;
library a_lib;

use std.a.all;
use work.b.c;
use a_lib.x.y;

context work.spam;
context a_lib.eggs;

entity vc2 is
  generic(vc_h : vc_handle_t);
end entity;
"""

        vc_path = self.make_file(join(self.tmp_dir, "vc2.vhd"), vc_contents)
        template, _ = ComplianceTest.create_vhdl_testbench_template(
            "vc_lib", vc_path, self.vci_path
        )
        template = VHDLDesignFile.parse(template)
        refs = template.references
        self.assertEqual(len(refs), 13)
        self.assertIn(VHDLReference("library", "vunit_lib"), refs)
        self.assertIn(VHDLReference("library", "vc_lib"), refs)
        self.assertIn(VHDLReference("library", "a_lib"), refs)
        self.assertIn(VHDLReference("package", "std", "a", "all"), refs)
        self.assertIn(VHDLReference("package", "vc_lib", "b", "c"), refs)
        self.assertIn(VHDLReference("package", "vc_lib", "vc_pkg", "all"), refs)
        self.assertIn(VHDLReference("package", "a_lib", "x", "y"), refs)
        self.assertIn(VHDLReference("package", "vunit_lib", "sync_pkg", "all"), refs)
        self.assertIn(VHDLReference("context", "vc_lib", "spam"), refs)
        self.assertIn(VHDLReference("context", "a_lib", "eggs"), refs)
        self.assertIn(VHDLReference("context", "vunit_lib", "vunit_context"), refs)
        self.assertIn(VHDLReference("context", "vunit_lib", "com_context"), refs)
        self.assertIn(VHDLReference("entity", "vc_lib", "vc2"), refs)

    def test_template_with_wrong_name(self):
        template_contents = """\
entity tb_vc2_compliance is
  generic(runner_cfg : string);
end entity;

architecture a of tb_vc2_compliance is
  constant vc_h : vc_handle_t := new_vc;
begin
  test_runner : process
  begin
    test_runner_setup(runner, runner_cfg);
    test_runner_cleanup(runner);
  end process test_runner;
end architecture;
"""

        template_path = self.make_file(
            join(self.tmp_dir, "template.vhd"), template_contents
        )

        compliance_test = ComplianceTest(self.vc_lib, "vc", "vc_pkg")
        self.assertRaises(
            RuntimeError, compliance_test.create_vhdl_testbench, template_path
        )

    def test_template_missing_contructor(self):
        template_contents = """\
entity tb_vc_compliance is
  generic(runner_cfg : string);
end entity;

architecture a of tb_vc_compliance is
begin
  test_runner : process
  begin
    test_runner_setup(runner, runner_cfg);
    test_runner_cleanup(runner);
  end process test_runner;
end architecture;
"""

        template_path = self.make_file(
            join(self.tmp_dir, "template.vhd"), template_contents
        )

        compliance_test = ComplianceTest(self.vc_lib, "vc", "vc_pkg")
        self.assertRaises(
            RuntimeError, compliance_test.create_vhdl_testbench, template_path
        )

    def test_template_missing_runner_cfg(self):
        template_contents = """\
entity tb_vc_compliance is
  generic(foo : bar);
end entity;

architecture a of tb_vc_compliance is
  constant vc_h : vc_handle_t := new_vc;
begin
  test_runner : process
  begin
    test_runner_setup(runner, runner_cfg);
    test_runner_cleanup(runner);
  end process test_runner;
end architecture;
"""

        template_path = self.make_file(
            join(self.tmp_dir, "template.vhd"), template_contents
        )

        compliance_test = ComplianceTest(self.vc_lib, "vc", "vc_pkg")
        self.assertRaises(
            RuntimeError, compliance_test.create_vhdl_testbench, template_path
        )

    def test_template_missing_test_runner(self):
        template_contents = """\
entity tb_vc_compliance is
  generic(runner_cfg : string);
end entity;

architecture a of tb_vc_compliance is
  constant vc_h : vc_handle_t := new_vc;
begin
  main : process
  begin
    test_runner_setup(runner, runner_cfg);
    test_runner_cleanup(runner);
  end process test_runner;
end architecture;
"""

        template_path = self.make_file(
            join(self.tmp_dir, "template.vhd"), template_contents
        )

        compliance_test = ComplianceTest(self.vc_lib, "vc", "vc_pkg")
        self.assertRaises(
            RuntimeError, compliance_test.create_vhdl_testbench, template_path
        )

    def test_creating_template_without_output_path(self):
        with mock.patch(
            "sys.argv", ["compliance_test.py", "create", self.vc_path, self.vci_path]
        ):
            main()

            self.assertTrue(
                exists(
                    join(dirname(self.vc_path), ".vc", "tb_vc_compliance_template.vhd")
                )
            )

    def test_creating_template_with_output_dir(self):
        output_dir = join(self.tmp_dir, "template")
        makedirs(output_dir)
        with mock.patch(
            "sys.argv",
            [
                "compliance_test.py",
                "create",
                "-o",
                output_dir,
                self.vc_path,
                self.vci_path,
            ],
        ):
            main()
            self.assertTrue(exists(join(output_dir, "tb_vc_compliance_template.vhd")))

    def test_creating_template_with_output_file(self):
        output_dir = join(self.tmp_dir, "template")
        makedirs(output_dir)
        output_path = join(output_dir, "template.vhd")
        with mock.patch(
            "sys.argv",
            [
                "compliance_test.py",
                "create",
                "--output-path",
                output_path,
                self.vc_path,
                self.vci_path,
            ],
        ):
            main()
            self.assertTrue(exists(output_path))

    def test_creating_template_with_invalid_output_path(self):
        output_dir = join(self.tmp_dir, "test")
        output_path = join(output_dir, "template.vhd")
        with mock.patch(
            "sys.argv",
            [
                "compliance_test.py",
                "create",
                "--output-path",
                output_path,
                self.vc_path,
                self.vci_path,
            ],
        ):
            self.assertRaises(IOError, main)

    def test_creating_template_with_default_vc_lib(self):
        with mock.patch(
            "sys.argv", ["compliance_test.py", "create", self.vc_path, self.vci_path]
        ):
            main()
            with open(
                join(dirname(self.vc_path), ".vc", "tb_vc_compliance_template.vhd")
            ) as fptr:
                self.assertIsNotNone(
                    re.search(
                        r"library\s+vc_lib\s*;",
                        fptr.read(),
                        re.IGNORECASE | re.MULTILINE,
                    )
                )

    def test_creating_template_with_specified_vc_lib(self):
        with mock.patch(
            "sys.argv",
            [
                "compliance_test.py",
                "create",
                "-l",
                "my_vc_lib",
                self.vc_path,
                self.vci_path,
            ],
        ):
            main()
            with open(
                join(dirname(self.vc_path), ".vc", "tb_vc_compliance_template.vhd")
            ) as fptr:
                self.assertIsNotNone(
                    re.search(
                        r"library\s+my_vc_lib\s*;",
                        fptr.read(),
                        re.IGNORECASE | re.MULTILINE,
                    )
                )

    def test_adding_vhdl_testbench(self):
        compliance_test = ComplianceTest(self.vc_lib, "vc", "vc_pkg")
        vc_test_lib = self.ui.add_library("vc_test_lib")
        compliance_test.add_vhdl_testbench(
            vc_test_lib, join(self.tmp_dir, "compliance_test")
        )

        self.assertTrue(
            exists(join(self.tmp_dir, "compliance_test", "tb_vc_compliance.vhd"))
        )
        self.assertRaises(
            RuntimeError,
            compliance_test.add_vhdl_testbench,
            vc_test_lib,
            join(self.tmp_dir, "compliance_test"),
        )