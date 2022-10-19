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
    print('Usage: skyskan_convert.py <folder with Display Target Table files> [number of targets per node] [version]')
    exit()

directory = sys.argv[1]

if len(sys.argv) == 3:
    target_count = int(sys.argv[2])
else:
    target_count = 1

if len(sys.argv) == 4:
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
    configuration_name = input('Enter the file name of the XML file that is to be created (default: skyskan.xml)\n') or 'skyskan.xml'
except SyntaxError:
    configuration_name = 'skyskan.xml'

print('\n\n')
while True:
    print('Considered files:')
    node_count = 0
    i = 0
    for f in files:
        print("-> Index = " + str(node_count) + " : " + f)
        i = i + 1
        if (i % target_count == 0):
            node_count = node_count + 1
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
print('Number of nodes: ' + str(node_count))
print('\n\n')

for node_index in range(node_count):
    node = {}
    print('Node (' + str(node_index) + ')')
    try:
        node['ip_address'] = input('Enter IP address (default: localhost): \n') or 'localhost'
    except SyntaxError:
        node['ip_address'] = 'localhost'

    try:
        node['resolutions'] = input('Enter resolution separated by space (default: 2048 1200): \n') or '2048 1200'
    except SyntaxError:
        node['resolutions'] = '2048 1200'

    resolutions = node['resolutions'].split()
    node['resolution_x'] = int(resolutions[0])
    node['resolution_y'] = int(resolutions[1])
    node['viewports'] = [];
    print(node_index)
    for target_index in range(target_count):
        print(target_index)
        file_index = (node_index * target_count) + target_index
        print(file_index)
        file = files[file_index]
        print('file (' + file + ')')
        viewport = {}
        with open(file, 'r') as f:
            current_line = 0
            lines = f.readlines()
            for l in lines:
                if l.startswith('Azimuth='):
                    viewport['azimuth'] = l[len('Azimuth='):].strip()
                elif l.startswith('Elevation='):
                    viewport['elevation'] = l[len('Elevation='):].strip()
                elif l.startswith('FOV='):
                    viewport['fov'] = l[len('FOV='):].strip()
                elif l.startswith('Aspect Ratio='):
                    viewport['aspect'] = l[len('Aspect Ratio='):].strip()
                elif l.startswith('Scissor='):
                    viewport['scissor'] = l[len('Scissor='):].strip()
                    scissors = viewport['scissor'].split()
                    viewport['scissor_left'] = float(scissors[0])
                    viewport['scissor_top'] = float(scissors[1])
                    viewport['scissor_right'] = float(scissors[2])
                    viewport['scissor_bottom'] = float(scissors[3])

                    viewport['scissor_pos'] = [viewport['scissor_left'], viewport['scissor_top']]
                    viewport['scissor_size'] = [viewport['scissor_right'] - viewport['scissor_left'], viewport['scissor_bottom'] - viewport['scissor_top']]
                elif l.startswith('Mesh='):
                    mesh_info = l[len('Mesh='):].split()
                    # Mesh=RGB xx yy
                    viewport['mesh_height'] = int(mesh_info[2])
                    viewport['mesh_width'] = int(mesh_info[1])
                    viewport['mesh_size'] = viewport['mesh_width'] * viewport['mesh_height']

                    size = [viewport['mesh_height'], viewport['mesh_width']]
                    mesh_index = current_line
                    break

                current_line = current_line + 1

            # Compute horizontal field of view in radians and normalized focal length
            HFOV = math.radians(float(viewport['fov']))
            NormFocalLength = 0.5 / math.tan(0.5 * HFOV)

            # Target angles for each side of texture viewport
            TargetLeft = math.atan2(0.5 - viewport['scissor_left'], NormFocalLength)
            TargetRight = math.atan2(viewport['scissor_right'] - 0.5, NormFocalLength)
            TargetTop = math.atan2(0.5 - viewport['scissor_top'], NormFocalLength)
            TargetBottom = math.atan2(viewport['scissor_bottom'] - 0.5, NormFocalLength)

            # Convert back to degrees and simple rounding to 6 decimals
            viewport['left_fov'] = round(math.degrees(TargetLeft),6)
            viewport['right_fov'] = round(math.degrees(TargetRight),6)
            viewport['up_fov'] = round(math.degrees(TargetTop),6)
            viewport['down_fov'] = round(math.degrees(TargetBottom),6)

            # node['left_right_fov'] = float(node['fov']) / 2.0
            # note: 'aspect_ratio' of output display is not related in a trivial way to the texture viewport aspect ratio!
            aspect_ratio = node['resolution_x'] / node['resolution_y']
            # node['up_down_fov'] = (float(node['fov']) / aspect_ratio) / 2.0

            print('Read from configuration file:')
            print('Azimuth: ' + viewport['azimuth'])
            print('Elevation: ' + viewport['elevation'])
            print('FOV: ' + viewport['fov'])
            print('Aspect Ratio: ' + viewport['aspect'])
            print('Scissor: ' + viewport['scissor'])
            print('Mesh starts at line: ' + str(mesh_index))
            print('Mesh size: ' + str(viewport['mesh_size']))

            print('')
            print('Left FOV: ' + str(viewport['left_fov']))
            print('Right FOV: ' + str(viewport['right_fov']))
            print('Up FOV: ' + str(viewport['up_fov']))
            print('Down FOV: ' + str(viewport['down_fov']))
            # Convert mesh into obj
            mesh_data = lines[mesh_index + 1:]
            vertices = []
            uv_coords = []
            for mesh_line in mesh_data:
                i = mesh_line.split()
                if len(i) > 0:
                    vertices.append([i[0], i[1]])
                    uv_coords.append([i[4], str(1.0 - float(i[5]))])

            # create one  obj file for each viewport
            viewport['obj_file'] = file[:-3] + 'obj'
            if viewport['obj_file'].startswith('.\\'):
                viewport['obj_file'] = viewport['obj_file'][2:]
            with open(viewport['obj_file'], 'w') as obj_file:
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

                    scaled_uv_x = (uv_x - viewport['scissor_left']) / (viewport['scissor_size'][0])
                    scaled_uv_y = (uv_y - viewport['scissor_top']) / (viewport['scissor_size'][1])

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
        node['viewports'].append(viewport)
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
        viewport_index = 0
        for vp in n['viewports']:
            
            window_x = 0
            if (viewport_index % 2 == 1):
                window_x = n['resolution_x']
            window_y = 0
            if (viewport_index >= target_count/2):
                window_y = n['resolution_y']
            f.write('    <Window fullScreen="true" name="#{}">\n'.format(current_idx))
            f.write('      <Pos x="{}" y="{}" />\n'.format(window_x, window_y))
            f.write('      <Size x="{}" y="{}" />\n'.format(n['resolution_x'], n['resolution_y']))
            f.write('      <Viewport mesh="{}">\n'.format(vp['obj_file']))
            f.write('        <Pos x="0.0" y="0.0" />\n')
            f.write('        <Size x="1.0" y="1.0" />\n')
            f.write('        <PlanarProjection>\n')

            down = vp['down_fov']
            up = vp['up_fov']
            left = vp['left_fov']
            right = vp['right_fov']
            f.write('          <FOV down="{}" left="{}" right="{}" up="{}" />\n'.format(down, left, right, up))

            heading = vp['azimuth']
            pitch = vp['elevation']
            roll = 0.0
            f.write('          <Orientation heading="{}" pitch="{}" roll="{}" />\n'.format(heading, pitch, roll))
            f.write('        </PlanarProjection>\n')
            f.write('      </Viewport>\n')
            f.write('    </Window>\n')
            viewport_index = viewport_index + 1
        f.write('  </Node>\n\n')

        current_idx = current_idx + 1

    f.write('  <User eyeSeparation="0.065">\n')
    f.write('    <Pos x="0.0" y="0.0" z="0.0" />\n')
    f.write('  </User>\n')
    f.write('</Cluster>\n')
