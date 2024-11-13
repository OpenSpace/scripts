import requests
import json
from datetime import datetime, timedelta
import os

# Output directory for geojson files
#output_directory = "path/to/viewline_geojson_output/"
#north_output_directory = "path/to/viewline_geojson_output/north/"
#south_output_directory = "path/to/viewline_geojson_output/south/"
north_output_directory = "C:/Users/alundkvi/Documents/work/scripts/scriptTest/viewline_asset_output/north/"
south_output_directory = "C:/Users/alundkvi/Documents/work/scripts/scriptTest/viewline_asset_output/south/"
# Output directory for .asset files
#asset_output_directory = 'path/to/viewline_asset_output/'
asset_output_directory = 'C:/Users/alundkvi/Documents/work/scripts/scriptTest/viewline_asset_output/'

def fetch_coordinates(url, direction=None):
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()

        adjusted_coordinates = []
        if direction == 'northern' or direction is None:
            northern_coordinates = data.get('northern', [])
            adjusted_coordinates.extend([(item['lng'] - 360, item['lat']) for item in northern_coordinates])

        if direction == 'southern' or direction is None:
            southern_coordinates = data.get('southern', [])
            adjusted_coordinates.extend([(item['lng'] - 360, item['lat']) for item in southern_coordinates])

        return adjusted_coordinates
    else:
        print(f"Failed to fetch data from {url}")
        return []

# Function to create LineString GeoJSON and save to file
def create_geojson_file(coordinates, output_path):
    if not os.path.exists(os.path.dirname(output_path)):
        os.makedirs(os.path.dirname(output_path))

    feature_collection = {
        "type": "FeatureCollection",
        "features": []
    }

    line_feature = {
        "type": "Feature",
        "properties": {
            "name": "Aurora viewline",
            "stroke": "#FF5733"
        },
        "geometry": {
            "type": "LineString",
            "coordinates": coordinates
        }
    }

    feature_collection["features"].append(line_feature)

    with open(output_path, 'w') as f:
        json.dump(feature_collection, f, indent=4)

# Define start and end datetime
start_datetime = datetime(2024, 5, 10, 15, 0, 0)
end_datetime = datetime(2024, 5, 12, 0, 0, 0)
interval = timedelta(minutes=15)

# Iterate through each interval
current_datetime = start_datetime
while current_datetime <= end_datetime:
    # Construct URL for the current interval
    formatted_datetime = current_datetime.strftime("%Y-%m-%dT%H:%M:%S%z")
    url = f"https://aurorasaurus.org/view-lines?end_date={formatted_datetime}&format=json&local_offset=0"

    northern_coordinates = fetch_coordinates(url, 'northern')
    southern_coordinates = fetch_coordinates(url, 'southern')

    output_filename = current_datetime.strftime("%Y-%m-%d_%H-%M-%S") + ".geojson"
    north_output_path = os.path.join(north_output_directory, output_filename)
    south_output_path = os.path.join(south_output_directory, output_filename)

    create_geojson_file(northern_coordinates, north_output_path)
    create_geojson_file(southern_coordinates, south_output_path)

    current_datetime += interval

# Function to generate .asset content for a folder of GeoJSON files
def generate_asset(folder_path, direction=''):
    # Lua script content template
    lua_script = f"""
local earth = asset.require("scene/solarsystem/planets/earth/earth")

local geojsonPath = asset.resource("geojson/viewline_geojsons/")

"""

    # Process each GeoJSON file in the folder
    file_index = 1
    for filename in sorted(os.listdir(folder_path)):
        if filename.endswith('.geojson'):
            date_time_str = filename.replace('_', ' ')
            date_time_str = date_time_str.replace('.geojson', '')
            date_time = datetime.strptime(date_time_str, "%Y-%m-%d %H-%M-%S")

        # Calculate start and end times for the 15-minute interval
            start_time_str = date_time.strftime("%Y %B %d %H:%M:%S")
            end_time = date_time + timedelta(minutes=15)
            end_time_str = end_time.strftime("%Y %B %d %H:%M:%S")
            # Generate Lua script for each GeoJSON file
            lua_script += f"""
local {direction}Viewline_{file_index} = {{
  Identifier = "{direction}Viewline_{date_time_str}_{file_index}",
  File = geojsonPath .. "{filename}",
  TimeFrame = {{
    Type = "TimeFrameInterval",
    Start = "{start_time_str}",
    End = "{end_time_str}"
  }},
  HeightOffset = 75000,
  Name = "{direction}Viewline_{date_time_str}_{file_index}"
}}

"""
            file_index += 1

    lua_script += f"""
asset.onInitialize(function()
"""

    for i in range(1, file_index):
      lua_script += f"""openspace.globebrowsing.addGeoJson(earth.Earth.Identifier, viewline_{i})
"""
    lua_script += f"""
end)
"""


    lua_script += f"""
asset.onDeinitialize(function()
"""
    for i in range(1, file_index):
      lua_script += f"""openspace.globebrowsing.deleteGeoJson(earth.Earth.Identifier, viewline_{i})
"""
    lua_script += f"""
end)

"""
    # Write Lua script to .asset file in asset_output_directory
    asset_filename = f"{direction}Viewline.asset"
    asset_filepath = os.path.join(asset_output_directory, asset_filename)
    with open(asset_filepath, 'w') as asset_file:
        asset_file.write(lua_script)

    print(f'Generated {asset_filename} in {asset_output_directory}')

# Ensure asset output directory exists
os.makedirs(asset_output_directory, exist_ok=True)

generate_asset(north_output_directory, 'north')
generate_asset(south_output_directory, 'south')