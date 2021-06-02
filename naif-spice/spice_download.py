import requests
# import tkinter as tk
# from tkinter import simpledialog
# ROOT = tk.Tk()
# ROOT.withdraw()
# LINK = simpledialog.askstring(title="Link", prompt="Please enter link of the NAIF website:")
LINK = input("NAIF Website Link: ")
KERNEL = input("File Type of Kernel (.bc will be bc): ")
r = requests.get(LINK)
page_source = r.text
page_source = page_source.split('\n')
StartPoint = "<!--start data_content-->"
for line in enumerate(page_source):
    if StartPoint in line:
        start = line
start = start[0]
endpoint = "<hr></pre>"
for line in enumerate(page_source):
    if endpoint in line:
        end = line
end = end[0]
Array = []
for line in page_source[start:end]:
    if KERNEL in line:
        Array.append(line)
TestStart = start + 7
beginning = page_source[TestStart].index('h') + 6
LinkArray = []
NameArray = []
count = 0
for i in Array:
    ending = i.index(KERNEL) + len(KERNEL)
    i = i[beginning:ending]
    NameArray.append(i)
    i = LINK + i
    LinkArray.append(i)
    for j in LinkArray:
        print("\n get file!!!" + i)

        r = requests.get(j, allow_redirects=True)
        print("\n GOT file!!!")
        open(NameArray[count], 'wb').write(r.content)
        print("\n WROTE file!!!")
        count = count + 1
print("\nThank you for using Project Micah, you may now move your files to their respective folder.")

