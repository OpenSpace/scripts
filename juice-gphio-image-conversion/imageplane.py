from cmath import isnan
from PIL import Image, ImageOps
import math
import matplotlib.pyplot as plt
import sys

# Removes the ith element from the list and returns the list
def remove_ith(lst, i):
  del lst[i]
  return lst

def calc_minmaxnum(lst):
  return (min(lst), max(lst), len(set(lst)))


# Open the file, read line-by-line, and convert each entry into floats
f = open(sys.argv[1])
lines = f.readlines()
values = [[float(i) for i in line.split(' ')] for line in lines]


if sys.argv[2] == "XY":
  # Remove the z component
  values = [remove_ith(a, 2) for a in values]
elif sys.argv[2] == "XZ":
  # Remove the y component
  values = [remove_ith(a, 1) for a in values]
else:
  print("Unknown second argument '{}'".format(sys.argv[2]))

# Calculate the minimum value, maximum value, and number of distinct values for each row
minmaxnum = []
for i in range(len(values[0])):
  minmaxnum.append(calc_minmaxnum([a[i] for a in values]))

def create_image(idx, name):
  img = Image.new(mode="RGBA", size=(minmaxnum[0][2], minmaxnum[1][2]))
  cmap = plt.cm.get_cmap('viridis')
  print("{}x{}".format(minmaxnum[0][2], minmaxnum[1][2]))
  for value in values:
    x = (value[0] - minmaxnum[0][0]) / (minmaxnum[0][1] - minmaxnum[0][0])
    x_pxl = round(x * (minmaxnum[0][2] - 1))
    y = (value[1] - minmaxnum[1][0]) / (minmaxnum[1][1] - minmaxnum[1][0])
    y_pxl = round(y * (minmaxnum[1][2] - 1))
    v = (value[idx] - minmaxnum[idx][0]) / (minmaxnum[idx][1] - minmaxnum[idx][0])
    
    # There are some NaN values in the file that the colormap doesn't like
    if math.isnan(v):
      v = 0

    color = cmap(v)
    r = int(round(color[0] * 255))
    g = int(round(color[1] * 255))
    b = int(round(color[2] * 255))
    img.putpixel((x_pxl, y_pxl), (r, g, b, 255))

  img.save("{}-{}.png".format(sys.argv[2], name))

create_image(2, "n")
create_image(3, "Ux")
create_image(4, "Uy")
create_image(5, "Uz")
create_image(6, "Utot")
create_image(7, "T")

img = Image.new(mode="RGBA", size=(minmaxnum[0][2], minmaxnum[1][2]))
print("{}x{}".format(minmaxnum[0][2], minmaxnum[1][2]))
for value in values:
  x = (value[0] - minmaxnum[0][0]) / (minmaxnum[0][1] - minmaxnum[0][0])
  x_pxl = round(x * (minmaxnum[0][2] - 1))
  y = (value[1] - minmaxnum[1][0]) / (minmaxnum[1][1] - minmaxnum[1][0])
  y_pxl = round(y * (minmaxnum[1][2] - 1))
  v3 = (value[3] - minmaxnum[3][0]) / (minmaxnum[3][1] - minmaxnum[3][0])
  if math.isnan(v3):
    v3 = 0
  v4 = (value[4] - minmaxnum[4][0]) / (minmaxnum[4][1] - minmaxnum[4][0])
  if math.isnan(v4):
    v4 = 0
  v5 = (value[5] - minmaxnum[5][0]) / (minmaxnum[5][1] - minmaxnum[5][0])
  if math.isnan(v5):
    v5 = 0
  img.putpixel((x_pxl, y_pxl), (int(round(v3 * 255)), int(round(v4 * 255)), int(round(v5 * 255)), 255))
img.save("{}-U.png".format(sys.argv[2]))
