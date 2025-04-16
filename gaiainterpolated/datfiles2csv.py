import sys
import os


if len(sys.argv) == 1:
    print("usage: readdatfile main.py <dat file directory> <scalefactor>")

folder = sys.argv[1]
if (len(sys.argv) > 2):
    scaleFactor = int(sys.argv[2])
else:
  scaleFactor = 1

print(f"hello {folder}")

particle_rows = []
steps = 0

steps = 0
# Loop through files in the folder
for filename in os.listdir(folder):
  file_path = os.path.join(folder, filename)
  if os.path.isfile(file_path):  # Ensure it's a file
      # Add your file processing logic here
      with open(file_path, 'r') as file:
        lines = file.readlines()
        for line in lines[4:]:  # Skip the first 4 lines
            row = line.strip().split()  # Split by spaces
            newrow = [steps, float(row[2]), float(row[3]), float(row[4]), float(row[0]), float(row[1])]
            particle_rows.append(newrow)
      steps += 1

particle_rows.sort(key=lambda x: x[0])


header_row = "time,x,y,z,type,mass"
with open(f"{folder}.csv", "w") as outfile:
  outfile.write(header_row + '\n')
  for row in enumerate(particle_rows):
    str_row = [str(v) for v in row[1]]
    comma_row = ','.join(str_row)
    outfile.write(f"{comma_row}\n")
outfile.close()

unit = "Kpc"
size = len(particle_rows)/steps

with open(f"{folder}.asset", "w") as outfile:
    asset = """local Node = {
  Identifier = '%s',
  Renderable = {
    Type = 'RenderableInterpolatedPoints',
    File = asset.resource('%s.csv'),
    NumberOfObjects = %s,
    Interpolation = {Speed = 25},
    SizeSettings = {
      EnableMaxSizeControl = true,
      ScaleExponent = 15,
      ScaleFactor = 1,
      SizeMapping = {ParameterOptions = { "type" }, Parameter = 'type'}
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
""" % (folder, folder, size, unit, folder)
    outfile.write(asset)
outfile.close()
