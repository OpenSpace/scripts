# dataScripts
From: http://internal.openspaceproject.com/projects/deep-space-network/data-preprocessing

Original repository: https://github.com/agnhe421/dataScripts

* Sort the positioning data (just to be safe) by running the sortDataFileOnTimestampCsvReaderWriter script in the sortData folder. (More information in readme.txt). The per minute data had many errors, and was unsorted, and this script is necessary. The hourly data seems not to have errors and seems to come sorted, so it may not be necessary to run this script for both the minute and hourly data. It may only need to be run on the minute data. Note when orignally processing there were a few position files that were too large to sort on the local machine, more memory may be needed for python.

* Process the position data by running the csvToJson in the convertRadecDataToOpenSpaceFormat folder (More information in readme.txt). This step is executed for each spacecraft.

* ReProcess the positoin data by running the same script again, but changing dataDir from data/hourly to data/byminute. NOTE hourly data must be processed before minute data.

* Process the signaldata by running the scheduleToJson in the convertScheduleSignals folder (More information in readme.txt).

* Move processed signal data and the processed position data to addLightTravelTimeToSignals folder.

* Run the script "addLightTravelTimeToSignalData" to update the signal data with the correct light travel time (More information in readme.txt)..

* The resulting folders should be moved into sync/http/dsn_data/1/ and "signalData" should be renamed to "signaldata" and "radecData" renamed to "positioning"
