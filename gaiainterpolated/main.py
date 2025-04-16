import sys

if len(sys.argv == 1):
    print("usage: python main.py <datafile> <scalefactor>")

filename = sys.argv[1]
if (len(sys.argv) > 2):
    scaleFactor = int(sys.argv[2])
else:
  scaleFactor = 1

name = filename.split('.')[-2].replace('\\','')
print(f"hello {name}")
starts = []
speeds = []
orig_interps = []
i=1
parsecInKM = 3.086e+13
with open(filename) as infile:
    for line in infile:
        if (not line.startswith("datavar")):
            row = line.split()
            # print(f'{row[0]}, {row[1]}, {row[2]}')
            if i < 3000000:
                interp_row = [0.0, float(row[0]), float(row[1]), float(row[2]), float(row[3]), float(row[4])]
                if row[13] != "NaN":
                    orig_interps.append(interp_row)
                    speeds.append([float(row[13]), float(row[14]), float(row[15]), float(row[16])])
                    starts.append([row[0], row[1], row[2]])
            i = i + 1
infile.close()


secondsPerYear = 3.154e+7
time = 3.0e6 * secondsPerYear

interps = orig_interps.copy()
size = len(orig_interps)
print(size)
print(interps[1])
for i, star in enumerate(orig_interps):
    u = speeds[i][0]
    v = speeds[i][1]
    w = speeds[i][2]
    interp_row = [
        1.0, 
        star[1] + (u*time)/parsecInKM*1/scaleFactor, 
        star[2] + (v*time)/parsecInKM*1/scaleFactor, 
        star[3] + (w*time)/parsecInKM*1/scaleFactor,
        star[4], star[5]]
    if (i==1):
        dist = u*time
        print(u)
        print(dist)
        print(u*time/parsecInKM + star[1])
        print(star)
        print(interp_row)
    interps.append(interp_row)

header_row = "time,x,y,z,color,lum"
with open(f"{name}.csv", "w") as outfile:
    outfile.write(header_row + '\n')
    for i, row in enumerate(interps):
        str_row = [str(v) for v in row]
        comma_row = ','.join(str_row)
        outfile.write(f"{comma_row}\n")
outfile.close()

unit = "pc"
if (scaleFactor == 1000):
    unit = "Kpc"

with open(f"{name}.asset", "w") as outfile:
    asset = """local Node = {
  Identifier = '%s',
  Renderable = {
    Type = 'RenderableInterpolatedPoints',
    File = asset.resource('%s.csv'),
    NumberOfObjects = %s,
    Coloring = {ColorMapping = {File = asset.resource('charity_bv2rgb.cmap'), Parameter = 'color'}},
    Interpolation = {Speed = 0.05},
    SizeSettings = {
      EnableMaxSizeControl = true,
      ScaleExponent = 15,
      ScaleFactor = 1,
      SizeMapping = {ParameterOptions = { "lum" }, Parameter = 'lum'}
    },
    Texture = {
      UseAlphaChannel = true,
      File = asset.resource('halo.png'),
      AllowCompression = true
    },
    Unit = "%s"
  },
  GUI = {Name = "%s", Path = "/Gaia"}
}

asset.onInitialize(function()
  openspace.addSceneGraphNode(Node)
end)

asset.onDeinitialize(function()
  openspace.removeSceneGraphNode(Node)
end)
""" % (name, name, size, unit, name)
    outfile.write(asset)
outfile.close()
