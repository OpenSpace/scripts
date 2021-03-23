## OpenSpace Jupyter Notebooks


# Purpose

These notebooks are ment to give examples of both how to use Jupyter Notebooks with OpenSpace
as well as to demonstrate sample use cases

# Examples

 - **GeoTiff-Import** : This notebook takes the path to a download geotiff, and uses the 
 'osgeo' package to convert the geotiff projection into longlat which is expected by
 OpenSpace. Along with converting the geotiff, this nodebook creates the .vrt and .info
 files needed to create the layer on a globe. Then adds the layer using the websocket api.

  - **StarTrails** : This notebook manipulates OpenSpace via the websocket api, outputs 
  screenshots, and then simulates 'astrophotragraphy stacking' of those screenshots. 
  Inspired by [https://ccnyplanetarium.org/posts/2020/06/23/martian-star-trails.html](https://ccnyplanetarium.org/posts/2020/06/23/martian-star-trails.html)

# In progress/needs work

  - **OpenSpace-Gaia-Sample** : This notebook will access the gaia source api, 
  select a set of stars and plot them in OpenSpace. 
  So far this just pulls 10 stars down and puts them in a .fits file
