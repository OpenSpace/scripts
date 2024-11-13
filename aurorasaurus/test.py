import h5py
# from PIL import Image

hdf5_file_path = 'C:/Users/alundkvi/Downloads/mothers_day_storm_data_for_bea/mothers_day_storm_data_for_bea/grid_gillam/rgb/2024/05/11/ut07/20240511_0723_110km_MOSv001_grid_trex-rgb.h5'


# # Function to map data values to colors
# def get_color(value):
#     if value == -999.0:
#         return (0, 0, 0, 0)  # Transparent
#     else:
#         # Normalize the value (assuming a max of 60.0 for scaling, adjust as needed)
#         normalized_value = min(max(value, 0), 60) / 60.0
#         color_value = int(normalized_value * 255)
#         return (color_value, 100, 200, 255)  # RGBA



# # Open the HDF5 file
# with h5py.File(hdf5_file_path, 'r') as f:
#     # Replace 'data/grid' with the correct path to your grid dataset
#     grid = f['data/grid'][:]

# # Choose a specific slice; for example, the first slice along the first dimension
# # Adjust the indices according to your needs (e.g., grid[0] for the first slice)
# selected_slice = grid[0]  # Modify the index to choose different slices if needed

# # Assuming the selected slice is a 2D array, create an image
# grid_height, grid_width = selected_slice.shape

# # Create a new RGBA image
# image = Image.new('RGBA', (grid_width, grid_height))

# # Fill the image with colors based on the selected slice of the grid data
# for y in range(grid_height):
#     for x in range(grid_width):
#         value = selected_slice[y, x]  # Accessing the value from the selected slice
#         color = get_color(value)
#         image.putpixel((x, y), color)

# # Save the image
# image.save('output_image.png')


# import h5py

# # Path to your HDF5 file


# # Open the HDF5 file
# with h5py.File(hdf5_file_path, 'r') as f:
#     # Replace 'data/grid' with the correct path to your grid dataset
#     grid = f['data/grid'][:]
    
#     # Print the shape of the grid
#     print("Shape of the grid:", grid.shape)
    
#     # Print a portion of the 3rd dimension (first slice of the 20 dimension)
#     print("Sample data from the 3rd dimension (first time slice):")
#     for i in range(3):  # Adjust range if necessary
#         print(f"Layer {i}:")
#         print(grid[:, :, i, 0])  # Change the last index as needed

#     # Print a portion of the 20th dimension (first slice of the 3rd dimension)
#     print("Sample data from the 20th dimension (first layer):")
#     for j in range(20):  # Adjust range if necessary
#         print(f"Category {j}:")
#         print(grid[:, :, 0, j])  # Change the first index as needed



# import h5py
# import numpy as np
# import matplotlib.pyplot as plt

# # Open the HDF5 file and read the grid data
# with h5py.File(hdf5_file_path, 'r') as f:
#     grid = f['data/grid'][:]
    
# # Extract the first layer (index 0) of the 3rd dimension
# layer_data = grid[:, :, 0, 0]  # Change the indices if you want a different layer

# # Mask invalid data (-999)
# masked_data = np.ma.masked_equal(layer_data, -999)

# # Reverse the data along the latitude axis
# masked_data = np.flip(masked_data, axis=0)

# # Create a figure with a transparent background
# plt.figure(figsize=(10, 5), dpi=300)
# plt.imshow(masked_data, cmap='viridis', origin='lower', alpha=1)

# # Set transparent background
# plt.gcf().patch.set_alpha(0)
# plt.axis('off')

# # Save the image with transparency
# plt.savefig('layer_image.png', bbox_inches='tight', pad_inches=0, transparent=True)
# plt.close()



import numpy as np
import matplotlib.pyplot as plt
import os


base_directory = 'C:/Users/alundkvi/Downloads/mothers_day_storm_data_for_bea/mothers_day_storm_data_for_bea/grid_gillam/rgb/2024/05/11'

output_directory = 'C:/Users/alundkvi/Downloads/mothers_day_storm_data_for_bea/mothers_day_storm_data_for_bea/grid_gillam/rgb/2024/05/11/images2'

# Create the output directory if it doesn't exist
os.makedirs(output_directory, exist_ok=True)

# Loop through each folder in the base directory
for folder_name in os.listdir(base_directory):
    folder_path = os.path.join(base_directory, folder_name)
    
    # Check if it's a directory
    if os.path.isdir(folder_path):
        # Loop through each HDF5 file in the folder
        for file_name in os.listdir(folder_path):
            if file_name.endswith('.h5'):
                hdf5_file_path = os.path.join(folder_path, file_name)

                # Extract date and time for naming the output image
                parts = file_name.split('_')
                date_str = parts[0]  # e.g., 20240511
                time_str = parts[1]  # e.g., 0425

                # Format the date and time as YYYY-MM-DD-HH-MM
                formatted_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
                formatted_time = f"{time_str[:2]}-{time_str[2:]}-00-000"

                output_image_name = f"{formatted_date}T{formatted_time}.png"
                output_image_path = os.path.join(output_directory, output_image_name)

                # Open the HDF5 file and read the grid data
                with h5py.File(hdf5_file_path, 'r') as f:
                    grid = f['data/grid'][:]
                    
                # Extract the first layer (index 0) of the 3rd dimension
                layer_data = grid[:, :, 0, 0]  # Change the indices for different layer

                # Mask invalid data (-999)
                masked_data = np.ma.masked_equal(layer_data, -999)

                # Reverse the data along the latitude axis
                masked_data = np.flip(masked_data, axis=0)

                
                plt.figure(figsize=(10, 5), dpi=300)
                plt.imshow(masked_data, cmap='viridis', origin='lower', alpha=1)

                # Set transparent background
                plt.gcf().patch.set_alpha(0)
                plt.axis('off')

                # Save the image with transparency
                plt.savefig(output_image_path, bbox_inches='tight', pad_inches=0, transparent=True)
                plt.close()