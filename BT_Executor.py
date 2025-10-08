# -*- coding: utf-8 -*-
"""
@author: smerino
"""

import paho.mqtt.client as mqtt
import json
import subprocess
import platform
import os
import logging
from time import sleep

# A plan contains the priority, user and the name of the task
class Plan():
    def __init__(self, identifier, priority, user, task, correction):
        self.identifier = identifier     # This identifier allows us to maintain the order by priority and id
        self.priority = priority
        self.user = user    
        self.task = task
        self.correction = correction
        self.active = False

# The planner maintains a list of queued plans or actions and executes them.    
class Planner():
    def __init__(self):
        self.identifier = 0
        self.execution_queue = []
        self.process = None
        self.filename = None
        self.idle = True
        self.user = None
        self.correction = None
    
        # Configure MQTT broker
        broker = "your_broker"
        port = 1884  
        username = "your_username"
        password = "your_password"
        
        self.client = mqtt.Client()
        self.client.username_pw_set(username, password)
        self.client.on_message = self.on_message
        self.client.connect(broker, port)
        
        # Subscribe to input topic
        TOPIC_IN = "BT_Planner/output"
        self.client.subscribe(TOPIC_IN)
        print("Waiting for messages on", TOPIC_IN)
    
        self.client.loop_start()
        
        # Configures log file "log.txt"
        logging.basicConfig(filename='log.txt', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Handles messages received on chatgpt/input
    def on_message(self, client, userdata, msg):  
        message = json.loads(msg.payload.decode())  # Decodes JSON
        self.correction = message.get("correction")
        self.user = message.get("user")
        self.filename = message.get("task")
                
        # Creates a plan with the task info
        parts = self.filename.split("_")  
        priority, identifier = parts[1], parts[2]
        
        # Introduces the plan into the execution queue and sorts it based on priority and counter
        self.execution_queue.append(Plan(identifier, priority, self.user, self.filename, self.correction))
        self.execution_queue.sort(key = lambda x: (x.correction, x.priority, x.identifier))
        print(f"Plan queue: {self.execution_queue}")
       
        if self.correction == "True":
            self.idle = True

    # Executes the plans in the execution queue
    def run(self):
        while True:
            # print(f"Cola: {self.execution_queue}")
            if len(self.execution_queue) > 0:
                # If there is no active plan, the planner executes the first one as a subprocess
                actives = sum(p.active == True for p in self.execution_queue)
                if actives == 0 and self.idle:
                    try:
                       if platform.system() == 'Windows':
                           self.process = subprocess.Popen(['python', self.execution_queue[0].task], stdout=subprocess.PIPE, text=True)
                       elif platform.system() == 'Linux':
                           self.process = subprocess.Popen(['python3', self.execution_queue[0].task], stdout=subprocess.PIPE, text=True)                       
                       self.execution_queue[0].active = True
                       print("Plan iniciated")
                       self.idle = False
                    except Exception as e:
                       print(f"Error while initializing plan: {e}")
    
                # Looks for the active plan, in case a new one with a higher priority arrived during execution
                for idx, x in enumerate(self.execution_queue):
                    if x.active == True:
                        break
                
                # Read output line by line
                for line in self.process.stdout:
                    line = line.strip()
                    print(f"BT Status: {line}")  # Process status updates in real-time
                
                self.process.wait(timeout=60)
                
                if self.process.returncode == 0:
                    print("Behavior Tree completed successfully!")
                    self.process.terminate()
                    self.process.wait(5)
                    if self.process:
                        print("Ending subprocess...")
                        self.process.kill()
                    filename = self.execution_queue[idx].task
                    if os.path.exists(filename):
                        os.remove(filename)
                    topic = "plan/finished"
                    payload = json.dumps({"plan":"finished"})
                    self.client.publish(topic, payload)
                    self.execution_queue.pop(idx)
                    self.idle = True
                    self.process.returncode = None
                    
                elif self.process.returncode == 1:
                    print("Behavior Tree failed!")
                    self.process.terminate()
                    self.process.wait(5)                    
                    topic = "Failure_Interpreter/input"
                    payload = json.dumps({"filename": self.filename, "error":"-", "user":self.user})
                    self.client.publish(topic, payload)
                    self.execution_queue.pop(idx)
                    self.process.returncode = None
                else:
                    pass
            sleep(0.1)
                
if __name__ == '__main__':
    p = Planner()
    print("Planner iniciated")
    p.run()