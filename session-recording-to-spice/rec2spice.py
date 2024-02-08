#rec2spice.py
import os
import sys
import textwrap
import platform
from astropy.time import TimeDelta, Time
from astropy import units as u
import spiceypy

#read the recording file into Lines array
filename = sys.argv[1]
if (filename[0:2] == ".\\"):
    filename = filename[2:]
file = open(filename, 'r')
Lines = file.readlines()

newname = filename.split(".")[0]

myfile = newname + ".bsp"
# If file exists, delete it.
if os.path.isfile(myfile):
    os.remove(myfile)

#string in file that represents switching targets
SWITCHSTR = 'openspace.setPropertyValueSingle("NavigationHandler.OrbitalNavigator.Anchor'
#our made up ID for the camera
SPICE_ID = -20010024
#mapping of naif codes to openspace identifiers
NAIF_CODES = {
    'Moon': 301,
    'Earth': 399,
    'Mars': 499,
}

#loop thru lines of file to create 'frames' for each segment of the recording based on target
count = 0
masterFrames = []
frames = []
for line in Lines:
    components = line.split(" ")
    focus = ''
    if (components[0] == 'camera'):
        frames.append({'et':float(components[3]),
                        'x': float(components[4]),
                        'y': float(components[5]),
                        'z': float(components[6]),
                        'i': float(components[7]),
                        'j': float(components[8]),
                        'k': float(components[9]),
                        'l': float(components[10]),
                        'focus': components[-1].strip()})
    elif (SWITCHSTR in line):
        #focus is switched, add frames to master list and create new list
        masterFrames.append(frames)
        frames = []
    count += 1
masterFrames.append(frames) #add final list of frames to master list

et_start = masterFrames[0][0]['et']
et_end = masterFrames[-1][-1]['et']

#astropy conver
#iso_start = (Time(2000, format='jyear') + TimeDelta(et_start*u.s)).iso
#iso_end = (Time(2000, format='jyear') + TimeDelta(et_end*u.s)).iso

#spicepyconvert
spiceypy.spiceypy.furnsh('naif0012.tls')
iso_start = spiceypy.spiceypy.et2utc(et_start, 'ISOC', 8)
iso_end = spiceypy.spiceypy.et2utc(et_end, 'ISOC', 8)

print(f"start {iso_start} | end {iso_end}")

#loop throu master list and add velocities 
for frames in masterFrames:
    count = 0
    framecount = len(frames)
    for frame in frames:
        if ( (count > 0) and (count < framecount-1) ): #skip first and last frames when calc'ing central difference 
            dt = frames[count+1]['et'] - frames[count-1]['et']
            dx = frames[count+1]['x']  - frames[count-1]['x']
            dy = frames[count+1]['y'] - frames[count-1]['y']
            dz = frames[count+1]['z'] - frames[count-1]['z']
            frame['vx'] = dx/dt
            frame['vy'] = dy/dt
            frame['vz'] = dz/dt
        count += 1
    #ditch first and last frames with no velocity
    frames.pop(0)
    frames.pop(-1)

for frames in masterFrames:
    focus = frames[0]['focus']
    #create .dat _position files formatted for spice with one lines per frame
    with open(focus + '_pos' + '.dat', 'w') as f:
        for frame in frames:
            line = "{}, {}, {}, {}, {}, {}, {}\n".format(
                frame['et'], frame['x'], frame['y'], frame['z'], frame['vx'], frame['vy'], frame['vz'])
            f.write(line)
        f.close()
    #create .dat _orientation files formatted for spice with one lines per frame
    with open(focus + '_ori' + '.dat', 'w') as f:
        for frame in frames:
            line = "{}, {}, {}, {}, {}\n".format(
                frame['et'], frame['i'], frame['j'], frame['k'], frame['l'])
            f.write(line)
        f.close()
    #generate setup.mkspk
    center_id = NAIF_CODES[focus]
    if (not center_id):
        print("Existing due to error looking up naif id for " + focus)
        exit(-1)
    with open(focus+".mkspk", 'w') as f:
        mkspk = """\\begindata\n
            INPUT_DATA_TYPE   = 'STATES'
            DATA_ORDER        = 'epoch x y z vx vy vz '
            DATA_DELIMITER    = ','
            LINES_PER_RECORD  = 1
            PRODUCER_ID       = 'OpenSpace (rec2spice)'
            OUTPUT_SPK_TYPE   = 13
            INPUT_DATA_UNITS  = ('DISTANCES=METERS')
            CENTER_ID         = %s
            OBJECT_ID         = %s
            REF_FRAME_NAME    = 'GALACTIC'
            LEAPSECONDS_FILE  = 'naif0012.tls'
            INPUT_DATA_FILE   = '%s'
            OUTPUT_SPK_FILE   = '%s.bsp'
            COMMENT_FILE      = 'commnt.txt'
            POLYNOM_DEGREE    = 9
            TIME_WRAPPER      = '# ETSECONDS'
            APPEND_TO_OUTPUT  = 'YES'
        \\begintext\n""" % (str(center_id), SPICE_ID, focus + '_pos.dat', newname)
        textwrap.dedent(mkspk)
        f.write(mkspk)
        f.close()
        os.system(f"mkspk.exe -setup {focus}.mkspk")

with open(newname+".asset", 'w') as f:
    asset_str = """    
    local sun = asset.require("scene/solarsystem/sun/sun")
    local name = '%s'
    local kernel = asset.localResource(name .. '.bsp')
    local pos = {
        Identifier = name .. '_pos',
        Parent = 'Moon',
        Transform = {
            Translation = {
                Type = "SpiceTranslation",
                Target = "%s",
                Observer = '301',
                Frame = "IAU_MOON"
            }
        },
        Renderable = {
            Type="RenderableModel",
            GeometryFile = asset.localResource('xwing.glb'),
            LightSources = {
                {
                    Type = "CameraLightSource",
                    Intensity = 0.6
                }
            }
        },
        GUI = {
            Path = '/SS7',
            Name = name .. " position"
        }
    }
    """ % (newname, SPICE_ID)

    asset_str += """local trail = {
        Identifier = name .. '_trail',
        Parent = "Moon",
        Renderable = {
            Type = "RenderableTrailTrajectory",
            Translation = {
                Type = "SpiceTranslation",
                Target = "%s",
                Observer = '301',
                Frame = "IAU_MOON"
            },
            Color = { 0.9, 0.9, 0.0 },
            StartTime = '%s',
            EndTime = '%s',
            SampleInterval = 1,
            TimeStampSubsampleFactor = 1,
            EnableFade = false,
            ShowFullTrail = true
        },
        GUI = {
            Path = '/SS7',
            Name = name .. " trail"
        }
    }
    """ % (SPICE_ID, iso_start, iso_end)

    asset_str += """
    asset.onInitialize(function()
        openspace.spice.loadKernel(kernel)
        openspace.addSceneGraphNode(pos)
        openspace.addSceneGraphNode(trail)
    end)

    asset.onDeinitialize(function()
        openspace.removeSceneGraphNode(pos)
        openspace.removeSceneGraphNode(trail)
        openspace.spice.unloadKernel(kernel)
    end)
    """
    asset_str = textwrap.dedent(asset_str)
    f.write(asset_str)
    f.close()
