/***************************************************************************/
This is a guideline to adding the light travel time from one data to another.
/***************************************************************************/

step 1. Add all of the signal data to the folder called signalData
step 2. Add all of the ra/dec data (json) to the folder called radecData
step 3. Make sure the radec data folder is named as the spacecraft identifier in the signal data. 
step 4. Run the script (addLightTravelTimeToSignalData.py). 
step 5. The signal data should be updated with the closest match in time for DLT.

/**************************************************************************/
This is how the data should look like when used in open space 
/**************************************************************************/
{
    "Signals": [
        {
            "eot": "2013-337T14:00:00",
            "facility": "DSS43",
            "bot": "2013-337T09:15:00",
            "projuser": "VGR2",
            "direction": "both",
            "DLT": "  5.19235527048887e+04"
        },
        {
            "eot": "2013-337T17:55:00",
            "facility": "DSS63",
            "bot": "2013-337T15:45:00",
            "projuser": "VGR1",
            "direction": "downlink",
            "DLT": "  6.33551683321189e+04"
        }
    ]
}
