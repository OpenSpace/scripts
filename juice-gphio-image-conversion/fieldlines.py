import json
import sys

time = "2000-01-01T12:00:00.000"

f = open(sys.argv[1])
lines = [[float(i) for i in line.split(' ')] for line in f.readlines()]

values = {}
minValue = 99999999999
maxValue = 0
for value in lines:
  if not value[0] in values:
    values[int(value[0])] = {
      "time": time,
      "trace": {
        "index": [],
        "columns": [ "x", "y", "z", "B" ],
        "data": []
      },
      "x": value[1] * 1000,
      "y": value[2] * 1000,
      "z": value[3] * 1000,
      "resolution": 0.003, #??
      "topology": "south_open" #??
    }
  
  values[int(value[0])]["trace"]["index"].append(len(values[value[0]]["trace"]["data"]))
  values[int(value[0])]["trace"]["data"].append([ value[1] * 1000, value[2] * 1000, value[3] * 1000, value[4] ])

  if value[4] > maxValue:
    maxValue = value[4]
  if value[4] < minValue:
    minValue = value[4]
  

print("Min: {}\nMax: {}".format(minValue, maxValue))
with open("{}.json".format(sys.argv[1]), 'w') as outfile:
  json.dump(values, outfile)
