# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2014-2019, Lars Asplund lars.anders.asplund@gmail.com

"""
SystemVerilog UART
------------------

A more realistic test bench of an UART to show VUnit SystemVerilog
usage on a typical module.
"""

from os.path import join, dirname
from vunit.verilog import VUnit

vu = VUnit.from_argv()

src_path = join(dirname(__file__), "src")

uart_lib = vu.add_library("uart_lib")
uart_lib.add_source_files(join(src_path, "*.sv"))

tb_uart_lib = vu.add_library("tb_uart_lib")
tb_uart_lib.add_source_files(join(src_path, "test", "*.sv"))

vu.main()
