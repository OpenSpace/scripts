import json
import csv
from pathlib import Path

signalDates  = []
signalDir = "C://Users//openspace//Agnes//convertToJSON//addLightTravelTimeToSignals//signalData"
pathlistSignal = Path(signalDir).glob('**/*.json')
tmp = ()
tmpSignal = {}
for signalpath in pathlistSignal:
	signalPathStr = str(signalpath)
	signalDates.append(signalPathStr[78:93])

for i in range (0, len(signalDates)):
	with open(str('signalData/' + signalDates[i][0:9]+ '.json'), 'r+') as f:
		signalData = json.load(f)
		
		for j in range( 0, len(signalData["Signals"])):
			spacecraft = signalData["Signals"][j]["projuser"]

			with open(str('radecData/' + spacecraft + '.dat')) as g:
					print(str('radecData/' + spacecraft + '.dat'))

					positionData = csv.DictReader(g, fieldnames=['TimeStamp', 'AzUp', 'ElUp', 'RngUp', 'AzDn', 'ElDn', 'RngDn',
 																		'RAUp', 'DecUp', 'GeoRngUp', 'RADn', 'DecDn', 'GeoRngDn', 'ULT', 'RTLT_Up', 'XADop', 'DLT', 'RTLT_Dn', 'OneWayDop', 'TwoWayDop']) 
 					
					for row in 	positionData:
						if(signalData["Signals"][j]["bot"][0:11] == row["TimeStamp"][0:11]):
							print("found for " + signalData["Signals"][j]["bot"][0:11] + " in " + row["TimeStamp"][0:11] + " and " + signalData["Signals"][j]["projuser"] + ' ------ ' + row["DLT"] )
							print("BEST ONE")
							signalData["Signals"][j]["DLT"] =  row["DLT"]
							break

						elif (signalData["Signals"][j]["bot"][0:7] == row["TimeStamp"][0:7]):
							print("found for " + signalData["Signals"][j]["bot"][0:8] + " in " + row["TimeStamp"][0:11] + " and " + signalData["Signals"][j]["projuser"] + ' ------ ' + row["DLT"] )
							signalData["Signals"][j]["DLT"] =  row["DLT"]
							print("MEDIUM ONE")
							break

						elif (signalData["Signals"][j]["bot"][0:2] == row["TimeStamp"][0:2]):
							print("found for " + signalData["Signals"][j]["bot"][0:4] + " in " + row["TimeStamp"][0:11] + " and " + signalData["Signals"][j]["projuser"] + ' ------ ' + row["DLT"] )
							signalData["Signals"][j]["DLT"] =  row["DLT"]
							break
		f.seek(0)
		json.dump(signalData, f, indent = 4)
		f.truncate()						
