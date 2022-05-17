import json
import sys

time = "2000-01-01T12:00:00.000"

f = open(sys.argv[1])
lines = [[float(i) for i in line.split(' ')] for line in f.readlines()]

values = {}
for value in lines:
  if not value[0] in values:
    values[value[0]] = {
      "time": time,
      "trace": {
        "index": [],
        "data": []
      },
      "columns": [ "x", "y", "z", "B" ],
      "x": value[1],
      "y": value[2],
      "z": value[3],
      "resolution": 0.003, #??
      "topology": "south_open" #??
    }
  
  values[value[0]]["trace"]["index"].append(len(values[value[0]]["trace"]["data"]))
  values[value[0]]["trace"]["data"].append([ value[1], value[2], value[3], value[4] ])
  

with open("{}.json".format(sys.argv[1]), 'w') as outfile:
  json.dump(values, outfile)
