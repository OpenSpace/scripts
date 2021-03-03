import csv, sys
import datetime

# user defined variables
localPath = "C:/OpenSpace/pythonscripts/sortData/"
spacecraftName = "NHPC"

# data variables
dataDir = "data/"
dataExtension = ".dat"

# Generated filename as date, Format: YYYY-DDDTHH
generatedDataDir = "result/"
generatedExtension = ".dat"
generatedFileName = spacecraftName
errorlog = 'errorlog.csv'

#stores our data in a dictionary
dataDictionary = {}

fieldnames = ['TimeStamp', 'AzUp', 'ElUp', 'RngUp', 'AzDn', 'ElDn', 'RngDn', 'RAUp', 'DecUp', 'GeoRngUp', 'RADn', 'DecDn', 'GeoRngDn', 'ULT',
		'RTLT_Up', 'XADop', 'DLT', 'RTLT_Dn', 'OneWayDop', 'TwoWayDop'] 

dataPath = dataDir + spacecraftName + dataExtension
newFilePathString = str( localPath + generatedDataDir + generatedFileName + generatedExtension )

with open(dataPath, 'r') as readFile:
	print(str("Reading data from " + localPath+dataPath))
	keysAsDate = []#[datetime.datetime.strptime(ts, "%Y-%m-%d") for ts in timestamps]
	reader = csv.DictReader(readFile, fieldnames=fieldnames) 
		
	for row in reader:

		try:
			timestamp = row['TimeStamp']
			#create a key based on the timestamp
			timestampKey = datetime.datetime.strptime(timestamp[0:16], "%Y-%jT%H:%M:%S")
			#save this key as a date, used later for sorting
			keysAsDate.append(timestampKey)
			#save the row data in a dictionary
			dataDictionary[timestampKey] = row

		except csv.Error as e:
			sys.exit('file %s, line %d: %s' % (errorlog, reader.line_num, e))

	#sort the keys
	keysAsDate.sort()

with open(newFilePathString, 'w') as writeFile:
	writer = csv.DictWriter(writeFile, fieldnames=fieldnames, lineterminator='\n')
	print(str("Writing data to" + newFilePathString))
	#loop over the sorted keys
	for idx in range(0, len(keysAsDate)):

		#get the row from our data dictionary 
		writeRow = dataDictionary[keysAsDate[idx]]
		#print(dataDictionary[keysAsDate[key]])
		writer.writerow(writeRow)
		if idx%30000 == 0:
			print("Writing to new file: " + str(int(idx/len(keysAsDate) * 100)) + "%")


print(str("Finished writing to file: " + newFilePathString))

