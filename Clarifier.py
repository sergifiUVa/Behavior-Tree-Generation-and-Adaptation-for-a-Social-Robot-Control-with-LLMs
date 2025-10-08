# -*- coding: utf-8 -*-
"""
@author: smerino
"""

import paho.mqtt.client as mqtt
import json
import re

# Configure MQTT broker
broker = "your_broker"
port = 1884  
username = "your_username"
password = "your_password"

TOPIC_IN = "chatgpt/output"

def on_message(client, userdata, msg):
    # Handles messages received on chatgpt/input
    message = json.loads(msg.payload.decode())  # Decode JSON
    correction = message.get("correction")
    user = message.get("user")
    text = message.get("response")
    
    # Tries to extract the code
    match_python = re.search(r"python\n(.*?)```", text, re.DOTALL)
    match_def = re.search(r'\bdef\b', text)
    
    # If ChatGPT generates a BT, it is sent to the BT Planner
    if match_python:   
        topic = "BT_Tester/input"
        text = match_python.group(1) 
        print("Code:\n",text)
        # Publish the response to BT_Planner module
        payload = json.dumps({"correction":correction, "user": user, "response": text})
        
    elif match_def:   
        topic = "BT_Tester/input" 
        print("Code:\n",text)
        # Publish the response to BT_Planner module
        payload = json.dumps({"correction":correction, "user": user, "response": text})
    
    # Otherwise, the robots asks the user for clarification
    else:
        topic = "robot/Temi_UVA/input/media/speak_listen"
        print("Clarification:", text)
        payload = json.dumps({'speech':text,'volume':5,'animation':'false'})
    
    
    client.publish(topic, payload)

# Configure MQTT client
client = mqtt.Client()
client.username_pw_set(username, password)
client.on_message = on_message
client.connect(broker, port)

# Subscribe to input topic
client.subscribe(TOPIC_IN)
print("Waiting for messages on", TOPIC_IN)

client.loop_forever()
