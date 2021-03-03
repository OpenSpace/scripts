#This code is used to decide whether a signal is an uplink or a downlink
#by using information from the equipmentlist.

#For uplink passes you’ll see a UPL. Note - this means they booked an uplink
#- not that they will actually use it.
#You’ll also see RRPA/B TLPA/B in the config code RRPs are receivers 
#that receives the RF from the spacecraft and convert it into digital bits .
#The TLP takes the received signal and generates telemetry frames . 
#So all this is indicative of a downlink from the spacecraft to earth 


#TLDR for active equipment for matching config code; 
#RRPA, RRPB, TLPA, TLPB --> Downlink
#UPL --> Uplink

import json
from pprint import pprint #for printing the json data
from pathlib import Path

#str(dataTuple[i]["starttime"] ) + 'json'
#outputData = open('result.json', 'w')

configcodeList = []
equipmentString = []
equipmentListObj = []
isDownlink = False
isUplink = False
linkString =''

directory_in_str = "C://Users//openspace//Agnes//convertToJSON//convertDataToOpenSpaceFormat//data"

pathlist = Path(directory_in_str).glob('**/*.json')
for path in pathlist:
	# because path is object not string
	path_in_str = str(path)
	print(path_in_str)

	with open(path_in_str) as data_file:    
		data = json.load(data_file)
		dataTuple = (data["result"]["item"])
		dataDict = {}
		startIndex = 0;

		#make a backwards iteration to get rid of all training sessions
		#i.e. work categories that are not 1A1
		for j in range(len(dataTuple)- 1, -1, -1):
			if(dataTuple[j]["wrkcat"] != "1A1"):
				print(dataTuple[j])
				del dataTuple[j]

		# Loop over remaining data and reformat it as we want it in OpenSpace
		for i in data:
			for j in range(0, len(dataTuple)):
					#delete the parameters we don't need
					del dataTuple[j]["starttime"]
					del dataTuple[j]["endtime"]
					del dataTuple[j]["activity"]
					del dataTuple[j]["configcode"]
					del dataTuple[j]["year"]
					del dataTuple[j]["nib"]
					del dataTuple[j]["scheduleitemid"]
					del dataTuple[j]["week"]
					del dataTuple[j]["wrkcat"]
					del dataTuple[j]["soecode"]
					del dataTuple[j]["version"]
					del dataTuple[j]["activitytype"]

					#add DSS to facility number
					dataTuple[j]["facility"] = "DSS" + str(dataTuple[j]["facility"])

					#get equipmentlist to decide if uplink/downlink, then delete it
					equipmentString = dataTuple[j]["equipmentlist"]
					equipmentListObj = equipmentString.split(",");
					del dataTuple[j]["equipmentlist"]

					#deal with uplink/downlink
					linkString =''
					isDownlink = False
					isUplink = False

					for equipment in equipmentListObj:
						if (equipment == 'UPL'):
							isUplink = True;
						if (equipment == 'RRPA' or equipment == 'RRPB' or equipment == 'TLPB' or equipment == 'TLPA'):
							isDownlink = True;
					if(isDownlink and isUplink):
							linkString += 'both'
					elif(isUplink):
							linkString += 'uplink'	
					elif(isDownlink):
							linkString += 'downlink'					
					else :
							linkString = "None"	
					
					dataTuple[j]["direction"] = linkString	


					#Sort data according to date, and store in seperate files depending on the day
					if(j+1 < len(dataTuple) and dataTuple[j+1]["bot"][0:8] != dataTuple[j]["bot"][0:8]):
							testTuple = dataTuple;
							fileName = str('C://Users//openspace//Agnes//convertToJSON//convertDataToOpenSpaceFormat//parsedData//' + testTuple[j]["bot"][0:9]) + '.json'
							outputData = open(fileName , 'w')
							
							dataDict["Signals"] = testTuple[startIndex:j+1];
							json.dump(dataDict, outputData, indent=4)

							testTuple = ();
							startIndex = j + 1;
				

			

	