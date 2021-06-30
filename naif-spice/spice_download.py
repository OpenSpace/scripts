import requests
import tkinter
from tkinter import filedialog
import os

# asking for the NAIF Website Link and registering it in requests
LINK = input("NAIF Website Link: ")
r = requests.get(LINK)

# asking for the type of Kernel, so to use this when searching for file names
KERNEL = input("File Type of Kernel (.bc will be bc): ")

# Asking for the file path
print("\nPlease choose the new location of your files by choosing a folder in the following pop-up")
root = tkinter.Tk()
root.withdraw()

file_path = filedialog.askdirectory()

# converting the link into a text file and splitting it at each line
page_source = r.text
page_source = page_source.split('\n')

# Setting the standardized start point, to help the searching process
StartPoint = "<!--start data_content-->"

# Finding the line number of the StartPoint, and setting it to the first value in the tuple
for line in enumerate(page_source):
    if StartPoint in line:
        start = line
start = start[0]

# Setting the standardized endpoint, common in all page sources
endpoint = "<hr></pre>"

# Searching for the line number of this endpoint, to help in file name searching
for line in enumerate(page_source):
    if endpoint in line:
        end = line
end = end[0]

# Establishing an array that saves the line numbers
Array = []
for line in page_source[start:end]:
    if KERNEL in line:
        Array.append(line)

# TestStart is to find the index of 'h' which is the standard beginning of the file names
TestStart = start + 7
beginning = page_source[TestStart].index('h') + 6

# Link and Name array to store the Links and Names separately
LinkArray = []
NameArray = []

# Going over the file names and adding the information to the Link and Name Array
for i in Array:
    ending = i.index(KERNEL) + len(KERNEL)
    i = i[beginning:ending]
    NameArray.append(i)
    i = LINK + i
    LinkArray.append(i)

# Going over the NameArray and LinkArray, to request the links with the file name of their respective names
for i in NameArray:
    for j in LinkArray:
        NameForFile = i
        final_file_path = os.path.join(file_path, NameForFile)
        r = requests.get(j, allow_redirects=True)
        open(final_file_path, 'wb').write(r.content)

# Print Message for when it is complete
print("\nYour files are now in the chosen folder. Thank you for using InternRobo. Ad Astra!")
