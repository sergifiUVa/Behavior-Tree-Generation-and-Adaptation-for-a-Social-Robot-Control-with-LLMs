# -*- coding: utf-8 -*-
"""
@author: celiasg
"""

# INDIVIDUAL INFERENCE + IMAGE RECEPTION BY MQTT:
# An MQTT client is created and subscribed to the topic output/info/image with the ConectorMQTT function.
# Every time a new image is received, the callback of detectFall is triggered 
# (which handles the whole process of creating the model, detecting person, detecting object, overlap...).
# The photo is saved in the general folder (PATH_PHOTO_TEST), the segmented person (PATH_BB_IMAGE)
# and its bounding box (PATH_BB_TEXT) will be saved in the "inference" folder, and 
# the prediction (PREDICTIONS_DIR) of fall or not fallen will be saved in the "predictions" folder.

import traceback
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import logging
import json

from ultralytics import YOLO
import cv2
import io
import shutil

from datetime import datetime
from PIL import Image

from torchvision import transforms, models
import torch
import torch.nn as nn
import torch.nn.functional as F
import paho.mqtt.client as mqtt
import sys


# Configure logging to send messages to "log.log"
logging.basicConfig(filename='log.txt', level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s')

#############################
# CONVNEXT MODEL CLASS
#############################
class MyConvNextModel(nn.Module):
    def __init__(self):
        super().__init__()
        # Load pre-trained ConvNext model
        self.convnext = models.__dict__['convnext_small'](pretrained=True)
        num_ftrs = self.convnext.classifier[2].in_features
        self.convnext.classifier[2] = nn.Linear(num_ftrs, 512)        
        
        # Text input dimension
        text_input_dim = 16
        self.fc_text = nn.Linear(text_input_dim, 256)
        # Concatenation and fully connected layers
        self.fc1 = nn.Linear(512 + 256, 128)
        self.fc2 = nn.Linear(128, 1)
        # Binary output → sigmoid
        self.sigmoid = nn.Sigmoid()

    def forward(self, images, texts):
        image_features = self.convnext(images) #(1,512)
        text_features = F.relu(self.fc_text(texts))
        combined_features = torch.cat((image_features, text_features), dim=1)
        output = F.relu(self.fc1(combined_features))
        output = self.fc2(output)
        output = self.sigmoid(output)
        return output

############################
# READ CONFIGURATION
############################
def read_config(file):
    try:
        config = {}
        with open(file, 'r') as f:
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

# Load config
config_file = 'config.txt'  
config = read_config(config_file)

###############################################################
# READ IMAGE AND TEXT
###############################################################
def readImgsBB(imgs_path, txts_path):
    imgs=[]
    txts=[]

    for img_file in os.listdir(imgs_path):
        if (img_file.endswith((".jpg",".png",".jpeg"))) and not img_file.endswith("debug.jpg"):
            # Save input image
            image = Image.open(os.path.join(imgs_path, img_file))
            imgs.append(image.copy())
            image.close()
            
            # Save input text (bb file)
            txt_file = img_file.replace(".jpg", ".txt").replace(".png", ".txt").replace(".jpeg",".txt")
            txt_path = os.path.join(txts_path, txt_file)
            with open(txt_path, 'r') as f:
                 txt = f.read()
                 vector_strings = txt.strip('[]').split('][')   
                 for sublist in vector_strings:
                    numbers = sublist.replace('[', '').replace(']', '').split(', ')
                    numbers = [float(num) for num in numbers]
                    txts.append(numbers)
    return imgs,txts


###############################################################
# SAVE BOUNDING BOX IN PROPER FORMAT
###############################################################
def save_bb(new_filename, classes, PATH_BB_TEXT):
    missing_vectors=[]
    existing_vectors=[]
    with open(os.path.join(PATH_BB_TEXT, os.path.splitext(new_filename)[0]+'.txt'),"r") as f:
        string=f.readline()
        vector_strings = string.strip('[]').split('][')
        for sublist in  vector_strings:
           elements = sublist.split(', ')
           sublist_array = [round(float(element),3) for element in elements]
           existing_vectors.append(sublist_array)
      
    with open(os.path.join(PATH_BB_TEXT, os.path.splitext(new_filename)[0]+'.txt'), "w") as f:
        for num in classes:
            found=False
            for vector in existing_vectors:
                if vector[0]==num:
                    found=True
                    break
            if not found:
                missing_vectors.append([num]+[0]*4)
           
        vectors_total=existing_vectors+missing_vectors
        sorted_vectors = sorted(vectors_total, key=lambda x: x[0])
        final_vector = [[sublist[i] for i in range(1, len(sublist))] for sublist in sorted_vectors]
        f.write(f"{final_vector}")


###################################
# CREATE IMAGE AND .TXT (BB)
###################################
def create_bb(classes, path):
    files = os.listdir(path)
    for filename in files:
        if filename.endswith((".png",".jpg",".jpeg")):
            image = cv2.imread(os.path.join(path, filename))
            h, w = image.shape[:2]
                            
            detect_params = model.predict(image)
            DP = detect_params[0].cpu().numpy()
            person_detected = any(box.cls.cpu().numpy()[0] == 0.0 for box in detect_params[0].boxes)
            
            if person_detected:
                if len(DP) != 0:
                    counter=1
                    bb_vectors=[]
                    filenames=[]
                    
                    # Detect persons
                    for i in range(len(detect_params[0])):
                        boxes = detect_params[0].boxes
                        box = boxes[i]
                        clsID = box.cls.cpu().numpy()[0]
                        conf = box.conf.cpu().numpy()[0]
                        bb = box.xyxy.cpu().numpy()[0]
                       
                        if clsID in classes and conf>=0.6:
                            if int(clsID) == 0.0:
                                print("class",clsID," conf",conf)
                                cropped = image[int(bb[1]):int(bb[3]), int(bb[0]):int(bb[2])]
                                x1, y1, x2, y2 = int(bb[0])/w, int(bb[1])/h, int(bb[2])/w, int(bb[3])/h
                                bb_vector=[x1,y1,x2,y2]
                                person_vector=[clsID]+bb_vector
                                
                                new_filename = filename if counter==1 else filename.replace(".", "_" + str(counter) + ".")
                                filenames.append(new_filename)
                                cv2.imwrite(os.path.join(PATH_BB_IMAGES, new_filename), cropped)
                                bb_vectors.append(bb_vector)
                                with open(os.path.join(PATH_BB_TEXT, os.path.splitext(new_filename)[0]+'.txt'), "a") as f:
                                    f.write(f"{person_vector}")
                                counter+=1
                                    
                    # Detect objects overlapping with persons
                    overlap=[0]*len(classes)
                    final_vectors=[0]*len(classes)
                    for person, new_filename in zip(bb_vectors, filenames):
                        for i in range(len(detect_params[0])):
                            boxes = detect_params[0].boxes
                            box = boxes[i]
                            clsID = box.cls.cpu().numpy()[0]
                            conf = box.conf.cpu().numpy()[0]
                            bb = box.xyxy.cpu().numpy()[0]
                                   
                            if clsID in classes and conf>=0.3 and int(clsID)!=0.0:
                                print("class",clsID," conf",conf)
                                index=classes.index(clsID)
                                bbobj_vector=[int(bb[0])/w, int(bb[1])/h, int(bb[2])/w, int(bb[3])/h]
                                obj_vector=[clsID]+bbobj_vector
                                if get_iou(person, bbobj_vector)>overlap[index]:
                                    overlap[index]=get_iou(person, bbobj_vector)
                                    final_vectors[index]=obj_vector
                                 
                        for j in final_vectors:
                            if(j!=0):       
                                with open(os.path.join(PATH_BB_TEXT, os.path.splitext(new_filename)[0]+'.txt'), "a") as f:
                                    f.write(f"{j}")
                        save_bb(new_filename,classes,PATH_BB_TEXT)
                    
            else:
                print("NO PERSON DETECTED")


##############################
# DEBUGGING
#############################
def final_name(PATH_PHOTO_TEST, save_path, falls,notfalls):
    new_name=datetime.now().strftime("%Y-%m-%d_%H-%M-%S")+f"_falls-{falls}_notfalls-{notfalls}.jpg"
    new_file_path=os.path.join(save_path,new_name)
    shutil.copy(PATH_PHOTO_TEST + "/image.jpg",new_file_path)

#####################
# IOU CALCULATION
#####################
def get_iou(rect1, rect2):
    x_left = max(rect1[0], rect2[0])
    y_top = max(rect1[1], rect2[1])
    x_right = min(rect1[2], rect2[2])
    y_bottom = min(rect1[3], rect2[3])
    if x_right < x_left or y_bottom < y_top:
        return False
    intersection_area = (x_right - x_left) * (y_bottom - y_top)
    rect1_area = (rect1[2] - rect1[0]) * (rect1[3] - rect1[1])
    rect2_area = (rect2[2] - rect2[0]) * (rect2[3] - rect2[1])
    iou = intersection_area / float(rect1_area + rect2_area - intersection_area)
    return iou
    

############################+
# FALL DETECTION CALLBACK
###########################
def detectFall(client, userdata, message):
    payload = message.payload
    try:
        image_save = Image.open(io.BytesIO(payload))
        image_save.save(PATH_PHOTO_TEST+"/image.jpg")
        print("Image received")
    except:
        logging.error("Could not save image")
    
    nfcont=0
    fcont=0 
    # Clean dirs
    for path in [PATH_BB_IMAGES,PATH_BB_TEXT,PREDICTIONS_DIR]:
        try: shutil.rmtree(path)
        except: pass
         
    for path in [PATH_BB_IMAGES,PATH_BB_TEXT,PREDICTIONS_DIR+"/fall",PREDICTIONS_DIR+"/not_fallen",PATH_DEBUG,PATH_FALLS,PATH_NOFALLS]:
        if not os.path.exists(path):
            os.makedirs(path)

    # PROCESSING IMAGE
    create_bb([0.0,56.0,57.0,59.0],PATH_PHOTO_TEST)
    
    # INFERENCE WITH IMAGE + TXT
    try:
        image_list,text_list=readImgsBB(PATH_BB_IMAGES,PATH_BB_TEXT)
        transform_inf = transforms.Compose([
                transforms.Resize((224,224)),
                transforms.ToTensor(),
                transforms.Normalize([0.485,0.456,0.406],[0.229,0.224,0.225])])
        
        with torch.no_grad():
            for image, text in zip(image_list, text_list): 
                original=image
                image=transform_inf(image).unsqueeze(0)
                text=torch.Tensor(text).unsqueeze(0)
                if torch.cuda.is_available():
                    image,text=image.cuda(),text.cuda()
                if k==1: 
                    outputs = models_list[0](image,text)
                else:
                    outputs = sum(m(image,text) for m in models_list)/k
                print("prediction confidence",outputs)
                if(outputs>=0.5):
                    original.save(PREDICTIONS_DIR+"/not_fallen/not_fallen"+str(nfcont)+".jpg")
                    nfcont+=1
                else:
                    original.save(PREDICTIONS_DIR+"/fall/fall"+str(fcont)+".jpg")
                    fcont+=1
            final_name(PATH_PHOTO_TEST, PATH_DEBUG, fcont,nfcont)
            if nfcont != 0 or fcont != 0:
                if nfcont != 0:
                    print(nfcont,"person not fallen")
                    final_name(PATH_PHOTO_TEST, PATH_NOFALLS , fcont,nfcont)
                elif fcont != 0:
                    print(fcont,"person fallen")
                    final_name(PATH_PHOTO_TEST, PATH_FALLS, fcont,nfcont)
                    
            msg_detect = {'fallen':fcont, "not_fallen":nfcont}
            payload_detect = json.dumps(msg_detect)
            topic_detect = "robot/Temi_UVA/output/info/person_found_state"
            client.publish(topic_detect, payload_detect)             
                
    except:
        print("Unable to create img or bb")
        logging.error("Unable to create img or bb")
        logging.warning(traceback.format_exc())
        

############################################################
# MAIN
############################################################
try:
    PATH_PHOTO_TEST= "Detection"
    PATH_BB_IMAGES= "Detection/inference"
    PATH_BB_TEXT= "Detection/inference"
    PREDICTIONS_DIR="Detection/predictions"
    PATH_DEBUG="Detection/debug"
    PATH_FALLS="Detection/falls"
    PATH_NOFALLS="Detection/not_falls"
    
    # Configure MQTT broker
    broker = "your_broker"
    port = 1884  
    username = "your_username"
    password = "your_password"
    
    client = mqtt.Client()
    client.username_pw_set(username, password)
    client.on_message = detectFall
    client.connect(broker, port)
        
    k = int(config['Repetitions_and_Others']['Fall_detection_models'])
    nfcont=0
    fcont=0
    model_name=config['Neural_models']['detection_model']
    
    # Load YOLO
    model = YOLO(PATH_PHOTO_TEST + "/yolov8s.pt")
    classes = model.names
    
    # Load CVV models
    models_list=[]
    for i in range(k):
        models_list.append(MyConvNextModel())
        print("Loading model "+model_name+str(i)+".pt")
        models_list[i].load_state_dict(torch.load(PATH_PHOTO_TEST+"/"+model_name+str(i)+".pt", map_location=torch.device('cpu')), strict=False)
        models_list[i].eval()
        if torch.cuda.is_available():
            models_list[i].cuda()
    
    # Subscribe to image topic
    topic_image = "robot/+/output/info/image"        
    client.subscribe(topic_image)
    client.loop_forever()
    
    def handle_signal(signum, frame):
        client.loop_stop()
        client.disconnect()
        sys.exit(0)  
    
except Exception as e:
    logging.error(f"Error in fall_detection_request: {e}")
    logging.warning(traceback.format_exc())
