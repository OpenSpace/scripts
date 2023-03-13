# This script is ment to simplify copying over urls from a list from a datasource to
# a servers identifier.json file , instead of needing to do it one line at a time manualy.
# The output text document will be overwriten ever run of the script.

# Edit the data variable by copying in your html file and remove what ever is not part of the table.
# note: Add a line break with \ at the end of each row for python to recognize it as one line
# Edit the numberOfLinesInData variable by selecting something that is unique in each row
# Edit the folder variable with what ever your folder is. 
	# include the http part. ex. http://liu-se.cdn.openspaceproject.com/ 
# Edit the subfolder vaiable to what ever you subfolder is.
	# ex.files/solarsystem/sun/bastille_day_event/bastille_day_mas_density/v1_v1/
# Edit the filenameLengthvariable with the number of characters of the file name
# Make sure the it variable uses find on something unique on each row that is 
	# before the file name, as well as edit the number to iterate to the first 
	# character of the file name 
	# ex. it = data.find('href', ... and it+=6;

# When output is succussfully written to file, copy everything and add 
	# to your identifiers.json file.
# If you use sublime text 3 to edit you json file, replace the \n with line break like so:
# Use Find > Replace... , or (Ctrl+H), to open the Find What/Replace With Window, and use
# Ctrl+Enter to indicate a new line in the Replace With inputbox.