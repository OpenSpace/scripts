import os

def rename_images(folder_path):
    for filename in os.listdir(folder_path):
        if filename.endswith(".png"):
            parts = filename.split('-')
            if len(parts) >= 5:
                base_name = '-'.join(parts[:-1])
                last_part = parts[-1].replace('.png', '')

                new_name = f"{base_name}T{last_part}-00-000.png"
                old_path = os.path.join(folder_path, filename)
                new_path = os.path.join(folder_path, new_name)

                os.rename(old_path, new_path)
                print(f'Renamed: {filename} -> {new_name}')

folder_path = 'C:/Users/alundkvi/Documents/work/scripts/oval_geojsons_south/combined_images_namechange'
rename_images(folder_path)