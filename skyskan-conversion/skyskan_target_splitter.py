#target_splitter.py

import sys

# Usage information and default values
if len(sys.argv) < 2:
    print('Usage: skyskan_target_splitter.py <folder with Display Target Table files>')
    exit()

input_folder = sys.argv[1]
output_folder = input_folder + '_split/'

import os
import shutil

if not os.path.exists(output_folder):
    os.makedirs(output_folder)
else:
    shutil.rmtree(output_folder)
    os.makedirs(output_folder)

print('Output folder created: ' + output_folder)

# Process each file in the input folder
for filename in os.listdir(input_folder):
    if filename.endswith('.txt'):
        input_file_path = os.path.join(input_folder, filename)
        with open(input_file_path, 'r') as infile:
            lines = infile.readlines()
        
        target_count = 0
        targets = []
        current_target = ["[TARGET]\n"]
        
        for line in lines:
            if line.strip() == '[TARGET]':
                if current_target:
                    if target_count > 0:
                        targets.append(current_target)
                        current_target = ["[TARGET]\n"]
                target_count += 1
            else:
                current_target.append(line)
        
        if current_target:
            targets.append(current_target)
        
        # Write each target to a separate file
        for idx, target_lines in enumerate(targets):
            output_file_path = os.path.join(output_folder, f'{filename[:-6]}-{idx + 1}.txt')
            with open(output_file_path, 'w') as outfile:
                outfile.writelines(target_lines)
        
        print(f'Processed {filename}: {target_count} targets found and split.')