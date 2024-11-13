import os
from PIL import Image

def flip_images_horizontally(folder_path):
    for filename in os.listdir(folder_path):
        if filename.endswith('.png'):
            file_path = os.path.join(folder_path, filename)
            try:
                with Image.open(file_path) as img:
                    flipped_img = img.transpose(Image.FLIP_LEFT_RIGHT)
                    flipped_img.save(file_path)
                    print(f'Flipped: {filename}')
            except Exception as e:
                print(f'Error processing {filename}: {e}')


folder_path = 'C:/Users/alundkvi/Downloads/mothers_day_storm_data_for_bea/mothers_day_storm_data_for_bea/grid_gillam/rgb/2024/05/11/images2'
flip_images_horizontally(folder_path)
