#rec2spice.py
import os
import sys
import textwrap
import platform
from astropy.time import TimeDelta, Time
from astropy import units as u
import spiceypy

spiceypy.spiceypy.furnsh('naif0012.tls')

#read the recording file into Lines array
filename = sys.argv[1]
if (filename[0:2] == ".\\"):
    filename = filename[2:]
file = open(filename, 'r')
Lines = file.readlines()

newname = filename.split(".")[0]

shot = sys.argv[2]
version = sys.argv[3]
SPICE_ID = f"-7{shot.zfill(2)}{version}"
SPICE_ID_POS = SPICE_ID[1:]
bspfile = newname + ".bsp"
ckfile = newname + ".bsp"
sclkfile = "ss7_" + SPICE_ID_POS + ".sclk"
fkfile = SPICE_ID_POS + ".tf"
# If file exists, delete it.
if os.path.isfile(bspfile):
    os.remove(bspfile)
if os.path.isfile(ckfile):
    os.remove(ckfile)
if os.path.isfile(sclkfile):
    os.remove(sclkfile)
if os.path.isfile(fkfile):
    os.remove(fkfile)

#string in file that represents switching targets
SWITCHSTR = 'openspace.setPropertyValueSingle("NavigationHandler.OrbitalNavigator.Anchor'
#our made up ID for the camera

#mapping of naif codes to openspace identifiers
NAIF_CODES = {
    'Moon': 301,
    'Earth': 399,
    'Mars': 499,
}

IFRAMES = {
    'Moon': 'IAU_MOON',
    'Earth': 'IAU_EARTH',
}

#loop thru lines of file to create 'frames' for each segment of the recording based on target
count = 0
masterFrames = []
frames = []
focus = ''

for line in Lines:
    components = line.split(" ")
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
        focus = components[-1].strip()
    elif (SWITCHSTR in line):
        newfocus = line[line.rindex(',')+3: -3]
        if (focus != newfocus):
            #focus is switched, add frames to master list and create new list
            masterFrames.append(frames)
            frames = []
            focus = newfocus
    count += 1
masterFrames.append(frames) #add final list of frames to master list

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
        mkspk = """\\begindata
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
            OUTPUT_SPK_FILE   = 'ss7_%s.bsp'
            COMMENT_FILE      = 'commnt.txt'
            POLYNOM_DEGREE    = 11
            TIME_WRAPPER      = '# ETSECONDS'
            APPEND_TO_OUTPUT  = 'YES'
        \\begintext\n""" % (str(center_id), SPICE_ID, focus + '_pos.dat', SPICE_ID[1:])
        textwrap.dedent(mkspk)
        f.write(mkspk)
        f.close()
        mkcmd =  "mkspk.exe" if platform.system() == 'Windows' else "mkspk"
        os.system(f"{mkcmd} -setup {focus}.mkspk >/dev/null 2>&1")
    #generate ss7_SPICEID.fk
    FRAME_NAME = f"SS7_SHOT_{shot}_VERSION_{version}"
    with open(f"ss7_{SPICE_ID[1:]}.tf", 'w') as f:
        fkfile = """
        \\begindata
            FRAME_%s     = %s000
            FRAME_%s000_NAME        = '%s'
            FRAME_%s000_CLASS       = 3
            FRAME_%s000_CLASS_ID    = %s000
            FRAME_%s000_CENTER      = %s
            CK_%s000_SCLK           = %s
            CK_%s000_SPK            = %s
        \\begintext
        """ % (FRAME_NAME, SPICE_ID, SPICE_ID, FRAME_NAME, 
               SPICE_ID, SPICE_ID, SPICE_ID,
               SPICE_ID, SPICE_ID, SPICE_ID,
               SPICE_ID, SPICE_ID, SPICE_ID)
        f.write(fkfile)
        f.close()
    #generate setup.msopck
    SCLK_STR = "MAKE_FAKE_SCLK"
    if os.path.isfile(sclkfile):
        SCLK_STR = "SCLK_FILE_NAME"
    with open(focus+".msopck", 'w') as f:
        msopck = """
        \\begindata
 
        LSK_FILE_NAME           = 'naif0012.tls'
        %s          = '%s'
        FRAMES_FILE_NAME        = 'ss7_%s.tf'
    
        INTERNAL_FILE_NAME      = '%s'
        COMMENTS_FILE_NAME      = 'commnt.txt'
    
        CK_TYPE                 = 3
        CK_SEGMENT_ID           = 'CAMERA ROTATION'
        INSTRUMENT_ID           = %s
        REFERENCE_FRAME_NAME    = '%s'
        ANGULAR_RATE_PRESENT    = 'NO'

        INPUT_TIME_TYPE         = 'ET'
        INPUT_DATA_TYPE         = 'MSOP QUATERNIONS',
        
        PRODUCER_ID             = 'rec2spice.py'
 
        \\begintext
        """ % (SCLK_STR, sclkfile, SPICE_ID_POS, focus + '_ori.dat', f"{SPICE_ID}000", IFRAMES[focus])
        textwrap.dedent(mkspk)
        f.write(msopck)
        f.close()
        mkcmd =  "msopck.exe" if platform.system() == 'Windows' else "msopck"
        syscmd = f"{mkcmd} {focus}.msopck {focus}_ori.dat ss7_{SPICE_ID_POS}.bc >/dev/null 2>&1"
        os.system(syscmd)

with open(f"ss7_{SPICE_ID_POS}.asset", 'w') as f:
    asset_str = """    
    local sun = asset.require("scene/solarsystem/sun/sun")
    local name = '%s'
    local Kernels = {
        asset.localResource('ss7_%s' .. '.sclk'),
        asset.localResource('ss7_%s' .. '.tf'),
        asset.localResource('ss7_%s' .. '.bsp'),
        asset.localResource('ss7_%s' .. '.bc')
    }
    
    local pos = {
        Identifier = name .. '_pos',
        Parent = 'SolarSystemBarycenter',
        Transform = {
            Translation = {
                Type = "SpiceTranslation",
                Target = "%s",
                Observer = '0',
                Frame = "GALACTIC"
            },
            Rotation = {
                Type = "SpiceRotation",
                SourceFrame = "%s",
                DestinationFrame = 'GALACTIC',
            }
        },
        GUI = {
            Path = '/SS7',
            Name = name .. " position"
        }
    }

    local renderable = {
        Identifier = '%s_visual',
        Parent = pos.Identifier,
        Renderable = {
            Type="RenderableSphericalGrid",
            Size = {1500, 25000},
            Color = {0.4, 0.8, 0}
        },
        GUI = {
            Path = '/SS7',
            Name = name .. " visual"
        }
    }

    local trails = {}
    """ % (newname,SPICE_ID_POS,SPICE_ID_POS, SPICE_ID_POS, SPICE_ID_POS, SPICE_ID, f"SS7_SHOT_{shot}_VERSION_{version}", SPICE_ID_POS)
    # print("num : %s" % len(masterFrames))
    for frames in masterFrames:
        et_start = frames[0]['et']
        et_end = frames[-1]['et']
        iso_start = spiceypy.spiceypy.et2utc(et_start, 'ISOC', 8)
        iso_end = spiceypy.spiceypy.et2utc(et_end, 'ISOC', 8)

        focus = frames[0]['focus']
        asset_str += """local %s_trail = {
            Identifier = '%s_trail',
            Parent = "%s",
            Renderable = {
                Type = "RenderableTrailTrajectory",
                Translation = {
                    Type = "SpiceTranslation",
                    Target = "%s",
                    Observer = '%s',
                    Frame = "%s"
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
                Name = name .. "_%s trail"
            }
        }\n
        table.insert(trails, %s_trail)
        """ % (focus, focus, focus, SPICE_ID,  NAIF_CODES[focus], IFRAMES[focus], iso_start, iso_end, focus, focus)

    asset_str += """
    asset.onInitialize(function()
        openspace.spice.loadKernel(Kernels)
        openspace.addSceneGraphNode(pos)
        openspace.addSceneGraphNode(renderable)
        for _, n in ipairs(trails) do
            openspace.addSceneGraphNode(n);
        end
    end)

    asset.onDeinitialize(function()
        openspace.removeSceneGraphNode(renderable)
        openspace.removeSceneGraphNode(pos)
        for _, n in ipairs(trails) do
            openspace.removeSceneGraphNode(n);
        end
        openspace.spice.unloadKernel(Kernels)
    end)
    """
    asset_str = textwrap.dedent(asset_str)
    f.write(asset_str)
    f.close()




###########END
#astropy conver
#iso_start = (Time(2000, format='jyear') + TimeDelta(et_start*u.s)).iso
#iso_end = (Time(2000, format='jyear') + TimeDelta(et_end*u.s)).iso

#spicepyconvert
# iso_start = spiceypy.spiceypy.et2utc(et_start, 'ISOC', 8)
# iso_end = spiceypy.spiceypy.et2utc(et_end, 'ISOC', 8)

# print(f"start {iso_start} | end {iso_end}")
