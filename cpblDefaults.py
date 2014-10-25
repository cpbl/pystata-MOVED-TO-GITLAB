#!/usr/bin/python
# -*- coding: utf-8 -*-
"""

2013 Nov: Restarting cpblDefaults.py from scratch. Bring back in other elements, like statscan, gallup, etc as needed.  See comments in cpblDefaults2013.py which will contain all remnants of code not yet separated out by theme.

"""
from copy import deepcopy
import os


def fDefaults(mode=None):
    Defaults=dict()


    boxName=os.uname()[1]
    curdir=os.getcwd()
    if curdir  in  ['/home/cpbl/bin','/home/cpbl/Dropbox/bin']:
        DefaultsMode='bin'
    elif 'gallup' in curdir:
        DefaultsMode='gallup'
    elif 'rdc' in curdir or 'srdc' in curdir:
        DefaultsMode='canada'
    elif 'gallup' in curdir or 'srdc' in curdir:
        DefaultsMode='gallup'
    elif 'bin/panel' in curdir  or 'panel/bin' in curdir or 'cpbl/panel/klips' in curdir or 'JungKim' in curdir:
        DefaultsMode='klips'
    elif 'sprawl' in curdir or 'unknown' in os.uname()[1] or 'ucsc' in os.uname()[1]:
        DefaultsMode='sprawl'
    elif boxName == 'projects/sprawl' in curdir:
        DefaultsMode='sprawl'
    else:
        from cpblUtilities import cwarning
        #cwarning(' Alert! Cannot discern mode from cwd')
        print(' cpblDefaults: Alert! Cannot discern mode from cwd')
        import imp
        try:
            imp.find_module('filepaths')
            found = True
        except ImportError:
            found = False

        DefaultsMode='sprawl' if found else 'unknown' #return(Defaults)#DefaultsMode=None
    print(DefaultsMode)

    Defaults={}##'unix':unixDefaults,'cygwin':cygwinDefaults,'windows':ntDefaults}

    Defaults['islaptop']= boxName in ['cpbl-thinkpad','cpbl-eee','cpbl-tablet']
    Defaults['manycoreCPU']='apollo' in boxName
    Defaults['islinux']=os.uname()[0].lower()=='linux' or os.uname()[1].lower()=='linux'
    # Oh, a better way:
    #Defaults['islinux']=(os.path.exists(unixDefaults['userhome']+'') or Defaults['inRDC']) and (os.uname()[0].lower()=='linux' or os.uname()[1].lower()=='linux')

    dirchar='/'

    # phome is some kind of top level folder, which may contain most other relevant folders, or symlinks to them.
    # However, it is updated or overwritten for the major modes, which have their own customized definitions.
    phome={'sprawl':'/home/projects/sprawl/',
           'gallup':'/home/cpbl/gallup/',
           'canada':'/home/cpbl/rdc/',
           'panel':'/home/cpbl/panel/',
           # Choose KLIPS path: for me or Jung Hwan on Apollo, or for me on laptop:
           'klips':[ppp for ppp in ['/home/cpbl/okaistudents/Barrington-Leigh/JungKim/','/OKAI/Barrington-Leigh/JungKim/','/home/cpbl/panel/klips/'] if os.path.exists(ppp)][0] if 'apollo' in boxName else '/home/cpbl/panel/klips/',
               }.get(DefaultsMode,os.getcwd()+'/')

    paths={'local':phome,
           'bin':phome+'bin/',
           'working':phome+'workingData/',
           'input':phome+'inputData/',
           'graphics':phome+'graphicsOut/',
           'tex':phome+'texdocs/',
           }
               
    Defaults['stataVersion']='linux12'
    Defaults['mode']=DefaultsMode
    Defaults['paths']=paths
    if DefaultsMode in ['sprawl']:
        from filepaths import paths
        Defaults['paths']=paths
    Defaults['native']={'paths':paths}
    if DefaultsMode in ['gallup']:
        Defaults=gallup_update_defaults(Defaults)
    if DefaultsMode in ['canada']:
        Defaults=rdc_update_defaults(Defaults)
    if DefaultsMode in ['canada','gallup','sprawl']:
        for pp in Defaults['paths'].values():
            if not('OKAI' in pp and 'adam.millard-ball@mcgill.ca' in os.getlogin()):
                    # amb Jan 2014: this was my workaround to avoid an issue of sudo arcgis not accessing OKAI
                    assert os.path.exists(pp) 
    return(Defaults)

def gallup_update_defaults(gallupD):
    if os.path.exists('/home/cbarri5/okai/gallup/'):
            gallupD['paths']['working']='/home/cpbl/okai/gallup/workingData/'
            gallupD['paths']['tex']='/home/cpbl/okai/gallup/texdocs/'
            gallupD['paths']['graphics']='/home/cpbl/okai/gallup/graphicsOut/'
    from copy import deepcopy
    gallupD['paths']['scratch']=gallupD['paths']['working']
    gallupD['stata']={'paths':deepcopy(gallupD['paths'])}

    gallupD['gallup']={
        'MAX_WP5':199,
        'MAX_WAVE':7,
#gDataVersion='The_Gallup_061808' # This is the latest inclusive data file
#gDataVersion='The_Gallup_111008-fromST' # This is the latest inclusive data file
#gDataVersion='The_Gallup_121708-fromST' # This is the latest inclusive data file: late Dec 2008
#gDataVersion='The_Gallup_042009' # This is the latest inclusive data file: April 2009. But what is new? wp7969 is still largely missing, there are just a few extra samples... N.B.: I SHOULD've resaved this with after "renvars *,lower"
#        'GWPdataVersion':'The_Gallup_071709'#  Resaved with lowercase variable names

#        'GWPdataVersion':'The_Gallup_041610'# NOT!  Resaved with lowercase variable names
         #'GWPdataVersion':'The_Gallup_071610', # renvars *,lower, saved as tmp_The .. in WP
         #'GWPdataVersion':'The_Gallup_101510', # renvars *,lower, saved as tmp_The .. in WP
            #'GWPcodebookTSV':unixDefaults['userhome']+'gallup/inputData/20101015/World_Poll_Documentation_101510.tsv',
         #'GWPrawdataDir':'/home/cpbl/gallup/inputData/20101015/',
            #'version':2010.8 # = 2010C
           #'GWPdataVersion':'The_Gallup_041511', # renvars *,lower, saved as tmp_The .. in WP
            #'GWPrawdataDir':'/home/cpbl/gallup/inputData/20110415/',

         # I think I sould make this obselete... since I need to know data row etc too.. ie. Just look in recodeGallup
            #'GWPcodebookTSV':'/home/cpbl/gallup/inputData/20110415/World_Poll_Documentation_041511.tsv',
            # Okay.. I'm making this obselete. recodeGallup now dfines the codebook/doc files..
            #'GWPcodebookTSV':'/home/cpbl/gallup/inputData/20120120/World_Poll_Documentation_012012.tsv',
        #'version':2010.6
            #'version':2011.4 # = 2011A

            #'version':2012.1, # = 2012A
            #'GWPrawdataDir':'/home/cpbl/gallup/inputData/20120120/',
           # 'GWPdataVersion':'The_Gallup_012012', # renvars *,lower, saved as tmp_The .. in WP
            #'version':2012.3, # = 2012C,D
            #'GWPdataVersion':'The_Gallup_042712', # renvars *,lower, saved as tmp_The .. in WP
            #'GWPrawdataDir':unixDefaults['userhome']+'gallup/inputData/20120427/',
            #'version':2012.7, # = 2012E
            #'GWPdataVersion':'The_Gallup_072712', # renvars *,lower, saved as tmp_The .. in WP
            #'GWPrawdataDir':unixDefaults['userhome']+'gallup/inputData/20120727/',
            'version':2012.9, # = 2012F
            'GWPdataVersion':'The_Gallup_012513',
            'GWPrawdataDir':gallupD['paths']['input']+'/20130125/',
            }

    return(gallupD)
def rdc_update_defaults(rdcD):
    if os.path.exists('/home/cbarri5/okai/rdc/'):
            rdcD['paths']['working']='/home/cpbl/okai/rdc/workingData/'
            rdcD['paths']['tex']='/home/cpbl/okai/rdc/texdocs/'
    rdcD['paths']['scratch']=rdcD['paths']['working']
    from copy import deepcopy
    rdcD['stata']={'paths':deepcopy(rdcD['paths'])}
    rdcD['stata']['os']='posix'


    rdcD['inRDC']=os.path.exists('/home/srdc')


    rdcD['shortnames']=dict([['GSS%d'%n,'G%d'%n] for n in range(1,30)])
    rdcD['shortnames'].update({'ESC2':'E2','ESC1':'E1','EDS':'ED','CCHS31-PUMF':'C3P','CCHS31':'C3','CCHS21':'C2','CCHS21-PUMF':'C2P','CCHS2007':'C7','CCHS20072008':'C78'})
    # As of 2010Feb, I'm making HR a custom region, in order that I can construct it for any census/survey data. I've made DA2HR lookup tables for 2001, 2006
    rdcD['customRegions']=['A15','A50','HR']

    # Set some year associations for aggregating surveys: OH THIS IS UNCLEAR. IT SHOULD BE A RANGE... MAKE ANOTHER CALLED SURVEYDATES
    rdcD['surveyYears']={'ESC1':[2001],
                             'GSS1':[1985],
                             'GSS2':[1986],
                             'GSS3':[1988],
                             'GSS4':[1989],
                             'GSS5':[1990],
                             'GSS6':[1991],
                             'GSS7':[1992],
                             'GSS8':[1993],
                             'GSS9':[1994],
                             'GSS10':[1995],
                             'GSS11':[1996],
                             'GSS12':[1998],
                             'GSS13':[1999],
                             'GSS14':[2000],
                             'GSS15':[2001],
                             'GSS16':[2002],
                             'GSS17':[2003], # Feb to Dec 2003
                             'GSS18':[2004],
                             'GSS19':[2005],# Jan to Dec 2005
                             'EDS':[2002],# April to August 2002
                             'ESC2':[2002,2003],# Dec 2002 to July 2003, but not uniformly by month! Peak in April
                             'GSS20':[2006], # Exact dates??
                             'GSS21':[2007],
                             'GSS22':[2008],
                             'GSS24':[2010],
                             'GSS25':[2011],
                             # All following should be checked
                             'CCHS31-PUMF':[2006], # PUMF says August 2006 No that's not interview date, though.. Shoot -- that's probably not in PUMF
                             'CCHS21':[2003], #
                             'CCHS21-PUMF':[2003], #
                             'CCHS31':[2005], #
                             'CCHS2007':[2007], #
                             'CCHS20072008':[2007,2008], #
                             'CCHS20082009':[2008,2009], #
                             'CCHS20092010':[2009,2010], #
                             'CCHS2010-PUMF':[2010], #
                             'CCHS20112012':[2011,2012], #
                             'CCHS2012-PUMF':[2012], #
                             # Agh! What is this doing here?!2013. This messes up stuff.
                             'masterCCHS':[0],
                             }
    rdcD['surveyDates']={'ESC1':[2001],
                             'GSS1':[1985],
                             'GSS2':[1986],
                             'GSS3':[1988],
                             'GSS4':[1989],
                             'GSS5':[1990],
                             'GSS6':[1991],
                             'GSS7':[1992],
                             'GSS8':[1993],
                             'GSS9':[1994],
                             'GSS10':[1995],
                             'GSS11':[1996],
                             'GSS12':[1998],
                             'GSS13':[1999],
                             'GSS14':[2000],
                             'GSS15':[2001],
                             'GSS16':[2002],
                             'GSS17':[2003], # Feb to Dec 2003
                             'GSS18':[2004],
                             'GSS19':[2005],# Jan to Dec 2005
                             'EDS':[2002],# April to August 2002
                             'ESC2':[2002,2003],# Dec 2002 to July 2003, but not uniformly by month! Peak in April
                             'GSS20':[2006], # Exact dates??
                             'GSS21':[2007],
                             'GSS22':[2008],
                             'GSS24':[2010],
                             'GSS25':[2011],
                             # All above are not yet filled in.
                             'CCHS21':[2003.05,2003.95], #
                             'CCHS21-PUMF':[2003.05,2003.95], #
                             'CCHS31-PUMF':[2005.05,2005.95], #
                             'CCHS31':[2005.05,2005.95], #
                             'CCHS2007':[2007.05,2007.97], #
                             'CCHS20072008':[2007.05,2008.95], #
                             'CCHS20082009':[2008.05,2009.95], #
                             'CCHS20092010':[2009.05,2010.95], #
                             'CCHS2010-PUMF':[2010.05,2010.95], #
                             'CCHS20112012':[2011.05,2011.95], #
                             'CCHS2012-PUMF':[2012.05,2012.95], #
                             }

    rdcD['surveyYearsString']={}
    for ss in rdcD['surveyYears']:
        rdcD['surveyYearsString'][ss]='-'.join([str(yy) for yy in rdcD['surveyYears'][ss]])


    ## rdcD['surveysByYear']={}
##     {2002:['GSS17','EDS','ESC2',],
##                                2003:['ESC2'],
##                                2005:['GSS19',],
##                                2006:['GSS20',]
##                                }
## #   rdcD['yearBySurvey']=
    rdcD['surveysByCensus']={2001:['GSS17','EDS','ESC2','CCHS21-PUMF','CCHS21'],
                               2006:['GSS19','GSS20','GSS22','GSS24','GSS25','CCHS31-PUMF','CCHS31','CCHS2007','CCHS20072008','CCHS20082009','CCHS20092010','CCHS2010-PUMF',
                             'CCHS20112012',
                             'CCHS2012-PUMF'],
                                }
    # Generate from above when smarter.  Well... no, I've now made it so that the value can be a dict rather than an int. When this is the case, it's another lookup which converts interview year to census year. This is all used when we do NOT want/use year interpolation from multiple censuses.
    # In following, I've set all 2006's to 2001, until I've done the DA translation from 2006 DAs back to 2001 DA regions. Many must have been renamed...
    # Okay, yes do generate from above, but then overwrite some things:
    rdcD['censusYearBySurvey']={}
    for yy in rdcD['surveysByCensus']:
        for sss in rdcD['surveysByCensus'][yy]:
            rdcD['censusYearBySurvey'][sss]=yy

    rdcD['censusYearBySurvey'].update({'CCHS21-PUMF':2001,'CCHS21':2001,'CCHS31-PUMF':2001,'CCHS31':2001,'masterCCHS':{2005:2001,2006:2001,2001:2001},})

    ###rdcD['knownSurveys']=['ESC1','ESC2','EDS','GSS17','GSS19','GSS20']
    GSSpoolCycles=['GSSp%d'%nn for nn in range(1,21)]
    allGSS=['GSS%d'%d for d in range(1,30)]
    rdcD['knownSurveys']=['ESC2','EDS',]+allGSS+['CCHS31-PUMF','CCHS31','CCHS21','CCHS21-PUMF','CCHS1.2','CCHS2007','CCHS20072008','CCHS20082009','CCHS20092010','CCHS2010-PUMF',                             'CCHS20112012',
                             'CCHS2012-PUMF'  ]+GSSpoolCycles
    #rdcD['knownSurveys']=['CCHS31']
    if rdcD['inRDC']:
        rdcD['availableSurveys']=['CCHS31','CCHS21','CCHS2007','ESC2','EDS','GSS19','GSS17','GSS20','GSS22']+GSSpoolCycles#,'ESC1']]#-PUMF',]#
    else:
        # Naming simplication: Now simplify things so that we do not need the PUMF suffixes!
        # The 20072008 is a PUMF; the 2007 is in RDC, so far...
        rdcD['availableSurveys']=['CCHS31-PUMF','CCHS21-PUMF','CCHS20072008','CCHS20082009','CCHS20092010','CCHS2010-PUMF','CCHS20112012','CCHS2012-PUMF','ESC2',]+allGSS
        # [#'EDS','GSS17','GSS19','GSS20',]#,'ESC1']
    #if 0 and os.path.exists(unixrdcD['userhome']+'') and os.uname()[1] in ['cpbl-server']:
    #    rdcD['availableSurveys']=['CCHS31-PUMF','ESC2']#,'ESC1']


    # Set some locations of raw files, since within the RDC I need not copy them to my own directory if they are already available in Stata format:
    rdcD['rawStataFile']={}
    for survey in rdcD['knownSurveys']:
        rdcD['rawStataFile'][survey]=rdcD['native']['paths']['input']+survey+'/'+survey+'.dta.gz'
        if 0 and survey=='GSS19':
            rdcD['rawStataFile'][survey]='i:/gss19/data/stata/c19analm_num_e.dta.gz'
        #if survey=='GSS20':
        #    rdcD['rawStataFile'][survey]='i:/gss20/data/stata/c20analm_num_e.dta.gz'
    for survey in GSSpoolCycles:
        rdcD['rawStataFile'][survey]=rdcD['native']['paths']['input']+'GSSpool/'+survey+'.dta.gz'


    if rdcD['inRDC']:
        rdcD['weatherSurveys']={
        'ESC2':[2002,2003],
        'CCHS':rdcD['surveyYears']['CCHS21']+rdcD['surveyYears']['CCHS31'],
        'CCHS21':rdcD['surveyYears']['CCHS21'],
        'CCHS31':rdcD['surveyYears']['CCHS31'],
        'GSS19':[2005],
        'ESC1':[2001],
        }
    else:
        rdcD['weatherSurveys']={
        'ESC2':[2002,2003],
        #'ESC1':[2001],
        }
    for ss in     rdcD['weatherSurveys'].keys():
        if not ss in rdcD['availableSurveys']+['CCHS']:
            rdcD['weatherSurveys'].pop(ss)


    ###if os.path.exists(unixrdcD['userhome']+'rdcLocal'): # ie my laptop
    ####    rdcD['availableSurveys']=['ESC2','EDS','GSS17','GSS19','GSS20']#,'ESC1']
    import time
    rdcD['weatherYears']=range(2000,time.localtime()[0])#[2000,2001,2002,2003,2004,2005,2006,2007]#[2002,2003,2005,2006,]#

    # Set some formatting strings for standardized CR uid names:
    rdcD['CRuidFormats']= {'CT':'%010.2f',
                               'DA':'%08.0f',
                               'CSD': '%07.0f',
                               'CD': '%04.0f',
                               'CMA': '%03.0f',
                               'PR': '%02.0f',
                               'A15': '%07.0f',
                               'A50': '%05.0f',
                               'HR': '%04d',
                               }

    # This is a list of what CRuids should be available (for calculating means, etc) for each survey.
    rdcD['CRsBySurvey']={}

    for sss in rdcD['knownSurveys']:
        if rdcD['inRDC']:
            rdcD['CRsBySurvey'][sss]= ['DA','CT','CSD','CD','CMA','PR','A50','A15','HR']
            if sss in GSSpoolCycles: #
                rdcD['CRsBySurvey'][sss]= ['PR',]
        else:
            rdcD['CRsBySurvey'][sss]= ['PR','HR'] if sss.startswith('CCHS') and sss not in ['CCHS20082009'] else ['PR']
    for sss in ['CCHS31','CCHS21','ESC2']+rdcD['inRDC']*['GSS17','GSS19']:
        rdcD['CRsBySurvey'][sss]=['DA','CT','CSD','CD','CMA','PR','A50','A15']
    for sss in ['CCHS31-PUMF','CCHS21-PUMF','CCHS20072008']+(not rdcD['inRDC'])*['CCHS31','CCHS21']:
        rdcD['CRsBySurvey'][sss]=['HR','PR']

    # For any survey with CT available, the custom regions A15 and A50 should be madeavailable.
    # For any survey with DA available, the custom region HR should be made available.
    for ss in     rdcD['CRsBySurvey']:
        if 'CT' in rdcD['CRsBySurvey'][ss] and 'A15' not in rdcD['CRsBySurvey'][ss]:
            rdcD['CRsBySurvey'][ss]+=['A15','A50']
        if 'DA' in rdcD['CRsBySurvey'][ss] and 'HR' not in rdcD['CRsBySurvey'][ss]:
            rdcD['CRsBySurvey'][ss]+=['HR']

    # Following is not good!!! It should come from the PRnames file, really??
    # It's a list so I can put it in order! E to W, roughly:
    rdcD['provinceNames']=[
 ['10', 'Nfld & Lab.'],
 ['12', 'Nova Scotia'],
 ['11', 'PEI'],
 ['13', 'New Brunswick'],
 ['24', 'Quebec'],
['35', 'Ontario'],
 ['46', 'Manitoba'],
 ['47', 'Saskatchewan'],
 ['48', 'Alberta'],
 ['59', 'British Columbia'],
 ['62',      'Nunavut',],
 ['61',  'NWT', ],
 ['60', 'Yukon/NWT/Nuna.'],
 #
] #['01','Canada']
    name2uid=dict([[b,a] for a,b in rdcD['provinceNames']])
    name2uid['Newfoundland and Labrador']=name2uid['Nfld & Lab.']
    name2uid['Newfoundland']=name2uid['Nfld & Lab.']
    name2uid['Prince Edward Island']=name2uid['PEI']
    name2uid ['Terre-Neuve-et-Labrador'] = name2uid['Nfld & Lab.']
    name2uid ['Terre-Neuve'] = name2uid['Nfld & Lab.']
    name2uid ['Île du Prince Édouard'] = name2uid ['PEI']
    rdcD['PRnameToPRuid']=name2uid
    # This struct is further updated below, with two-letter codes.
    rdcD['PRtoFrench']={
'British Columbia':'Colombie-Britannique',
 'New Brunswick':'Nouveau-Brunswick',
'Newfoundland':'Terre-Neuve',
'Nfld & Lab.':'Terre-Neuve et Lab.',
'Nova Scotia':'Nouvelle-Écosse',
'Northwest Territories':'Territoires du Nord-Ouest',
'Prince Edward Island':'Île du Prince Édouard',
'Quebec':'Québec',
 'Yukon Territory':'Territoire du Yukon',
 }

    rdcD['provinceShortNames']=[['35', 'ON'], ['10', 'NF'], ['11', 'PE'], ['12', 'NS'], ['13', 'NB'], ['46', 'MB'], ['47', 'SK'], ['48', 'AB'], ['24', 'QC'], ['59', 'BC'], ['60', 'YT/NT/NU'],['61', 'NWT'],['62', 'NU']]

    """
    *  AB - Alberta
    * BC - British Columbia
    * MB - Manitoba
    * NB - New Brunswick
    * NF - Newfoundland
    * NS - Nova Scotia
    * NT - Northwest Territories
    * NU - Nunavut
    * ON - Ontario
    * PE - Prince Edward Island
    * QC - Quebec
    * SK - Saskatchewan
    * YT - Yukon Territory
"""
    # Also allow PRuid lookup by two-letter codes:
    for uid,pr in rdcD['provinceShortNames']:
        rdcD['PRnameToPRuid'][pr]=uid


    return(rdcD)

# 2014: Following makes no sense to me. We set it always to be privateMode, so how can it affect anything?
# privateMode member
global privateMode # Make this accesible to all instances of cpblDefaults, ie every time it gets called/imported...
privateMode=''
# The goal here is to allow the first invocator of cpblDefaults to modify it. Then, it will not be updated by any other modules which call it.

if not privateMode:
    defaults= fDefaults(mode=None)
    RDC=False
    PUMF=False
    if defaults and defaults['mode'] in ['canada','statscan','RDC','gallup']:
        if defaults['mode'] in ['canada','statscan']:
            RDC=defaults['inRDC']
            PUMF=not RDC
    if defaults:
        paths=defaults['paths']
        WP=defaults['paths']['working']
        IP=defaults['paths']['input']

if __name__ == '__main__':
    print( defaults)




