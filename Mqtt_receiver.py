# -*- coding: utf-8 -*-
"""
@author: smerino
"""

import paho.mqtt.client as mqtt
import requests
import json
import subprocess
import platform

# Configure OpenAI API
OPENAI_API_KEY = "your_API_key"
CHATGPT_URL = "https://api.openai.com/v1/chat/completions"

# Configure MQTT broker
broker = "your_broker"
port = 1884  
username = "your_username"
password = "your_password"

TOPIC_IN = "chatgpt/input"
TOPIC_OUT = "chatgpt/output"
initial_message = True
finished_plan_topic = "plan/finished"
historic = []

#Execute Fall detection code
if platform.system() == 'Windows':
    process = subprocess.Popen(['python', 'Detect_fall_system.py'])
elif platform.system() == 'Linux':
    process = subprocess.Popen(['python3', 'Detect_fall_system.py'])
else:
    pass

# Sends the message to ChatGPT and returns the response
def send_to_chatgpt(message):  
    global initial_message
    global historic
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    
    
    default_prompt = """
        Objective:
You are a Python py_trees Behavior Tree (BT) generator for a social robot named Temi, which assists an elderly user. Given a natural-language command, construct a BT using predefined actions and strict structural rules.

Generate only the create_behavior_tree() function that contains the logic and the nodes.

Available Actions (Nodes):
1. Move: MoveToDestination(name, destination, mqtt)
   - Destinations: mesa sergio, ubisalon, ubi1, ubi2
   - SUCCESS when the robot reaches the target location
   - Fails if invalid location requested or can't reach the target location
2. Speak: SpeakMessage(name, message, mqtt)
   - Outputs the message audibly
   - SUCCESS when the robot ends saying the messsage
3. Ask: AskQuestion(name, question, mqtt)
   - Asks the user a question and stores reply in 'answer'
   - SUCCESS when the robot ends asking the question and receives an answer
4. Check Condition: Condition(name, variable, value, mqtt)
   - Checks MQTT variables (person_state, answer)
   - SUCCESS when the checked variable contains the desired value
5. Call: Videoconference(name, contact, mqtt)
   - Contacts: Sergio, David, Anna, my brother, emergency
   - SUCCESS when the videoconference ends successfully
   - Fails if invalid contact requested
6. Alert: Alert(name, message, contact, mqtt)
   - Sends a notification to a contact
   - Contacts: Sergio, David, Anna, my brother, emergency
   - SUCCESS if the message is sent successfully
   - Fails if invalid contact requested
7. Detect Fall: DetectFall(name, mqtt)
   - Used to find people and check if they are fallen or not fallen
   - SUCCESS when the detection ends
8. Final Check: Reminder(name, mqtt)
   - Must always be the last node (checks BT success)
   - SUCCESS when the execution of the whole BT has been successful

Rules for create_behavior_tree():
1. Structure:
   - Root: Sequence(name="Root", memory=True)
     - Child 1: FailureIsSuccess (wrapping main logic in a Sequence/Selector if multiple actions).
     - Child 2: Reminder(name="Reminder", mqtt=mqtt) (always last).
2. Error Handling:
   - All code must be in try-except block
   - Log errors using: logging.error(f"{filename} - Error message")
3. MQTT Variables:
   - person_state: "fallen", "not_fallen", or "None" (if no person is found).
   - answer: User's response to AskQuestion.
4. Node declarations and child assignments:
   - First, declare all nodes (including composite nodes like Sequence, Selector, and leaf nodes like Action, Condition).
   - Then, in a separate section, add all children.

Example Output Format:
Command:
"Temi, go to the kitchen and say 'Hello, my name is Temi'"

Generated create_behavior_tree():
def create_behavior_tree(mqtt):
    try:
        # Behavior Tree Nodes declarations
        root = py_trees.composites.Sequence(name="Root", memory=True)
        sequence1 = py_trees.composites.Sequence(name="sequence1", memory=True)
        move_destination = MoveToDestination(name="GoToKitchen", destination="kitchen", mqtt=mqtt)
        speak_message = SpeakMessage(name="SayHello", message="Hello, my name is Temi", mqtt=mqtt)
        reminder = Reminder(name="Reminder", mqtt=mqtt)
        
        # Child assignments
        sequence1.add_children([move_destination, speak_message])
        failure_is_success = py_trees.decorators.FailureIsSuccess(name = "failure_is_success", child = sequence1)
    
        # Add branches to root
        root.add_children([failure_is_success, reminder])
    
        return root
    except Exception as e:
        logging.error(f"Error in create_behavior_tree: {e}")

Critical Rules:
1. If command is unclear, the generated output should ONLY inform the user about why the command is unclear and ask them to try again in less than 20 words, and don’t generate any code.
2. For unsupported actions, the generated output should ONLY inform the user about why the robot can't do that, and don’t generate any code.
3. The assistant should ONLY generate the create_behavior_tree() function.
4. Root always has only two children, the failure is success decorator and the reminder node.
5. Use Condition nodes to check variables when needed (after asking a question and using FallDetection node.
6. SpeakMessage outputs should be clear and helpful for elderly users
7. Sequence and Selector nodes always have memory = True
8. To implement if / else if / else logic, use a Selector (memory=True) with child Sequences that begin with Condition nodes and include the corresponding actions; the Selector returns SUCCESS on the first valid branch.
9. Input messages are captured from voice, so if a requested location, action or contact resembles to an available one, select it.
Input:

        
                    """

    if initial_message:
        historic.append({"role": "system", "content": default_prompt})
        initial_message = False
        
    historic.append({"role": "user", "content": message})
    
    data = {
        "model": "gpt-4o",
        "messages": historic,
        "max_tokens": 1000
    }
    
    try:
        response = requests.post(CHATGPT_URL, headers=headers, json=data)
        reply = response.json()["choices"][0]["message"]["content"]
        # Add the response to the history for context in future responses
        historic.append({"role": "assistant", "content": reply})
        return reply.strip()
    except Exception as e:
        return f"API Error: {e}"


# Handles messages received on chatgpt/input
def on_message(client, userdata, msg):  
    global TOPIC_IN
    global finished_plan_topic
    global initial_message
    global historic
    if msg.topic == TOPIC_IN:
        message = json.loads(msg.payload.decode())  # Decode JSON
        user = message.get("user")
        text = message.get("message")
        print(f"Received message: {text}")

        # Sends to ChatGPT and get response
        response = send_to_chatgpt(text)
        print(f"ChatGPT response: {response}")
           
        # Publish the response to Clarifier module
        response = json.dumps({"correction":"False", "user": user, "response": response})
        client.publish(TOPIC_OUT, response)
    if msg.topic == finished_plan_topic:
        print(("Plan finished"))
        initial_message = True
        historic = []

# Configure MQTT client
client = mqtt.Client()
client.username_pw_set(username, password)
client.on_message = on_message
client.connect(broker, port)

# Subscribe to input topic
client.subscribe(TOPIC_IN)
client.subscribe(finished_plan_topic)
print("Waiting for messages on", TOPIC_IN)

client.loop_forever()
