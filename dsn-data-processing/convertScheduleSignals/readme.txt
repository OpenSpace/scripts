/***************************************************************************/
This is a guideline to convert json data from the format provided by JPL 
to a format that will work in OpenSpace running your DSN module.
/***************************************************************************/

step 1. Make sure you have the proper data to your DATAPATH
step 3. Run the script scheduleToJson.py 
step 4. Check that the folder "parsed" has been updated with the parsed data.

/***************************************************************************/
Double checks of data
/***************************************************************************/

The data from JPL should be seperated into files for every new week and the data should have the format: 


*                      DSN 7-DAY OPERATIONS SCHEDULE
*                            ACTIVITIES LISTING
*                   WEEK NO. 01 *** 30 DEC 13 -  5 JAN 14
*-------------------------------------------------------------------------------
*DAY START BOT  EOT  END FACILITY USER   ACTIVITY         PASS  CONFIG/ WRK A C
*                                                         NO.   SOE     CAT R F
*-------------------------------------------------------------------------------
*----------
*MON 30 DEC
*----------
 364 0010 0110 0210 0225  DSS-24  CHDR   TKG PASS         0364  N064  A 1A1    
          CCP,NMC,RNG,RRPA,SHMT,STXL,TLPA,UPL;                                  
 364 0015 0130 0915 0930  DSS-55  MRO    MA11             0364  N120    1A1    
          CCP,NMC,RNG,RRPB,TLPA,UPL,XHMT,XTXL;                                  
 364 0030 0130 0505 0520  DSS-54  M01O   TKG PASS         0364  N003    1A1    
          CCP,NMC,RNG,RRPA,TLPB,UPL,XHMT,XTXL;                                  
 364 0040 0110 0215 0230  DSS-63  GTL    TR DUMP 131S     0364  N030  F 1A1    
          NMC,RRPA,SHMT,TLPA;                                                   
 364 0055 0055 0310 0310  DSS-15  DSN    ALB/SPS AT             NONE    2C2    
                                                                        
 364 0140 0310 0510 0540  DSS-14  GSSR   EUROPA/GANYMEDE        T012    1B5    
          NMC;                                                                  
 364 0140 0240 0600 0615  DSS-34  SOHO   UPO LGA MR       0364  N064  M 1A1    
          CCP,NMC,RNG,RRPA,SHMT,STXL,TLPA,UPL;                                  
 364 0225 0225 0810 0810  DSS-24  DSN    RRT SW V11.3 AT        NONE    2C1    
                                                                        
 364 0330 0415 0815 0830  DSS-43  STF    TKG PASS         0364  N001    1A1    
          CCP,NMC,RRPA,TLPB,UPL,XHMT,XTXL;                                      
 364 0345 0445 0645 0700  DSS-65  M01O   TKG PASS         0364  N006    1A1    
          CCP,NMC,RNG,RRPA,TLPB,UPL,XTWM,XTXL;                                  
 364 0555 0625 0915 0930  DSS-55  M01O   MAX2             0364  N008    1A1    
          NMC,RRPA,TLPB,XHMT;                                                   
 364 0600 0700 0800 0815  DSS-45  ACE    RNG ONLY         0364  N046  P 1A1    
          NMC,RNG,RRPA,SHMT,STXL,TLPA,UPL;                                      
 364 0602 0632 0734 0749  DSS-15  CLU1   WBD              0364  N030  A 1A1    
          NMC,RRPA,SHMT,TLPA;                                                   
 364 0602 0632 0734 0749  DSS-14  CLU4   WBD              0364  N030  A 1A1    
          NMC,RRPA,SHMT,TLPA;                                                   
 364 0610 0640 0715 0730  DSS-63  THC    SSR DUMP/UNATT   0364  N030  T 1A1    
          NMC,RRPA,SHMT,TLPA;                                                   
                                                                PAGE:   2



The resulting data in result.json should look something along the lines like this: 

	{
   	 "Signals": [
     	   {
            "facility": "DSS34",
            "bot": "2018-362T09:15",
            "eot": "2018-362T12:40",
            "projuser": "MRO",
            "direction": "both",
            "DLT": 0
     	   },
     	

and so on.....


/********************************************************************************
About the dishes
/********************************************************************************
The following dishes are not part of NASAs three ground stations and are therefore 
not included in the data. 

DSS95 - India
DSS48 - Japan

DSS84 - ESA

DSS74 - ESA
