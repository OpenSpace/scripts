import json
import requests
import os
from datetime import datetime, timedelta
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
import geopandas as gpd
import numpy as np
from PIL import Image

root_folder_path = "C:/Users/alundkvi/Documents/work/scripts/scriptTest/oval/"

# Function to convert RGB to Hex
def rgb_to_hex(rgb_str):
    """
    Convert RGB color string in format 'rgb(r, g, b)' to HEX color code.

    Parameters:
    rgb_str (str): RGB color string in format 'rgb(r, g, b)'

    Returns:
    str: HEX color code
    """
    rgb_values = rgb_str.split('(')[1].split(')')[0].split(',')
    r = int(rgb_values[0].strip())
    g = int(rgb_values[1].strip())
    b = int(rgb_values[2].strip())

    r = max(0, min(r, 255))
    g = max(0, min(g, 255))
    b = max(0, min(b, 255))

    return '#{:02x}{:02x}{:02x}'.format(r, g, b)



def douglas_peucker(coords, tolerance):
    """Douglas-Peucker algorithm for simplifying coordinates."""
    from math import sqrt

    def perpendicular_distance(pt, start, end):
        # Calculate the perpendicular distance from pt to line defined by start-end
        if start == end:
            return sqrt((pt[0] - start[0]) ** 2 + (pt[1] - start[1]) ** 2)
        else:
            numerator = abs((end[1] - start[1]) * pt[0] - (end[0] - start[0]) * pt[1] + end[0] * start[1] - end[1] * start[0])
            denominator = sqrt((end[1] - start[1]) ** 2 + (end[0] - start[0]) ** 2)
            return numerator / denominator

    def recursive_douglas_peucker(coords, tolerance, start=0, end=None):
        if end is None:
            end = len(coords) - 1

        if end <= start + 1:
            return [coords[start], coords[end]]

        max_distance = 0
        max_index = 0

        for i in range(start + 1, end):
            distance = perpendicular_distance(coords[i], coords[start], coords[end])
            if distance > max_distance:
                max_distance = distance
                max_index = i

        if max_distance >= tolerance:
            first_part = recursive_douglas_peucker(coords, tolerance, start, max_index)
            second_part = recursive_douglas_peucker(coords, tolerance, max_index, end)
            return first_part[:-1] + second_part
        else:
            return [coords[start], coords[end]]

    return recursive_douglas_peucker(coords, tolerance)


# Function to ensure proper order, closure, and orientation of coordinates
def process_coordinates(coords):

    if coords[0] != coords[-1]:
        coords.append(coords[0])

    poly = Polygon(coords)
    oriented_coords = list(orient(poly).exterior.coords)

    oriented_coords.reverse()

    return [[round(x, 6), round(y, 6)] for x, y in oriented_coords]

# Function to simplify coordinates using Douglas-Peucker algorithm
def simplify_coordinates(coords, tolerance=0.001):
    simplified_coords = douglas_peucker(coords, tolerance)
    return simplified_coords

# Function to process each entry and generate GeoJSON asset
def process_entry(entry):
    fill_color = entry.get('fill_color', None)
    paths = entry.get('paths', [])

    if not fill_color or not paths:
        return None

    fill_color_hex = rgb_to_hex(fill_color)

    optimized_paths = []

    for path in paths:
        optimized_path = []
        for coord in path:
            lat = coord.get('lat', None)
            lng = coord.get('lng', None)

            # Skip if coordinates are in the northern hemisphere
            if lat is not None and lat > 0:
                continue

            if lat is not None and lng is not None:
                optimized_path.append([
                    lng - 360,
                    lat
                ])

        if optimized_path:
            simplified_coords = simplify_coordinates(optimized_path)
            #final_coords = process_coordinates(simplified_coords)
            optimized_paths.append(simplified_coords)

    # GeoJSON structure
    if optimized_paths:
        asset = {
            "type": "Feature",
            "properties": {
                "stroke": fill_color_hex,
                "stroke-width": 2,
                "stroke-opacity": 1,
                "fill": fill_color_hex,
                "fill-opacity": 0.75
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": optimized_paths
            }
        }

        return asset
    else:
        return None

# Function to fetch data from URL
def fetch_data_and_process(url):
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return data
    else:
        print(f"Failed to fetch data from {url}")
        return []

start_time = datetime(2024, 5, 10, 15, 0)
end_time = datetime(2024, 5, 12, 0, 0)

current_time = start_time
interval_minutes = 15

while current_time <= end_time:
    formatted_time = current_time.strftime("%Y-%m-%d-%H-%M")
    folder_name = formatted_time.replace(':', '-')
    output_folder = f'{root_folder_path}{folder_name}/'

    try:
        os.makedirs(output_folder, exist_ok=True)
    except OSError as e:
        print(f"Error creating directory {output_folder}: {e}")
        continue

    url = f'https://aurorasaurus.org/oval-data?end_date={current_time.strftime("%Y-%m-%dT%H:%M%z")}&local_offset=0'
    data = fetch_data_and_process(url)

    if data:
        # Process each entry
        for index, entry in enumerate(data):
            asset = process_entry(entry)
            if asset:
                output_file = f'{output_folder}output{index + 1}.geojson'

                # Write to output file
                try:
                    with open(output_file, 'w') as out_f:
                        json.dump(asset, out_f, indent=2)
                    print(f'Processed entry {index + 1} saved to {output_file}')
                except Exception as e:
                    print(f"Error writing to {output_file}: {e}")
            else:
                print(f'Skipped entry {index + 1} due to missing or invalid data')

    # Move to the next interval
    current_time += timedelta(minutes=interval_minutes)


# Function to determine the shift needed for longitudes to fit within -180 to 180
def calculate_shift_amounts(coords):
    longitudes = coords[:, 0]
    shift = 0
    plus = True
    abs_max = abs(np.max(longitudes))
    abs_min = abs(np.min(longitudes))

    if abs_max > abs_min and np.max(longitudes) > 180:
        shift = np.max(longitudes) - 180
        plus = False
    elif abs_max < abs_min and np.min(longitudes) < -180:
        shift = -180 - np.min(coords[:, 0])
        plus = True

    return shift, plus

def shift_image(image_path, degrees, root_folder_path):

    image = Image.open(image_path).convert("RGBA")
    width, height = image.size

    pixels_per_degree = width / 360
    shift_pixels = int(degrees * pixels_per_degree)

    new_image = Image.new('RGBA', (width, height), (0, 0, 0, 0))

    right_part = image.crop((width - shift_pixels, 0, width, height))
    left_part = image.crop((0, 0, width - shift_pixels, height))

    new_image.paste(right_part, (0, 0), right_part)
    new_image.paste(left_part, (shift_pixels, 0), left_part)

    new_image.save(root_folder_path)

def shift_image_left(image_path, degrees, root_folder_path):

    image = Image.open(image_path).convert("RGBA")
    width, height = image.size

    pixels_per_degree = width / 360
    shift_pixels = int(degrees * pixels_per_degree)

    new_image = Image.new('RGBA', (width, height), (0, 0, 0, 0))

    left_part = image.crop((0, 0, shift_pixels, height))
    right_part = image.crop((shift_pixels, 0, width, height))

    new_image.paste(left_part, (width - shift_pixels, 0), left_part)
    new_image.paste(right_part, (0, 0), right_part)

    new_image.save(root_folder_path)

# Function to adjust coordinates based on shift amounts
def adjust_longitudes(coords, shift, plus):
    if plus == False:
        coords[:, 0] -= shift
    else:
        coords[:, 0] += shift
    return coords

# Iterate over all subdirectories and their files
for dirpath, _, filenames in os.walk(root_folder_path):
    geojson_files = [f for f in filenames if f.endswith('.geojson')]

    if not geojson_files:
        continue

    # Process each GeoJSON file to determine the maximum and minimum longitudes
    all_coords = []
    for filename in geojson_files:
        geojson_file = os.path.join(dirpath, filename)
        gdf = gpd.read_file(geojson_file)
        polygon_coords = np.array(gdf['geometry'][0].exterior.coords.xy).T
        all_coords.append(polygon_coords)

    all_coords = np.vstack(all_coords)

    shift, plus = calculate_shift_amounts(all_coords)

    for filename in geojson_files:
        geojson_file = os.path.join(dirpath, filename)
        gdf = gpd.read_file(geojson_file)
        polygon_coords = np.array(gdf['geometry'][0].exterior.coords.xy).T

        adjusted_coords = adjust_longitudes(polygon_coords, shift, plus)

        fill_color = gdf['fill'][0]

        fig, ax = plt.subplots(figsize=(72, 36))

        if len(adjusted_coords) > 0:
            polygon_patch = Polygon(adjusted_coords, closed=True, edgecolor=fill_color, facecolor=fill_color, alpha=1)
            ax.add_patch(polygon_patch)

        ax.set_xlim(-180, 180)
        ax.set_ylim(-90, 90)
        ax.set_aspect('equal')
        ax.axis('off')

        output_file = os.path.splitext(filename)[0] + '.png'
        output_path = os.path.join(dirpath, output_file)

        plt.savefig(output_path, bbox_inches='tight', pad_inches=0, transparent=True)
        plt.close()

        shift_image_left(output_path, shift, output_path)

    files = os.listdir(dirpath)

    images = [filename for filename in files if filename.startswith('output') and (filename.endswith('.jpg') or filename.endswith('.png'))]
    images.sort(key=lambda x: int(x.split('output')[1].split('.')[0]))  # Sort by numeric order

    base_image = None

    for filename in images:

        img = Image.open(os.path.join(dirpath, filename)).convert('RGBA')

        if base_image is None:
            base_image = img.copy()

        base_image = Image.alpha_composite(base_image, img)

    # Save the combined image for the current folder
    if base_image:
        folder_name = os.path.basename(dirpath)
        combined_image_path = os.path.join(root_folder_path, f'combined_images/{folder_name}.png')
        base_image.save(combined_image_path)  # Save the combined image
        print(f"Combined image saved for folder '{folder_name}' at: {combined_image_path}")
    else:
        print(f"No images found matching the criteria in folder '{folder_name}'.")
