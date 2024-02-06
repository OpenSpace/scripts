#rec2spice.py
import sys

filename = sys.argv[1]
# Using readlines()
file = open(filename, 'r')
Lines = file.readlines()


SWITCHSTR = 'openspace.setPropertyValueSingle("NavigationHandler.OrbitalNavigator.Anchor'

count = 0
# Strips the newline character
masterFrames = []
frames = []
for line in Lines:
    count += 1
    components = line.split(" ")

    if (components[0] == 'camera'):
        et = components[3]
        x =  components[4]
        y =  components[5]
        z =  components[6]
        qx =  components[7]
        qy =  components[8]
        qz =  components[9]
        qw =  components[10]
        focus = components[-1].strip()
        frames.append({'et':float(et), 'x': float(x), 'y': float(y), 'z': float(z), 'focus': focus})
    elif (SWITCHSTR in line):
        print("switch focus")
        masterFrames.append(frames)
        frames = []

masterFrames.append(frames)
for frames in masterFrames:
    count = 0
    framecount = len(frames)
    print("frameCount" + str(framecount))
    for frame in frames:
        if ( (count > 0) and (count < framecount-1) ):
            dt = frames[count+1]['et'] - frames[count-1]['et']
            dx = abs(frames[count+1]['x']  - frames[count-1]['x'])
            dy = abs(frames[count+1]['y'] - frames[count-1]['y'])
            dz = abs(frames[count+1]['z'] - frames[count-1]['z'])
            frame['vx'] = dx/dt
            frame['vy'] = dy/dt
            frame['vz'] = dz/dt
        count += 1
    frames.pop(0)
    frames.pop(-1)

print(masterFrames[0][0])
print(masterFrames[1][0])
print("frameCount|" + str(len(masterFrames[0])))
print("frameCount|" + str(len(masterFrames[1])))



for frames in masterFrames:
    with open('states_' + frames[0]['focus'] + '.txt', 'w') as f:
        for frame in frames:
            #print(frame)
            line = "{}, {}, {}, {}, {}, {}, {}\n".format(
                frame['et'], frame['x'], frame['y'], frame['z'], frame['vx'], frame['vy'], frame['vz'])
            f.write(line)
        f.close()

