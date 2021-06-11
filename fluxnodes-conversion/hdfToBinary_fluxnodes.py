#!/opt/anaconda3/bin/python
####/usr/local/bin/python


# Hi Peter,
# The hdf4 files do not have metadata.
# These integrated fluxes are not a direct product of either MAS or EPREM, they are created by post-processing EPREM data (which is primarily netcdf).  Here is how they are organized:

# int_flux_cube files:
# Integrated particle fluxes interpolated onto a 3D cube in spherical coordinates (about 16 GB):
# /nobackup/rcaplan/corhel/ut200007140000-custom/cme20000714_v5/sep/int_flux_cube/data/
# 3D hdf4 files with particles fluxes for the different GOES energy channels.
# These are organized exactly like MAS MHD files, with the scales (# of dimensions and r, theta phi), followed by the data values.
# Whatever you are using to read MAS MHD files should work on these.  The data is in log10 of the flux.  Unlike MAS files, r is in AU.  theta and phi are in radians.

# int_flux_time files:
# The integrated particle fluxes on the EPREM nodes (about 28 GB):
# /nobackup/rcaplan/corhel/ut200007140000-custom/cme20000714_v5/sep/int_flux_time/data/
# 3D hdf4 files with particle fluxes at the EPREM nodes, with dimensions  4x<N_STREAMS>x<N_NODES>.
# The 4 values for each node are: <integrated flux, r, t, and p>.
# These should also be readable in the same way as an MAS file, but are organized differently, because of the nature of EPREM data.
# EPREM data is on streams, the streams are a list of nodes that are linked by the flow.
# Here the scales are 1-4 for the first dimension, stream number for the 2nd dimension, and node number for the 3rd dimension.
# log10 of the integrated flux is index 1 of the first dimension, r in AU is index 2, theta and phi in radians are indexes 3 and 4.
#  It take a moment to get your head oriented when scanning through planes of this data.

# For the integrated particle fluxes, the file name label "eMin" indicates the GOES channel.  emin01 is >10Mev, emin02 is >50Mev, and emin03 is >100MeV.
# We also calculate the total integrated flux for all energies and call this emin00, but we don’t typically plot this.  The focus on visualization should be for emin01-emin03.

# Best wishes,
# Jon

from array import array
from pyhdf import SD
import argparse
import datetime
import glob
import json
import math
import numpy as np
import pandas as pd


#   sphCoord[0] = 'R', sphCoord[1] ='Theta', sphCoord[2] ='Phi'
def sphericalToCartesianCoord(r, t, p):
  cartesianPosition = []
  cartesianPosition.append(r * math.sin(t) * math.cos(p))
  cartesianPosition.append(r * math.sin(t) * math.sin(p))
  cartesianPosition.append(r * math.cos(t))
  return cartesianPosition

def argParsing():
  parser = argparse.ArgumentParser(description='This converter converts stream node data from .hdf to binary files used for the OpenSpace softwares renderable named renderableFluxNodes')
  
  parser.add_argument('-energyBin',
                      help='Specify what energy bin to use. \
                      As of now emin01 (>10 MeV) and emin03 (>100 MeV) is supported \
                      It is used to select the right files. Check to make sure the file names',
                      dest='engBin',
                      default='emin03',
                      required=False)
  return parser.parse_args()  


#def corhel_read_hdf4_file(filename,fdata0,fdata1,fdata2,data):
def corhel_read_hdf4_file(filename, _all, _positions, _fluxes, _radiuses):

  print('========================================================')
  print(filename)
  print('========================================================')
  # Dataset names
  dataset2 = 'Data-Set-2'
  fdim0 = 'fakeDim0'           # Longitude in radians
  fdim1 = 'fakeDim1'           # Co-latitude in radians
  fdim2 = 'fakeDim2'           # Radius in AU

  # open the hdf file
  hdf = SD.SD(filename)
  print(hdf)

  datasets = hdf.datasets()
  print('Datasets Summary:')
  print(datasets)

  # select and read the sds data
  sds = hdf.select(dataset2)
  data = sds.get()

  #print(dataset2)
  #print('Shape is ',data.shape)
  #print(data[1999][383][3])

  if "flux_cube" in filename:
    print('Data cube')
    print('Coord 1:  Longitude in radians')
    print('Coord 2:  Co-latitude in radians')
    print('Coord 3:  Radius in AU')


  # For the integrated particle fluxes, the file name label "eMin" indicates the GOES channel.  emin01 is >10Mev, emin02 is >50Mev, and emin03 is >100MeV.
  if "emin00" in filename:
    print('Energy channel: Integrated over all GOES energy channels.')
  if "emin01" in filename:
    print('Energy channel: > 10MeV')
  if "emin02" in filename:
    print('Energy channel: > 50MeV')
  if "emin03" in filename:
    print('Energy channel: > 100MeV')

  # select and read the fakeDim0 data
  #flux is unit of angle,
  #emin is looking at the energy, emin01 is >10Mev flux of particles with energies greater then 10 MeV, emin02.
  #emin is looking at the energy,
  #the flux values values are basically the logs with base 10.
  #Noah looks at energy bins for these channels. Nasa shrag targets 10, 50 and 100 MeV.
  #Flight rules, take action for astronauts.
  #visualize some measurement with goes satellite from this.
  # R, theta, phi.
  # In that model, should be in karrengting frame. Heliographics
  #The earth is moving more rapidly in that coordinate
  # The eprem data is probably in the same coordinate system.
  # See if we can show them as fieldlines between points.
  # Oskar how he got the values for the fieldlines, or the values he had to colorcode the fieldlines.
  # Note from Peter that he wants to ask a question.
  # Are the flux units the same as the Goes flux units: Pfu since they are in intergral channel. It is in the same units as in Goes(?).
  fd0 = hdf.select(fdim0)
  fdata0 = fd0.get()
  #print(fdim0)
  #print('Shape is ',fdata0.shape)
  #print('Range: ',str(fdata0[0]),' to ',str(fdata0[-1]))
  #print('testar fdata0', fdata0)

  # select and read the fakeDim1 data
  fd1 = hdf.select(fdim1)
  fdata1 = fd1.get()
  #print(fdim1)
  #print('Shape is ',fdata1.shape)
  #print('Range: ',str(fdata1[0]),' to ',str(fdata1[-1]))
  #print(fdata1)

  # select and read the fakeDim2 data
  fd2 = hdf.select(fdim2)
  fdata2 = fd2.get()
  #print(fdim2)
  #print('Shape is ',fdata2.shape)
  #print('Range: ',str(fdata2[0]),' to ',str(fdata2[-1]))
  #print('Testdatadim2', str(fdata2[0]))
  #print(fdata2)

  #for i in range(0, 10):
      #for j in range(0, 15):
          #print(' Stream:' + str(i) + 'Node: ' + str(j) + ' Phi: ', np.degrees(data[i][j][3]), 'Theta: ', np.degrees(data[i][j][2]), 'R in Au', data[i][j][1], 'Flux', data[i][j][0])
  # Terminate access to the data set
  nStreams = data.shape[1]
  nNodes = data.shape[0]
  print("nodes: ", nNodes, "streams: ", nStreams)

  sds.endaccess()

  # Terminate access to the SD interface and close the file
  hdf.end()

  AuToMeter = 149597870700.0

#  alldata = {}
  for j in range(0, nStreams): #nStreams
       #j is streams
      # i is nodes
      for i in range(0, nNodes): #nNodes
          
          Flux = data[i][j][0]
          R = data[i][j][1]
          R = R*AuToMeter
          Theta = data[i][j][2]
          Phi = data[i][j][3]

          sphCor = sphericalToCartesianCoord(R, Theta, Phi)
          x= sphCor[0]
          y= sphCor[1]
          z= sphCor[2]
          _positions.append(x)
          _positions.append(y)
          _positions.append(z)
          _fluxes.append(Flux)
          _radiuses.append(R)

          #_all.append(Flux)
          #_all.append(R)
          #_all.append(x)
          #_all.append(y)
          #_all.append(z)

      #end of for
#     alldata['stream' + str(j)] = tempDataArrayAll

      #tempDataArrayAll = []
  #end of for

# _all.append(alldata)


  return data

def decidetime(timestamp):
     data = pd.read_csv('Timestamps_all_columns.csv', sep=";")
     #print(data['time'][timestamp])
     #print(data.head(timestamp))
     #dt = timedelta(days=0, hours=0, minutes=0, seconds=0)
     #09.62 timestamp for the first
     #96.46?
     #should it be  * 24?
     #res = 8.3999 + (data['time'][timestamp] * 24)
     #res = 8.589 + (data['time'][timestamp] * 24)
     #08.48 => 08:33
     #09.46 => 09:27
     # 09:27 + 4:50 = 09:32:25

     # 11:09 First sign of CME
     #res = 8.548 + (data['time'][timestamp] * 24)
     #08.5601
     #res = 8.5362 + (data['time'][timestamp] * 24)
     #res = 8.6372 + (data['time'][timestamp] * 24)
     #res = 9.6166 + (data['time'][timestamp]*24)
     res = 8.56032917 + (data['time'][timestamp]*24)
     
     #print(res)
     hour = str(int(res))
     minute = str(int((res - int(res))*60.0))
     second = str(int( ((res - int(res))*60 - int((res - int(res))*60  ))*60.0))

     hour_s = hour.zfill(2)
     minute_s = minute.zfill(2)
     second_s = second.zfill(2)
     #print(datetime.time(hour, minute, second).strftime('%H:%M:%S'))
     #print(str(hour) + ':' + str(minute))

     returnstring = '2000-07-14T' + hour_s + '-' + minute_s + '-' + second_s + '-000'
     #secs_per_day = 24*60*60
     #dt.total_seconds()/secs_per_day
     #originaltime = datetime.date(2000, 7, 14)
     #print(returnstring)
     return returnstring
     #print(originaltime)

if __name__ == '__main__':

  #filename = 'int_flux_cube_sp00_emin03_t000255.hdf'
  #corhel_read_hdf4_file(filename)
  #corhel_read_hdf4_file(filename,fdata0,fdata1,fdata2,data)
  #filename = 'intfluxsp00emin00t000255.hdf'

  import timeit

  start = timeit.default_timer()
  args = argParsing()
  engBin = args.engBin

  _all = []
  _positions =[]
  _fluxes = []
  _radiuses = []

  filesInDirectory = []
  for file in sorted(glob.glob("*.hdf")):
    filesInDirectory.append(file)

  nHdfFiles=len(filesInDirectory)
      #Temp number of files
  #nHdfFiles = 2
  #nStreams = data.shape[1]
  #nNodes = data.shape[0]
  
  #nParameters = 5 # 3 position, 1 radius, 1 flux 
  
  #_positions.append(np.uint8(2))
  #_positions.append(np.uint32())
    #_fluxes.append(np.uint8(2))
  #_radiuses.append(np.uint8(2))
  #np.append(_all, np.uint8(2))
  #_all.append(np.uint8(2))
  for i in range(nHdfFiles):

  #filename = 'int_flux_sp00_emin01_t000' + str(201) + '.hdf'
  #corhel_read_hdf4_file(filename, 201)

    if(i == 0):
      #outfilename = decidetime(i)
      #print("first time step: ", outfilename)
      filename = 'int_flux_sp00_'+ engBin +'_t00000' + str(i) + '.hdf'
      corhel_read_hdf4_file(filename, _all, _positions, _fluxes, _radiuses)
    elif(i < 10):
      #outfilename = decidetime(i)
      filename = 'int_flux_sp00_'+ engBin +'_t00000' + str(i) + '.hdf'
      corhel_read_hdf4_file(filename, _all, _positions, _fluxes, _radiuses)
    elif(i < 100):
      #outfilename = decidetime(i)
      filename = 'int_flux_sp00_'+ engBin +'_t0000' + str(i) + '.hdf'
      corhel_read_hdf4_file(filename, _all, _positions, _fluxes, _radiuses)
    elif(i < 275):
      #outfilename = decidetime(i) 
      filename = 'int_flux_sp00_'+ engBin +'_t000' + str(i) + '.hdf'
      corhel_read_hdf4_file(filename, _all, _positions, _fluxes, _radiuses)

    print("============= End of conversion of one file ==================")

  nrOfNodes = len(_fluxes)
  nrOfNodesPerTimeStep = nrOfNodes/nHdfFiles
  nrOfNodesPerTimeStep_int = int(nrOfNodesPerTimeStep)
  
  if not nrOfNodesPerTimeStep.is_integer():
    print("Code exited before creating file because number of nodes per timestep/hdf-file was not consistent")
    exit()
  #else:

  float_array_fluxes = array('f', _fluxes)
  outfileBinaryFluxes = open("fluxes_"+engBin, 'wb')  # wb = write binary
  float_array_fluxes.tofile(outfileBinaryFluxes)

  float_array_radiuses = array('f', _radiuses)
  outfileBinaryRadiuses = open("radiuses_"+engBin, 'wb')
  float_array_radiuses.tofile(outfileBinaryRadiuses)

  nrOfNodesPerTimeStep_int = [nrOfNodesPerTimeStep_int]
  numberOfElements = array('L', nrOfNodesPerTimeStep_int)
  nHdfFiles = [nHdfFiles]
  nrOfFiles = array('L', nHdfFiles)
  float_array_positions = array('f', _positions)
  outfileBinaryPositions = open("positions_"+engBin, 'wb')
  numberOfElements.tofile(outfileBinaryPositions)
  nrOfFiles.tofile(outfileBinaryPositions)
  float_array_positions.tofile(outfileBinaryPositions)

  #float_array_all = array('f', _all)
  #outfileBinaryAll = open("all", 'wb')
  #float_array_all.tofile(outfileBinaryAll)
  
  stop = timeit.default_timer()

  print("Number of timesteps: ", _positions[0], _positions[1], _positions[2], _positions[3], _positions[4], _positions[5], "(should be noStreams * noNodes per stream when read as uint32.)")
  print("but here its interpreted as somthing else.")
  print("Successfully run script. Total time: ", stop - start)
  exit(0)
