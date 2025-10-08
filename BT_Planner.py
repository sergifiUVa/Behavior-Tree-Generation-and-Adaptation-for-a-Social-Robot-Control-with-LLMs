# -*- coding: utf-8 -*-
"""
@author: smerino
"""

import paho.mqtt.client as mqtt
import json

# Configure MQTT broker
broker = "your_broker"
port = 1884  
username = "your_username"
password = "your_password"

TOPIC_IN = "BT_Planner/input"
TOPIC_OUT = "BT_Planner/output"

identifier = 0

code1 = """import py_trees
from BT_classes import MoveToDestination, SpeakMessage, Reminder, Videoconference, AskQuestion, Condition, DetectFall, receiveTopics
from time import sleep
import logging
import os
import sys
from py_trees.blackboard import Client
from py_trees.common import Access

# Configure logging
logging.basicConfig(filename='log.txt', level=logging.INFO,
                   format='%(asctime)s - %(levelname)s - %(message)s')

filename = os.path.basename(__file__)

# Register Blackboard Client
blackboard = Client(name="BlackboardCliente")
blackboard.register_key(key="resultado_final", access=Access.WRITE)
"""

code3 = """
# Saves the failure
def guardar_fallo(clase, name, e, mqtt):
    if mqtt.resultado_BT:
        mqtt.resultado_BT = False
        blackboard.resultado_final = f"Error en {clase} update ({name}): {e}"

def main():
    try:
        # MQTT instance
        mqtt = receiveTopics()
        mqtt.connect()
        
        blackboard.resultado_final = "-"
        
        # Create the tree
        tree = create_behavior_tree(mqtt)
        
        # Execute the tree
        while True:
            tree.tick_once()
            if tree.status == py_trees.common.Status.SUCCESS or tree.status == py_trees.common.Status.FAILURE:
                break
            sleep(0.1)
    
    except Exception as e:
        logging.error(f\"{filename} - Error in main: {e}\")
        sys.exit(1)

if __name__ == \"__main__\":
    main()
"""

# Handles messages received on chatgpt/input
def on_message(client, userdata, msg):    
    global identifier
    message = json.loads(msg.payload.decode())  # Decode JSON
    correction = message.get("correction")
    user = message.get("user")
    code2 = message.get("response")
    
    # Task priority is given by the user who requested it
    if user == "emergency":
        priority = 3
    if user == "user":
        priority = 2
    else:
        priority = 1

    filename = f"task_{priority}_{identifier}.py"
    identifier += 1

    # Save the content to a file
    code = code1 + code2 + code3
    with open(filename, "w") as f:
        f.write(code)    
        
    # Publish the response to BT_Executor module
    response = json.dumps({"correction":correction, "user":user, "task": filename})
    client.publish(TOPIC_OUT, response)

# Configure MQTT client
client = mqtt.Client()
client.username_pw_set(username, password)
client.on_message = on_message
client.connect(broker, port)

# Subscribe to input topic
client.subscribe(TOPIC_IN)
print("Waiting for messages on", TOPIC_IN)

client.loop_forever()
