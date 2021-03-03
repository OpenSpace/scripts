/***************************************************************************/
This is a guideline to convert json data from the format provided by JPL 
to a format that will work in OpenSpace running the DSN module.
/***************************************************************************/

step 1. This is done for each spacecraft seperatly
step 2. Make sure you have the proper data to your localPath
step 3. Make sure you have the porpoer spacecraft selected for "spacecraftName"
step 4. Make sure there's an empty folder named like the spacecraft in the parsed folder.
step 5. Run the script csvToJson.py 
step 6. Check that the folder specified has been updated with the parsed data.

/***************************************************************************/
Double checks of data
/***************************************************************************/

The data from JPL should be seperated into files for every new week and the data should have the format: 


2018-244T12:03:00.000000,  2.54409651864157e+02, -2.41668089327785e+01,  6.74353051254649e+07,  2.54407988835268e+02, -2.41673373603530e+01,  6.74411634388243e+07,  3.01899446194386e+02, -2.59729675968447e+01,  6.74327020675999e+07, 
 3.01899789162305e+02, -2.59744881676221e+01,  6.74385592956549e+07,  2.24939965385870e+02,  4.49909371852875e+02,  2.27388233489929e-05,  2.24959506615821e+02,  4.49889572978020e+02,  2.12970840471860e-05,  4.25916549075932e-05


The resulting data in result.json should look something along the lines like this: 
{
    "Positions": [
        {
            "TimeStamp": "2018-244T12:00",
            "RAUp": "  3.01899520526456e+02",
            "DecUp": " -2.59736044529448e+01",
            "GeoRngUp": "  6.74315513366134e+07",
            "DLT": "  2.24955720183651e+02"
        },
        {
            "TimeStamp": "2018-244T12:01",
            "RAUp": "  3.01899485968703e+02",
            "DecUp": " -2.59733954512235e+01",
            "GeoRngUp": "  6.74319313496176e+07",
            "DLT": "  2.24956972094499e+02"
        },

and so on.....