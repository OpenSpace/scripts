#ezie_l3_to_magfield.py
from sys import argv

import numpy as np
import netCDF4 as nc

def convert_geodetic_to_ecef(lat, lon, alt):
    # WGS84 ellipsoid constants
    a = 6378.137  # semi-major axis in km
    e2 = 6.69437999014e-3  # first eccentricity squared

    lat_rad = np.radians(lat)
    lon_rad = np.radians(lon)

    N = a / np.sqrt(1 - e2 * np.sin(lat_rad)**2)

    x = (N + alt) * np.cos(lat_rad) * np.cos(lon_rad) * 1000 * -1  # convert to meters
    y = (N + alt) * np.cos(lat_rad) * np.sin(lon_rad) * 1000 * 1  # convert to meters
    z = (N * (1 - e2) + alt) * np.sin(lat_rad) * 1000  # convert to meters

    return np.array([x, y, z])

if __name__ == "__main__":
    # load file ezie_l3_20250523_001810_sva_v001_r001.nc4
    
    l3_file = argv[1] if len(argv) > 1 else "ezie_l3_20250523_001810_sva_v001_r001.nc4"
    dataset = nc.Dataset(l3_file)
    print(dataset)
    print(dataset['l3_data'].variables)  # Replace with actual variable name
    points80 = np.zeros(dataset['l3_data'].variables['lat'].shape + (6,))  # 6 for x, y, z, vx, vy, vz
    points110 = np.zeros(dataset['l3_data'].variables['lat'].shape + (6,))  # 6 for x, y, z, je, jn, jd
    #quit()
    print("Points array shape:", points80.shape)

    #loop through the lat and lon variables and convert to ECEF coordinates, then store in points array along with the magnetic field vector
    for i in range(points80.shape[0]):
        for j in range(points80.shape[1]):
            points80[i, j] = np.zeros(6)  # Initialize the 6 components to zero
            lat = dataset['l3_data'].variables['lat'][i][j]
            lon = dataset['l3_data'].variables['lon'][i][j]
            coords80 = convert_geodetic_to_ecef(lat, lon, 80)  # alt = 80 km
            coords110 = convert_geodetic_to_ecef(lat, lon, 110)  # alt = 110 km
            coords80[0] = coords80[0] * -1  # Invert x-coordinate for ECEF
            coords110[0] = coords110[0] * -1  # Invert x-coordinate for ECEF
            points80[i, j, 0:3] = coords80
            points80[i, j, 3:6] = np.array([
                dataset['l3_data'].variables['Be_geod_80'][i][j],
                dataset['l3_data'].variables['Bn_geod_80'][i][j],
                dataset['l3_data'].variables['Bd_geod_80'][i][j]
            ])
            points110[i, j, 0:3] = coords110
            points110[i, j, 3:6] = np.array([
                dataset['l3_data'].variables['Je_110'][i][j] / 1000000,  # Convert from mA/m^2 to A/m^2
                dataset['l3_data'].variables['Jn_110'][i][j] / 1000000,  # Convert from mA/m^2 to A/m^2
                0.0  # No vertical current density component provided, set to 0
            ])

    
    
    #flatten the points array to have shape (N, 9) where N is the total number of points
    points80 = points80.reshape(-1, 6)
    points110 = points110.reshape(-1, 6)

    # output the points array to a csv file
    np.savetxt(l3_file.replace(".nc4", "_80.csv"), points80, delimiter=",", header="x,y,z,vx,vy,vz", comments='')
    np.savetxt(l3_file.replace(".nc4", "_110.csv"), points110, delimiter=",", header="x,y,z,vx,vy,vz", comments='')
    quit()




    # plot the ploints in 3D on a spehere with radius 6371 km (Earth's radius) and the points in blue
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')

    # Plot the points in 3D
    ax.scatter(points[:, 0], points[:, 1], points[:, 2], c='b', marker='o')

    # Draw a sphere with Earth's radius (6371 km)
    u = np.linspace(0, 2 * np.pi, 100)
    v = np.linspace(0, np.pi, 100)
    x_sphere = 6371 * np.outer(np.cos(u), np.sin(v))
    y_sphere = 6371 * np.outer(np.sin(u), np.sin(v))
    z_sphere = 6371 * np.outer(np.ones(np.size(u)), np.cos(v))
    ax.plot_surface(x_sphere, y_sphere, z_sphere, alpha=0.2)

    ax.set_xlabel('X (km)')
    ax.set_ylabel('Y (km)')
    ax.set_zlabel('Z (km)')

    #make the points vectors instead of points
    for i in range(points.shape[0]):
        #normalize the magnetic field vector for better visualization
        mag = np.linalg.norm(points[i, 3:6])
        if mag > 0:
            points[i, 3:6] = points[i, 3:6] / mag
        ax.quiver(points[i, 0], points[i, 1], points[i, 2], points[i, 3], points[i, 4], points[i, 5], length=100, color='r')
    ax.set_title('ECEF Coordinates of EZIE L3 Data Points on Earth Sphere')
    plt.show()

    # l3_data = dataset.variables['l3_variable_name'][:]  # Replace with actual variable name
    # magfield_data = l3_to_magfield(l3_data)
    # print("Converted Magnetic Field Data:", magfield_data)


