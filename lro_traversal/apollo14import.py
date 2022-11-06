import os.path
import urllib.parse
import urllib.request
import json
import datetime
import re

def strip_identiifier(id):
  return re.sub(r"[^a-zA-Z0-9 ]", "", id)

def create_keyframes(geofile, start):
  #parse traversal
  lua = ""
  eva1file = f = open(geofile)
  eva1shep = json.load(eva1file)
  end_time = 0;


  lua += "  ['" + str(datetime.datetime.fromtimestamp(start-1)) + "'] = {\n"
  lua += "    Type = 'GlobeTranslation',\n"
  lua += "    Globe = 'Moon',\n"
  lua += "    Latitude = 0,\n"
  lua += "    Longitude = 0,\n"
  lua += "    Altitude = 0.25,\n"
  lua += "    UseHeightmap = true\n"
  lua += "  },\n"

  for point in eva1shep['features']:
    point_time = point['properties']['surface_seconds']
    if point_time < 0:
      continue
    keyframe_time = datetime.datetime.fromtimestamp(start + point_time);
    lua += "  ['" + str(keyframe_time) + "'] = {\n"
    lua += "    Type = 'GlobeTranslation',\n"
    lua += "    Globe = 'Moon',\n"
    lua += "    Latitude = " + str(point['geometry']['coordinates'][1]) + ",\n"
    lua += "    Longitude = " + str(point['geometry']['coordinates'][0]) + ",\n"
    lua += "    Altitude = 0.25,\n"
    lua += "    UseHeightmap = true\n"
    lua += "  },\n"
    if (point_time > end_time):
      end_time = point_time
  lua = lua[:-2] + "\n"
  return lua, end_time

def create_traversal(geofile, assetfile, start):
  keyframes, end_time = create_keyframes(geofile, start)
  lua = "local keyframes = {\n";
  lua += keyframes
  lua += "}\n"
  lua += "\nasset.export('keyframes', keyframes);\n"

  with open(assetfile, 'w') as asset:
      asset.write(lua)
  return end_time

def create_asset(travfile, assetfile, start, end, color_str):
  title = travfile[7:-6]
  start_str = str(datetime.datetime.fromtimestamp(start))
  end_str  = str(datetime.datetime.fromtimestamp(start + end))

  lua = "local traversal = asset.require('./" + title + "')\n\n" #7 for asset/
  lua += "local sunTransforms = asset.require('scene/solarsystem/sun/transforms')\n\n" #7 for asset/
  #translation
  lua += "local keyframeTranslation = {\n"
  lua += "  Type = 'TimelineTranslation',\n"
  lua += "  Keyframes = traversal.keyframes\n"
  lua += "}\n\n"

  #node
  lua += "local position = {\n"
  lua += "  Identifier = '" + title + "-position',\n"
  lua += "  Parent = 'Moon',\n"
  lua += "  Transform = {\n"
  lua += "    Translation = keyframeTranslation,\n"
  lua += "  },\n"
  lua += "  TimeFrame = {\n"
  lua += "    Type = 'TimeFrameInterval',\n"
  lua += "    Start = '" + start_str + "'\n"
  lua += "  },\n"
  lua += "  GUI = {\n"
  lua += "    Name = '" + title + " Position',\n"
  lua += "    Path = '/Solar System/Missions/Apollo/14'\n"
  lua += "  }\n"
  lua += "}\n\n"

  #suit
  lua += "local suit_holder = {\n"
  lua += "  Identifier = '" + title + "_suit_holder',\n"
  lua += "  Parent = position.Identifier,\n"
  lua += "  Transform = {\n"
  lua += "    Rotation = {\n"
  lua += "      Type = 'StaticRotation',\n"
  lua += "      Rotation = {0.0,1.35,-1.81}\n"
  lua += "    }\n"
  lua += "  },\n"
  lua += "  TimeFrame = {\n"
  lua += "    Type = 'TimeFrameInterval',\n"
  lua += "    Start = '" + start_str + "',\n"
  lua += "    End = '" + end_str + "'\n"
  lua += "  },\n"
  lua += "  GUI = {\n"
  lua += "    Name = '" + title + " Suit Holder',\n"
  lua += "    Path = '/Solar System/Missions/Apollo/14',\n"
  lua += "  }\n"
  lua += "}\n\n"

  pieces = ['hard_surf_decimated.obj', 'suit_ext-part_01-high.obj', 'suit_ext-part_02-high.obj', 'suit_ext-part_03-high.obj']
  for piece in pieces:
    piece_strip = strip_identiifier(piece)
    lua += "local " + piece_strip + " = {\n"
    lua += "  Identifier = '" + title + piece_strip + "',\n"
    lua += "  Parent = suit_holder.Identifier,\n"
    lua += "  Renderable = {\n"
    lua += "    Type = 'RenderableModel',\n"
    lua += "    GeometryFile = asset.localResource('suit/" + piece + "'),\n"
    lua += "    ModelScale = 'Millimeter',\n"
    lua += "    PerformShading = true,\n"
    lua += "    LightSources = {{\n"
    lua += "        Type = 'SceneGraphLightSource',\n"
    lua += "        Identifier = 'Sun',\n"
    lua += "        Node = sunTransforms.SolarSystemBarycenter.Identifier,\n"
    lua += "        Intensity = 1.0\n"
    lua += "      }\n"
    lua += "    }\n"
    lua += "  },\n"
    lua += "  GUI = {\n"
    lua += "    Name = '" + title + " Suit " + piece_strip + "',\n"
    lua += "    Path = '/Solar System/Missions/Apollo/14',\n"
    lua += "  }\n"
    lua += "}\n\n"

  #trail
  lua += "local trail = {\n"
  lua += "  Identifier = '" + title + "-trail',\n"
  lua += "  Parent = 'Moon',\n"
  lua += "  Renderable = {\n"
  lua += "      Type = 'RenderableTrailTrajectory',\n"
  lua += "      Translation = keyframeTranslation,\n"
  lua += "      Color = " + color_str + ",\n"
  lua += "      StartTime = '" + str(datetime.datetime.fromtimestamp(start-1)) + "',\n"
  lua += "      EndTime = '" + end_str + "',\n"
  lua += "      SampleInterval = 20,\n"
  lua += "      Fade = 8,\n"
  lua += "      EnableFade = true,\n"
  lua += "      ShowFullTrail = false,\n"
  lua += "      Enabled = true,\n"
  lua += "      BoundingSphere = 55000,\n"  
  lua += "  },\n"
  lua += "  GUI = {\n"
  lua += "      Name = '" + title + " Trail',\n"
  lua += "      Path = '/Solar System/Missions/Apollo/14'\n"
  lua += "  }\n"
  lua += "}\n\n"

  #boiler plate
  lua += "asset.onInitialize(function()\n"
  lua += "  openspace.addSceneGraphNode(position)\n"
  lua += "  openspace.addSceneGraphNode(suit_holder)\n"
  for piece in pieces:
    lua += "  openspace.addSceneGraphNode(" + strip_identiifier(piece) + ")\n"
  lua += "  openspace.addSceneGraphNode(trail)\n"
  lua += "end)\n\n"

  lua += "asset.onDeinitialize(function()\n"
  lua += "  openspace.removeSceneGraphNode(trail)\n"
  for piece in pieces:
    lua += "  openspace.removeSceneGraphNode(" + strip_identiifier(piece) + ")\n"
  lua += "  openspace.removeSceneGraphNode(suit_holder)\n"
  lua += "  openspace.removeSceneGraphNode(position)\n"
  lua += "end)\n\n"

  lua += "asset.export('position', position)\n"
  lua += "asset.export('trail', trail)\n"
  
  with open(assetfile, 'w') as asset:
      asset.write(lua)

#end functions

#create dirs
os.makedirs('data', exist_ok=True)
os.makedirs('assets', exist_ok=True)

#get needed files
urls = [
    "http://lroc.sese.asu.edu/geojson/apollo_14_eva1_cdr_shepard_point.geojson",
    "http://lroc.sese.asu.edu/geojson/apollo_14_eva2_cdr_shepard_point.geojson",
    "http://lroc.sese.asu.edu/geojson/apollo_14_eva1_lmp_mitchell_point.geojson", 
    "http://lroc.sese.asu.edu/geojson/apollo_14_eva2_lmp_mitchell_point.geojson"]
for url in urls:
    parse = urllib.parse.urlparse(url)
    filename = os.path.basename(parse.path)
    savepath = "data/" + filename
    if not os.path.exists(savepath):
        urllib.request.urlretrieve(url, savepath)

#create traversals setup
eva1start = 34612933
eva2start = 34719075
shep_eva1_end = create_traversal("data/apollo_14_eva1_cdr_shepard_point.geojson", 
    "assets/apollo_14_eva1_cdr_shepard_traversal.asset", eva1start)
shep_eva2_end = create_traversal("data/apollo_14_eva2_cdr_shepard_point.geojson", 
    "assets/apollo_14_eva2_cdr_shepard_traversal.asset", eva2start)

mitch_eva1_end = create_traversal("data/apollo_14_eva1_lmp_mitchell_point.geojson", 
    "assets/apollo_14_eva1_lmp_mitchell_traversal.asset", eva1start)
mitch_eva2_end = create_traversal("data/apollo_14_eva2_lmp_mitchell_point.geojson", 
    "assets/apollo_14_eva2_lmp_mitchell_traversal.asset", eva2start)

#create assets
create_asset("assets/apollo_14_eva1_cdr_shepard_traversal.asset",
    "assets/apollo_14_eva1_cdr_shepard.asset",
    eva1start, shep_eva1_end, "{ 0.54, 0.95, 0.89 }")
create_asset("assets/apollo_14_eva2_cdr_shepard_traversal.asset",
    "assets/apollo_14_eva2_cdr_shepard.asset",
    eva2start, shep_eva2_end, "{ 1.0, 0.23, 0.13 }")

create_asset("assets/apollo_14_eva1_lmp_mitchell_traversal.asset",
    "assets/apollo_14_eva1_lmp_mitchell.asset",
    eva1start, mitch_eva1_end, "{ 0.22, 0.74, 0.49 }")
create_asset("assets/apollo_14_eva2_lmp_mitchell_traversal.asset",
    "assets/apollo_14_eva2_lmp_mitchell.asset",
    eva2start, mitch_eva1_end, "{ 1.0, 0.71, 0.55 }")
