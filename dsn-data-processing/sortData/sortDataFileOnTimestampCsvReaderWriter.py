import csv, sys
import datetime
from pathlib import Path

# user defined variables
localPath = "C:/OpenSpace/pythonscripts/sortData/"
#spacecraftName = "NHPC"

# data variables
dataDir = localPath + "data/"
fileExtension = ".dat"
pathlistData = Path(dataDir).glob('**/*'+ fileExtension)

# Generated filename as date, Format: YYYY-DDDTHH
generatedDataDir = localPath + "sorted_data/"
errorlog = 'errorlog.csv'

fieldnames = ['TimeStamp', 'AzUp', 'ElUp', 'RngUp', 'AzDn', 'ElDn', 'RngDn', 'RAUp', 'DecUp', 'GeoRngUp', 'RADn', 'DecDn', 'GeoRngDn', 'ULT',
		'RTLT_Up', 'XADop', 'DLT', 'RTLT_Dn', 'OneWayDop', 'TwoWayDop'] 

for dataPath in pathlistData:

	dataFileName = str(dataPath).replace('\\', '/')
	newFilePathString = dataFileName.replace(dataDir,generatedDataDir)
	
	with open(dataPath, 'r') as readFile:
		print(str("Reading data from " + dataFileName))

		reader = csv.reader(readFile)

		dataList = list(reader)
		print("Data read sucessfully!")
		print("Sorting data...")
		#since we know our timestamp is the first value of the row
		#we can use it to sort our list
		dataList.sort(key=lambda row: datetime.datetime.strptime(row[0][0:16], "%Y-%jT%H:%M:%S"))
	readFile.close()
	with open(newFilePathString, 'w') as writeFile:
		writer = csv.writer(writeFile, lineterminator='\n')
		print(str("Writing data to " + newFilePathString))
		#loop over the sorted keys
		#writer.writerow(fieldnames)
		for idx, row in enumerate(dataList):

			writer.writerow(row)
			if idx%30000 == 0:
				print("Writing to new file: " + str(int(idx/len(dataList) * 100)) + "%")


	print(str("Finished writing to file: " + newFilePathString))

	writeFile.close()


