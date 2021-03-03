/***************************************************************************/
This is a guideline to convert json data from the format provided by JPL 
to a format that will work in OpenSpace running your DSN module.
/***************************************************************************/

step 1. Make sure you have the proper data to your DATAPATH
step 2. Change the filepath convertDataToOpenSpace.py  if necessary in to the DATAPATH where you have your data
step 3. Run the script convertDataToOpenSpace.py 
step 4. Check that the folder "parsedData" has been updated with the parsed data.

/***************************************************************************/
Double checks of data
/***************************************************************************/

The data from JPL should be json files and have json objects with something along the lines like this: 

	{"endtime":"2016-160T04:45:00","starttime":"2016-160T01:40:00",
	"activityid":456574,"nib":" ","configcode":"N007","wrkcat":"1A1","version":72,"scheduleitemid":10096580,
	"eot":"2016-160T04:30:00","facility":14,"equipmentlist":"NMC,RRPA,TLPA,XHMT","bot":"2016-160T02:10:00",
	"activitytype":"SSPA","soecode":"A","year":2016,"projuser":"VGR1","activity":"SCIENCE         ","week":23}



The resulting data in result.json should look something along the lines like this: 

	{
   	 "Signals": [
     	   {
   	        "activityid": 517141,
   	         "eot": "2018-246T07:45:00",
   	         "facility": "DSS14",
   	         "bot": "2018-246T03:10:00",
    	        "year": 2018,
    	        "projuser": "VGR1",
     	       "direction": "downlink"
     	   },
     	   {
      	      "activityid": 517164,
     	       "eot": "2018-246T20:25:00",
     	       "facility": "DSS43",
     	       "bot": "2018-246T16:40:00",
      	      "year": 2018,
      	      "projuser": "VGR2",
     	       "direction": "both"
    	    },

and so on.....