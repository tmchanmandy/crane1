import base64
import traceback
import numpy as np
import math

#*******
#vercel link
#https://python-web-api-server-culw-git-main-james-projects-e0971478.vercel.app
#
#website account infomation stored in vercel
#acc: admin  pw: 1234
#*********

import os

import matplotlib

matplotlib.use('Agg')  # Non-interactive backend for Vercel

import matplotlib.pyplot as plt
import pandas as pd

from flask import Flask, send_file, request, jsonify, render_template

from flask_cors import CORS
import io
from io import BytesIO
import pymongo
from pymongo import MongoClient
from pymongo.server_api import ServerApi

app = Flask(__name__)
CORS(app)
    
def upload_csv():
    try:
        # Mongodb account stored in environment variable,  the database don't block ip
        mongodb_username = os.environ.get("MONGODB_USERNAME")
        mongodb_password = os.environ.get("MONGODB_PASSWORD")
        uri = f"mongodb+srv://{mongodb_username}:{mongodb_password}@cluster0.wwhbk9o.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"

        # Create a new client and connect to the server
        client = MongoClient(uri, server_api=ServerApi('1'))
        # Send a ping to confirm a successful connection
        try:
            client.admin.command('ping')
            print("Pinged your deployment. You successfully connected to MongoDB!")
        except Exception as e:
            print(e)

        db = client["crane_calculator"]
        model_dict = {}
        working_radii_dict = {}
        boom_length_dict = {}

        #import all lifting capacity tables, name: model name, model_dict: capacity table of that model,
        #working radii dict: store all working radii values stated in that model's table
        #boom length dict: store all boom length values (in float) stated in that model's table
        
        for name in db.list_collection_names():
            collection = db[name]
            cursor = collection.find({})
            temp = pd.DataFrame(list(cursor))
            model_dict[name] = temp.iloc[:, 1:]
            working_radii_dict[name] = list(model_dict[name].pop(model_dict[name].columns[0]))
            boom_length_dict[name] = model_dict[name].columns
            boom_length_dict[name] = [float(col.replace('m', '')) for col in boom_length_dict[name]]


        return {"model_dict": model_dict, "working_radii_dict": working_radii_dict,
                "boom_length_dict": boom_length_dict}

    except Exception as e:
        print(f"Error loading CSVs: {e}")
        traceback.print_exc()
        return None


dictionaries = upload_csv()
model_dict = dictionaries["model_dict"]
working_radii_dict = dictionaries["working_radii_dict"]
boom_length_dict = dictionaries["boom_length_dict"]

#second check if model is available, html checked once
def check_model_valid(model_dict, model):
    keys = list(model_dict.keys())
    if model not in keys:
        return 0
    else:
        return model

#no negative input allowed
def check_input_positive(a, d, j, safety_margin, building_distance, building_height, working_radius):
    if any(i < 0 for i in [a, d, j, safety_margin, building_distance, building_height, working_radius]):
        return 0
    else:
        return 1

#if inputed number error or extreme cases, angles will reach or exceed 90 degrees, this calculator will fail to proceed 
def check_angle_valid(horizontal_arm_angle, vertical_arm_angle):
    if (np.radians(0) <= horizontal_arm_angle) & (horizontal_arm_angle <= np.radians(90)) & (
            np.radians(0) <= vertical_arm_angle) & (vertical_arm_angle < np.radians(85)):
        return 1
    else:
        return 0


@app.route("/")
def upload_website():
    return render_template("crane_login.html")


@app.route("/login", methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    valid = 0
    redirect = ""

    #*********
    #website account infomation stored in vercel
    #acc: admin  pw: 1234
    #*********
    
    admin_user = os.environ.get("ADMIN_USER")
    admin_password = os.environ.get("ADMIN_PASSWORD")
    if username == admin_user and password == admin_password:
        valid = 1
        redirect = "/success_login"
    return jsonify({"valid": valid, "redirect": redirect})


@app.route("/success_login")
def success_login():
    model_namelist = list(model_dict.keys())
    return render_template("crane_test2.html", model_namelist = model_namelist)


@app.route("/crane-calculator", methods=['POST'])
def crane_calculator():
    data = request.json
    model = data.get('model')
    working_radius = data.get('working_radius')
    building_height = data.get('building_height')
    building_distance = data.get('building_distance')
    safety_margin = data.get('safety_margin')
    j = data.get('J')
    a = data.get('A')
    d = data.get('D')

    model = check_model_valid(model_dict, model)
    
    #*********
    #return error message for invalid model
    #*********
    
    if model == 0 or model == "0":
        response = {'image': 0,
                    'horizontal_arm_angle': 0,
                    'vertical_arm_angle': 0,
                    'boom_length': 0,
                    'model': 0,
                    "estimated_lifting_capacity": -1,
                    "error": "Model invalid"
                    }
        return jsonify(response)

    
    horizontal_arm_angle, vertical_arm_angle, boom_length, boom_height = calculate_boom_length_and_angle(a, d, j,
                                                                                                         safety_margin,
                                                                                                         building_distance,
                                                                                                         building_height,
                                                                                                         working_radius)

    #*********
    #return error message
    #*********
    
    input_positive = check_input_positive(a, d, j, safety_margin, building_distance, building_height, working_radius)
    if not input_positive:
        response = {'image': 0,
                    'horizontal_arm_angle': 0,
                    'vertical_arm_angle': 0,
                    'boom_length': 0,
                    'model': 0,
                    "estimated_lifting_capacity": -1,
                    "error": "Negative input"
                    }
        return jsonify(response)
    
    angle_valid = check_angle_valid(horizontal_arm_angle, vertical_arm_angle)
    if not angle_valid:
        response = {'image': 0,
                    'horizontal_arm_angle': -1,
                    'vertical_arm_angle': -1,
                    'boom_length': 0,
                    'model': -1,
                    "estimated_lifting_capacity": -1,
                    "error": "Invalid horizontal/vertical angle"
                    }
        return jsonify(response)

    #*********
    #valid input --> plot graph and return results
    #*********
    
    plot_image = draw_graph(a, d, j, building_distance, building_height, working_radius, boom_height)
    indexes = finding_index(model, working_radius, boom_length)
    if indexes[0] == -1:
        
        estimated_lifting_capacity = 0
    else:
        #**********
        # estimate the lifting capacity by getting average of nearest reference points
        #**********
        
        nearest_lifting_capacity = model_dict[model].iloc[[indexes[0] - 1, indexes[0]], [indexes[1] - 1, indexes[1]]]
        nearest_lifting_capacity = np.array(nearest_lifting_capacity)
        
        estimated_lifting_capacity = finding_lifting_capacity(model, indexes, working_radius, boom_length,
                                                              nearest_lifting_capacity) * 0.85
    response = {'image': plot_image, 'horizontal_arm_angle': math.degrees(horizontal_arm_angle),
                'vertical_arm_angle': math.degrees(vertical_arm_angle), 'boom_length': boom_length, 'model': model,
                'estimated_lifting_capacity': estimated_lifting_capacity}
    return jsonify(response)


def calculate_boom_length_and_angle(a, d, j, safety_margin, building_distance, building_height, working_radius):
    # adjust the starting point to tail of arm
    horizontal_arm_angle = np.arcsin(j / working_radius)
    zero_margin_vertical_angle = np.arctan((building_height - a) / (building_distance + d))
    vertical_arm_angle = np.arcsin(
        safety_margin / np.sqrt((building_distance + d) ** 2 + (building_height - a) ** 2)) + zero_margin_vertical_angle
    boom_length = (working_radius + d) / np.cos(vertical_arm_angle)
    boom_height = np.sqrt(boom_length ** 2 - (working_radius + d) ** 2)
    return horizontal_arm_angle, vertical_arm_angle, boom_length, boom_height


def finding_index(model, working_radius, boom_length):
    if (working_radius < working_radii_dict[model][0] or working_radius > working_radii_dict[model][-1]
            or boom_length < boom_length_dict[model][0] or boom_length > boom_length_dict[model][-1]):
        print("Distance out of Bound.")
        return [-1, -1]

    else:
        for radius_index in range(len(working_radii_dict[model])):
            if working_radius <= working_radii_dict[model][radius_index]:
                rounded_working_radius_index = radius_index
                break
        for length_index in range(len(boom_length_dict[model])):
            if boom_length <= boom_length_dict[model][length_index]:
                rounded_length_index = length_index
                break
        return [rounded_working_radius_index, rounded_length_index]


# assuming the lifting capacity is linear function of working radius and boom length
# using interpolating to estimate: estimate = x1 + (x2 - x1) * (x - x1) / (x2 - x1)

def finding_lifting_capacity(model, indexes, working_radius, boom_length, nearest_lifting_capacity):
    lower_working_radius_lifting_capacity = nearest_lifting_capacity[0][0] + (
                boom_length_dict[model][indexes[1]] - boom_length) / (
                                                        boom_length_dict[model][indexes[1]] - boom_length_dict[model][
                                                    indexes[1] - 1]) * (
                                                        nearest_lifting_capacity[1][0] - nearest_lifting_capacity[0][0])
    
    higher_working_radius_lifting_capacity = nearest_lifting_capacity[0][1] + (
                boom_length_dict[model][indexes[1]] - boom_length) / (
                                                         boom_length_dict[model][indexes[1]] - boom_length_dict[model][
                                                     indexes[1] - 1]) * (
                                                         nearest_lifting_capacity[1][1] - nearest_lifting_capacity[0][
                                                     1])
    
    ans = lower_working_radius_lifting_capacity + (working_radii_dict[model][indexes[0]] - working_radius) / (
                working_radii_dict[model][indexes[0] - 1] - working_radii_dict[model][indexes[0]]) * (
                      higher_working_radius_lifting_capacity - lower_working_radius_lifting_capacity)

    return (ans)


def draw_graph(a, d, j, building_distance, building_height, working_radius, boom_height):
    crane_x, crane_y = -d, a
    boom_x, boom_y = crane_x + working_radius, boom_height
    x = [crane_x, boom_x]
    y = [crane_y, boom_y]
    x2 = [0, j]
    y2 = [1, boom_y]
    fig, axes = plt.subplots(1, 2, figsize=(10, 5))
    axes[0].plot(x, y, label="side view")
    axes[0].set_xlim(-5, boom_x + 5)
    axes[0].set_ylim(0, boom_y + 5)
    axes[0].hlines(y=building_height, xmin=building_distance, xmax=boom_x + 5)
    axes[0].vlines(x=building_distance, ymin=0, ymax=building_height)
    axes[0].vlines(x=boom_x, ymin=boom_y - 3, ymax=boom_y, colors="red")
    axes[0].set_title("Side View")
    axes[0].grid(True)
    axes[0].legend()

    axes[1].plot(x2, y2, label="front view")
    axes[1].set_xlim(- j - 5, j + 5)
    axes[1].set_ylim(0, boom_y + 5)
    axes[1].hlines(y=building_height, xmin=- j - 5, xmax=j + 5)
    axes[1].vlines(x=0, ymin=0, ymax=boom_y + 5, colors="black", linestyle="dashed")
    axes[1].vlines(x=j, ymin=boom_y - 3, ymax=boom_y, colors="red")
    axes[1].set_title("Front View")
    axes[1].grid(True)
    axes[1].legend()

    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    plt.close(fig)  # Close the figure to free memory
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    return img_base64


if __name__ == "__main__":
    app.run(debug=True)
