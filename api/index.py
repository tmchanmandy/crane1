import base64

from flask import Flask, send_file, request, jsonify
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Use a non-interactive backend
import matplotlib.pyplot as plt
import io
from flask_cors import CORS
import matplotlib.image as image
from matplotlib.offsetbox import (OffsetImage, AnnotationBbox)
from matplotlib.ticker import MultipleLocator
import math


#logo = image.imread(file)



app = Flask(__name__)
CORS(app)

@app.route('/')
def create_website():
    return render_template("crane_test2.html")

def plot_crane(boom_length, boom_angle_rad, boom_angle_deg, obstacle_distance, obstacle_height, load_length):
    crane_x, crane_y = 0, 0
    boom_start_x, boom_start_y = crane_x, crane_y + 2
    boom_x = crane_x + boom_length * np.cos(boom_angle_rad)
    boom_y = boom_start_y + boom_length * np.sin(boom_angle_rad)
    plt.xlim(-5, crane_x + boom_x + obstacle_distance)
    plt.ylim(0, boom_y + 10)

    plt.figure(figsize=(12, 12))
    #plt.scatter(crane_x, crane_y, color='red', s=100, label='Crane')

    fig, ax = plt.subplots(figsize = (12, 12))
    ax.set_xlim(-5, crane_x + boom_x + obstacle_distance)
    ax.set_ylim(0, boom_y + 1)
    file = "vehicle-v3.png"
    ax.xaxis.set_major_locator(MultipleLocator(5))
    ax.yaxis.set_major_locator(MultipleLocator(5))

    logo = image.imread(file)

    if logo.ndim == 2:
        logo = np.stack([logo] * 3 + [255 * np.ones_like(logo)], axis=-1)  # Grayscale → RGBA
    if logo.dtype == np.float32 or logo.dtype == np.float64:
        logo = (logo * 255).astype(np.uint8)

    # Define size in DATA UNITS
    desired_width = 5  # 5 units wide on the x-axis
    desired_height = 5  # 5 units tall on the y-axis
    left = crane_x - desired_width / 2
    right = crane_x + desired_width / 2
    bottom = crane_y - desired_height / 2
    top = crane_y + desired_height / 2

    ax.imshow(
        logo,
        extent=[left, right, bottom, top],
        aspect='equal',  # Let the image stretch to fit the extent
        zorder=10,
    )

    ax.plot([crane_x, boom_x], [boom_start_y, boom_y], color='blue', linewidth=16)

    load_pos_x, load_pos_y = boom_x, (boom_y - load_length)

    ax.plot([boom_x, load_pos_x], [boom_y, load_pos_y], color='green', linewidth=4)



    ax.text(boom_x / 2, boom_y / 2, f'{boom_angle_deg:.1f}°', fontsize=12, color='black')





    x_fixed = crane_x + obstacle_distance
    y_start, y_end = 0, obstacle_height  # Define length
    ax.plot([x_fixed, x_fixed], [y_start, y_end], color='orange')
    horiz_line = ax.plot([x_fixed, ax.get_xlim()[1]], [y_end, y_end], color='orange')

    plt.axhline(0, color='black', linewidth=1, ls='--')
    #plt.axvline(0, color='black', linewidth=0.5, ls='--')
    plt.title('Crane Boom Diagram')
    plt.grid()

    # Save the figure to a BytesIO object
    img = io.BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    plt.close()  # Close the figure to free memory

    base64_str = base64.b64encode(img.getvalue()).decode('utf-8')
    return base64_str
    # return img

@app.route('/crane-calculate/v1', methods=['POST'])
def plot_crane_service_img():
    data = request.json
    boomLength = data.get('boom_length')
    #boomAngleRad = data.get('boomAngleRad')
    boomAngleDeg = data.get('boom_angle_deg')
    obstacleDistance = data.get('obstacle_distance')
    obstacleHeight = data.get('obstacle_height')
    loadLength = data.get('load_length')

    if boomLength is None or boomAngleDeg is None or obstacleDistance is None or obstacleHeight is None:
        return {"error": "Missing parameters"}, 400

    
    
    boomAngleRad = math.radians(boomAngleDeg)

    base64_image = plot_crane(boomLength, boomAngleRad, boomAngleDeg, obstacleDistance, obstacleHeight, loadLength)
    img = base64.b64decode(base64_image)
    image_io = io.BytesIO(img)

    # Return the image as a PNG file
    return send_file(image_io, mimetype='image/png', as_attachment=False, download_name='image.png')




def plot_crane_v2(working_radius: float, obstacle_distance: float=None, obstacle_height: float=None):

    if (working_radius <= 0 or (obstacle_distance is not None and obstacle_distance <= 0) or (obstacle_height is not None and obstacle_height < 0)):
        raise ValueError("Please provide positive inputs and non-zero inputs for obstacle distance")

    # Assuming here that a crane will not be deploying its boom in a way that causes the boom to directly come into contact with the obstacle
    height_safety_margin = 5
    crane_height = 1

    if obstacle_distance is None or obstacle_height is None:
        boom_angle_rad = 0
        boom_angle_deg = 0
    else:
        safe_height = obstacle_height + height_safety_margin
        
        # No need for a raised angle at all if obstacle is not within working radius or if obstacle is shorter than crane height
        if (working_radius < obstacle_distance or crane_height > obstacle_height):
            boom_angle_rad = 0
            boom_angle_deg = 0
        else:
            boom_angle_rad = np.arctan(safe_height / obstacle_distance)
            boom_angle_deg = math.degrees(boom_angle_rad)

    if (boom_angle_deg >= 90 or boom_angle_deg < 0):
        raise ValueError("Invalid boom angle with given obstacle data")


    boom_length = working_radius / np.cos(boom_angle_rad)


    crane_x, crane_y = 0, 0
    boom_start_x, boom_start_y = crane_x, crane_y + crane_height
    boom_x = crane_x + boom_length * np.cos(boom_angle_rad)
    boom_y = boom_start_y + boom_length * np.sin(boom_angle_rad)
    plt.xlim(-5, crane_x + boom_x + obstacle_distance)
    plt.ylim(0, max(boom_y, obstacle_height) + 10)

    plt.figure(figsize=(6, 6))
    #plt.scatter(crane_x, crane_y, color='red', s=100, label='Crane')

    fig, ax = plt.subplots(figsize = (6, 6))
    ax.set_xlim(-5, crane_x + boom_x + obstacle_distance)
    ax.set_ylim(0, max(boom_y, obstacle_height) + 10)
    file = "vehicle-v3.png"
    ax.xaxis.set_major_locator(MultipleLocator(5))
    ax.yaxis.set_major_locator(MultipleLocator(5))

    logo = image.imread(file)

    if logo.ndim == 2:
        logo = np.stack([logo] * 3 + [255 * np.ones_like(logo)], axis=-1)  # Grayscale → RGBA
    if logo.dtype == np.float32 or logo.dtype == np.float64:
        logo = (logo * 255).astype(np.uint8)

    # Define size in DATA UNITS
    desired_width = 5  # 5 units wide on the x-axis
    desired_height = 5  # 5 units tall on the y-axis
    left = crane_x - desired_width / 2
    right = crane_x + desired_width / 2
    bottom = crane_y - desired_height / 2
    top = crane_y + desired_height / 2

    ax.imshow(
        logo,
        extent=[left, right, bottom, top],
        aspect='equal',  # Let the image stretch to fit the extent
        zorder=10,
    )

    # Calculate zoom
    ax_min_aspect_inches = min(fig.get_size_inches()[0],fig.get_size_inches()[1]) * min(ax.get_position().width, ax.get_position().height)
    desired_aspect_inches = ax_min_aspect_inches * 0.05
    zoom = desired_aspect_inches * fig.dpi / logo.shape[1]
    ax.plot([crane_x, boom_x], [boom_start_y, boom_y], color='blue', linewidth=(72 * zoom), label=f'{boom_angle_deg:.1f}°\n{boom_length:.1f}m')


    #Arbitrary length to emulate hook
    load_length = min(5, boom_y)
    load_pos_x, load_pos_y = boom_x, (boom_y - load_length)

    ax.plot([boom_x, load_pos_x], [boom_y, load_pos_y], color='green', linewidth=(36 * zoom))



    #ax.text(boom_x / 4, boom_y / 2, f'{boom_angle_deg:.1f}°\n{boom_length:.1f}m', fontsize=12, color='black')





    x_fixed = crane_x + obstacle_distance
    y_start, y_end = 0, obstacle_height  # Define length
    ax.plot([x_fixed, x_fixed], [y_start, y_end], color='orange')
    horiz_line = ax.plot([x_fixed, ax.get_xlim()[1]], [y_end, y_end], color='orange')

    plt.axhline(0, color='black', linewidth=1, ls='--')
    #plt.axvline(0, color='black', linewidth=0.5, ls='--')
    plt.title('Crane Boom Diagram')
    plt.grid()
    plt.legend()

    # Save the figure to a BytesIO object
    img = io.BytesIO()
    plt.savefig(img, format='png')
    img.seek(0)
    plt.close()  # Close the figure to free memory

    base64_str = base64.b64encode(img.getvalue()).decode('utf-8')
    return base64_str
    # return img







@app.route('/crane-calculate/v2', methods=['POST'])
def plot_crane_service_img_v2():
    data = request.json
    #boomLength = data.get('boom_length')
    #boomAngleRad = data.get('boomAngleRad')
    #boomAngleDeg = data.get('boom_angle_deg')
    workingRadius = data.get('working_radius')
    obstacleDistance = data.get('obstacle_distance')
    obstacleHeight = data.get('obstacle_height')
    #loadLength = data.get('load_length')

    if workingRadius is None:
        return {"error": "Missing parameters"}, 400


    
    

    try:
        base64_image = plot_crane_v2(workingRadius, obstacleDistance, obstacleHeight)
    except ValueError as e:
        return {"error": f"{e}"}, 400




    img = base64.b64decode(base64_image)
    image_io = io.BytesIO(img)

    # Return the image as a PNG file
    return send_file(image_io, mimetype='image/png', as_attachment=False, download_name='image.png')

if __name__ == "__main__":
    app.run(debug = True)
