# -*- coding: utf-8 -*-
"""

@author: smerino

"""
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from time import sleep, time
from py_trees.behaviour import Behaviour
from py_trees.common import Status, Access
from py_trees.blackboard import Client
import json
import random
import logging
import paho.mqtt.client as mqtt
import smtplib
from email.message import EmailMessage

# Configure the log to send messages to a log.txt file
logging.basicConfig(filename='log.txt', level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s')


# ----------------------------- Utilities -----------------------------

# Function to read configuration data
def read_config(file):
    try:
        config = {}
        with open(file, 'r', encoding='utf-8') as f:
            current_section = None
            for line in f:
                line = line.strip()
                if line:
                    if ':' in line:
                        key, value = line.split(':', 1)
                        key = key.strip()
                        value = value.strip()
                        if current_section:
                            config[current_section][key] = value
                        else:
                            config[key] = value
                    else:
                        current_section = line
                        config[current_section] = {}
        return config
    except Exception as e:
        logging.error(f"Error reading config: {e}")


# Extract information from config file
file = 'config.txt'  
config = read_config(file)


# Register Blackboard client
blackboard = Client(name="BlackboardClient")
blackboard.register_key(key="final_result", access=Access.WRITE)

filename = os.path.basename(__file__)

# Class that connects to the MQTT broker and receives robot messages
class receiveTopics():
    def __init__(self):
        # Variables
        global config
        self.topic_header = "robot/Temi_UVA"
        self.robot_status = ""
        self.robot_command = ""
        self.room_mqtt = ""
        self.location_mqtt = ""
        self.status_description_id = ""
        self.interaction_positioning = False
        self.previous_status = ""
        self.response = ""   # User’s response        
        self.menu = ""       # Current screen menu
        self.responseGPT = ""
        self.speaking = ""   # When robot finishes speaking
        self.answer = ""
        self.usage_timer = 0 # Reset to time() when user interacts
        self.end_call = False
        self.camera_error = False
        self.BT_result = True
        self.result_description = None
        self.person_state = None
            
    def connect(self):
        try:
            # Configure MQTT broker
            broker = "your_broker"
            port = 1884  
            username = "your_username"
            password = "your_password"
            
            self.mqtt_client = mqtt.Client()
            self.mqtt_client.username_pw_set(username, password)
            self.mqtt_client.connect(broker, port)
            
            # Define necessary topics
            self.topic1 = self.topic_header + "/output/info/movement/status"    
            self.topic2 = self.topic_header + "/output/info/movement/position"  
            self.topic3 = self.topic_header + "/output/info/button"             
            self.topic4 = self.topic_header + "/output/info/media/speak"
            self.topic5 = self.topic_header + "/output/info/answer"  
            self.topic6 = self.topic_header + "/output/info/interaction"  
            self.topic7 = self.topic_header + "/output/info/media/videoconf"  
            self.topic8 = self.topic_header + "/output/info/menu"  
            self.topic10 = self.topic_header + "/output/info/person_found_state"  
            self.topicGeneral = self.topic_header + "/output/info/#"
            self.mqtt_client.message_callback_add(self.topicGeneral, self.process_message)
            self.mqtt_client.subscribe(self.topicGeneral)
            self.mqtt_client.loop_start()
        except Exception as e:
            logging.error(f"{filename} - Error connecting to MQTT: {e}")
            
    # Subscribe to a topic without creating a new client
    def subscribe_mqtt(self, topic):
        self.mqtt_client.subscribe(topic)     
        
    # Publish MQTT messages from nodes without creating a new client       
    def publish_mqtt (self, topic, message):
        self.mqtt_client.publish(topic, message, 1)
    
    # Disconnect from MQTT client 
    def disconnect(self):
        try:
            self.mqtt_client.client.loop_stop()
            self.mqtt_client.client.disconnect()
        except Exception as e:
            logging.error(f"{filename} - Error disconnecting from BT: {e}") 
                        
    # Handle robot MQTT messages 
    def process_message(self, client, userdata, message):
        topic = message.topic
        if topic == self.topic_header + "/output/info/imagen":
            payload = message.payload
        else:
            payload = message.payload.decode("utf-8")
        
        # Movement status
        if topic == self.topic1:
            data = json.loads(payload)            
            if "status" and "command" and "descriptionId" in data:
                self.robot_status = str(data["status"])
                if self.robot_status == "abort" and self.previous_status == "reposing":
                    self.interaction_positioning = True
                self.previous_status = self.robot_status
                self.robot_command = str(data["command"])
                self.status_description_id = str(data["descriptionId"])
                
        # Robot position                   
        if topic == self.topic2:
            data = json.loads(payload)
            if "location" in data:
                self.location_mqtt = data["location"]
            if "room" in data:
                self.room_mqtt = data["room"]
               
        # Pause button response           
        if topic == self.topic3:
            data = json.loads(payload)
            if "status" in data:
                self.response = str(data["status"])

        # Robot speaking        
        if topic == self.topic4:
            data = json.loads(payload)
            if "status" in data:
                self.speaking = str(data["status"])
                
        # User’s answer
        if topic == self.topic5:
            data = json.loads(payload)
            if "texto" in data:
                self.response = str(data["text"].strip("[]"))

        # User interaction with robot        
        if topic == self.topic6:
            self.usage_timer = time()
        
        # End video call
        if topic == self.topic7:
            data = json.loads(payload)
            if "status" in data:
                if str(data["status"]) == "ended":
                    self.end_call = True  
        
        # Robot menu
        if topic == self.topic8:
            data = json.loads(payload)
            if "menu" in data:
                self.menu = str(data["menu"])
         
        # Fall detection result
        if topic == self.topic10:  
            if not self.fall_result_received:
                data = json.loads(payload)
                if "fallen" and "not_fallen" in data:
                    
                    if int(data["fallen"]) > 0:
                        self.person_state = "fallen"
                        self.fall_result_received = True
                    elif int(data["not_fallen"]) > 0:
                        self.person_state = "not_fallen"
                        self.fall_result_received = True
                    else:
                        self.person_state = "nobody"   # cambiar
                        self.fall_result_received = True 


# Function to store if an error occurs
def store_failure(cls, name, e, mqtt):
    if mqtt.BT_result:
        mqtt.BT_result = False
        blackboard.final_result = f"{filename} - Error in {cls} update ({name}): {e}"
        
 
    
# ----------------------------- BT Nodes -----------------------------
        
# Node that sends the robot to the destination
class MoveToDestination(Behaviour):
    def __init__(self, name, destination, mqtt):
        try:
            super(MoveToDestination, self).__init__(name)
            global config
            self.destination = destination
            self.mqtt = mqtt
            self.topic_header = self.mqtt.topic_header
            self.timer = 0
            self.obstacle_timer = 0
            self.pause_timer = 0
            self.robot_moving = False
            self.max_move_time = int(config['Waits_and_Times']['Time_to_reach_destination'])
            self.max_pause_time = int(config['Waits_and_Times']['Max_pause_time'])
            self.speed = config['Repetitions_and_Others']['Movement_speed']
        except Exception as e:
            logging.error(f"{filename} - Error in MoveToDestination init: {e}")

    def update(self):
        try:
            # Send MQTT order to move the robot to the destination
            if not self.robot_moving:
                if self.destination is None:
                    logging.error("Robot destination is None")
                    return Status.FAILURE
                msg_dest = {'location': self.destination, 'speedLevel': self.speed}
                msg_dest = json.dumps(msg_dest)
                topic = self.topic_header + "/input/movement/move_dest"
                self.mqtt.publish_mqtt(topic, msg_dest)
                self.timer = time()
                self.obstacle_timer = time()
                self.robot_moving = True

            # If user interacts while positioning, restart movement
            if self.mqtt.interaction_positioning:
                self.robot_moving = False
                self.timer = time()
                self.obstacle_timer = time()
                self.mqtt.interaction_positioning = False
                logging.info("Interaction during robot positioning. Restarting movement")

            # If it arrives, return SUCCESS
            if self.mqtt.robot_status == "complete":
                self.mqtt.robot_status = None
                return Status.SUCCESS

            # If it cannot arrive, FAILURE
            elif time() - self.timer > self.max_move_time or time() - self.obstacle_timer > 10 or self.mqtt.status_description_id == "1003":
                self.mqtt.robot_status = None
                return Status.FAILURE

            # If user interacts, enter pause state with options (yes/no/finish)
            elif self.mqtt.status_description_id == "1005":
                msg = {"pause": "true"}
                msg = json.dumps(msg)
                topic = self.topic_header + "/input/system/click_button"
                self.mqtt.publish_mqtt(topic, msg)
                self.pause_timer = time()
                # Manage possible responses
                while time() - self.pause_timer < self.max_pause_time:
                    if self.mqtt.response == "yes" or self.mqtt.response == "yeah":
                        self.mqtt.response = ""
                        return Status.SUCCESS
                    elif self.mqtt.response == "no":
                        self.robot_moving = False
                        self.mqtt.status_description_id = "0"
                        self.mqtt.response = ""
                        return Status.RUNNING
                    elif self.mqtt.response == "end" or time() - self.pause_timer > self.max_pause_time:
                        self.mqtt.response = ""
                        return Status.FAILURE
            # If no obstacle detected, reset obstacle timer
            else:
                if self.mqtt.robot_status == "obstacle detected":
                    pass
                else:
                    self.obstacle_timer = time()
                return Status.RUNNING
        except Exception as e:
            logging.error(f"{filename} - Error in MoveToDestination update: {e}")
            store_failure(self.__class__.__name__, self.name, e, self.mqtt)
            return Status.FAILURE


# Node that plays a message
class SpeakMessage(Behaviour):
    def __init__(self, name, message, mqtt):
        try:
            super(SpeakMessage, self).__init__(name)
            global config
            self.message = message
            self.speak_ended = False
            self.mqtt = mqtt
            self.topic_header = self.mqtt.topic_header
            self.speak_timer = 0
            self.volume = 5
            self.max_speak_time = int(config['Waits_and_Times']['Max_speak_time'])
        except Exception as e:
            logging.error(f"{filename} - Error in SpeakMessage init: {e}")

    def update(self):
        try:
            # Send MQTT to make the robot speak
            if not self.speak_ended:
                msg_say = {'speech': self.message, 'volume': self.volume, 'animation': 'false'}
                msg_say = json.dumps(msg_say)
                topic = self.topic_header + "/input/media/speak"
                self.mqtt.publish_mqtt(topic, msg_say)
                self.mqtt.speaking = "1"
                self.speak_timer = time()
                self.speak_ended = True

            # If confirmed that speaking finished, SUCCESS
            if self.mqtt.speaking == "0":
                self.speak_ended = False
                return Status.SUCCESS
            # If no confirmation within time, FAILURE
            elif time() - self.speak_timer > self.max_speak_time:
                self.speak_ended = False
                return Status.FAILURE
            return Status.RUNNING
        except Exception as e:
            logging.error(f"{filename} - Error in SpeakMessage update: {e}")
            store_failure(self.__class__.__name__, self.name, e, self.mqtt)
            self.speak_ended = False
            return Status.FAILURE

# Node to check whether a condition holds
class Condition(Behaviour):
    def __init__(self, name, variable, value, mqtt):
        try:
            super(Condition, self).__init__(name)
            self.mqtt = mqtt
            self.variable = str(variable)
            self.variable_name = self.variable
            self.expected = value
        except Exception as e:
            logging.error(f"{filename} - Error in Condition init: {e}")

    def update(self):
        try:
            sleep(1)
            current_value = getattr(self.mqtt, self.variable)
            if current_value == self.expected:
                return Status.SUCCESS
            else:
                return Status.FAILURE
        except Exception as e:
            logging.error(f"{filename} - Error in Condition {self.name} update: {e}")
            store_failure(self.__class__.__name__, self.name, e, self.mqtt)
            return Status.FAILURE

 
# Node that plays a final reminder and checks the BT result
class Reminder(Behaviour):
    def __init__(self, name, mqtt):
        try:
            super(Reminder, self).__init__(name)
            global config
            self.speak_ended = False
            self.mqtt = mqtt
            self.topic_header = self.mqtt.topic_header
            self.speak_timer = 0
            self.reminder_text = ""
            self.volume = 5
            self.max_speak_time = int(config['Waits_and_Times']['Max_speak_time'])
        except Exception as e:
            logging.error(f"{filename} - Error in Reminder init: {e}")

    # Load a random reminder sentence
    def load_reminder(self, file_path):
        reminders = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reminders = f.readlines()
                phrase = random.choice(reminders).strip()
                return phrase
        except Exception as e:
            logging.error(f"{filename} - Error in load_reminder: {e}")

    def update(self):
        try:
            # Send the reminder message
            if not self.speak_ended:
                file_path = config['Files']['Reminders_file']
                self.reminder_text = self.load_reminder(file_path)
                msg_say = {'speech': self.reminder_text, 'volume': self.volume, 'animation': 'false'}
                msg_say = json.dumps(msg_say)
                topic = self.topic_header + "/input/media/speak"
                self.mqtt.publish_mqtt(topic, msg_say)  
                self.speak_timer = time()
                self.mqtt.speaking = "3"
                self.speak_ended = True

            if self.mqtt.BT_result:
                return Status.SUCCESS
            else:
                return Status.FAILURE
        except Exception as e:
            logging.error(f"{filename} - Error in Reminder update: {e}")
            store_failure(self.__class__.__name__, self.name, e, self.mqtt)
            return Status.FAILURE
        

# Node to ask a question
class AskQuestion(Behaviour):
    def __init__(self, name, question, mqtt):
        try:
            super(AskQuestion, self).__init__(name)
            global config
            self.mqtt = mqtt
            self.topic_header = self.mqtt.topic_header
            self.message = question
            self.answer_timer = 0
            self.volume = 5
            self.wait_answer_secs = int(config['Waits_and_Times']['Answer_wait'])
        except Exception as e:
            logging.error(f"{filename} - Error in AskQuestion init: {e}")

    def initialise(self):
        try:
            # Ask the question
            self.mqtt.answer == None
            msg = {'speech': self.message, 'volume': self.volume, 'animation': 'false'}
            msg = json.dumps(msg)
            topic = self.topic_header + "/input/media/speak_listen"
            self.mqtt.publish_mqtt(topic, msg)
            self.answer_timer = time()
        except Exception as e:
            logging.error(f"{filename} - Error in AskQuestion initialise: {e}")

    def update(self):
        try:
            # Wait for the answer
            if time() - self.answer_timer < self.wait_answer_secs:
                if self.mqtt.response:
                    self.mqtt.answer = self.mqtt.response
                    self.mqtt.response = ""
                    return Status.SUCCESS
                else:
                    self.mqtt.response = ""
                    return Status.RUNNING
            else:
                self.mqtt.answer = "no answer"
                self.mqtt.response = ""
                return Status.SUCCESS
        except Exception as e:
            logging.error(f"{filename} - Error in AskQuestion update: {e}")
            store_failure(self.__class__.__name__, self.name, e, self.mqtt)
            return Status.FAILURE
        
        
# Node to perform a video call
class Videoconference(Behaviour):
    def __init__(self, name, contact, mqtt):
        try:
            super(Videoconference, self).__init__(name)
            global config
            self.mqtt = mqtt
            self.topic_header = self.mqtt.topic_header
            self.contact = contact
            self.max_call_time = int(config['Waits_and_Times']['Max_call_time'])
            self.call_timer = 0
        except Exception as e:
            logging.error(f"{filename} - Error in Videoconference init: {e}")

    def initialise(self):
        try:
            # Start the call
            if self.contact == "emergency":
                self.contact = config['Contacts']['Emergency_contact']
            msg_call = {"user": self.contact}
            msg_call = json.dumps(msg_call)
            topic = self.topic_header + "/input/videoconf/start"
            self.mqtt.publish_mqtt(topic, msg_call)
            self.call_timer = time()
            self.mqtt.end_call = False
            self.mqtt.menu == ""
        except Exception as e:
            logging.error(f"{filename} - Error in Videoconference initialise: {e}")

    def update(self):
        try:
            # If it exceeds max time or call ends, stop it
            if self.mqtt.end_call or time() - self.call_timer >= self.max_call_time:
                msg_call = {'user': "Sergio"}
                msg_call = json.dumps(msg_call)
                topic = self.topic_header + "/input/videoconf/stop"
                self.mqtt.publish_mqtt(topic, msg_call)
                return Status.SUCCESS
            return Status.RUNNING
        except Exception as e:
            logging.error(f"{filename} - Error in Videoconference update: {e}")
            store_failure(self.__class__.__name__, self.name, e, self.mqtt)
            return Status.FAILURE
        
        
# Node to send an alert
class Alert(Behaviour):
    def __init__(self, name, message, contact, mqtt):
        try:
            super(Alert, self).__init__(name)
            global config
            self.mqtt = mqtt
            self.topic_header = self.mqtt.topic_header
            self.message = message
            self.contact = contact
            
            # Email information
            self.SMTP_HOST = "smtp.gmail.com"   
            self.SMTP_PORT = 587                
            self.USER = "your_email@gmail.com"      
            self.PASSWORD = "your_password"   
        except Exception as e:
            logging.error(f"{filename} - Error in Alert init: {e}")

    def update(self):
        try:
            if self.contact == "emergency":
                self.contact = config['Contacts']['Emergency_contact']
                
            # Selects the destinatary email based on the contact (you can add yours)
            # Example:
            if self.contact == "Sergio":
                email = "sergiomerfi@gmail.com"
            
            # Send the email
            msg = EmailMessage()
            msg["Subject"] = "Alert"
            msg["From"] = self.USER
            msg["To"] = email
            msg.set_content(self.message)
            
            with smtplib.SMTP(self.SMTP_HOST, self.SMTP_PORT) as s:
                s.starttls()
                s.login(self.USER, self.PASSWORD)
                s.send_message(msg)
            return Status.SUCCESS
        except Exception as e:
            logging.error(f"{filename} - Error in Alert update: {e}")
            store_failure(self.__class__.__name__, self.name, e, self.mqtt)
            return Status.FAILURE


# Node to detect falls
class DetectFall(Behaviour):
    def __init__(self, name, mqtt):
        try:
            super(DetectFall, self).__init__(name)
            global config
            self.mqtt = mqtt
            self.topic_header = self.mqtt.topic_header
            self.timer = 0
            self.photo_angle = int(config['Repetitions_and_Others']['Angle_when_taking_picture'])
        except Exception as e:
            logging.error(f"{filename} - Error in DetectFall init: {e}")

    def initialise(self):
        try:
            # Open the camera and take a photo (start stream request)
            topic_open_cam = self.topic_header + "/input/video/image"
            payload = {"frequency": 0, "angle": self.photo_angle, "resolutionX": 600, "resolutionY": 600}
            payload = json.dumps(payload)
            self.mqtt.publish_mqtt(topic_open_cam, payload)
            self.timer = time()
            self.mqtt.fall_result_received = False
            self.mqtt.person_state = "nobody"
        except Exception as e:
            logging.error(f"{filename} - Error in DetectFall initialise: {e}")

    def update(self):
        try:
            # If a person is detected, close camera and end detection
            if time() - self.timer < 20 and not self.mqtt.fall_result_received:
                if self.mqtt.person_state != "nobody":
                    topic_stop_cam = self.topic_header + "/input/video/image_stop"
                    payload = {"frequency": 0, "angle": self.photo_angle, "resolutionX": 600, "resolutionY": 600}
                    payload = json.dumps(payload)
                    self.mqtt.publish_mqtt(topic_stop_cam, payload)
                    return Status.SUCCESS
                else:
                    return Status.RUNNING
            else:
                topic_stop_cam = self.topic_header + "/input/video/image_stop"
                payload = {"frequency": 0, "angle": self.photo_angle, "resolutionX": 600, "resolutionY": 600}
                payload = json.dumps(payload)
                self.mqtt.publish_mqtt(topic_stop_cam, payload)
                self.mqtt.fall_result_received = False
                self.timer = 0
                return Status.SUCCESS
        except Exception as e:
            logging.error(f"{filename} - Error in DetectFall update: {e}")
            store_failure(self.__class__.__name__, self.name, e, self.mqtt)
            return Status.FAILURE