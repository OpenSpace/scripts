---hdfToBinary_fluxnodes.py---
The script is a converter from HDF files to binary used for the OpenSpace softwares renderable named renderableFluxNodes.
Note worthy is that your "time file" with the associated time stamp for each hdf file needs to be either a .csv, .dat, .txt 
or without file extention but then atleast with the word "time" in the file name. The time stamps in that time file needs to be
on the last column of each row and in the UTC ISO8601 format (yyyy-mm-ddThh:mm:ss) ex. 2000-07-14T09:50:44.270

---Requires---
python package pyhdf

---Usage---
Put in same folder as your .hdf files
Run by writing:		python hdfToBinary_fluxnodes.py -energyBin <energy bin>

---Parse arguments---
Replace <energy bin> with either emin01 or emin03. (emin03 is default and corresponds to >100MeV)
