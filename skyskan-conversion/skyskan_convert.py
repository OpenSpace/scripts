import glob
import os
import sys
import math

# Convert DS/DM geometry to OpenSpace
Latest_Version = 2
master_resolution = [1280, 720]
master_fov = { 'left': 30, 'right': 30, 'up': 16.875, 'down': 16.875}
starting_port = 20400

# Usage information and default values
if len(sys.argv) < 2:
    print('Usage: skyskan_convert.py <folder with Display Target Table files> [version]')
    exit()

directory = sys.argv[1]
if len(sys.argv) == 3:
    version = int(sys.argv[2])
else:
    version = Latest_Version

# Parse the passed directory to find all .txt files and only accept those that start with
# the line
# [TARGET]
# and discard the rest
potential_files = glob.glob(directory + '/*.txt', recursive=True)
files = []
for file in potential_files:
    with open(file, 'r') as f:
        lines = f.readlines()
        if lines[0].strip() == "[TARGET]":
            files.append(file)

# The file names are of the form DMDT-DS-ii-j.txt, so sorting them lexically will not work
# super well, but without knowing more about the naming scheme it's hard to parse them
# correctly
files.sort()

print('\n')
try:
    configuration_name = input('Enter the file name of the XML file that is to be created (default: skyskan.xml)\n')
except SyntaxError:
    configuration_name = 'skyskan.xml'

print('\n\n')
while True:
    print('Considered files:')
    i = 0
    for f in files:
        print("-> Index = " + str(i) + " : " + f)
        i = i + 1
    print('')

    # try:
    #     inp = input('Index of file to remove (or blank line to continue without removal)\n')
    # except SyntaxError:
    #     inp = ''

    # user entering zero breaks us out of the loop
    # if inp == '':
    #     break
    # else:
    #     del files[int(inp)]
    #     if len(files) == 0:
    #         print('Empty list is remaining, exiting...')
    #         exit()
    # print('')
	
    break
	
# print('====================\n')
# print('Remaining files')
# for f in files:
#     print(f)
# print('')


try:
    master_ip = input('Enter the IP address of the master node (default: localhost)\n')
except SyntaxError:
    master_ip = 'localhost'

print('Master IP: ' + master_ip + '\n')

nodes = []
print('Number of nodes: ' + str(len(files)))
print('\n\n')

for i in range(1, len(files) + 1):
    file = files[i - 1]
    print('Node 1 (' + file + ')')

    node = {}

    try:
        node['ip_address'] = input('Enter IP address (default: localhost): \n')
    except SyntaxError:
        node['ip_address'] = 'localhost'

    try:
        node['resolutions'] = input('Enter resolution separated by space (default: 2048 1200): \n')
    except SyntaxError:
        node['resolutions'] = '2048 1200'
    
    resolutions = node['resolutions'].split()
    node['resolution_x'] = int(resolutions[0])
    node['resolution_y'] = int(resolutions[1])


    with open(file, 'r') as f:
        current_line = 0
        lines = f.readlines()
        for l in lines:
            if l.startswith('Azimuth='):
                node['azimuth'] = l[len('Azimuth='):].strip()
            elif l.startswith('Elevation='):
                node['elevation'] = l[len('Elevation='):].strip()
            elif l.startswith('FOV='):
                node['fov'] = l[len('FOV='):].strip()
            elif l.startswith('Aspect Ratio='):
                node['aspect'] = l[len('Aspect Ratio='):].strip()
            elif l.startswith('Scissor='):
                node['scissor'] = l[len('Scissor='):].strip()
                scissors = node['scissor'].split()
                node['scissor_left'] = float(scissors[0])
                node['scissor_top'] = float(scissors[1])
                node['scissor_right'] = float(scissors[2])
                node['scissor_bottom'] = float(scissors[3])

                node['scissor_pos'] = [node['scissor_left'], node['scissor_top']]
                node['scissor_size'] = [node['scissor_right'] - node['scissor_left'], node['scissor_bottom'] - node['scissor_top']]
            elif l.startswith('Mesh='):
                mesh_info = l[len('Mesh='):].split()
                # Mesh=RGB xx yy
                node['mesh_height'] = int(mesh_info[2])
                node['mesh_width'] = int(mesh_info[1])
                node['mesh_size'] = node['mesh_width'] * node['mesh_height']

                size = [node['mesh_height'], node['mesh_width']]
                mesh_index = current_line
                break

            current_line = current_line + 1

        # Compute horizontal field of view in radians and normalized focal length
        HFOV = math.radians(float(node['fov']))
        NormFocalLength = 0.5 / math.tan(0.5 * HFOV)
        
		# Target angles for each side of texture viewport
        TargetLeft = math.atan2(0.5 - node['scissor_left'], NormFocalLength)
        TargetRight = math.atan2(node['scissor_right'] - 0.5, NormFocalLength)
        TargetTop = math.atan2(0.5 - node['scissor_top'], NormFocalLength)
        TargetBottom = math.atan2(node['scissor_bottom'] - 0.5, NormFocalLength)

		# Convert back to degrees and simple rounding to 6 decimals
        node['left_fov'] = round(math.degrees(TargetLeft),6)
        node['right_fov'] = round(math.degrees(TargetRight),6)
        node['up_fov'] = round(math.degrees(TargetTop),6)
        node['down_fov'] = round(math.degrees(TargetBottom),6)

        # node['left_right_fov'] = float(node['fov']) / 2.0
        # note: 'aspect_ratio' of output display is not related in a trivial way to the texture viewport aspect ratio!
        aspect_ratio = node['resolution_x'] / node['resolution_y']
        # node['up_down_fov'] = (float(node['fov']) / aspect_ratio) / 2.0

        print('Read from configuration file:')
        print('Azimuth: ' + node['azimuth'])
        print('Elevation: ' + node['elevation'])
        print('FOV: ' + node['fov'])
        print('Aspect Ratio: ' + node['aspect'])
        print('Scissor: ' + node['scissor'])
        print('Mesh starts at line: ' + str(mesh_index))
        print('Mesh size: ' + str(node['mesh_size']))

        print('')
        print('Left FOV: ' + str(node['left_fov']))
        print('Right FOV: ' + str(node['right_fov']))
        print('Up FOV: ' + str(node['up_fov']))
        print('Down FOV: ' + str(node['down_fov']))
        # Convert mesh into obj
        mesh_data = lines[mesh_index + 1:]
        vertices = []
        uv_coords = []
        for mesh_line in mesh_data:
            i = mesh_line.split()
            if len(i) > 0:
                vertices.append([i[0], i[1]])
                uv_coords.append([i[4], str(1.0 - float(i[5]))])

        # create one  obj file for each node
        node['obj_file'] = file[:-3] + 'obj'
        if node['obj_file'].startswith('.\\'):
            node['obj_file'] = node['obj_file'][2:]
        with open(node['obj_file'], 'w') as obj_file:
            # display vertices positions
            for v in vertices:
                v_x = float(v[0])
                v_y = float(v[1])

                norm_v_x = 2.0 * v_x - 1.0
                norm_v_y = 1.0 - 2.0 * v_y

                its_the_final_value_x = norm_v_x
                its_the_final_value_y = norm_v_y

                obj_file.write('v ' + str(its_the_final_value_x) + ' ' + str(its_the_final_value_y) + ' 0.0\n')
            # texture vertices positions (aka DM target)	
            for uv in uv_coords:
                uv_x = float(uv[0])
                uv_y = float(uv[1])

                scaled_uv_x = (uv_x - node['scissor_left']) / (node['scissor_size'][0])
                scaled_uv_y = (uv_y - node['scissor_top']) / (node['scissor_size'][1])

                its_the_final_uv_x = scaled_uv_x
                its_the_final_uv_y = scaled_uv_y

                obj_file.write('vt ' + str(its_the_final_uv_x) + ' ' + str(its_the_final_uv_y) + '\n')
            # triangles...
            for row in range(0, size[0] - 1):
                for i in range(0, size[1] - 1):
                    i0 = row * size[1] + i
                    i1 = row * size[1] + (i + 1)
                    i2 = (row + 1) * size[1] + (i + 1)
                    i3 = (row + 1) * size[1] + i

                    if float(vertices[i0][0]) == -1.0 or float(vertices[i0][1]) == -1.0 or float(vertices[i1][0]) == -1.0 or float(vertices[i1][1]) == -1.0 or float(vertices[i3][0]) == -1.0 or float(vertices[i3][1]) == -1.0 or float(vertices[i2][0]) == -1.0 or float(vertices[i2][1]) == -1.0:
                        continue

                    vi0 = '{}/{}/{}'.format(i0 + 1, i0 + 1, i0 + 1)
                    vi1 = '{}/{}/{}'.format(i1 + 1, i1 + 1, i1 + 1)
                    vi2 = '{}/{}/{}'.format(i2 + 1, i2 + 1, i2 + 1)
                    vi3 = '{}/{}/{}'.format(i3 + 1, i3 + 1, i3 + 1)

                    first_triangle = 'f {} {} {}'.format(vi3, vi1, vi0)
                    second_triangle = 'f {} {} {}'.format(vi2, vi1, vi3)
                    obj_file.write(first_triangle + '\n')
                    obj_file.write(second_triangle + '\n')

    nodes.append(node)
    print('------')

current_idx = 0
# Writing the XML configuration file
with open(configuration_name, 'w') as f:
    f.write('<?xml version="1.0" ?>\n')
    f.write('<Cluster masterAddress="{}">\n'.format(master_ip))
    f.write('  <!-- Header information -->\n')
    f.write('  <Settings>\n')
    f.write('    <Display swapInterval="0" />\n')
    f.write('  </Settings>\n\n')

    f.write('  <!-- Master Node -->\n')
    f.write('  <Node address="{}" port="{}">\n'.format(master_ip, starting_port))
    f.write('    <Window fullScreen="false" name="OpenSpace">\n')
    f.write('      <Pos x="0" y="0" />\n')
    f.write('      <Size x="{}" y="{}" />\n'.format(master_resolution[0], master_resolution[1]))
    f.write('      <Viewport>\n')
    f.write('        <Pos x="0.0" y="0.0" />\n')
    f.write('        <Size x="1.0" y="1.0" />\n')
    f.write('        <PlanarProjection>\n')
    down = master_fov['down']
    left = master_fov['left']
    right = master_fov['right']
    up = master_fov['up']
    f.write('          <FOV down="{}" left="{}" right="{}" up="{}" />\n'.format(down, left, right, up))
    f.write('          <Orientation heading="0.0" pitch="0.0" roll="0.0" />\n')
    f.write('        </PlanarProjection>\n')
    f.write('      </Viewport>\n')
    f.write('    </Window>\n')
    f.write('  </Node>\n\n')

    current_idx = 1
    for n in nodes:
        f.write('  <!-- Node #{} -->\n'.format(current_idx))
        f.write('  <Node address="{}" port="{}">\n'.format(n['ip_address'], starting_port + current_idx))
        f.write('    <Window fullScreen="true" name="#{}">\n'.format(current_idx))
        f.write('      <Pos x="0" y="0" />\n')
        f.write('      <Size x="{}" y="{}" />\n'.format(n['resolution_x'], n['resolution_y']))
        f.write('      <Viewport mesh="{}">\n'.format(n['obj_file']))
        f.write('        <Pos x="0.0" y="0.0" />\n')
        f.write('        <Size x="1.0" y="1.0" />\n')
        f.write('        <PlanarProjection>\n')

        down = n['down_fov']
        up = n['up_fov']
        left = n['left_fov']
        right = n['right_fov']
        f.write('          <FOV down="{}" left="{}" right="{}" up="{}" />\n'.format(down, left, right, up))

        heading = n['azimuth']
        pitch = n['elevation']
        roll = 0.0
        f.write('          <Orientation heading="{}" pitch="{}" roll="{}" />\n'.format(heading, pitch, roll))
        f.write('        </PlanarProjection>\n')
        f.write('      </Viewport>\n')
        f.write('    </Window>\n')
        f.write('  </Node>\n\n')

        current_idx = current_idx + 1

    f.write('  <User eyeSeparation="0.065">\n')
    f.write('    <Pos x="0.0" y="0.0" z="0.0" />\n')
    f.write('  </User>\n')
    f.write('</Cluster>\n')
