# 🤖 Behavior Tree Generation and Adaptation for a Social Robot Control with LLMs

## 🧠 Overview
This project presents a **robotic control system** that combines **Large Language Models (LLMs)** with **Behavior Trees (BTs)** to allow a social robot to understand natural language commands, generate task plans, and adapt to failures or unexpected situations.  

The system transforms user instructions into executable **Behavior Trees**, which are dynamically adjusted during execution to ensure the task is completed even when something goes wrong.  

---

## ⚙️ System Description
The system is composed of six main modules that run simultaneously and communicate through the **MQTT** protocol:

| Module | Description |
|---------|-------------|
| **Mqtt_receiver** | Receives natural language orders from the robot and manages MQTT communication. |
| **Clarifier** | Interprets the LLM’s response and asks for clarification if the command is ambiguous or unfeasible. |
| **BT_Tester** | Validates the structure and logic of the generated Behavior Trees. |
| **BT_Planner** | Embeds the Behavior Tree in a complete executable structure and sends it to the executor. |
| **BT_Executor** | Executes the BTs according to their priority and communicates with the robot. |
| **Failure_Interpreter** | Detects execution failures and asks the LLM to modify the BT accordingly. |

Together, these modules form a complete **natural language → planning → execution → adaptation** loop, enabling fully autonomous and interpretable robot behavior.

---

## 🧩 Example

**Example command:**
> “Temi, go to the kitchen and say ‘Hello, my name is Temi.’”

1. The robot converts speech to text and sends it via MQTT.  
2. The **LLM (ChatGPT)** generates a Behavior Tree such as:
   ```
   Root (Sequence)
   ├── FailureIsSuccess (Decorator)
   │   └── MainTask (Sequence)
   │       ├── GoToKitchen (Action)
   │       └── SayHello (Action)
   └── Reminder (Action)
   ```
3. The **BT_Tester** validates the BT, **BT_Planner** embeds it into the execution framework, and **BT_Executor** runs it.  
4. If an error occurs (e.g., the robot cannot reach the kitchen), the **Failure_Interpreter** automatically modifies the plan or asks for user clarification.

---

## 🧠 How It Works
The system integrates a social robot, a PC, and an LLM accessed via API.  
Each module has a specific role in ensuring robust, adaptive behavior generation:

1. **Natural Language Processing** – Converts the user’s spoken instruction into text.  
2. **Behavior Tree Generation** – ChatGPT interprets the request and outputs the corresponding BT code.  
3. **Clarification and Validation** – Ambiguities or structural issues are handled by the *Clarifier* and *BT_Tester*.  
4. **Execution and Monitoring** – The BT is executed in real time, with status updates and MQTT-based robot control.  
5. **Failure Handling** – If a node fails, the *Failure_Interpreter* uses ChatGPT to repair or adapt the BT dynamically.

---

## 🧱 Setup and Execution

1. **Download or clone this repository**
   ```bash
   git clone https://github.com/<your-username>/<repo-name>.git
   cd <repo-name>
   ```

2. **Unzip the detection models**  
   The detection models are included in this repository.  
   Simply **unzip the model directory** and place its contents **in the same folder as the other system files**.

3. **Configure your connections**  
   Edit the configuration file to include:
   - Your **MQTT client data** (broker address, port, topics)
   - Your **ChatGPT API key**
   - The **robot communication parameters**

   Example:
   ```json
   {
     "mqtt_host": "localhost",
     "mqtt_port": 1883,
     "chatgpt_api_key": "YOUR_API_KEY",
     "robot_topic": "temi/actions"
   }
   ```

4. **Run all modules simultaneously**  
   Each module should be executed in a separate terminal window (or as background processes):

   ```bash
   python Mqtt_receiver.py
   python Clarifier.py
   python BT_Tester.py
   python BT_Planner.py
   python BT_Executor.py
   python Failure_Interpreter.py
   ```

   💡 Tip: you can create a simple shell script or `.bat` file to launch all six modules at once.

---

## 🧪 Example Use Case

**User command:**
> “Temi, check if someone is in the kitchen, and if there is, call David.”

- The LLM generates a Behavior Tree that includes navigation, perception (via the fall detection model), and communication actions.  
- If the robot cannot detect a person or the call fails, the system automatically adapts the BT to retry, clarify, or inform the user.

---

## 📈 Performance

The system has been validated on a **Temi social robot** across multiple real-world experiments.  
It achieved an **89.6% success rate** in task execution, including recovery from unexpected failures and handling of ambiguous user instructions.  

This demonstrates its reliability and adaptability for real environments such as **domestic assistive robotics**.

---

## 🧩 Credits

Developed by the **ITAP-DISA Research Group** at the **University of Valladolid**, in collaboration with **CARTIF**.  
Part of the **ROSOGAR** and **EIAROB** research projects.  

> *Based on the paper:*  
> **Merino-Fidalgo, S., Sánchez-Girón, C., Zalama, E., Gómez-García-Bermejo, J., Duque-Domingo, J. (2025).**  
> *Behavior Tree Generation and Adaptation for a Social Robot Control with LLMs.*
