# -*- coding: utf-8 -*-
"""
@author: smerino
"""

import paho.mqtt.client as mqtt
import subprocess
import json
import os
import re

# Configure MQTT broker
broker = "your_broker"
port = 1884  
username = "your_username"
password = "your_password"

TOPIC_IN = "BT_Tester/input"

def remove_try_except(bt_code):
    # Remove the try/except block from create_behavior_tree 
    pattern = r"def create_behavior_tree\(.*?\):\s*try:\s*((?:\n\s+.+)+?)\n\s*except.*?:\s*((?:\n\s+.+)+?)"
    match = re.search(pattern, bt_code)
    if match:
        body = match.group(1)
        return f"def create_behavior_tree(mqtt):{body}\n"
    return bt_code  # If there is no try/except, returns the original

def on_message(client, userdata, msg):
    # Handles messages received on chatgpt/input
    message = json.loads(msg.payload.decode())  # Decode JSON
    correction = message.get("correction")
    user = message.get("user")
    bt_code = message.get("response")
    
    test_bt_code = remove_try_except(bt_code)
    # Executes the test_bt
    result = subprocess.run(
        ["pytest", "-s", "test_bt.py", f"--bt-code={test_bt_code}"],
        capture_output=True,
        text=True
    )
    
    print("STDOUT:\n", result.stdout)
    print("STDERR:\n", result.stderr)
    
    result_data = {}
    try:
        with open("result.json", "r", encoding="utf-8") as f:
            result_data = json.load(f)
            test_result = result_data["result"]
            test_error = result_data["error"]
            
        # Publishes in topic according to result
        if test_result == "PASSED":
            topic = "BT_Planner/input"
            payload = json.dumps({"correction":correction, "user": user, "response": bt_code})

        else:
            filename = "BT_Tester_fail.py"
            with open(filename, "w") as f:
                f.write(bt_code)
            
            topic = "Failure_Interpreter/input"
            payload = json.dumps({"filename": filename, "error": test_error, "user": user})
        
        client.publish(topic, payload)    
            
        print("\n Test result:", test_result)
        if test_error:
            print(" Error type:", test_error)
    except FileNotFoundError:
        print("result.json not found.")
    finally:
        if os.path.exists("result.json"):
            os.remove("result.json")

# Configure MQTT client
client = mqtt.Client()
client.username_pw_set(username, password)
client.on_message = on_message
client.connect(broker, port)

# Subscribe to input topic
client.subscribe(TOPIC_IN)
print("Waiting for messages on", TOPIC_IN)

client.loop_forever()