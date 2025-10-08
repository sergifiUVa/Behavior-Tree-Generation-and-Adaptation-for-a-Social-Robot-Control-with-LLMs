# -*- coding: utf-8 -*-
"""
@author: smerino
"""

import pytest
import py_trees
import itertools
import logging
import json
from collections import Counter
import re

# Status aliases for readability
SUCCESS = py_trees.common.Status.SUCCESS
FAILURE = py_trees.common.Status.FAILURE

# Global log of nodes that were ticked during execution
tick_log = []

# -------------------------------------------------------
# DummyNode
# -------------------------------------------------------
# A simple replacement node that mimics a BT behaviour.
# Instead of real logic, it returns results from a
# predefined results_vector (SUCCESS/FAILURE).
# This allows exhaustive testing without executing
# real robot actions.
class DummyNode(py_trees.behaviour.Behaviour):
    def __init__(self, name, index, results_vector):
        super().__init__(name)
        self.index = index
        self.results_vector = results_vector

    def update(self):
        tick_log.append(self.name)  # keep track of execution order
        return self.results_vector[self.index]


# -------------------------------------------------------
# remove_try_except
# -------------------------------------------------------
# Some BTs wrap create_behavior_tree() in try/except blocks.
# For analysis, we strip them away so that we can execute
# the function directly without swallowing errors.
def remove_try_except(bt_code):
    pattern = r"def create_behavior_tree\(.*?\):\s*try:\s*((?:\n\s+.+)+?)\n\s*except.*?:\s*((?:\n\s+.+)+?)"
    match = re.search(pattern, bt_code)
    if match:
        body = match.group(1)
        return f"def create_behavior_tree(mqtt):{body}\n"
    return bt_code


# -------------------------------------------------------
# extract_action_nodes
# -------------------------------------------------------
# Collects the names of all action nodes defined in the BT.
# It replaces each action constructor (MoveToDestination,
# SpeakMessage, etc.) with a dummy factory that only
# records the node name.
def extract_action_nodes(bt_code_str):
    defined_nodes = []

    # Minimal fake node implementation
    class FakeNode:
        def __init__(self, name):
            self.name = name
            self.children = []

        def add_children(self, children):
            self.children.extend(children)

    def create_dummy(name, **kwargs):
        print(f"[extract_action_nodes] Node detected: {name}")
        defined_nodes.append(name)
        return FakeNode(name)

    # Override environment so that BT code uses dummy constructors
    exec_env = {
        "py_trees": py_trees,
        "MoveToDestination": create_dummy,
        "SpeakMessage": create_dummy,
        "Reminder": create_dummy,
        "AskQuestion": create_dummy,
        "Condition": create_dummy,
        "Videoconference": create_dummy,
        "Alert": create_dummy,
        "DetectFall": create_dummy,
        "mqtt": None,
        "logging": logging
    }

    try:
        bt_code_str_clean = remove_try_except(bt_code_str)
        print("Without try-except:", bt_code_str_clean)
        exec(bt_code_str_clean, exec_env)
        exec_env['create_behavior_tree'](mqtt=None)
    except Exception:
        # If evaluation fails, that's okay – we only care about collecting node names
        pass

    return defined_nodes


# -------------------------------------------------------
# build_executable_bt
# -------------------------------------------------------
# Builds a real, runnable BehaviourTree, but with DummyNodes
# instead of real action nodes. Each node is assigned a
# SUCCESS/FAILURE outcome according to result_vector.
def build_executable_bt(bt_code_str, result_vector):
    index = [-1]  # mutable index so it increments across calls

    def dummy_factory(name, **kwargs):
        index[0] += 1
        return DummyNode(name, index[0], result_vector)

    exec_env = {
        "py_trees": py_trees,
        "MoveToDestination": dummy_factory,
        "SpeakMessage": dummy_factory,
        "Reminder": dummy_factory,
        "AskQuestion": dummy_factory,
        "Condition": dummy_factory,
        "Videoconference": dummy_factory,
        "Alert": dummy_factory,
        "DetectFall": dummy_factory,
        "mqtt": None,
        "logging": logging
    }

    exec(bt_code_str, exec_env)
    return exec_env['create_behavior_tree'](mqtt=None)


# -------------------------------------------------------
# Pytest fixture to pass BT code via command line
# -------------------------------------------------------
@pytest.fixture
def bt_code(request):
    return request.config.getoption("--bt-code")


# -------------------------------------------------------
# test_exhaustive_bt
# -------------------------------------------------------
# This is the core test.
# 1. Extract all action node names.
# 2. Build a dummy BT where each node is replaced with DummyNode.
# 3. Generate *all combinations* of SUCCESS/FAILURE outcomes.
# 4. Tick the tree for each combination, recording executed nodes.
# 5. Validate:
#    - No duplicate node names
#    - All nodes were ticked in at least one run
#    - If all good, test passes
def test_exhaustive_bt(bt_code):
    global tick_log
    passed = False
    try:
        defined_node_names = extract_action_nodes(bt_code)
        print(f"TOTAL nodes detected: {len(defined_node_names)}")
        print(f"NODES: {defined_node_names}")
        n = len(defined_node_names)

        # Generate every possible combination of SUCCESS/FAILURE for n nodes
        all_combinations = list(itertools.product([SUCCESS, FAILURE], repeat=n))
        ticked_total = set()

        for combo in all_combinations:
            tick_log = []
            tree = build_executable_bt(bt_code, combo)
            bt_runner = py_trees.trees.BehaviourTree(root=tree)
            bt_runner.setup()
        
            MAX_TICKS = 20  # safety limit to avoid infinite loops
            for _ in range(MAX_TICKS):
                status = bt_runner.tick()
                if status != py_trees.common.Status.RUNNING:
                    break
        
            ticked_total.update(tick_log)

        # --- VALIDATION ---

        # Detect duplicated node names
        node_counts = Counter(defined_node_names)
        duplicated_nodes = [name for name, count in node_counts.items() if count > 1]

        # Detect nodes that were never ticked
        missing_nodes = list(set(defined_node_names) - ticked_total)
        
        if duplicated_nodes:
            result_data = {
                "result": "FAILED",
                "error": f"Duplicated node names: {sorted(duplicated_nodes)}"
            }
            passed = False
        elif missing_nodes:
            result_data = {
                "result": "FAILED",
                "error": f"Some nodes were never ticked in any test run: {sorted(missing_nodes)}"
            }
            passed = False
        else:
            result_data = {
                "result": "PASSED",
                "error": ""
            }
            passed = True

    except Exception as e:
        result_data = {
            "result": "FAILED",
            "error": f"Error in code: {e}"
        }

    # Write result summary to JSON file
    with open("result.json", "w", encoding="utf-8") as f:
        json.dump(result_data, f, indent=2)

    # Force pytest to fail if not passed
    assert passed, result_data["error"]
