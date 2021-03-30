This script picks out a sequence of 2d slizes from non uniform 3d grids of integrated flux from STAT's integrated flux cubes, specified in hdf files and makes it into .png images. 
You can specify different input variables, such as if you want equatorial, meridial or spherical cut. 
The script to run is the one called plot_eq_from_stat_integrated_flux_cube.py which requires psihdf.py to be in the same folder.

Simply put files into a directory and call it as:
python ./plot_eq_from_stat_integrated_flux_cube.py -cubefile <name_of_int_flux_cube> -cutplaneType <choose_cutplane_type> -startIndex <index> -endIndex <index> 

	NOTE: for -cubefile, replace <name_of_int_flux_cube>, like so: int_flux_cube_sp00_emin01_
	NOTE: Script is not 100% generalized for different CME event but specifically created for the bastille day event.

The scripts relies on the following python3 packages:
numpy
pyhdf
h5py
argparse
signal
sys
matplotlib

The most robust way to install these packages (especially pyhdf) is by using a miniconda environment with conda-forge.
