#rec2spice.py

#read the recording file into Lines array
import sys
filename = sys.argv[1]
file = open(filename, 'r')
Lines = file.readlines()

#string in file that represents switching targets
SWITCHSTR = 'openspace.setPropertyValueSingle("NavigationHandler.OrbitalNavigator.Anchor'

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

#loop throu master list and add velocities 
for frames in masterFrames:
    count = 0
    framecount = len(frames)
    for frame in frames:
        if ( (count > 0) and (count < framecount-1) ): #skip first and last frames when calc'ing central difference 
            dt = frames[count+1]['et'] - frames[count-1]['et']
            dx = abs(frames[count+1]['x']  - frames[count-1]['x'])
            dy = abs(frames[count+1]['y'] - frames[count-1]['y'])
            dz = abs(frames[count+1]['z'] - frames[count-1]['z'])
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
        mkspk = """\\begindata\n\
            INPUT_DATA_TYPE   = 'STATES'\n\
            DATA_ORDER        = 'epoch x y z vx vy vz '\n\
            DATA_DELIMITER    = ','\n\
            LINES_PER_RECORD  = 1\n\
            PRODUCER_ID       = 'OpenSpace (rec2spice)'\n\
            OUTPUT_SPK_TYPE   = 9\n\
            INPUT_DATA_UNITS  = ('DISTANCES=METERS')\n\
            OBJECT_ID         = -20010024\n\
            CENTER_ID         = %s\n\
            REF_FRAME_NAME    = 'J2000'\n\
            LEAPSECONDS_FILE  = 'naif0012.tls'\n\
            INPUT_DATA_FILE   = '%s'\n\
            OUTPUT_SPK_FILE   = '%s.bsp'\n\
            COMMENT_FILE      = 'commnt.txt'\n\
            POLYNOM_DEGREE    = 9\n\
            TIME_WRAPPER      = '# ETSECONDS'\n\
            APPEND_TO_OUTPUT  = 'YES'\n\
        \\begintext\n""" % (str(center_id), focus + '_pos.dat', filename)
        f.write(mkspk)
        f.close()

# with open(focus+".mkspk", 'w') as f:
#         mkspk = """\\begindata\n\
#             INPUT_DATA_TYPE   = '%s'\n\
#             APPEND_TO_OUTPUT  = 'YES'\n\
#         \\begintext\n""" % (str(center_id), focus + '_pos.dat', filename)
#         f.write(mkspk)
#         f.close()


