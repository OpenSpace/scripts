import csv
import json
import os
from collections import defaultdict

localPath = "C:/Users/openspace/Agnes/convertToJSON/convertRadecDataToOpenSpaceFormat/"
generatedDataDir = "parsed/"
generatedExtension = ".json"
spacecraftName = "ACE"
dataDir = "data/hourly/"
dataExtension = ".dat"

# Generated filename as date, Format: YYYY-DDDTHH
nameFormat = ""
hours = []
nameFormatList = []
positionsDictionary = {}
data = []
oneHourData = []
times = []

dataPath = dataDir + spacecraftName + dataExtension

with open(dataPath) as f:
	reader = csv.DictReader(f, fieldnames=['TimeStamp', 'AzUp', 'ElUp', 'RngUp', 'AzDn', 'ElDn', 'RngDn', 
		'RAUp', 'DecUp', 'GeoRngUp', 'RADn', 'DecDn', 'GeoRngDn', 'ULT', 'RTLT_Up', 'XADop', 'DLT', 'RTLT_Dn', 'OneWayDop', 'TwoWayDop']) 
	for row in reader:
		del row['AzUp']
		del row['ElUp']
		del row['RngUp']
		del row['AzDn']
		del row['ElDn']
		del row['RngDn']
		del row['RAUp'] 
		del row['DecUp']
		del row['GeoRngUp']
		del row['ULT']
		del row['RTLT_Up']
		del row['XADop']
		#del row['DLT']
		del row['OneWayDop']
		del row['TwoWayDop']
		del row['RTLT_Dn']

		#print(row['TimeStamp'])
		row['RADn'] = float(row['RADn'])
		row['DecDn'] = float(row['DecDn'])
		row['GeoRngDn'] = float(row['GeoRngDn'])
		row['DLT'] = float(row['DLT'])
		row['TimeStamp'] = row['TimeStamp'][0:14]
		
		#Create our filename from the timestamp
		nameFormat = row["TimeStamp"][0:11]
		nameFormatList.append(nameFormat)

		time = row["TimeStamp"]
		times.append(time)

		data.append(row)

firstIndexInNewFile = 0
for i in range(0, len(data)):

	if (i+1 < len(times) and times[i] == times[i+1]):
		firstIndexInNewFile = firstIndexInNewFile+1
		continue

	# append the very first index to file
	if i == firstIndexInNewFile :
		oneHourData.append(data[i])

	# Compare the Format: YYYY-DDDTHH with the format of the next index in the data
	if(i+1 < len(nameFormatList) and nameFormatList[i] == nameFormatList[i+1]):
		oneHourData.append(data[i+1])

	#only dump to file if there is data for that particular hour
	elif (len(oneHourData) > 0):
		fileNameString = str( localPath + generatedDataDir + spacecraftName + "/" + nameFormatList[i] + generatedExtension )

		#Creates the file or open it for appending
		outputDataFile = open(fileNameString, 'a')

		# if file is NOT empty we have to open it and append the data that it does not have
		# TODO: make sure the appended data is sorted according to timestamp
		if not os.stat(fileNameString).st_size == 0 :
			#print("NOT EMPTY: " + fileNameString)
			outputDataFile.close()
			#read the previously written data into json objects
			with open(fileNameString, "r") as json_file:  
				usedData = json.load(json_file)
				tempData = []
				for testIdx in range(0, len(oneHourData)):

					shouldBeAppended = True
					for p in range(0, len(usedData['Positions']))	:
						# don't append duplicated data
						if (oneHourData[testIdx]["TimeStamp"] == usedData['Positions'][p]):
							shouldBeAppended = False

					if(shouldBeAppended):
							tempData.append(oneHourData[testIdx])

			oneHourData.clear()
			oneHourData = tempData
			json_file.close()
			outputDataFile = open(fileNameString , 'w')

		#update the index for the following file
		firstIndexInNewFile = firstIndexInNewFile + len(oneHourData)

		positionsDictionary["Positions"] = oneHourData
		#write to json file
		print("working on:  " + fileNameString[84:95])
		json.dump(positionsDictionary,outputDataFile, indent=4)
		del oneHourData[:]



