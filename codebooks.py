#!/usr/bin/python
"""

To do: 
 - In Stata, "label list" gives an instant readout of all value labels. Use this rather than labelbook !?! [oct 2011]

2013: Also, use statsmodels' pydta package as soon as its slightly mature! (now?)

2013: Major issue with value labels has been horrid unicode support by Stata. How to get good encoding in .log output?
 --> TO DO: read in with codec, not file
                # May 2013: check for funny chars?
                
"""
from .pystata_config import defaults,paths
assert defaults is not None

#try:
from cpblUtilities import tsvToDict,doSystem, debugprint,dgetget
#uniqueInOrder, debugprint, tsvToDict, chooseSFormat, orderListByRule,str2latex, fileOlderThan, tonumeric, fNaN, renameDictKey,cwarning,str2pathname, dgetget, doSystem,shelfSave,shelfLoad
from cpblUtilities.cpblunicode import str2latex
from cpblUtilities.textables import chooseSFormat
#    #from cpblUtilities.mathgraph import  seSum,mean_of_means
#except ImportError:
#    print(__file__+": Unable to find or import? CPBL's utilities package. Test: importing it directly.")
#    import sys
#    print("     Here's the current path: "+str(sys.path))

from copy import deepcopy
#from pystata import stataSystem,stataLoad

from codecs import open # arrrrgh. i hate unicode in python<3. dec 2011

import os
import re

def shortenStataName(ss,ml=31):
    if len(ss)<ml:
        return(ss)
    if '_' in ss:
        return(shortenStataName(ss.replace('_','')))
    return(ss[:ml])
###########################################################################################
###
class stataCodebookClass (dict):  #  # # # # #    MAJOR CLASS    # # # # #  #
    ###
    #######################################################################################
    """
    Allow outsiders to access the main data member, the dict "codebook". This is basically, then, just a wrapper for the associated functions. It's a child of dict, so you can refer to instances directly.

    N.B.: There are othe functions, in extractCodebooks, that get the info from non-Stata means.. Well, maybe I'll move those into pystata too??

    Dec 2008, CPBL.

    May 2009: this seems a mess. I have redundant code and efforts in differently places... Maybe consolidate more/all in this quite-extensive class... I am trying today to add a fromPDF option. It takes the .txt file (or the .pdf filee)

    I should also make it so that if the fromXXXX argument is the name of a survey rather than a filename, the appropriate filename is constructed. (Hm, I am just making a survey= argument that should do the best from what's available)


    July 2009: I am changing an argument from forceRecreate to recreate. It's None as default.  a "False" means do not recreate even if you think you should! ie if the file is outdated. a "True" means recreate no matter what. The default will do the smart thing if you're not in a rush or suspect the codebook log file is broken (in which case you should just delete it anyway).
    Hm.. Adding "showVars" option to __init__: to restrict variables taken from fromDTA.

2010Feb: Adding a "survey" option for __init__:

Fields in a stataCodebookClass object:
'labelbook',   : raw text from a Stata labelbook command
'stataCodebook', raw text from a Stata codebook command
'labels',   lookup dict from values to labels
'prompt',  the question in the survey, corresponding / relating to this variable [non-unique??]
'desc',  a description of the variable
'labelsname': the name (in some other application? like Stata) to be used for the value labels object.
...


    """

    def __init__(self,fromDTA=None,fromTSV=None,fromPDF=None, loadName=None,codebook=None,  recreate=None, toLower=None,showVars=None,survey=None,version=None,stringsAreTeX=None):#*args,foo=None):  # Agh. June 2010: added "version" here this might confuse things, but there was a bug...
        """ Allow instantiation from a dict (codebook=dict) or from a Stata dataset itself (fromDTA=filename)

        myCodebook=stataCodebookClass()
        myCodebook=stataCodebookClass(fromDTA=myfilepath)
        myCodebook=stataCodebookClass(codebook=myDict)
        myCodebook=stataCodebookClass( a dict already in format of codebook)
            i.e.: {varname:    }

        """

        self._survey=None
        # Nov 2010: This setting tells whether variable descriptions are LaTeX-ready, or should be converted...
        self.stringsAreTeX=stringsAreTeX
        if self.stringsAreTeX is None:
            self.stringsAreTeX=False

        #assert fromDTA==None  or codebook==None
        if 0: # April 2010: Not sure these following two make sense anymore.
            assert recreate==None or fromDTA #
            assert toLower==None or fromDTA # pdf not yet done
        #assert (fromDTA==None and fromPDF==None) or codebook==None
        #assert (fromDTA==None or fromPDF==None)
        # For some applications, we may want to preserve the original order of the variables. So store it in this:
        self.__orderedVarNames=[]

        if fromDTA==None and codebook==None and fromTSV==None and fromPDF==None and survey==None:
            self.clear( )
            self.update({})

        if survey not in [None]: # I think (April 2010) that this is just becoming an interface to self.load() 
            self._survey=survey
            assert fromDTA==None and codebook==None and fromTSV==None and fromPDF==None

            self.load(survey,version=version) # May not work, ie the file may not exist.. But load() is supposed to be the smart thing, now, which just does whatever necessary to make it.
            #self.load(str2pathname(paths['working']+'codebook-'+survey)) # May not work, ie the file may not exist.. But load() is supposed to be the smart thing, now, which just does whatever necessary to make it.
            if toLower:
                self.allNamesToLowercase() # Hmm... this may have already been done in most cases, april 2010
            return
            # feb2010: Following untested And I am not sure PDF really works? And should I add fromTSV option?  Some surveys come with a spreadsheet codebook...
            # This should really check for a saved file ie try self.load(survey-codebook.pythonshelf) or etc.
            dta=defaults['rawStataFile'][survey]
            return(self.stataCodebookClass(fromPDF=survey,fromDTA=dta))


        if fromDTA and fromPDF and not fromTSV: # New initialisation mode, July 2009: load best available / combine them
            """
            What is this mode for? Only for starting to recode a survey, when the raw data are in DTA format and a PDF is also available. So.... should not really make any stats or tables from this yet, as we're about to recode it

            """

            assert not self
            PDFupper,PDFlower,DTAupper,DTAlower=False,False,False,False

            # First, read the PDF and get what we can from it.

            # Get (better!) codebook from the PDF:
            codebookPDF=stataCodebookClass(fromPDF=fromPDF,recreate=recreate,toLower=toLower)
            #self.fromPDFCodebook(fromPDF) # PRovide filename without suffix but with full path


            if all([kk.isupper() for kk in codebookPDF]):
                print("   Note that %s  variables in the PDF are ALL UPPERcase"%fromPDF)
                PDFupper=True
            if all([kk.islower() for kk in codebookPDF]):
                print("   Note that %s  variables in the PDF are ALL LOWERcase"%fromPDF)
                PDFlower=True


            """ Codebook PDf always has capital letter names...
            Codebook DTA seems to have lower case in the RDC.

            So I am making a bug for outside RDC for the moment so as to accomodate CCHS 2.1 and CCHS 3.1 inside...
            """

            # Next, Get codebook from the Stata file:
            # This now also includes summary statistics (Feb 2009)
            self.fromStataCodebook(fromDTA,recreate=recreate,showVars=showVars) # PRovide filename without dta suffix but with full path
            #codebookDTA=stataCodebookClass(fromDTA=fromDTA,recreate=recreate) # This will skip doing means since 'weight' does not exist.
            assert self.keys()
            if all([kk.isupper() for kk in self]):
                print("   Note that %s  variables in the DTA are ALL UPPERcase"%fromDTA)
                DTAupper=True
            if all([kk.islower() for kk in self]):
                print("   Note that %s  variables in the DTA are ALL LOWERcase"%fromDTA)
                DTAlower=True


            print 'Finished getting codebooks. Getting (possibly old) summary stats will hae been skipped.'


            # Now merge some infos
            # To do this, make a poiter lookup of the DTA codebook by its "rawnames":
            #rawLookup=[[codebookDTA[vv]['rawname'],codebookDTA[vv]] for vv in codebookDTA if codebookDTA[vv]['rawname']]
            # Uh... no, not yet. I am not sure that is possible..

            """ This should look at rawname too. does not yet."""
            for VV in codebookPDF:
                if toLower:
                    vv=VV.lower()
                if PDFupper and DTAlower:
                    vv=VV.lower()
                elif PDFupper and DTAupper:
                    vv=VV.lower()
                elif PDFlower and DTAlower:
                    vv=VV
                else:
                    Not_sure_here_WHATOTHERPOSSIBILITIESOCCUR
                if vv in self:#codebookDTA:
                    self[vv]['fulldesc']=codebookPDF[VV]['concept']+(': ``'+codebookPDF[VV]['question']+"''")*(not codebookPDF[VV]['question']=='')


            # DEC 2009: I'M TURNING THIS FUNCTOINALITY OFF FOR THE MOMENT If you want means, you have to ask for them specifically. So then we do not waste our time getting means of every single variable........
            if 0:
                if 'weight' in self:
                    sumstats=self.getDescriptiveStatistics(fromDTA,weightvar='weight',recreate=recreate,showVars=None)##,showVars=None,weightvar=None,ifcondition=None)
                    for vv in sumstats:
                        self[vv]['sumstats']=sumstats[vv]
                else:
                    print '   stataCodebookClass:__init__: Skipping creation of DescriptiveStatistics for %s because I do not know of a "weight" variable.'%fromDTA



            # Now make a table of summaries:
            self.summaryStatisticsTable_singleSurvey(descriptionField='fulldesc',showVars=self.orderedKeys(),texFilename=fromDTA+'-microSummaryStats.tex')#self,fields=None,showVars=None,texFilename=None,substitutions=None,includeQuestions=False):



        elif fromDTA:
            assert not self
            self.fromStataCodebook(fromDTA,recreate=recreate,toLower=toLower,showVars=showVars) # PRovide filename without dta suffix but with full path
            if 0: # SEEEE ABOVE COMENT
                if 'weight' in self:
                    sumstats=self.getDescriptiveStatistics(fromDTA,weightvar='weight',recreate=recreate,showVars=None)##,showVars=None,weightvar=None,ifcondition=None)
                    for vv in sumstats:
                        self[vv]['sumstats']=sumstats[vv]
                else:
                    print '   stataCodebookClass:__init__: Skipping creation of DescriptiveStatistics because I do not know of a "weight" variable.'
        elif fromPDF:
            assert not self
            self.fromPDFCodebook(fromPDF,toLower=toLower) # PRovide filename without suffix but with full path

        if fromTSV:
            assert not self
            self.fromTSVCodebook(fromTSV) # PRovide filename without suffix but with full path
        if codebook:
            assert not self
            self.clear()
            self.update(dict(codebook))
        if loadName:
            self.load(loadName,version=version)


##     def __init__(self,*args,foo=None):
##         """ Allow instantiation from a dict or from nothing
##         """
##         if len(args)==0: #
##             self.clear()
##             self.update({})
##         if len(args)==1: # dict # Needs more error checking for format...
##             self.clear()
##             self.update(dict(args[0]))



    ################################################################
    ################################################################
    def fromTSVCodebook(self,datafilepath): # PRovide filename without dta suffix but with full path
    ################################################################
    ################################################################
        print('Loading codebook from TSV for '+datafilepath)
        if datafilepath.endswith('.tsv'):
            datafilepath=datafilepath[0:-4]
        tsvs=tsvToDict(datafilepath+'.tsv',utf8=False)
        cbook=dict([[avd['varname'],avd]  for  avd in tsvs])

        self.update(cbook)
        if 0:
            ffffffffffffffffxxx,"make sure this is in utf-8?"
        self.__orderedVarNames=[LL[1] for LL in open(datafilepath+'.tsv','rt').readlines()[1:]]
        return

    
    ################################################################
    ################################################################
    def fromPDFCodebook(self,datafilepath, toLower=None):
    ################################################################
    ################################################################
        """ PDF derivatives go in workingPath (while DTA source derivatives can go in IP to save time).

        April 2010: Made gss22 PUMF work. maybe gss17.  but there's still TONNES to clean up in this messy class. Is not all this info available in a spreadsheet somewhere from stats can? Ridiculous lengths I am going to for little good (well, motivated by crappy DTAs from various places)

        2012Nov: added toLower

        """

        if datafilepath in defaults['availableSurveys']:
            survey=datafilepath
            if os.path.exists(paths['input']+survey+'/'+survey+'-codebook.pdf'):
                print 'Having to recreate the txt file from PDF! for '+paths['input']+survey+'/'+survey+'-codebook.pdf to '+paths['working']+survey+'-pdfcodebook.txt'
                doSystem("""
              pdftotext -layout %s %s"""%(paths['input']+survey+'/'+survey+'-codebook.pdf',paths['working']+survey+'-pdfcodebook.txt'))
                datafilepath=paths['working']+survey+'-pdfcodebook.tsv'
                _pdfcodebooktxt2tsv(paths['working']+survey+'-pdfcodebook.txt',datafilepath,survey=survey)
            elif os.path.exists(paths['input']+survey+'/'+survey+'-pdfcodebook.tsv'):
                datafilepath=paths['input']+survey+'/'+survey+'-pdfcodebook.tsv'
            elif os.path.exists(paths['working']+survey+'/'+survey+'-pdfcodebook.tsv'):
                datafilepath=paths['working']+survey+'/'+survey+'-pdfcodebook.tsv'
            elif os.path.exists(paths['input']+survey+'/'+survey+'-pdfcodebook.txt'):
                datafilepath=paths['working']+survey+'/'+survey+'-pdfcodebook.tsv'
                _pdfcodebooktxt2tsv(paths['input']+survey+'/'+survey+'-pdfcodebook.txt',datafilepath,survey=survey)
            else:
                print("You should rename the PDF codebook to surveyname+'-codebook.pdf'")
                print( "Failed to find PDF codebook for "+survey+", or its .txt child or its .tsv child!")
                stophere
                return
                #datafilepath=defaults['inputPath']+datafilepath+'_codebook.txt'

        if datafilepath.endswith('.txt') and os.path.exists(tsvfn):
                return(self.fromTSVCodebook(tsvfn))
        if datafilepath.endswith('.tsv') and os.path.exists(datafilepath):
                return(self.fromTSVCodebook(datafilepath))
        assert foodlefish
        #return(allVarsDict,varOrder)



        tsvs=tsvToDict(datafilepath+'.tsv',utf8=False)
        cbook=dict([[avd['varname'],avd]  for  avd in tsvs])

        self.update(cbook)
        self.__orderedVarNames=[LL[1] for LL in open(datafilepath+'.tsv','rt').readlines()[1:]]
        return


    ################################################################
    ################################################################
    def fromStataCodebook(self,datafilepath,recreate=None,toLower=None,showVars=None):
    ################################################################
    ################################################################
        """

        Initialise a codebook object from a Stata file's own information.
        If Stata's codebooks have not already been logged, or if they are older than the dta, Stata will be called.
        If it has, the resulting log files will simply be parsed.


        Takes a .dta stata file and generates text files containing the codebook and labelbook. Can be slow for big datasets!
        See the parsing function, next, for parsing said text files.

        (You might also google for PyDTA, a python package to import Stata data, but it is not a substitute).

        Note: the do file and log file goes in the source dir (do file has to go there since the statasystem call puts it in the same place). The tsv goes in workingPath.

        Note: this is run even on raw versions of datasets, which is kind of useless in the case of summary statistics, since they may contain all manner of non-response numeric values still...


        """
        import os
        from cpblUtilities import doSystem
        from pystata import stripdtagz

        datafilepath=stripdtagz(datafilepath)
        sourceDir,sourceName=os.path.split(datafilepath)
        assert '.' not in sourceName         # because stupid Stata screws up filenames for choosing log name/location!
        """
        if defaults['mode'] not in ['gallup','klips']:
            try: 
                from rdc_make import cpblRequireRDC as cpblRequire
                cpblRequire(datafilepath)
            except AssertionError: #placeholder; it'll be something elsee
                foiu
        """
        if not os.path.exists(datafilepath+'.dta.gz'):
            print('   ********* There is no data file '+datafilepath+' from which to make a codebook... so no DTA codebook for you!!!!! (If this is not solved by running through any Stata execution, something is wrong!)')#cwarning
            fooo
            return


        ###fxdnm=datafilepath#sourceDir+'/'+sourceName#.replace('.','_')
        CdoFileName=datafilepath+'_StataCodebook'+'.do' ## paths['working']+sourceName
        ClogFileName=datafilepath+'_StataCodebook'+'.log'

        if recreate==False:
            print ' WARNING!!!!!! RECREATE SET TO "FALSE", WHICH ALLOWS CODEBOOK TO BECOME OUTDATED. SET IT BACK TO DEFAULT "NONE"'

        # Logic below: if recreate is None, then check to see if log file is outdated or not. If recreate is True or False, then that overrides.
        forceC=recreate
        if recreate in [None,True] and not os.path.exists(ClogFileName):
            print('%s does not exist! Recreating from %s.'%(ClogFileName,datafilepath+'.dta.gz'))
            forceC=True
        elif recreate in [None,True] and os.path.getmtime(ClogFileName)<os.path.getmtime(datafilepath+'.dta.gz'):
            print('%s is older than %s!  Recreating it.'%(ClogFileName,datafilepath+'.dta.gz'))
            forceC=True
        showVarsString='codebook \n'
        if showVars:
            showVarsString="""
foreach var in  """+' '.join(showVars)+""" {
capture confirm variable `var',exact
if _rc==0 {
codebook `var'
}
}
"""
        if forceC:

            print '    To create '+CdoFileName+':  '
            from pystata import stataSystem,stataLoad
            rlogfn=stataSystem("""
              clear
            set more off
            """+stataLoad(datafilepath)+"""
             """+showVarsString+"""
            * DONE SUCCESSFULLY GOT TO END
            """)#,filename='tmp_doMakeCodebook')
            if 'DONE SUCCESSFULLY GOT TO END' in open(rlogfn,'rt').read(): #,encoding='utf-8' Nov 2012: removed the encoding line... hmmm.
                #import shutil
                #shutil.move(rlogfn,CdoFileName)
                doSystem('cp %s %s'%(rlogfn,ClogFileName))
                print " Overwrote "+ClogFileName
            else:
                print " Failed to update "+ClogFileName

        LdoFileName=datafilepath+'_StataLabelbook'+'.do' ## paths['working']+sourceName
        LlogFileName=datafilepath+'_StataLabelbook'+'.log'
        # Logic below: if recreate is None, then check to see if log file is outdated or not. If recreate is True or False, then that overrides.
        forceL=recreate
        if recreate in [None,True] and not os.path.exists(LlogFileName):
            print('%s does not exist! Recreating from %s.'%(LlogFileName,datafilepath+'.dta.gz'))
            forceL=True
        elif recreate in [None,True] and os.path.getmtime(LlogFileName)<os.path.getmtime(datafilepath+'.dta.gz'):
            print('%s is older than %s!  Recreating it.'%(LlogFileName,datafilepath+'.dta.gz'))
            forceL=True
        if forceL:

            print '    To create '+LdoFileName+':  '
            rlogfn=stataSystem("""
              clear
            set more off
            """+stataLoad(datafilepath)+"""
            labelbook
            * DONE SUCCESSFULLY GOT TO END
            """)#,filename='tmp_doMakeLabelbook')
            if 'DONE SUCCESSFULLY GOT TO END' in open(rlogfn,'rt').read():
                #import shutil
                #shutil.move(rlogfn,LdoFileName)
                doSystem('cp %s %s'%(rlogfn,LlogFileName))
                print " Overwrote "+LlogFileName
            else:
                print " Failed to update "+LlogFileName


        # Check work (and make a tsv version) by calling the following:
        # This sets self to the codebook.
        self.parseStataCodebook(ClogFileName,LlogFileName,toLower=toLower)


        assert self.keys()

        return


    ###########################################################################################
    ###
    def recodeMissingasMissing(self,missingNames=None,onlyVars=None):
        ###
        #######################################################################################
        """
        This looks for all values that are "don't know", etc, and sets them to missing. This is needed for the RDC GSS22, in its original form.  IT's also needed for at least some of the GSS's prior to GSS17...
        *'"

        Agh.. I have found some GSSpool for which the label for value n is "n: not stated", ie I need to look for something more general than just the missingname "not stated" (done..., May 2010)

        May 2010: match caselessly on label name (though case still matters for variable name)
        May 2010: do not change it if the value starts with a ".", already.

        Dec 2011: omg! It looks like I rewrote this function, absentmindedly, here, when I had already got one ( setMissingValuesByLabel(self,missingNames,vars=None)), below?!
        Well, let's assume this more recent one is better.

        Dec 2011: This is not good enough. I should make use of the .a, .b, .c ... facility of recent Stata's: in particular, I want to know in WVS which missings were refusals rather than not asks. Ah, but the Stata version of the raw data do not tell me that!! even though the labelbook list the (usually negative integers) missing value reasons. agh!  Look at SAS version?

        """
        if not missingNames:
            missingNames=["don't know","not stated",'not asked','not available','not applicable']
        outs=''
        if onlyVars==None:
            onlyVars=self.keys()
        else:
            onlyVars=[vv for vv in onlyVars if vv in self]

        foundRecode=''
        for vv in onlyVars:
            # Following last part of if tries to avoid reclassifying ".a", ".b" etc, which are already missing!.
            recodes=''.join([' (%d=.) '%LL for LL in self[vv].get('labels',{}) if self[vv]['labels'][LL].lower() in missingNames+[str(LL)+': '+mmn for mmn in missingNames] and not (isinstance(LL,str) and LL.startswith('.'))])
            if recodes:
                outs+="""
recode %s %s
"""%(vv,recodes)
            foundRecode+=' '+vv
        debugprint( foundRecode)
        return(outs)
    ###########################################################################################
    ###
    def getDescriptiveStatistics_deprecated2010(self,statafile,showVars=None,weightvar=None,ifcondition=None, recreate=None):
        ###
        #######################################################################################
        """

CAUTION!!!!!!!!!!!!!!!   THE MORE-AUTOMATIC FUNCTION IS NOW IN THE OTHER CLASS. IT'S CALLED ADDDESCRIPTIVESTATISTICS.
BUT THIS ONE PROBABLY STILL GETS USED, E.G. BY MY ACCOUNTING PROGRAM, ETC???
BUT AS OF DEC 2009 IT'S NOT LONGER BEING CALLED AUTOMATICALLY WHEN CODEBOOK IS MADE FROM A DTA.


        Dec 2009: I am not sure why this is a member of codebook class. I've now changed this function so it works in two very different modes. One is to generate Stata code to make an arbitrary table in the middle (or end) of a latex file using the current stata data in memory. The other is to use a generic dta-file-associated (more) comprehensive means list. Maybe this should be ditched!! Whoever wants a compreshensive list? I have little need for such things due to my more modern behaviour of regtables...

        Dec 2009: yikes. It looks like this is not used/called anywhere?! except in this class, above.

        Feb 2009, shortly after writing first version, I am redoing this to use "details" option of summary. That gets around the horrid name truncation. But only if you kill all variable labels first (!).
        There's also a "tabexport" but it looks like it truncates horribly too.

        Oh. No. I am doing it yet another way: one variable at a time. Though it's now missing weights and ifconditions!! agh.
        Feb 2009: converted to a member function of statacodebookclass
        June 2009: Why is the variable truncation a problem? Do them one by one, and look at the variable name in the command call. [not yet implemented/changed]
        July 2009: recreate flag now is "None" for automatic behaviour (ie check if file outdated), or True/False to force behaviour.
Aug 2009: Making more general sum-reading function, readStataSum...(). IT could be used to rewrite this?
        """
        if showVars==None:
            assert self
            showVars=' '.join(self.keys())


        statafile=deepcopy(statafile)
        #dta= '.dta'*( not statafile[-4:].lower() == '.dta')+''

        if not statafile.endswith('.dta.gz'):
            statafile+='.dta.gz'
        if statafile and not os.path.exists(statafile):
            print "CAUTION!!!!!!!  %s does not exist, so SKIPPING getDescriptiveStatistics."%statafile
            return({})

        microVars=showVars
        if isinstance(microVars,str) or isinstance(microVars,unicode):
            microVars=[vv for vv in microVars.split(' ') if vv]
        assert isinstance(microVars,list)
        #Require that variables are a unique list; otherwise order will be messed up? (Or could rely on auto ordering)


        if weightvar==None:
            weightsif='[w=weight]'
        elif not weightvar:
            weightsif=''
        else:
            weightsif='[w='+weightvar+']'

        if not ifcondition==None:
            assert isinstance(ifcondition,str)
            weightsif+=' if '+ifcondition
        else:
            weightsif+=' '

        if not len(uniqueInOrder(microVars)) == len(microVars):
            cwarning("You probably want to fix this so as not to screw up order...")
            microVars=uniqueInOrder(microVars)
        vString=' '.join(microVars)

        if statafile:
            print 'Generating automatic descriptive statistics from %s using weight/condition "%s", and variables "%s".'%(statafile,weightsif,vString)


            pp,ff=os.path.split(statafile)
            if ff.lower().endswith('.dta.gz'):
                ff=ff[0:-4]
            else:
                statafile+='.dta.gz' # So that I can check its timestamp below
            logfname=paths['working']+'summaryStatisticsFromStata_%s.log'%(ff.replace('.','_'))#%os.path.splitext(ff)[0]

        # Actually, we must have weights; do not allow unweighted results.
        assert weightsif.strip()
        outPrint="""
            """+stataLoad(statafile) + """

            **log using %s,replace text """%logfname  + ''.join(["""
            *-=-=-=-=-=-=-=-=
            sum """+vv+' '+weightsif+"""
            *~=~=~=~=~=~=~=~
            return list
            """ for vv in microVars])+"""
            **log close


            * Succeeded / got to end.
            """

        """ Now... I may or may not be calling Stata below. IF I am returning Stata code OR I do not need to recreate the log file, then I wo not call Stata.
        """
        if recreate==False or not statafile or (recreate==None and (os.path.exists(logfname) and os.path.getmtime(logfname)>os.path.getmtime(statafile) and 'Succeeded' in open(logfname,'rt').read())):
            print '--> Using EXISTING '+logfname+' for summary stats.\n   If you want to refresh it, simply delete the file and rerun it .'
            #import time
            #moddays= (time.time()-os.path.getmtime(logfname))/3600./24.
            #if moddays>14:
            #    print 'CAUTION: %s is %f days old! Please delete it ...'%(logfname,moddays)
        elif logfname:
            stataSystem(outPrint,filename=logfname.replace('.log',''))

        if not logfname and not os.path.exists(logfname):
            print " ****  SKIPPING THE DESCRIPTIVE STATS IN ... BECAUSE YOU HAVE NOT RUN STATA YET."
        else:
            sfields=[
                ['N','N','N'],
                ['sum_w','',''],
                ['mean','mean',''],
                ['Var','',''],
                ['sd','sd',''],
                ['min','min',''],
                ['max','max',''],
                ['sum','',''],
                ]
            sstr=r"""
    .\s+.-=-=-=-=-=-=-=-=
    .\s+sum (\S*) [^\n]*(.*?)
    .\s+.~=~=~=~=~=~=~=~
    .\s+return list[\n]*
    scalars:
    """+ '\n'.join([r'\s+r.%s. =\s+(\S*)'%ff[0] for ff in sfields])
            fa=re.findall(  sstr,''.join(open(logfname,'rt').readlines()), re.DOTALL)
            if not fa:
                print 'SUMMARY STATISTICS *****failed ************* regexp found nothing'
                oioiuiu
            descStats={}
            for vv in fa:
                descStats[vv[0]]={}
                for isf in range(len(sfields)):
                    descStats[vv[0]][sfields[isf][1]] = vv[2+isf]

        if statafile: # Stata was called, above, if needed, ie the stata executable code has already been used.
            return(descStats)
        else: # We will run this later, when doing regressions...
            return(outPrint,descStats)

    ################################################################
    ################################################################
    def summaryStatisticsTable_singleSurvey(self,fields=None,showVars=None,texFilename=None,substitutions=None,includeQuestions=True,descriptionField=None,latex=None,comments=None):
    ################################################################
    ################################################################
        """
        The fromDTA codebooks now have summary stats built in too, so can make a single table with summary stats and descriptions... ?

        June 2009: providing "latex"  param allows adding the table to an output tex file... It must be an instance of my latexregtablething class.

        Algorithm: I deal with decriptionField / questions separately from the other "fields", which are numerical.

2010Feb: Need to update this to produce a parallel file for RDC export.
Oh, no! I ca not just disclose the raw log file!

2010Nov: variable names are being detexed!?
        """
        if fields==None:
            fields=[
                ['mean','Mean'],
                ['sd','Std.Dev.'],
                ['min','min'],
                ['max','max'],
                ['N','Obs.'],
                ]
        if descriptionField in [None,'auto']:
            descriptionField='desc'
        if showVars==None:
            showVars=self.keys()
        elif isinstance(showVars,str):
            showVars=[vv for vv in showVars.split(' ') if vv]

        if not substitutions and latex:
            substitutions=latex.substitutions

        # Next line unused at moment.
        fieldOrder=['Mean','StdDev','Min','Max','Obs']
        fieldKeys=[ff[0] for ff in fields]
        fieldNames=[ff[1] for ff in fields]

        tex=r"""

        \renewcommand{\ctNtabCols}{%d"""%(len(fieldNames)+1+int(includeQuestions))+ r"""}
        \renewcommand{\ctFirstHeader}{"""+       ' & '.join(['Variable']+fieldNames+includeQuestions*['Description'])+r"""\\
    \hline\hline
    }
        \renewcommand{\ctSubsequentHeaders}{\ctFirstHeader} """+0*(' & '.join(['Variable']+fieldNames+includeQuestions*['Description'])+r"""\\
    \hline
    }""")+r"""
        \renewcommand{\ctBody}{"""
        from pystata import substitutedNames
        for vv in showVars:
            #if newmode: # Should still leave '_' fixing up to a str2latex function, no?
            # Nov 2010: Agh!!! I'm sure I'll break things for someone else, but my variable names come with tex substitutions, so do NOT detex them, as was being done until today. I removed two ".replace('_','-')"'s!!!
            # Okay, I should have made this facultative. Set a new variable, maybe in the codebook class???
            if self.stringsAreTeX:
                tex+=' & '.join([substitutedNames(vv,subs=substitutions)]+\
                        [chooseSFormat(self.get(vv,{}).get('sumstats',{}).get(field,''),convertStrings=True) for field in fieldKeys])+\
                        (includeQuestions)*('& '+self.get(vv,{}).get(descriptionField,''))  + r'\\'+'\n '
            else:
                tex+=' & '.join([substitutedNames(vv,subs=substitutions)]+\
                        [chooseSFormat(self.get(vv,{}).get('sumstats',{}).get(field,''),convertStrings=True) for field in fieldKeys])+\
                        (includeQuestions)*('& '+str2latex(self.get(vv,{}).get(descriptionField,'')))  + r'\\'+'\n '
        #assert 'LSavgL' not in showVars or not 'SWL'==vv



        tableFormat='l'+'r'*(len(fieldNames))
        if includeQuestions:
            tableFormat+=r'p{0.5\textwidth}'
        tex+=r"""
    \cline{1-\ctNtabCols}
    }

        % This .tex file is meant to be called by something from
        % cpblTables.sty. If it is not, then output something crude:
        \ifx\@ctUsingWrapper\@empty
        %Code to be executed if the macro is undefined
        \begin{table}
        \begin{tabular}{"""+tableFormat+r"""}
        \ctFirstHeader
        \ctBody
        \end{tabular}
        \end{table}
        \else
        %Code to be executed if the macro IS defined
        \fi

        % Better yet, for version "CA" of cpblTables, define methods so that the format need not be specified in the call.
        \renewcommand{\ctStartTabular}{\begin{tabular}{"""+tableFormat+r"""}}
        \renewcommand{\ctStartLongtable}{\begin{longtable}[c]{"""+tableFormat+r"""}}
        """


        # Make sure the texfile name exists and has a full path:
        if not texFilename:
            print 'CAUTION: Did not get a name for the table tex file!!! Using a rather generic one.'
            lklklklklk
            texFilename=defaults['paths']['tex']+'microSummaryStats.tex'

        if not os.path.split(texFilename)[0]:
            texFilename=defaults['paths']['tex']+texFilename
        if not os.path.isabs(texFilename):
            cwarning('Warning... you should use absolute path names: ',texFilename)

        fout=open(texFilename,'wt')
        fout.write(tex)
        fout.close()
        print 'Wrote tex file ................',texFilename

        if latex:
            latex.append(r"""
                \newpage
\setlength\tabcolsep{6pt}
{\usetinytablefont \cpblTableCALong{}{Summary statistics}{Summary statistics}{Summary statistics}{tab:Summarystatistics}{\footnotesize   """+str(comments)+""" }{"""+texFilename.replace(defaults['paths']['tex'],r'\texdocs ')+"""}

}
        """)

        if 0: # I am not compiling this, nad it's buggy (dec 2009), so skip it for nw...
            # As well as including it in the main output file (append(), above), also create a standalone latex file with the summary stats:
            fout=open(defaults['paths']['tex']+'sumstatsPreview.tex','wt')
            fout.write(r"""
                \documentclass{article}

    %%%% This file created automatically by CPBL's latexRegressionFile class
    \usepackage{amsfonts} %% Some substitions use mathbb
    \usepackage{lscape}
    \usepackage{rotating}
    \usepackage{relsize}
    \usepackage{colortbl} %%%% handy for colored cells in tables, etc.
    \usepackage{xcolor} %%%% For general, v powerful color handling: e.g simple coloured text.
    %%%%\usepackage[svgnames]{xcolor} %%%% svgnames clashes with Beamer?
    \usepackage{geometry}
    \usepackage[colorlinks]{hyperref}

    %%%% Make a series of capsules to format tables different ways:

    \usepackage{cpblTables} %% If you do not have this, just google for cpblTables.sty...
    \renewcommand{\ctDraftComment}[1]{{\sc\scriptsize ${\rm #1}$}} %% Show draft-mode comments
    \renewcommand{\ctDraftComment}[1]{{\sc\scriptsize #1 } %% Show draft-mode comments

            \geometry{verbose,letterpaper,tmargin=0cm,bmargin=0cm,lmargin=0cm,rmargin=0cm}
            %%%%

            \begin{document}
            \title{Regression results preview}\author{CPBL}\maketitle \listoftables
            \pagestyle{empty}%%%%\newpage
      %%      \begin{landscape}

    \clearpage\section{sumstats}

    \cpblTableCALong{auto}{A}{B}{C}{tab:D}{}{%s}

    %%\end{landscape}
            \end{document}
            """%texFilename)
            fout.close()

        return



    ################################################################
    ################################################################
    def _deprecated2015_let_us_use_assignLabelsInStata_createValueLabels(self,lookupDict,varname=None,labelname=None):
    ################################################################
    ################################################################
        """
        This takes a labelbook values in python and makes a Stata statement to create the value label and optionally assign it to some variable.


        So I've used this to good effect taking the master country concordance table (tsv) and making a better label.

        I could also implement this as a built in option for tsv2dta, for a specified set of pairs.
2014: See    assignLabelsInStata(self,autofindBooleans=True,missing=None,onlyVars=None) for something related

how is this different from  assignLabelsInStata?  2015: It looks like it doesn't do the actual value labels
        """

        if varname and not labelname:
            labelname=varname+'_label'
        outs=''

        outs+='\n capture label drop %s'%labelname
        outs+='\n label define %s'%labelname+' '+' '.join(['%d "%s"'%(vv,lookupDict[vv]) for vv in lookupDict])+'\n'
        if varname:
            outs+='\nlabel values %s %s\n'%(varname,labelname)
        return(outs)


    ################################################################
    ################################################################
    def parseStataCodebook(self,codebookFile,labelbookFile,toLower=None):
    ################################################################
    ################################################################
        """

        This function is now meant to be used only internally.
        Just call fromStataCodebook to initialise a codebook object from a Stata file's own information.
        If it has not already been done, Stata will be called. If it has, the resulting log files will simply be parsed.


        If your dataset is well internally documented, use Stata to create a text log file of the codebook command and another of the labelbook command. Feed those files to this function to get a dict of the available variables.

    When Stata prints the variable description on multiple lines, this captures it properly.

    One issue is that the resulting codebook structure does not preserve the order of variables (which is prserverd in the codebook command in Stata. So return a separate list of variable names?

        """
        print '  Parsing stata codebook file '+codebookFile

        cbook={}
        try:
            ff=open(codebookFile,encoding='utf-8').read()
        except (UnicodeDecodeError):
            print('    ---> (Legacy?) utf-8 method Failed on codebook reading. Trying non-utf-8')
            ff=open(codebookFile).read()
        import re

        #variableNames=re.findall(r'-------------------------------------------------------------------------------\n([^\n\s]*)\s+([^\n\s]*)\n-------------------------------------------------------------------------------',ff,re.MULTILINE)#
        #print variableNames

        grs=ff.split('-------------------------------------------------------------------------------')
        variableNs=grs[1::2]
        listOfNames=[]
        variableDescs=grs[2::2]
        for ivar in range(len(variableNs)):
            vv,desc=re.findall(r'([^\s]*)\s+(.*)',variableNs[ivar].strip(),re.DOTALL)[0]
            if toLower:
                vv=vv.lower()
            listOfNames+=[vv]
            cbook[vv]={}
            desc=re.sub(r'\s+',' ',desc)
            cbook[vv]['desc']=desc
            cbook[vv]['stataCodebook']=variableDescs[ivar] # For now, store everything!


        """ NOW READ LABELBOOK
        This may fail if labels are reused for multi variables, but can be fixed...
        IT now works for value labels which span more than one line, though it's frageile / kludged.

        """

        # Dec 2011: desperate. can't deal with utf-8 sheis. so using errors='replace'. :(
        ff=open(labelbookFile,encoding='utf-8',errors='replace').read()
        lrs=ff.split('-------------------------------------------------------------------------------')
        variableLabels=lrs[2::2]
        for vL in variableLabels:
            labelListAndVars=re.findall(r'\n\s+definition\n(.*?)\n\s*variables:(.*?)\n',vL,re.MULTILINE+re.DOTALL)[0]

            for  avar in  labelListAndVars[1].strip().split(','):
                var=avar.strip()
                couldBeMultipleVars=var.split(' ')
                var=couldBeMultipleVars[0]
                if toLower:
                    var=var.lower()
                if var in cbook: # 2010 Jan: N.B. THis was not necessary until I started allowing "showVars" restriction for the codebook: I now may get codebook for a subset of variables, but labelbook for all of them.
                    cbook[var]['labels']={}
                for otherVar in couldBeMultipleVars[1:]:
                    if var in cbook: # See comment just above Jan 2010
                        cbook[otherVar]['labels']= cbook[var]['labels']

                """Horrid kludge to join multi-line descriptions: (ie assuming a fairly fixed format by STata)
                It has a problem for cases when there are values with no description?
                """
                revisedTable=labelListAndVars[0].strip().replace('\n               ',' ').split('\n')
                for LL in revisedTable:#labelListAndVars[0].strip().split('\n'):
                    assert not '               ' in LL
                    val_name_=re.findall(r'([^\s]*)\s+(.*)',LL.strip())
                    if val_name_:
                        val_name=val_name_[0]
                    else: # Maybe there's a value without a label here?
                        val_name=[LL.strip(),'']
                    if var in cbook: # See comment above, Jan 2010
                        # The value could be a ".a" or etc, ie not a number!
                        if val_name[0].startswith('.'):
                            cbook[var]['labels'][val_name[0]]=val_name[1]
                        else:
                            cbook[var]['labels'][int(val_name[0])]=val_name[1]
                            assert not '.' in val_name[0] #fishing.. does my code for ".a" work?
                        cbook[var]['labelbook']=deepcopy(vL)

            #       print cbook[var]['desc']+':'+var+ str(cbook[var]['labels'])

        # Let's also make a convenient summary tsv file of the variables. Use original order of variables

        import os
        cbfDir,cbfName=os.path.split(codebookFile)

        fnn=paths['working']+cbfName+'_varlist.tsv'
        fout=open(fnn,'wt')
        for vv in listOfNames:#cbook:
            fout.write('\t%s\t%s\n'%(vv,cbook[vv]['desc']))
        fout.close()
        assert listOfNames
        print "   Parsed codebook file to find %d variables; Wrote %s."%(len(listOfNames),fnn)

        assert self==None or self=={}
        self.update(cbook)
        self.__orderedVarNames=listOfNames
        #self._stataCodebookClass__orderedVarNames =listOfNames
        #self.variableOrder.update(listOfNames)
        return

    ################################################################
    ################################################################
    def allNamesToLowercase(self,vars=None):
    ################################################################
    ################################################################
        """ Change all names in the dict to lower case. And produce stata code to do so. (latter is trivial with renvars!)
        """
        newones={}
        stataOut=""
        oldkeys=self.keys()
        if vars:
            oldkeys=[kk for kk in vars if kk in oldkeys]
        for kk in oldkeys:
            if not kk.lower()==kk:
                #assert kk.lower() not in self or
                stataOut+="""
            capture rename %s %s
            """%(kk,kk.lower())
                self[kk.lower()]=self.pop(kk)

        return(stataOut)


    ################################################################
    ################################################################
    def orderedKeys(self):
    ################################################################
    ################################################################
        """ Return a list of variable names in original order
        If they're known!... not yet implemented for TSV origin case (feb2009)
        """
        #assert self.__orderedVarNames
        return(deepcopy(self.__orderedVarNames ))

    ################################################################
    ################################################################
    def setMissingValuesByLabel_deprecated(self,missingNames,vars=None):
    ################################################################
    ################################################################
        print 'DEPRECATED: I wrote a newer version of this recodeMissingasMissing(self,missingNames=None,onlyVars=None)'
        """
        This returns some Stata code to set values of variables to missing based on the labelbook. That is, you supply a list of text labels that you want removed (e.g. ["Dont know", 'Not asked']) and all such will be set to ".", ie missing. Code is not called; it's just returned.

        So this is a natural first thing to call when recoding a dataset after generating the codebook/labelbook with functions above.

vars=None should allow a restricted set of variables to apply this to.

But this could be done more efficiently with a single "recode" statement (July 2009: not done??)

AHAHHHHHHHHHHHHH I JUST REWROTE THIS, ABOVE!!     def recodeMissingasMissing(self,missingNames=None,onlyVars=None):
Probabl newer one is better? [Dec2011]. I think this original one I wrote for Gallup / WVS ? and the recent one for GSS. Let's see whether I can deprecate this.
        """
        outStata=''
        for var in [kk for kk in self.keys() if vars==None or kk in vars]:
            if 'labels' in self[var]:
                for value in self[var]['labels']:
                    if self[var]['labels'][value] in missingNames:
                        outStata+="""
                        """+'*  %s==%d means %s'%(var,value,self[var]['labels'][value])+"""
                        """+'replace %s=. if %s==%d'%(var,var,value)+"""
                        """
        return(outStata)




    ################################################################
    ################################################################
    def normaliseVar_originalCallingFormat(self,newname,oldname,low,high,missing='.'):
        """"
        Actually, I like the calling format of the version below better. therefore THIS FUNCTION IS DEPRECATED!! USE THE NEW ONE, BELOW.
Calls made in this format with the new name will be redirected here.
       """
    ################################################################
    ################################################################

        outs=""
        if newname==oldname:
            outs+="replace "+newname+"="+str(missing)+ ' if %s>%f | %s<%f\n'%(oldname,max(low,high),oldname,min(low,high))
        else:
        # For variables which have meaningful positive values, rescale them to 0 to 1 scale, usually useful for reversing the order
            newname=shortenStataName(newname)
            outs+="gen %s=%s\n"%(newname,missing)
            # Update the codebook:
            self._changeName(oldname,newname)

        outs+="replace %s=(%s-%f)/(%f-%f)  if %s>=%f & %s<=%f\n"%(newname,oldname,low,high,low,oldname,min(low,high),oldname,max(low,high))

        """Need to get rid of any existing labelbook for this var (when oldname=newname)
            """
        if oldname in self:
            desc=self[oldname]['desc']
        else:
            desc='(unknown)'
        outs+='label variable %s "[rescaled %s] %s"\n'%(newname,oldname,desc)+"""
            label values %s %s_rescaled
            format %s  %%9.0g
            """%(newname,oldname[0:(32-11)],newname)

        #outs+="replace %s=(%s-%f)/(%f-%f)  if %s>0\n"%(newname,oldname,low,high,low,oldname)

        #outs+='label variable %s "[rescaled %s] %s"\n'%(newname,oldname,self[oldname]['desc'])


        # Should delete the old variable name here,unless specified (NOT YET IMPLEMENTED).
        return(outs)
        #"""

    ################################################################
    ################################################################
    def normaliseVar(self,oldname,low,high,newname=None,missing='.',desc='',newmax=1.0,failSafe=True): # failSafe was false until 2011Oct
    ################################################################
    ################################################################
        """
        2011 Oct: Rather than copy things, why not use the recode function, thus keeping all the labels. Yes, I should but I cannot find out how to do this!! Wow. I could use the labels from my codebook, I guess... Ugh. It's just that that seems slightly dangerous. How would I check I wasn't missing something?

        N.B. Stata does not allow value labels for non-integers, so we try below only to label the top and bottom values, assuming they will remain integers.

newmax:        2014 Sep: Now can "normalize" to 0--10, ie something other than 0--1, using newmax.
        """
        if isinstance(low,str):
            print( "  --> Invoking legacy function call format for normaliseVar (%s)..."%oldname)
            return(self.normaliseVar_originalCallingFormat(oldname,low,high,newname,missing=missing))

        if newname==None:
            newname=deepcopy(oldname)
        newname=shortenStataName(newname)


        if failSafe and oldname not in self:
            print 'CAUTION!!! Skipping normliseVar for %s because %s is not in codebook'%(newname,oldname)
            return('')

        outs=''
        # Copy the label from oldvar to new:
        outs+="\nlocal tmplabel: variable label %s\n"%oldname

        " Generate Stata code to rescale a variable, and put it in the codebook "
        # For variables which have meaningful positive values, rescale them to 0 to 1 scale, usually useful for reversing the order

        if newname==oldname:
            outs+="replace "+newname+"="+str(missing)+ ' if %s>%f | %s<%f\n'%(oldname,max(low,high),oldname,min(low,high))
        else:
        # For variables which have meaningful positive values, rescale them to 0 to 1 scale, usually useful for reversing the order
            newname=shortenStataName(newname)
            outs+="gen %s=%s\n"%(newname,missing)
            # Update the codebook:
            self._changeName(oldname,newname)

        outs+="""
        tab %(oldname)s, missing
        * Drop invalid values:
        replace %(newname)s=. if %(oldname)s > %(max)s | %(oldname)s < %(min)s 
        * Rescale to 0--1 range (or 0--newmax)
        replace %(newname)s=(%(oldname)s-%(low)f)/(%(high)f-%(low)f)*%(newmax)f   if %(oldname)s>=%(min)f & %(oldname)s<=%(max)f
        """%{'newname':newname, 'oldname':oldname, 'low':low, 'high':high, 'min':min(low, high), 'newmax':newmax, 'max':max(low,high)}
#*replace %s=(%s-%f)/(%f-%f)*%f   if %s>=%f & %s<=%f\n
#"""%(newname,oldname,low,high,low,oldname,min(low,high),newmax,oldname,max(low,high))

        # LABELBOOK

        """Need to get rid of any existing labelbook for this var (when oldname=newname)
            """
        outs+='label variable %s "[rescaled %s] %s"\n'%(newname,oldname,self.get(newname,{}).get('desc','[no desc in nV]').replace('"',"'"))+"""
            format %s  %%9.0g
            """%(newname)
        # Following removed from above oct 2011, since label seems not to exist.
        #            "label values %s %s_rescaled" %newname,oldname[0:(32-11)]


        # LABEL

        if not desc:
            desc=dgetget(self,newname,'desc','')
        if not desc:
            # Copy the label from oldvar to new:
            outs+="""label variable %s "[scaled]: `tmplabel'"\n"""%(newname)
            """ " ' " ' """
        else:
            outs+="""label variable %s "[scaled]: %s"\n"""%(newname,desc.replace('"',"'"))

        #outs+="replace %s=(%s-%f)/(%f-%f)  if %s>0\n"%(newname,oldname,low,high,low,oldname)
        #outs+='label variable %s "[rescaled %s] %s"\n'%(newname,oldname,self[oldname]['desc'])

        # Should delete the old variable name here,unless specified (NOT YET IMPLEMENTED).


        # Oct 2011: Try to create value labels for values we have revised: But we can only label integers. 
        # So only label the two extreme values.  
        # 2014: Now that newmax can be larger than 1, it could be that more of these are integers. Can't I just remap them?!  In fact, if I used recode, gen then a new value label would automatically be set up by Stata.  Alternatively, could just loop over all known codebook values here looking for which will be integer.
        ##valuesWithinRange=[vv for vv in self[newname]['labels'].keys() if vv<=high and vv>=low]
        if dgetget(self,[newname,'labels',low],False) and dgetget(self,[newname,'labels',high],False):
            vlu=self[newname]['labels']
            lname=shortenStataName(newname,28)+'_'+str(int(newmax))
            outs+="""
            label define %s %d "%s" %d "%s"
            label values %s %s
            tab %s, missing
            """%(lname,   0, vlu[low], newmax, vlu[high],  newname, lname ,newname)

        return(outs)


    ###########################################################################################
    ###
    def old_normaliseVar2(self,oldname,low,high,newname=None,desc='',missing='.',surveyName=''):
        # I found this in regressionsGallup.py... but it should be merged into above functoin!!
        # That's now done, so this can be retired in 2010, say.
        ###
        #######################################################################################
        " Generate Stata code to rescale a variable, and put it in the codebook "
        outs=''
        # For variables which have meaningful positive values, rescale them to 0 to 1 scale, usually useful for reversing the order
        if newname==None:
            newname=oldname
        newname=shortenStataName(newname)

        #if  missing: # If this is empty, then assume var has already been generated! Just replace it.
        #    outs="gen %s=%s\n"%(newname,missing)
        if newname == oldname:
            # Hm, if it was integers I could just use recode command.
            outs+="local tmplabel: variable label %s\n"%oldname
            outs+="""capture drop tmpVV
            gen tmpVV=.
            copydesc %s tmpVV
            replace tmpVV=(%s-%f)/(%f-%f)  if %s>=min(%s,%s) & %s<=max(%s,%s)
            replace %s=tmpVV
            drop tmpVV
            """%(oldname,oldname,low,high,low,oldname,low,high,oldname,low,high,newname)
        else:
            outs+="replace %s=(%s-%f)/(%f-%f)  if %s>=min(%s,%s) & %s<=max(%s,%s)\n"%(newname,oldname,low,high,low,oldname,low,high,oldname,low,high)

        #outs+='label variable %s "rescaled: %s"\n'%(newname,codebook)
        if not desc:
            # Copy the label from oldvar to new:
            outs+="""label variable %s "[scaled]: `tmplabel'"\n"""%(newname)
            """ " ' " ' """
        else:
            outs+="""label variable %s "[scaled]: %s"\n"""%(newname,desc)
        #if not desc:
        #    addJointCodebookEntry(surveyName,oldname,newname,'[scaled]: ')
        #if desc:
        #    addJointCodebookEntry(surveyName,oldname,newname,'[scaled]: ',description=desc)
        return(outs)



    ################################################################
    ################################################################
    def toBoolVar(self,newname,oldname,missing='.',trueval=1):
    ################################################################
    ################################################################
        """
        This is strangely specific: it is for renaming/creating a boolean variable.
        By default, it expects the value "1" to represent true.

        Agh.. There are choices of whether to copy descriptions and value labels from the python codebook or the Stata values.

        2011 Oct: Rather than copy things, why not use the recode function, thus keeping all the labels. No, it's too hard. My codebook lists the values (e.g., -2, 99) which have since been recoded to missing.  How can I tell which  should be missing and which should be 0? The best I can do is to keep the label for the one which is to be "1".  That's what I already do.

        """
        outs=''
        # Set unknown values to  "missing":
        if not newname==oldname:
            outs+="gen %s=%s\n"%(newname,missing)+"""
            *copydesc %s %s
            """%(oldname,newname)

        outs+="replace %s= %s==%d if %s<. \n"%(newname,oldname,trueval,oldname)
        #outs+="replace %s=1 if %s==%d\n"%(newname,oldname,trueval)
        #outs+="replace %s=0 if %s~=%s & %s<.\n"%(newname,oldname,trueval,oldname)

        if 'labels' in self[oldname] and trueval in  self[oldname]['labels']:
            assert len(newname)<20
            outs+="""
            label define %s_b %d "%s" 0 "not %s"            """%(newname,trueval,self[oldname]['labels'][trueval],self[oldname]['labels'][trueval])+"""
            label values %s %s_b
            """%(newname,newname)

        ## Copy the label from oldvar to new:
        ##outs+="local tmplabel: variable label %s\n"%oldname
        #outs+="""label variable %s "[bool(%s)] `tmplabel'"\n"""%(newname,oldname)
        #outs+=0*"""\n * "`'" \n"""
        outs+="""label variable %s "[bool(%s)] %s"\n"""%(newname,oldname,self[oldname]['desc'])


        # Update the codebook:  (update the values NOT YET IMPLEMENETED)
        if not newname==oldname:
            self._changeName(oldname,newname)

        # Should delete the old variable name here,unless specified (NOT YET IMPLEMENTED).

        return(outs)

    ################################################################
    ################################################################
    def newVar(self,newname,expression,descriptionSource=None,description=None):
    ################################################################
    ################################################################
        if self: # Codebook exists
            assert newname not in self
            self[newname]={'rawname':'(derivednewVar)'}
            ##self._changeName(vfrom,vto,deleteOld=True,oldnamefield=None)
            self.__orderedVarNames+=[newname]
##             assert vfrom in self
##             assert vto not in self
##             assert 'rawname' not in self[vfrom]
##             self[vfrom]['rawname']=vfrom
##             self[vto]=self.pop(vfrom)

        stataCode="""
        gen %s= %s
        """%(newname,expression)
        if descriptionSource:
            stataCode+="""
                copydesc %s %s
                """%(descriptionSource,newname)
        if description:
            stataCode+="""
                label variable %s "%s"
                """%(newname, description)
            self[newname]['desc']=description
        return(stataCode)
    ################################################################
    ################################################################
    def renameVar(self,vto,vfrom,overwriteCB=False):
    ################################################################
    ################################################################
        if self: # Codebook exists
            if vfrom==vto:
                print " N.B.: not renaming %s --> %s since they're identical"%(vfrom,vto)
                assert vfrom in self
                return("\n* N.B.: not renaming %s --> %s since they're identical\n"%(vfrom,vto))
            else:
                self._changeName(vfrom,vto,deleteOld=True,oldnamefield=None,overwriteCB=overwriteCB)

##
##             assert vto not in self
##             assert 'rawname' not in self[vfrom]
##             self[vfrom]['rawname']=vfrom
##             self[vto]=self.pop(vfrom)


        return("""
        rename %s %s
        """%(vfrom,vto))

    ################################################################
    ################################################################
    def noteVar(self,newname,rhs=None,prefix=None,sourceVar=None,description=None,formula=None,comments=None):
    ################################################################
    ################################################################
        """Adapted from old addJointCodebookEntry(survey,surveyvar,mastervar,prefix,description=None,formula=None,comments=None), April 2010.
This is just used to make a note of a new variable that was defined in raw Stata rather than through a built-in thing like "normalseVar()", etc.  So no Stata code is returned. ("" is returned, for consistency with similar funcitons)

    mastervar is the variable name used in the combined datasets
    prefix is some description of what was done to it (e.g. rescaled) ususally in square brackets??

    var:
    desc:
    comments:
    details: the options given in the questionnaire, ie the value labels


    April 2010: new plan:
     - the new variable, newname, should not yet exist in self
     - Possibly parse rhs to see whether it has a unique variable name in it. If so, ...copy some description etc from that?
     - second argument can be either a variable name, or a more complex expression.
        - if it's not a pure variable, then also allow "formula" to exist. In this case, the 2nd argument is the sourceVar.

     - so specifying sourceVar explicitly seems to be deprecated so far.

     - this could be used by other functions, like newvar, which already do it all, but in addition make the stata code.
    """

        if comments==None:
            comments=""


        assert self # !huh? why/how not!? oh.... if this is called externally???? or if it's just empty so far.. So: this not dealt with yet.
        assert newname not in self

        if self: # Codebook exists
            self[newname]={'varname':newname,'rawname':'(derived)'}
            self.__orderedVarNames+=[newname]

        assert not sourceVar # Not used.. deprecated? apr2010
        # First, can we figure out a sourceVar?
        if rhs and rhs in self:
            sourceVar=rhs
            #assert formula or description # Otherwise we're just assigning directly?
        elif rhs:
            """
            We do not have an trivial guess of what the base variable(s) is or was. We could try to infer it.
            """
            print ' Should still do a bit more here to look for a rhs variable in "%s" for %s'%(rhs,newname)

        # Now create the new entry
        if sourceVar:
            self[newname]=deepcopy(self[sourceVar])
            self[newname]={'varname':newname,'rawname':sourceVar}
        else:
            self[newname]={'varname':newname,'rawname':'(derived)'}


        # Now possible provide some information on the expression used to calculate it.
        if formula:
                """
                So rhs was given as an indication of a primary source variable. Let's copy (we assume newname not in self) everything over from there, before possibly overwriting some stuff
                """
                self[newname].update({'rawname':'(derived: %s)'%formula})


        # And now fill in any other info given:
        assert not prefix # Not done yet
        if description:
            self[newname]['desc']=description
        return('')



    ################################################################
    ################################################################
    def _changeName(self,vfrom,vto,deleteOld=True,oldnamefield=None,overwriteCB=False):
    ################################################################
    ################################################################
        """
        An internal function to be called whenever renaming a variable.

         Update codebook here.

         deleteOld: unless specified (NOT YET IMPLEMENTED).

         Note: "deleteOld" is about deleting the variable from the codebook, not in Stata.
        """

        if not oldnamefield:
            oldnamefield='rawname'

        if self: # Codebook exists
            if vfrom not in self and vfrom.upper() in self:
                debugprint('Changing FROM name to upper case! : ',vfrom)
                vfrom=vfrom.upper()
            if vfrom not in self and vfrom.lower() in self:
                debugprint('Changing FROM name to lower case! : ',vfrom)
                vfrom=vfrom.lower()
            assert vfrom in self
            assert vto not in self or overwriteCB
            assert oldnamefield not in self[vfrom]
            self[vto]=deepcopy(self[vfrom])#self.pop(vfrom)
            self[vto][oldnamefield]=vfrom
            self.pop(vfrom)
        if vfrom in self.__orderedVarNames:
            self.__orderedVarNames[self.__orderedVarNames.index(vfrom)]=vto
        #for x in self.__orderedVarNames:
        #    if x==vfrom:
        #        x=vto
        return()

    ################################################################
    ################################################################
    def purgeRawNames(self,keep=None):
    ################################################################
    ################################################################
        """ This gives Stata code to get rid of all variables that have not been renamed. keep is a list of variables to protect from droppingn


        """
        from pystata import stataSafeDrop
        dropped=[]
        if keep==None:
            keep=[]
        kk=self.keys()
        for vv in kk:
            if 'rawname' not in self[vv] and vv not in keep:
                #self.pop(vv)
                dropped+=[vv]
                assert not 'firstLangFrench'==vv
        debugprint( 'Purging ',dropped)
        return(stataSafeDrop(varlist=dropped))
            #return("""
            #drop """+' '.join(vv) +"""
            #""")

    ################################################################
    ################################################################
    def save(self,saveName=None,version=None):
    ################################################################
    ################################################################
        """
        July 2009: Tie between rawnames and derived names, etc, etc, are only built up during recoding process. So the result should be saved so that it can be easily loaded later, e.g. for use in regressions and for making summary tables, etc.
        Is this useful? Well, no. Currently I ignore all those details and simply load up the DTA codebook info from the master (recoded) version of the file. So these shelf files are only useful if I need to fill in some of the questions etc. And note also that, e.g. for CCHS, these shelf files are likely only to exist for each individual wave, so there will be some difficulty in choosing which shelf file to get info from. Best thing, obviously is to make sure the stata version has all the questions, etc in its label.


2010Feb: version is the field to save under. What is a default?? Codebook, I guess.



        So here are the possible entries in a shelf file:
        'recoded'
        'fromPDF'
        'orderedVarNames'
        (codebook)

        """
        import shelve
        assert saveName

        assert version
        newFile=False

        assert not saveName.endswith('.pythonshelf')
        #saveName=saveName.replace('.pythonshelf.pythonshelf','.pythonshelf')

        print '\n Attempting to save in codebook shelf file %s.pythonshelf (saving mode %s)'%(saveName,str(version))
        if not os.path.split(saveName)[0]:
            saveName=paths['working']+saveName

        if 0 and not os.path.exists(saveName+'.pythonshelf'):
            newFile=True


        shelffile = shelve.open(saveName+'.pythonshelf')
        if not shelffile:
            print ('  Created NEW  %s.pythonshelf, codebook file'%saveName)
        shelffile[version]=dict(self.items())
        shelffile['orderedVarNames']=self.__orderedVarNames
        shelffile.close()
        return()
    ################################################################
    ################################################################
    def load(self,saveNameOrSurvey,version=None):
    ################################################################
    ################################################################
        """
        July 2009: See save().
        Much updated and started to be used, Feb 2010.


        2010March: This is now becoming smarter. Can ask for a survey and any nonexisting version, and it might know how to create that version.

I am having a bunch of confusion with whether ".pythonshelf" is appended to savename.

NO!!!
If saveNameOrSurvey is a saveName, it SHOULD come with the suffix already.
If it comes as a survey, saveName should be constructed with the suffix.
That is, whenever passing filenames to load() or save(),

April 2010: load(survey) should be robust to nonexistence of PDF...

        """
        import shelve
        assert saveNameOrSurvey
        survey=None

        if 0 and not version:
            version='recoded'
            print '  Load codebook: Assuming "recoded" version for ',survey


        assert not saveNameOrSurvey.endswith(".pythonshelf")

        # If saveNameOrSurvey looks like a survey name, ASSUME THAT IS WHAT IS MEANT!
        if 'knownSurveys' in defaults and saveNameOrSurvey in defaults['knownSurveys']:
            survey=saveNameOrSurvey
            saveName=paths['working']+'codebook-'+saveNameOrSurvey
        else:
            # testStophere
            if not os.path.split(saveNameOrSurvey)[0]:
                saveName=paths['working']+saveNameOrSurvey
            else:
                saveName=saveNameOrSurvey

        assert not saveName.endswith('.pythonshelf')

        if not os.path.exists(saveName+'.pythonshelf') and not survey:
            print (' CAUTION! Could not find any %s.pythonshelf, so codebook is empty!!'%saveName)
            assert 0
            return(None)





        if not os.path.exists(saveName+'.pythonshelf'): # hence is a survey name
            assert version
            assert survey
            print (' Deriving new codebook element(s) %s for survey %s'%(version,survey))
            shelffile=[]
        else:
            print '\n Attempting to load existing codebook shelf file %s.pythonshelf  (looking for mode %s)'%(saveName,version)
            shelffile = shelve.open(saveName+'.pythonshelf')
            if not shelffile:
                print '    Shelf file '+saveName+'.pythonshelf is empty'
            else:
                print '    Shelf file '+saveName+'.pythonshelf has versions: '+str(shelffile.keys())
            if version and version in shelffile:
                self.update(shelffile[version])
                if 'orderedVarNames' in shelffile:
                    self.__orderedVarNames=shelffile['orderedVarNames']
                shelffile.close()
                return()
        if not version:
            for vv in ['codebook','recoded','raw']:
                if vv in shelffile:
                    print 'No component specified. Using %s'%vv
                    version=vv
                    break
        if survey and version=='raw':
            self.load(survey,'PDF')
            print "     (I am setting all PDF names to lowercase. That seems pretty safe for Stats Can docs)"
            self.allNamesToLowercase()
            self.save(saveName,'PDF')
            assert all([kk.lower()==kk for kk in self])
            codebookPDF=dict(deepcopy(self.items()))
            self.clear()
            self.load(survey,'rawDTA')
            print "     (I am setting all rawDTA names to lowercase. That's not strictly general here..?)"
            self.allNamesToLowercase()
            self.save(saveName,'rawDTA')
            assert all([kk.lower()==kk for kk in self])
            codebookDTA=dict(deepcopy(self.items()))
            for kk in codebookPDF:
                if kk in self:
                    self[kk].update(codebookPDF[kk])
                else:
                    self[kk]=codebookPDF[kk]
            self.save(saveName,version='raw')
            assert all([kk.lower()==kk for kk in self])

        elif survey and version=='best':
            if 'recoded' not in shelffile:
                return(self.load(survey,'PDF'))
            self.load(survey,'PDF')
            codebookPDF=dict(deepcopy(self.items()))
            self.load(survey,'recoded')
            ##recodedCB=dict(deepcopy(self.items()))
            # Now merge these!!
            """ This should look at rawname too. does not yet."""

            PDFupper=all([kk.isupper() for kk in codebookPDF])
            PDFlower= all([kk.islower() for kk in codebookPDF])
            RCDupper=all([kk.isupper() for kk in self])
            RCDlower=all([kk.islower() for kk in self])
            # See earlier in this file for explanations of above
            for VV in codebookPDF:
                if toLower:
                    vv=VV.lower()
                if PDFupper and RCDlower:
                    vv=VV.lower()
                elif PDFupper and RCDupper:
                    vv=VV.lower()
                else:
                    Not_sure_here_WHATOTHERPOSSIBILITIESOCCUR
                    vv=VV
                if vv in self:#codebookDTA:
                    self[vv]['fulldesc']=codebookPDF[VV]['concept']+(': ``'+codebookPDF[VV]['question']+"''")*(not codebookPDF[VV]['question']=='')
            ####self.save(saveName,version=version)

        elif survey and version=='rawDTA':
            self.clear()
            self.fromStataCodebook(defaults['rawStataFile'][survey])
            assert self.keys()
            self.save(saveName,version=version)
        elif survey and  version=='PDF':
            self.fromPDFCodebook(survey)
            if not self.keys():
                print 'Got nothing for PDF codebook ... leaving that empty'
            else:
                self.save(saveName,version=version)
        elif survey and  version=='recoded':
            """
            if defaults['mode'] not in ['gallup'] and defaults['mode'] in ['canada','RDC']:
                from rdc_make import cpblRequire
                cpblRequire('recoded-'+survey)
            """
            # So now try thie following again, since file may/should exist now...
            shelffile = shelve.open(saveName+'.pythonshelf')
            self.update(shelffile[version])
            shelffile.close()
        elif survey:
            print 'Oh-oh!!!!!!!!!! I do not know how to derive '+version
        else:
            print 'AGH! Could not find %s in %s.pythonshelf!!!!!!!!!!1'%(version,saveName)

        if os.path.exists(saveName+'.pythonshelf'):
            shelffile = shelve.open(saveName+'.pythonshelf')
            if shelffile and 'orderedVarNames' in shelffile:
                self.__orderedVarNames=shelffile['orderedVarNames']
        if shelffile:
            shelffile.close()
        return(version)

    ################################################################
    ################################################################
    def writeVariableList(self,fname):
    ################################################################
    ################################################################
        """ Nov 2010. Sorry if this already exists somewhow."""
        fout=open(fname,'wt')
        for vv in sorted(self.keys()):
            newname=''
            if ' ' not in self[vv]['desc']:
                newname=self[vv]['desc']
            fout.write("""["%s",'%s',"%s"],\n"""%(newname,vv,self[vv]['desc']))
        fout.close()

    ################################################################
    ################################################################
    def writeVariableTable(self,fname,onlyVars=None):
    ################################################################
    ################################################################
        """ Dec 2011. I'm sure this exists somewhere. I want to make another table just like the one I already made for Quebec paper in 2010. But how did I make it?!


        ahhhh this garbage. i'm sure i just did ti by hand last time.

        """
        from codecs import open
        fout=open(fname,'wt',encoding='utf-8')
        header=['GSS Cycle and variable name','Question used (English and French)','Values']
        body=[]
        for vv in sorted(self.keys()):
            if onlyVars and vv not in onlyVars:
                continue
            if 'desc' in self[vv]:
                #L=self[vv]['labels']
                #body+=[ [vv,self[vv]['desc'],' '.join(['%d %s '%(a,b) for a,b in self[vv]['labels'].items()])  ]  ]
                body+=[ [vv,self[vv]['desc'],' / '.join(dgetget(self,[vv,'labels'],{}).values()) ] ]

            if ' ' not in self[vv]['desc']:
                newname=self[vv]['desc']
            fout.write('\n'.join([' & '.join(LL) for LL in body]))
            #fout.write("""["%s",'%s',"%s"],\n"""%(newname,vv,self[vv]['desc']))
        fout.close()

    ################################################################
    ################################################################
    def replaceSomeHighCharacters(self,TeX=True):
    ################################################################
    ################################################################
        """
        Look for bad characters in strings. Make standard TeX-compatible substitutions here.

        or if TeX is false, do non-TeX version? [not done]

        # See http://www.petefreitag.com/cheatsheets/ascii-codes/ for instance, for a lookup!
        If you get a plotting error with

        Dec 2011: All rewritten using new general tools in cpblUtilities


        """
        from cpblUtilities import accentsToLaTeX
        for vv in self:
            for LL in dgetget(self,[vv,'labels'],[]):
                self[vv]['labels'][LL]=str2latex(self[vv]['labels'][LL])
                self[vv]['desc']=str2latex(self[vv]['desc'])


    def assignLabelsInStata(self,autofindBooleans=True,missing=None,onlyVars=None,valuesOnly=False):
        from surveypandas import surveycodebook
        _cb=surveycodebook(self)
        return(
            _cb.assignLabelsInStata(autofindBooleans=autofindBooleans,missing=missing,onlyVars=onlyVars,valuesOnly=valuesOnly)
            )

    ################################################################
    ################################################################
    def _deprecated_use_the_one_in_surveypandas_assignLabelsInStata(self,autofindBooleans=True,missing=None,onlyVars=None,valuesOnly=False):
    ################################################################
    ################################################################
        """ 2014 June: Overwrite all variable labels and value labels based on the codebook.

        By default, also look for yes/no boolean variables, and recode them to be 1/0.

        onlyVars : Don't actually bother with output except for these variables. What's nice is that this (which must be a list), can contain '.*' to denote a wildcard (or other REs)

        Not yet implemented: 

        missing : set of values like "don't know" which should be considered missing
        valuesOnly: This will create labels for values, but it won't relabel the variables themselves

ohoh. is this sthe same as createValueLAbels?  Retire one of them!? The other doesn't do the value labels.
        """
        outs=''
        import re
        if isinstance(onlyVars,str):
            onlyVars=[onlyVars]
        for thisVar,vcb in self.items():
            if onlyVars: # Skip any definitions if not in desired list
                if thisVar not in onlyVars and re.match(onlyVars[0],thisVar) is None:
                    continue
            valueLs=vcb.get('labels',vcb.get('values',{}))
            if valueLs:
                #assert not any(['"' in alabel for aval,alabel in valueLs.items()])
                yes=[aa   for aa,bb in valueLs.items() if bb.lower()=='yes']
                no=[aa   for aa,bb in valueLs.items() if bb.lower()=='no']
                #if set(sorted([vv.lower() for vv in valueLs.values()]))==set(['yes','no']):
                if len(yes)==1 and len(no)==1 and len(valueLs)==2:
                    outs+='\ncapture noisily replace %s = %s == %d\n'%(thisVar,thisVar,yes[0])
                    self[thisVar]['labels']={1:'yes',0:'no'}
                    vcb=self[thisVar]
                #assert not any(["don't know" in aval for aval in valueLs.values()])
                valueLabelName=thisVar+'_LABEL' if 'labelsname' not in vcb else vcb['labelsname']
                outs+='\n label define '+valueLabelName+' '+' '.join(['%d "%s"'%(aval,alabel) for aval,alabel in valueLs.items()])+'\n'
                #assert 'other than ' not in '\n label define %s_LABEL'%thisVar+' '+' '.join(['%d "%s"'%(aval,alabel) for aval,alabel in valueLs.items()])+'\n'
                outs+='\n capture noisily label values %s %s\n'%(thisVar,valueLabelName)

            #assert not '"' in vcb['desc']
            outs+='\n'+'*'*(not not valuesOnly)+'capture noisily label variable %s "%s"\n'%(thisVar,vcb['desc'])
        return(outs)


    ################################################################
    ################################################################
    def dummiesByValueLabel(self,newprefix,oldname,omit=None,returnNewVars=False):
    ################################################################
    ################################################################
        """
        See dummyLabelByValue(newprefix,oldname,numeric=True) for the non-codebook version.
        This looks at value labels to make useful variable names for dummies. You can specify the omitted value, by numeric value, but full value label, or by the truncated value label that would be used in a dummy variable name.

if returnNewVars is True, then a tuple will be returned: text and a list of the new dummy variable names
        """
        assert oldname in self
        outs=''
        labels=self[oldname]['labels']
        valnames=dict([[aval, (newprefix+''.join([c for c in alabel if c.isalpha()])   )[:20]] for aval, alabel in labels.items()])
        omitnames=dict([[aval, alabel[len(newprefix):]] for aval, alabel in valnames.items()])
        assert omit is None or omit in labels or omit in labels.values() or omit in omitnames.values()
        for aval in valnames:
            if omit is not None and (omit==aval or omit==labels[aval] or omit==omitnames[aval]):
                continue
            outs+=self.newVar(valnames[aval],oldname+'=='+str(aval))#,descriptionSource=None,description=None):
        if returnNewVars:
            return(outs,valnames.values())
        return(outs)







###########################################################################################
###
def dummyLabelByValue(newprefix,oldname,numeric=True):
    ###
    #######################################################################################
    """ Replacement for below???
    e.g. dummyLabelByValue('dyear','year')
    2014June: N.B. If you have the code, you can use value label values from it. 
    """
    oldCode= ("""
    levelsof %(on)s, local(levels)
    foreach k of local levels {
    gen %(np)s`k'=%(on)s=="""+'"'*(not numeric)+"`k'"+'"'*(not numeric)+"""
    }
    """)%{'on':oldname,'np':newprefix}
    return(oldCode)
    


###########################################################################################
###
def dummyLabel(newprefix,oldname,valuesNames,missing='.',surveyName='',noCodebook=None,baseValue=None):
    ###
    #######################################################################################
    """ Generate Stata code to make dummies from a variable, and put it in the codebook

April 2010: Having a look at this, doing some cleanup. This appears not to be finished! There is no codebook implementation here.. Very crude.

The valuesNames list is a list of pairs of form [value, dDummyName]

baseValue is the value to exclude!  ie if it is in valuesNames, it will be ignored.

examples of usage?
"""
    print "REally!? apr 201: don't use this: you should be using pystataCodebook.py functions" # See above, too.
    # Apart from nicer names, this is necessary because I want tab,gen() to be able to replace existing dummies; it ca not.
    outs=""
    if missing==None:
        missing='.'
    for vv in [vvv for vvv in valuesNames if not vvv[0] == baseValue]:
        #if missing:
        outs+="gen %s%s =%s\n"%(newprefix,vv[1],missing)
        #else:
        #    outs+="capture gen %s%s =.\n"%(newprefix,vv[1])
        if isinstance(vv[0],str):
            outs+='replace %s%s = %s=="%s"\n'%(newprefix,vv[1],oldname,vv[0])
        else:
            outs+="replace %s%s = %s==%s\n"%(newprefix,vv[1],oldname,str(vv[0]))
    if not noCodebook: # THis added July 2009 for gallup to kludge it to work.. This should be in codebook class!
        addJointCodebookEntry(stataCodebookClass(),surveyName,oldname,newprefix+'*','[dummies]: ')
    return(outs)



################################################################
################################################################
def _pdfcodebooktxt2tsv(txtfile,tsvfile,survey=None):
    """
    Given a .txt file made from a pdf file, read and parse the txt, using knowledge about the format of the PDF documentation for that survey.
    """
    ################################################################
    ################################################################
    assert txtfile.endswith('.txt')
    if not tsvfile:
        tsvfile=paths['working']+os.path.split(txtfile).replace('.txt','.tsv')
    allVarsListOfDicts=None

    print (' Having to recreate the TSV from TXT (which comes from PDF) for %s!...'%txtfile)
    #assert 'CCHS' in txtfile # Yeah.. thi si not general yet..? well, test with others.
    source=''.join(file(txtfile,'rt').readlines())
    # May 2013: check for funny chars?
    pdfFields={}
    pdfFields['GSS17']=[['\nVariable Name:','varname'],
                  ['Position:','position'],
                  ['Length:','length'],
                  ['\n\n','desc'],
                  ['\n\n','pdfFreq'],
                  ['\nCoverage:','coverage'],
                  ['\n\n','end'],
                  ]
    pdfFields['GSS27']=[['\n *Variable Name','varname'],
                  ['Length','length'],
                  ['Position','position'],
                  ['\n *Question Name','questionname'],
                  ['\n *Concept','concept'],
                  ['\n *Question Text','question'],
                  ['\n *Universe','universe'],
                  ['\n *Note','note'],
                  ]

    if 'CCHS' in txtfile:
        reFields=[['\nVariable Name','varname'],
                  ['Length','length'],
                  ['Position','position'],
                  ['\nQuestion Name','questionname'],
                  ['\nConcept','concept'],
                  ['\nQuestion','question'],
                  ['\nUniverse','universe'],
                  ['\nNote','note'],
                  ]
        reString=''.join([r'%s(.*?)'%(ff[0]) for ff in reFields])
        allVars=re.findall(reString,source,re.DOTALL)
        assert allVars
        allVarsListOfDicts=[dict([[reFields[iiv][1].strip(),av[iiv].strip()] for iiv in range(len(reFields))])     for av in allVars]
        if toLower:    # From PDF should do lower case..
            for vv in allVarsListOfDicts:
                vv['varname']=vv['varname'].lower()
    if survey in ['GSS17','GSS22','GSS27']:
        #if 'GSS22' in txtfile or 'GSS17' in txtfile or 'GSS27' in txtfile  or 'GSS26' in txtfile:
        # Ca not get the question text for GSS22 hmmm.
        reFields= PDFfields[survey]#{'GSS27':GSS17fields if 'GSS22' in txtfile or 'GSS17' in txtfile else GSS27fields
        reString=''.join([r'%s(.*?)'%(ff[0]) for ff in reFields])
        allVars=re.findall(reString,source,re.DOTALL)
        assert allVars
        print('     Succeeded: found/parsed variable metadata from PDF codebook for '+txtfile)
        allVarsListOfDicts=[dict([[aff[1].strip(),av[iiv].strip()] for iiv,aff in enumerate(reFields)])     for av in allVars]
        for vv in allVarsListOfDicts:
            # From PDF should do lower case..
            vv['varname']=vv['varname'].lower()
            vv['fromPDF']=True

    if 'GSS17' in txtfile:
        print '!!!!!!!!!!! CANNOT READ GSS17 PDF YET'
        return
        reFields=[['\nVariable Name','varname'],
                  ['Length','length'],
                  ['Position','position'],
                  ['\nQuestion Name','questionname'],
                  ['\nConcept','concept'],
                  ['\nQuestion','question'],
                  ['\nUniverse','universe'],
                  ['\nNote','note'],
                  ]
        print """This_HAS_NEVER_BEEN_PROGRAMMED_
        SO_FAR_JUST_USING_FROMDTA
        woeiruwoeiu"""

    if allVarsListOfDicts is None:
        print("   Failed to parse PDF txt output for %s..."%survey)
    assert allVarsListOfDicts

    varOrder=[avd['varname'] for  avd in allVarsListOfDicts]
    allVarsDict=dict([[avd['varname'],avd]  for  avd in allVarsListOfDicts])
    assert len(varOrder)>100
    for vv in allVarsDict:
        allVarsDict[vv]['rawname']=allVarsDict[vv]['varname']
    fout=open(tsvfile,'wt')
    fout.write('\t'.join([ff[1].strip() for ff in reFields])+'\n')
    for var in allVarsListOfDicts:
        fout.write('\t'.join([str(var[ff[1].strip()].replace('\n',' ').strip()) for ff in reFields])+'\n')

    fout.close()
    return
