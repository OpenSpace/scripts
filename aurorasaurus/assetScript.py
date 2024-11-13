import os
import pandas as pd
import re
from urllib.parse import unquote

# Configuration
csv_file_path = 'C:/Users/alundkvi/Documents/work/data/auroraData/Filter_web_observation_may2024.csv'
output_file_base = "C:/Users/alundkvi/Documents/work/scripts/scriptTest/auroraAssets/"
image_base_path = 'C:/Users/alundkvi/Documents/work/data/auroraData/mayImagesCompressed/'
user_assets_path = '${USER_ASSETS}/aurorasaurus/icons/newIcons2/'
default_icon_path = 'green2.png'
max_variables_per_file = 190  # Maximum number of local variables per file

# Define image paths based on colors
color_to_image_path = {
    'green': 'green2.png',
    'red': 'red2.png',
    'white': 'white2.png',
    'pink': 'pink2.png',
    'green,red': 'greenRed2.png',
    'green,white': 'greenWhite2.png',
    'green,pink': 'greenPink2.png',
    'green,red,white': 'greenRedWhite2.png',
    'green,pink,red': 'greenRedPink2.png',
    'green,pink,white': 'greenWhitePink2.png',
    'green,pink,red,white': 'greenRedWhitePink2.png',
    'red,white': 'redWhite2.png',
    'pink,red': 'redPink2.png',
    'pink,red,white': 'redWhitePink2.png',
    'pink,white': 'whitePink2.png'
}

color_to_image_path_camera = {
    'green': 'greenCamera.png',
    'red': 'redCamera.png',
    'white': 'whiteCamera.png',
    'pink': 'pinkCamera.png',
    'green,red': 'greenRedCamera.png',
    'green,white': 'greenWhiteCamera.png',
    'green,pink': 'greenPinkCamera.png',
    'green,red,white': 'greenRedWhiteCamera.png',
    'green,pink,red': 'greenRedPinkCamera.png',
    'green,pink,white': 'greenWhitePinkCamera.png',
    'green,pink,red,white': 'greenRedWhitePinkCamera.png',
    'red,white': 'redWhiteCamera.png',
    'pink,red': 'redPinkCamera.png',
    'pink,red,white': 'redWhitePinkCamera.png',
    'pink,white': 'whitePinkCamera.png'
} 

# Load data
df = pd.read_csv(csv_file_path)

# Ensure all_colors is a string and handle missing values
df['all_colors'] = df['all_colors'].fillna('').astype(str)

# Lua Template
lua_template = '''local {var_name} = {{
  Identifier = "{identifier}",
  Parent = earth.Earth.Identifier,
  TimeFrame = {{
    Type = "TimeFrameInterval",
    Start = "{start_time}",
    End = "{end_time}"
  }},
  Transform = {{
    Translation = {{
      Type = "GlobeTranslation",
      Globe = earth.Earth.Identifier,
      Latitude = {latitude},
      Longitude = {longitude},
      Altitude = {altitude},
      UseHeightmap = false
    }}
  }},
  Renderable = {{
    Type = "{renderable_type}",
    {renderable_details}
  }},
  GUI = {{
    Path = "/{gui_path}",
    Name = "{gui_name}"
  }}
}}

'''

# Function to write Lua script to file
def write_lua_script(filename, lua_script, aurora_identifiers):
    earth_asset_code = 'local earth = asset.require("scene/solarsystem/planets/earth/earth")\n\n'

    earth_asset = "scene/solarsystem/planets/earth/earth"
    earth_asset_code = f'local earth = asset.require("{earth_asset}")\n\n'
    file_path_code = 'local image_filepath = "${USER_ASSETS}/aurorasaurus/mayImagesCompressed/"\n\n'
    icon_path_code = 'local icon_filepath = "${USER_ASSETS}/aurorasaurus/icons/newIcons2/"\n\n'

    asset_management_code = "\n\nasset.onInitialize(function()\n"
    asset_management_code += ''.join([f"  openspace.addSceneGraphNode({identifier})\n" for identifier in aurora_identifiers])
    asset_management_code += "end)\n\n"

    asset_management_code += "asset.onDeinitialize(function()\n"
    asset_management_code += ''.join([f"  openspace.removeSceneGraphNode({identifier})\n" for identifier in aurora_identifiers])
    asset_management_code += "end)\n\n"

    asset_management_code += ''.join([f"asset.export({identifier})\n" for identifier in aurora_identifiers])

    final_lua_script = earth_asset_code + file_path_code + icon_path_code + '\n'.join(lua_script) + asset_management_code

    with open(filename, 'a') as f:
        f.write(final_lua_script)

    print(f"Lua script generated and saved to {filename}")

# Function to generate Lua code
def generate_lua_code(var_name, identifier, start_time, end_time, latitude, longitude, altitude, renderable_type, renderable_details, gui_path, gui_name):
    return lua_template.format(
        var_name=var_name,
        identifier=identifier,
        start_time=start_time,
        end_time=end_time,
        latitude=latitude,
        longitude=longitude,
        altitude = altitude,
        renderable_type=renderable_type,
        renderable_details=renderable_details,
        gui_path=gui_path,
        gui_name=gui_name
    )

start_date = pd.Timestamp('2024-05-9').tz_localize(None)
end_date = pd.Timestamp('2024-05-13').tz_localize(None)
chunk_counter = 0
lua_scripts = []
aurora_identifiers = []

# Loop through DataFrame rows
for index, row in df.iterrows():
  time_start = pd.Timestamp(row['time_start']).tz_localize(None)
  if start_date <= time_start <= end_date:
      longitude, latitude = map(float, re.findall(r'[-]?\d+\.\d+', row['location']))

      start_time = time_start.strftime('%Y %b %d %H:%M:%S')
      end_time = pd.to_datetime(row['time_end']).strftime('%Y %b %d %H:%M:%S')
      if not row['see_aurora']:
          var_name = f"notSeenAuroraIcon{index+1}"
          identifier = var_name
          altitude = 9500
          gui_name = f"Aurora not seen {index+1}"
          renderable_details = f'''Size = 1,
    Origin = "Center",
    Billboard = true,
    Texture = icon_filepath .. "grayIcon.png",
    Opacity = 1.0,
    Enabled = true,
    ScaleByDistance = true,
    ScaleRatio = 0.01,
    ScaleByDistanceMaxHeight = 200000,
    RenderBinMode = "PostDeferredTransparent",
    ScaleByDistanceMinHeight = 30000'''
          renderable_type = "RenderablePlaneImageLocal"
      else:
          colors = [c.strip().lower() for c in row['all_colors'].split(',')]
          # Join sorted colors to handle combinations correctly
          color_key = ','.join(sorted(colors))

          if not pd.isna(row['image']) and row['image'] != 'NA':
              var_name = f"Aurora{''.join([c.capitalize() for c in colors])}{index+1}"
              identifier = var_name
              image_name = f"image_{index+1}.{'jpg' if os.path.exists(os.path.join(image_base_path, f'image_{index+1}.jpg')) else 'png'}"
              icon_path = color_to_image_path_camera.get(color_key, default_icon_path)
              altitude = 15000
              gui_name = f"Aurora Image {index+1}"
              renderable_details = f'''Renderable1 = {{
        Type = "RenderablePlaneImageLocal",
        Size = 50000,
        Origin = "Center",
        Billboard = true,
        Texture = image_filepath .. "{image_name}",
        Opacity = 1,
        Enabled = true
      }},
    Renderable2 = {{
      Type = "RenderablePlaneImageLocal",
      Size = 1,
      Origin = "Center",
      Billboard = true,
      Texture = icon_filepath .. "{icon_path}",
      Opacity = 1,
      Enabled = true,
      ScaleByDistance = true,
      ScaleRatio = 0.01,
      ScaleByDistanceMaxHeight = 200000,
      ScaleByDistanceMinHeight = 30000
    }},
    RenderBinMode = "PostDeferredTransparent",
    DistanceThreshold = 1000000'''
              renderable_type = "RenderableSwitch"
          else:
              var_name = f"icon{''.join([c.capitalize() for c in colors])}{index+1}"
              identifier = var_name
              icon_path = color_to_image_path.get(color_key, default_icon_path)
              gui_name = f"Time Frame Icon {' '.join([c.capitalize() for c in colors])} {index+1}"
              altitude = 10000
              renderable_details = f'''Size = 1,
      Origin = "Center",
      Billboard = true,
      Texture = icon_filepath .. "{icon_path}",
      Opacity = 1.0,
      Enabled = true,
      ScaleByDistance = true,
      ScaleRatio = 0.01,
      ScaleByDistanceMaxHeight = 200000,
      RenderBinMode = "PostDeferredTransparent",
      ScaleByDistanceMinHeight = 30000'''
              renderable_type = "RenderablePlaneImageLocal"

      # Generate Lua code and append to lua_scripts
      lua_code = generate_lua_code(var_name, identifier, start_time, end_time, latitude, longitude, altitude, renderable_type, renderable_details.strip(), "Aurorasaurus/IconsWithoutImage" if row['image'] == 'NA' else "Aurorasaurus", gui_name)
      lua_scripts.append(lua_code)
      aurora_identifiers.append(identifier)

      # Check if we need to write lua_scripts to a new file
      if len(lua_scripts) >= max_variables_per_file:
          chunk_counter += 1
          filename = f"{output_file_base}{chunk_counter}.asset"
          write_lua_script(filename, lua_scripts, aurora_identifiers)
          # Reset lua_scripts and aurora_identifiers for the next chunk
          lua_scripts = []
          aurora_identifiers = []

# Write remaining lua_scripts to file if any
if lua_scripts:
    chunk_counter += 1
    filename = f"{output_file_base}{chunk_counter}.asset"
    write_lua_script(filename, lua_scripts, aurora_identifiers)