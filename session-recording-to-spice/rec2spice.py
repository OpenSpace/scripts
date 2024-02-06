#rec2spice.py

# Using readlines()
file = open('a174.osrectxt', 'r')
Lines = file.readlines()
 
count = 0
# Strips the newline character
frames = []
for line in Lines:
    count += 1
    components = line.split(" ")

    if (components[0] == 'camera'):
        et = components[3]
        x =  components[4]
        y =  components[5]
        z =  components[6]
        focus = components[-1].strip()
        frames.append({'et':float(et), 'x': float(x), 'y': float(y), 'z': float(z), 'focus': focus})

count = 0
framecount = len(frames)
for frame in frames:
    if ( (count > 0) and (count < framecount-1) ):
        dt = frames[count+1]['et'] - frames[count-1]['et']
        dx = abs(frames[count+1]['x']) - abs(frames[count-1]['x'])
        dy = abs(frames[count+1]['y']) - abs(frames[count-1]['y'])
        dz = abs(frames[count+1]['z']) - abs(frames[count-1]['z'])
        frame['vx'] = dx/dt
        frame['vy'] = dy/dt
        frame['vz'] = dz/dt
    count += 1

frames.pop(0)
frames.pop(-1)

with open('states.txt', 'w') as f:
    for frame in frames:
        print(frame)
        line = "{}, {}, {}, {}, {}, {}, {}\n".format(
            frame['et'], frame['x'], frame['y'], frame['z'], frame['vx'], frame['vy'], frame['vz'])
        f.write(line)
    f.close()

