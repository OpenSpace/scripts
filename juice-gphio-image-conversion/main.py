from PIL import Image
import sys

# Removes the ith element from the list and returns the list
def remove_ith(lst, i):
  del lst[i]
  return lst

# Open the file, read line-by-line, and convert each entry into floats
f = open(sys.argv[1])
lines = f.readlines()
values = [[float(i) for i in line.split(' ')] for line in lines]


if sys.argv[2] == "XY":
  values = [remove_ith(a, 2) for a in values]
elif sys.argv[2] == "XZ":
  values = [remove_ith(a, 1) for a in values]
else:
  print("Unknown second argument '{}'".format(sys.argv[2]))

coord0 = [a[0] for a in values]
coord0_min = min(coord0)
coord0_max = max(coord0)
coord1 = [a[1] for a in values]
coord1_min = min(coord1)
coord1_max = max(coord1)
print(coord0_min, coord0_max, coord1_min, coord1_max)
