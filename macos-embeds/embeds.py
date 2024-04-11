from subprocess import run
import os
import os.path

osversion = "0.19.1"

BASE_DIR = os.path.dirname(os.path.realpath(__file__))

def getlib(line, thing="name"):
  start = line.find(" name") + 6
  if start < 0:
    return ""
  lib = line[start:]
  end = lib.index(" ")
  lib = lib[:end]
  return lib  

def countFiles(dir):
  _, _, files = next(os.walk(dir))
  return len(files)

def copyLibs(grep, printcommand=False):
  dir_list = os.listdir("./Embeds/") 
  for file in dir_list:
    if file.endswith("dylib"):
      # print(f"-- {grep} CheckFile: {file}")
      sublibs = run(f"otool -l Embeds/{file} | grep {grep}", capture_output=True, shell=True)
      liblcid = run(f"otool -DX Embeds/{file}", capture_output=True, shell=True).stdout.decode('UTF-8')
      libpath = run(f"dirname {liblcid}", capture_output=True, shell=True).stdout.decode('UTF-8').strip()

      sublines = sublibs.stdout.decode('UTF-8').splitlines();
      for line in sublines:
        #print("line:" + line)
        lib = getlib(line)
        if len(lib) == 0:
          continue

        if lib.find("@rpath") >= 0:
          slash = lib.rindex("/") + 1
          libfile = lib[slash:]
          lib = libpath + "/" + libfile

        cmd = f"cp {lib} Embeds/"
        slash = lib.rindex("/") + 1
        libfile = lib[slash:]

        if printcommand:
          print(cmd)
        if not (os.path.isfile(f"{BASE_DIR}/Embeds/{libfile}")):
          run(cmd, capture_output=True, shell=True)

def fixup_libs(grep, printcommand=False):
  dir_list = os.listdir("./Embeds/") 
  for file in dir_list:
    if file.endswith("dylib"):
      sublibs = run(f"otool -l Embeds/{file} | grep {grep}", capture_output=True,shell=True)
      sublines = sublibs.stdout.decode('UTF-8').splitlines();
      for line in sublines:
        lib = getlib(line)
        if len(lib) == 0: #these are not the lines you are looking for
          continue
        slash = lib.rfind("/") + 1
        libfile = lib[slash:]
        cmd2 = f"install_name_tool -change {lib} @rpath/{libfile} Embeds/{file}"
        cmd3 = f"install_name_tool -add_rpath @executable_path/../Frameworks/ Embeds/{file}"
        if printcommand:
          print(cmd2)
        run(cmd2, capture_output=True, shell=True)
        run(cmd3, capture_output=True, shell=True)

print("-----RPATH HELL-------")
run("mkdir ./Embeds", capture_output=True, shell=True)
libs = run("otool -l OpenSpace-"+osversion+"/bin/OpenSpace.app/Contents/MacOS/OpenSpace | grep opt", capture_output=True,shell=True)
lines = libs.stdout.decode('UTF-8').splitlines();
for line in lines:
  lib = getlib(line)
  cmd = f"cp \"{lib}\" Embeds/"
  slash = lib.rindex("/") + 1
  libfile = lib[slash:]
  cmd2 = f"install_name_tool -change {lib} @rpath/{libfile} OpenSpace-"+osversion+"/bin/OpenSpace.app/Contents/MacOS/OpenSpace"
  # print(cmd)
  run(cmd, capture_output=True, shell=True)
  print("****:"+cmd2)
  os.system(cmd2)


#look for opt and Cellar libs (and any rpath referenced ones)
lastfcount = -1
fcount = countFiles("./Embeds")
while fcount != lastfcount:
  copyLibs("opt", False)
  copyLibs("Cellar", False)
  copyLibs("rpath", False)
  lastfcount = fcount
  fcount = countFiles("./Embeds")
  print(f"counts {fcount} {lastfcount}")
#fixup localpaths to rpaths
fixup_libs("opt", False)
fixup_libs("Cellar", False)
#copy files
os.system("cp -R Embeds/* OpenSpace-"+osversion+"/bin/OpenSpace.app/Contents/Frameworks/")
os.system("cp -R QTEmbeds/* OpenSpace-"+osversion+"/bin/OpenSpace.app/Contents/Frameworks/")
os.system("cp -R OSEmbeds/* OpenSpace-"+osversion+"/bin/OpenSpace.app/Contents/Frameworks/")
os.system("mkdir -p OpenSpace-"+osversion+"/bin/OpenSpace.app/Contents/Plugins/platforms")
os.system("cp -R ~/os/local/Qt6/6.4.1/macos/plugins/platforms/ OpenSpace-"+osversion+"/bin/OpenSpace.app/Contents/Plugins/platforms/")
os.system("install_name_tool -add_rpath @executable_path/../Frameworks/ OpenSpace-"+osversion+"/bin/OpenSpace.app/Contents/MacOS/OpenSpace")
