# Script to collect the files needed for an OpenSpace build.
#
# Command line arguments:
# arg 1: source folder (The OpenSpace folder)
# arg 2: destination folder
# ## TODO: Qt folder

import sys
import glob, os, shutil

# TODO: Qt stuff
QT_DEFAULT_PATH = "C:\Qt\6.4.0\msvc2019_64\bin"
QT_VERSION = "6"

source_dir = sys.argv[1]
destination_dir = sys.argv[2]

print("Copying filed from OpenSpace folder: '" + source_dir + "' to target folder '" + destination_dir + "'")

if (not os.path.isdir(destination_dir)):
    os.mkdir(destination_dir)
    print("Directory '% s' created" % destination_dir)
elif (os.path.isdir(destination_dir) and not os.listdir(destination_dir)):
    print("Using existing empty destination directory '% s'" % destination_dir)
else:
    print("Destination directory '% s' already existed and is not an empty directory. Do you want to overwrite its content? (Y/N)" % destination_dir)
    string = str(input())
    if (string.lower() != 'y'):
        print("OK. Aborting...")
        sys.exit()

print("Copying folders...")

folders = ["bin", "config", "data", "modules", "scripts", "shaders"]
for f in folders:
    dest_dir = os.path.join(destination_dir,f)
    if (not os.path.isdir(dest_dir)):
        shutil.copytree(os.path.join(source_dir,f),  dest_dir)

print("Coying files...")

md_files = glob.iglob(os.path.join(source_dir, "*.md"))
for file in md_files:
    if os.path.isfile(file):
        shutil.copy2(file, destination_dir)

shutil.copy2(os.path.join(source_dir,"openspace.cfg"), destination_dir)

print("Cleaning up bin folder...")

relWithDebFolder = os.path.join(destination_dir, "bin/RelWithDebInfo")
binFolder = os.path.join(destination_dir, "bin")
if (os.path.isdir(relWithDebFolder)):
    # Clean up some logs an non-needed files
    for file in glob.iglob(os.path.join(relWithDebFolder, "*.pdb")):
        os.remove(file)
    for file in glob.iglob(os.path.join(relWithDebFolder, "*.dmp")):
        os.remove(file)

    # Then move all files out to the bin directory
    for file in os.listdir(relWithDebFolder):
        # construct full file path
        source = os.path.join(relWithDebFolder, file)
        destination = os.path.join(destination_dir, "bin/" + file)
        # copy only files
        if os.path.isfile(source) or os.path.isdir(source):
            shutil.move(source, destination)

    # Remove the folder, but first check that it is empty
    if not os.listdir(relWithDebFolder):
        os.rmdir(relWithDebFolder)
    else:
        print("ERROR when emptying RelWithDebInfo folder. Some files remain")

elif (os.path.isdir(binFolder)):
    # Clean up some logs an non-needed files
    for file in glob.iglob(os.path.join(binFolder, "*.pdb")):
        os.remove(file)
    for file in glob.iglob(os.path.join(binFolder, "*.dmp")):
        os.remove(file)

# TODO: Qt dll files and platforms/qwindows.dll

print("Done!")
