# -*- coding: utf-8 -*-
"""
@author: smerino
"""

def pytest_addoption(parser):
    parser.addoption("--bt-code", action="store", help="BT code as a string")
