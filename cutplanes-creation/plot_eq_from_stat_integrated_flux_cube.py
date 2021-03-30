#!/usr/bin/env python3
import argparse
import signal
import sys
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import psihdf as ps

mpl.use('Agg') # This can disable plt.show() but is better for remote png saves.

def signal_handler(signal, frame):
        print('You pressed Ctrl+C! Stopping!')
        sys.exit(0)
signal.signal(signal.SIGINT, signal_handler)

def coords(s):
    try:
        r, p = map(float, s.split(','))
        return r,p
    except:
        raise argparse.ArgumentTypeError("Coordinates must be r,p")

def decidetime(timestamp):
    data = pd.read_csv('Timestamps_all_columns.csv', sep=";")
    res = 8.56032 + (data['time'][timestamp] * 24)
    # res = 8.536
    #res = 9.6166 + (data['time'][timestamp]*24)
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
    return returnstring
    #print(originaltime)

def p2c(p,r):
    x = r*np.cos(p)
    y = r*np.sin(p)
    return x,y

def argParsing():

    parser = argparse.ArgumentParser(description='plot_eq_from_stat_integrated_flux_cube:  This tool plots the integrated flux in the r-phi cut nearest to latitude 0 (eq plane).')

    parser.add_argument('-cubefile',
                        help='Run tag name to append filename with. Dont include indexing',
                        dest='file_name_cube',
                        required=True)

    parser.add_argument('-startIndex',
                        help='Start index of both input and output file names',
                        dest='startIndex',
                        required=True)

    parser.add_argument('-endIndex',
                        help='End index of both input and output file names',
                        dest='endIndex',
                        required=True)

    #parser.add_argument('-png_output_name',
    #                    help='Name of png image to write.',
    #                    dest='oFile',
    #                    required=True)

    parser.add_argument('-cutplaneType',
                        help='Name of type of cutplane (must be equatorial, meridial or spherical)',
                        dest='cutplaneType',
                        default='equatorial',
                        required=True)

    parser.add_argument('-AU',
                        help='Radius in AU, Only needed if cutplaneType == spherical',
                        dest='AU',
                        default=177,    # index 177 = 1.0053557 AU, index 166 = 0.719821 AU (Venus), index 145 = 0.38032115 AU (Mercury)
                        required=False)

    parser.add_argument('-rlimit',
                        help='Radius limit for plot axis (AU).  If not set, uses max.',
                        dest='rlimit',
                        required=False)

    parser.add_argument('-cmin',
                        help='Colormap min value (log10)',
                        dest='cmin',
                        default=-2.0,
                        required=False)

    parser.add_argument('-cmax',
                        help='Colormap max value (log10)',
                        dest='cmax',
                        default=5.5,
                        required=False)

    parser.add_argument('-obspos',
                        help='Plot observer at entered position r,phi',
                        dest='obspos',
                        type=coords,
                        nargs=1,
                        required=False)

    return parser.parse_args()


############################# MAIN #############################
## Get input arguments:

args = argParsing()

cmin        = float(args.cmin)
cmax        = float(args.cmax)

startIndex = int(args.startIndex)
endIndex =  int(args.endIndex)

if endIndex < startIndex:
    print('startIndex needs to be bigger than endIndex')
    exit(0)

for index in range(startIndex, endIndex):
    file_name_cube = args.file_name_cube
    if(index == 0):
        file_name_cube = file_name_cube + 't00000' + str(index) + '.hdf'
    elif(index < 10):
        file_name_cube = file_name_cube + 't00000' + str(index) + '.hdf'
    elif(index < 100):
        file_name_cube = file_name_cube + 't0000' + str(index) + '.hdf'
    elif(index < 1000):
        file_name_cube = file_name_cube + 't000' + str(index) + '.hdf'


    #Read first data files:
    rvec,tvec,pvec,cubes = ps.rdhdf_3d(file_name_cube)
    #cubes = np.transpose(cubes)
    rvec = np.array(rvec)
    tvec = np.array(tvec)
    pvec = np.array(pvec)

    proportionX = 8
    proportionY = 8

    if args.cutplaneType == 'equatorial':
        #Get index closest to equatorial plane:
        tval = np.pi/2.0
        tidx = np.searchsorted(tvec, tval, side="left")
        if (tidx > 0):
            if (np.abs(tval-tvec[tidx-1]) < np.abs(tval-tvec[tidx])):
                tidx=tidx-1

        #Extract R-PHI cut:
        cubes_flux = np.squeeze(cubes[:,tidx,:])

        xvec_plot = rvec
        yvec_plot = pvec

        P,R = np.meshgrid(yvec_plot,xvec_plot,indexing='ij')

        #Get coordinates of cube slice (projected to 2D plane):
        xvec_plot,yvec_plot = p2c(P,R)

    elif args.cutplaneType == 'meridial':
        proportionX = 4

        #index 171.833=>309.3 = carrington longitude at earth
        #index 172 -> 309.9 degrees carrington longitude
        cubes_flux = np.squeeze(cubes[172, :, :])

        xvec_plot = rvec
        yvec_plot = tvec

        P,R = np.meshgrid(yvec_plot, xvec_plot, indexing='ij')

        yvec_plot, xvec_plot = p2c(P,R)

    elif args.cutplaneType == 'spherical':
        proportionY = 4

        cubes_flux = np.squeeze(cubes[:, :, int(args.AU)])
        cubes_flux = np.rot90(cubes_flux)
        xvec_plot = pvec
        yvec_plot = tvec

    fig = plt.figure(figsize=[proportionX, proportionY], facecolor=None)
    plot_cube = plt.pcolormesh(xvec_plot, yvec_plot, cubes_flux)

    #axis_cube=plt.gca()
    #axis_cube.set_aspect('equal')
    #plt.ion()
    plt.axis('off')
    plt.set_cmap('CMRmap')
    plt.clim([cmin,cmax])
    #cb=plt.colorbar(fraction=0.025, pad=0.020, aspect=38)
    #cb.set_label(cbstr, fontsize=fsize - 2)
    #cbvals=range(int(cmin),int(cmax+1))
    #cb.set_ticks(cbvals)
    #newlabels = ["$10^{"+str(x)+"}$" for x in cbvals]
    #cb.ax.set_yticklabels(newlabels)
    #cb.ax.tick_params(labelsize=fsize - 4)
    #plt.xlabel('$r\,\,\cos\,\phi$ [AU]', {'fontsize': fsize})
    #plt.ylabel('$r\,\,\sin\,\phi$ [AU]', {'fontsize': fsize})
    #plt.xticks(size=fsize - 2)
    #plt.yticks(size=fsize - 2)
    #plt.axis([-rlimit, rlimit, -rlimit, rlimit])
    #axis_cube.grid(b=True, which='major', color='w', linestyle='-')

    #if plotobs:
        #plt.scatter(
        #        obspos[0], obspos[1], s=75, marker='d', c='#000000',
        #        edgecolors='#888888', linewidth=2)

    outputName = decidetime(index) + '.png'
    print('input name : ', file_name_cube)
    print('ouput name : ', outputName)

    fig.savefig(outputName, bbox_inches='tight', pad_inches=0, dpi=300, facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close(fig)


