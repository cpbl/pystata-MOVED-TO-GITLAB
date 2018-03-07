#!/usr/bin/python
"""
CPBL, 2005-2014+
This is now 10 years of learning python, changes, rewrites, and tools which were built for a custom need.
Much code could probably be edited out, and some still needs to be revised to use new pandas methods.
Inline documentation is not great, as of the first github release  / Oct 2014, so start out with the demo, and with the README description for an overview

Please help by separating out things that make sense, and cleaning up that which doesn't.

Also currently depends heavily on cpblUtilities and latex-stat-tables .. and cpblDefaults. These can be excised...

Direction for future work:
    The approach to separate creating Stata code from both parsing the logfiles.
    In this approach, a set of means, oaxaca, etc, generates a log file which corresponds solely to the contents of one function.   As  a result, it should become standard practice to include the loading of data as part of each table code, so that the file loading is always in the same log as the table.
    Ultimately, we should separate the creation of the Stata code from the parsing of the log files. For instance, the new "oaxacaThreeWays" depends on oaxacaThreeWays_generate and oaxacaThreeWays_parse. This paired function pattern should exist for regressions, means, etc too. Currently, that's not the case for regTables(), which both generates and parses OLS/etc regression tables.  Log-parsing code should be in principle independent of code generation, so that we can also parse external do-file output.


Calculating means:
  It seems I've needed to do this several times and different ways ,so there are currently too many options for automating the calculation of means by groups. 
To clarify when to use each, here they are:

  - stataAddMeansByGroup(groupVar,meanVars,weightExp='[pw=weight]',groupType=str):#stataFile,subsetVar=None,subsetValues=None,incomeVars=None,giniPrefix='gini',opts=None):

  - meansByMultipleCategories(groupVars,meanVars,meansFileName,weightExp='[pw=weight]',forceUpdate=False,sourceFile=None,precode='',useStataCollapse=False):

  - genWeightedMeansByGroup(oldvar,group,prefix=None,newvar=None,weight='weight',se=False,label=None):

  - compareMeansByGroup(vars,latex=None):
                #pass # Placeholder for now; see cpblstatalatex.

  - latex.compareMeansInTwoGroups(self,showVars,ifgroups,ifnames,tableName=None,caption=None,usetest=None,skipStata=False,weight=' [pw=weight] ',substitutions=None):

  - generate_postEstimate_sums_by_condition: rather than groups, this takes simple if conditions. It looks only within the sample from the most recent regression. It is a bit confused about whether it wants only the all-variables-available sample or each variable's own available sample.

Configuration:
 A config.ini file should be used to set up folders to be used by pystata. The configuration procedure is as follows:
  (1) pystata.configure() can be called to explicity set config values.
  (2) Otherwise, pystata will look for a config.ini file in the operating system's local path at run time. Typically, this would be a file in the package of some caller module and would be in .gitignore so that it can be locally customized
  (3) Otherwise, pystata will look for a config.ini file in its own (the pystata repository) folder.  
"""
import os,re
import matplotlib.pyplot as plt
from .pystata_config import defaults,paths
assert 'paths' in defaults
WP=paths['working']
assert defaults is not None
try:
    codebookFilename=   defaults['native']['paths']['working']+'tmpCodebook'
    codebookTSVfilename=defaults['native']['paths']['working']+'tmpCodebook.tsv'
    codebookTeXfilename=defaults['native']['paths']['working']+'tmpCodebook.tex'
    mcodebook={} # This is a master codebook variable used to collect descriptions of variables that I actually use. Contrast rawCodebooks masterCodebook, below.
except KeyError:
    print("  Default file paths not defined for pystata")

try:
    from cpblUtilities import uniqueInOrder, debugprint, tsvToDict, orderListByRule, fileOlderThan
    from cpblUtilities import doSystem,shelfSave,shelfLoad,  renameDictKey,cwarning, str2pathname,dgetget
    from cpblUtilities.mathgraph import tonumeric, fNaN, seSum, weightedPearsonCoefficient
    from cpblUtilities.cpblunicode import str2latex
    from cpblUtilities.parallel import runFunctionsInParallel
except ImportError:
    import sys
    print(__file__+": Unable to find or import? CPBL's utilities package. Try importing it yourself to debug this.")

try:
    from cpblUtilities.textables import cpblTableStyC, cpblTableElements,chooseSFormat
except ImportError:
    print(__file__+": Unable to find (or unable to import) cpblTables module. Try importing it yourself to debug this.")

from copy import deepcopy
import pandas as pd
import numpy as np

global rawCodebooks
# Load up lists of *all* variables for surveys, if this info is available: (No, I need to reprogram thi to do it based just on the codebook class I've made)
##import extractCodebooks
##reload(extractCodebooks)

global missingVars
missingVars=[]
figureNumber=2999

crlist=['DA','CT','CSD','CMA','PR'] # Define possible census region scales.
EXACT='exact'
# Aug 2009: I am now including a fourth column in the below which can specify that the string must match the entire string, not just a subset.  I have yet to figure out how newmode will deal with underscores.
# I think the third columb is a text (not latex) version of the same thing.
standardSubstitutions=[ # Make LaTeX output look prettier. Third column is for spreadsheet output. #:(((
['_cons','constant'], # THIS IS A KLUDGE FOR NEWMODE. DEAL WITH IT PROPERLY...
        ['csd40100_','4-10 km: '],
        ['csd100200_','10-20 km: '],
        ['csd20200_','2-20 km: '],
        ['csd200400_','20-40 km: '],
        ['csd400990_','40-100 km: '],
        ['da0001_','$<$100 m: '],
        ['da0108_','0.1-0.8 km: '],
        ['da0820_','0.8-2 km: '],
        ['da2040_','2-4 km: '],
        ['ct0820_','0.8-2 km: '],
        ['ct2040_','2-4 km: '],
        ['swl4','SWL~(4-point)'],
        ['lsatis','SWL'],
        ['neigh0008_','$<$0.8 km: '],
        ['neigh0040_','$<$4 km: '],
        ['neigh0820_','0.8-2 km: '],
        ['neigh100200_','10-20 km: '],
        ['neigh200400_','20-40 km: '],
        ['neigh400990_','40-100 km: '],
        ['neigh2040_','2-4 km: '],
        ['neigh20200_','2-20 km: '],
        ['neigh40100_','4-10 km: '],
        ['neighn050_','(nearest 50): '],
        ['e(N)','obs.',[],EXACT],
        ['N','obs.',[],EXACT],
        ['e(N_psu)',r'N$_{\rm PSU}$'],
        ['e(N_clust)',r'N$_{\rm clusters}$'],
        ['e(r2_p)','pseudo-$R^2$'],
        ['e(r2)','$R^2$'],
        ['e(r2_a)','$R^2$(adj)'],
        ['r2_a','$R^2$(adj)',[],EXACT],
        ['r2_o','$R^2$(overall)',[],EXACT],
        ['e(ll)','log likelihood',[],EXACT],
        ['widstat','Weak ID $F$',[],EXACT], # This is generated by ivreg2
        ['idp','Under ID $p$',[],EXACT], # This is generated by ivreg2
        ['jp','Hansen J $p$',[],EXACT], # This is generated by ivreg2
        ['r2_p','pseudo-$R^2$',[],EXACT],
        ['r2','$R^2$',[],EXACT],
        ['ll','log likelihood',[],EXACT], # Is this necc? e(ll) wasn't working.
        ['N_clust',r'N$_{\rm clusters}$',[],EXACT],
        ['r(p)',r'$P\left(\sum\beta_{\rm{inc}}=0\right)$',[],EXACT],
        ['lnHHincome','ln(HH~inc)'],
        ['lnavHHincome','ln(HH~inc)'],
        ['lnadjHHincome',r'ln(HH~inc$_{\rm adj}$)'],
        ['lnadjHHinc',r'ln(HH~inc$_{\rm adj}$)'],
        ['lnRHHincome','ln(HH~inc$_{R}$)'],
        ['lnRIndivIncome','ln(own~inc$_{R}$)'],
        ['lnRavHHincome','ln(HH~inc$_{R}$)'],
        ['lnIndivIncome','ln(own~inc)'],
        ['lnAdjHHincome','ln(HH~inc$/\\sqrt{hh}$)'],
        ['trustBool','trust (social)'],#general trust'],
        ['imp_trust','imported trust'],#general trust'],
        ['edurank','rank(educ)'],
        ['educHighSchool','high school'],
        ['educStartedCollege','started college'],
        ['educUnivDegree','university degree'],
        ['HHincomerank','rank(HH~inc)'],
        ['incomerank','rank(own~inc)'],
        ['kmDowntown2','(km~downtown)$^2$'],
        ['kmDowntown2','km~downtown'],
        ['nearby08_','$<0.8$~km:~'],
        ['nearby20_','$<$2~km:~'],
        ['nearby40_','$<$4~km:~'],
        ['ageSquaredOver','(age/100)$^2$'],
        ['ageOverSquared','(age/100)$^2$'],
        ['ageOver','age/100'],] +\
        [['ld%s_'%cr.lower(),'%s:~$\\Delta^-$'%cr] for cr in crlist]  +\
        [['gd%s_'%cr.lower(),'%s:~$\\Delta^+$'%cr] for cr in crlist]  + [
        ['ageSquared','(age/100)$^2$'],
        ['da_','DA:~'],
        ['ct_','CT:~'],
        ['cma_','CMA:~'],
        ['pr_','PR:~'],
# Census micro moments:
        ['ctm_','CT:~'],
        ['csdm_','CSD:~'],
        ['cmam_','CMA:~'],
        ['prm_','PR:~'],
#
        ['hr_','HR:~'],
        ['csd_','CSD:~'],
        ['a15_','A15:~'],
        ['a50_','A50:~'],
        ['lnpopDensity','$\\ln(\\rho_{\\rm pop})$'],
        ['popDensity','$\\rho_{\\rm pop}$'],
        ['logpop','ln(pop)'],
        ['knowNeighbours','know neighbours'],
        ['trustNeighbour','trust (neighbours)'],
        ['trustColleagues','trust (colleagues)'],
        ['confidencePolice','confidence in police'],
        ['lnFreqSeeFamily','see family (frequency)'],
        ['lnFreqSeeFriends','see friends (frequency)'],
        ['loghouseValue','ln(houseValue)'],
        ['belongCommunity','belonging (community)'],
        ['belongProvince','belonging (province)'],
        ['belongCountry','belonging (country)'],
        ['herf_','Homogeneity:~'],
        ['frc_','Fraction:~'],
        # For ESC in particular:
        ['socialiseFriends','socialise (friends)'],
        ['socialiseNeighbour','socialise (neighbours)'],
        ['socialiseFamily','socialise (family)'],
        ['dNoReligion','no religion'],
        ['godImportance','religiosity'],
            ['godPracticed','religious practice'],
        ['godParticipateFrequency','church, etc attendance'],
        ['trustPolice','trust (police)'],
        ['nOrgCategories','memberships'],
['inc_div','income div'],
        #[['herf_%s'%vv,'Homogeneity:~%s'%vv] for vv in ['vismin','occupation','religion']]+\
        #[['frc_%s'%vv,'Fraction:~%s'%vv] for vv in ['immigrants','noReligion','occu_1to5','married','age65up']],
        ['foreignBorn','immigrant'],
        ]+[# Gallup World Poll stuff
            ['age100t3','(age/100)$^3$'],
            ['agecu100','(age/100)$^3$'],
            ['age100t4','(age/100)$^4$'],
            ['agefo100','(age/100)$^4$'],
            ['age100sq','(age/100)$^2$'],
            ['age100','age/100'],
            ['agesq100','(age/100)$^2$'],
['sepdivwid','sep/div/wid'],
['sepdiv','separated/divorced'],
['marriedAsMarried','(as)~married'],
['asMarried','as~married','as married'],
['firstLangFrench',r'francophone'],
['firstLang_french',r'francophone'],
['firstLang_others',r'allophone'],
['&','\&'],# Some country names ahve an ampersand...
# For GSSpool / time series / etc: GSS:
['highHHincome',r'HH income $>$100k\$/yr'],
['satisJob','Job satisfaction'],
#
['SWL1','SWL (scaled to [0,1])',[], EXACT],
['commonLawEver','ever lived common law'],
['friendlyPolice','friendly police'],
['gayPartner','homosexual partner'],
['godPartFreq','religious attendance (freq)'],
['happy','happy'],
['happyLife','happy life'],
#['health','health'],
['paidWorkHours','paid work hours'],
['safeWalkNight','safe to walk at night'],
['satisFinances','satisfaction with finances'],
['satisFriendships','satisfaction with friendships'],
['satisHousing','satisfaction with housing'],
['satisOtherTime','work-life balance'],
['satisRelFamily','good family relations'],
     ]

# Fill in any unfilled third columns: ( this if for non-tex output, maybe?)
def _addThirdColToSubs(subs):

    for sss in subs:
        if len(sss)==2:
            sss+=[sss[1].replace('~',' ')]
        elif not sss[2]:
            sss[2]=sss[1].replace('~',' ')
    return()

_addThirdColToSubs(standardSubstitutions)




def collapseMeansWithLabels(fromToList,commonPrefix=None,options=None,byKey=None,func='mean'):
    """

    Fix stata's collapse behaviour that does not preserve useful variable labels.
    This is so far just for collapsing to means. But the means can be differently named from the original variables.

    A simple version obtains if the commonPrefix is given. In that case, fromToList is just a list of variable names, not a list of pairs.


July 2010 Comment. hm. This is used for Gallup. But what is my general philosophy now on collapsing vs just calculating means?

July 2010: Adding

options:  It looks like you put if clauses here...

Nov2012: weird. The only variable I want to keep labels for is the collapse variable. The rest become continuous
    """
    outs=""


    if commonPrefix:
        allvars=' '+' '.join(fromToList)+' '
        fromtos=' '.join(['%s%s=%s'%(commonPrefix,ft,ft) for ft in fromToList])

        allcollapsedvars=' '+' '.join(['%s%s'%(commonPrefix,ft) for ft in fromToList])+' '

        # First, save ALL variable labels as though they will be collapsed, even though they may not.
        outs+="""
        foreach v of var * {
       	local l%s`v' : variable label `v'
       if `"`l%s`v''"' == "" {
    	local l%s`v' "`v'"
 	}
 }
"""%(commonPrefix,commonPrefix,commonPrefix)+0*"""  `"``''"'
"""+ """

        collapse  """+fromtos+ ' '+options+  ' , '*(',' not in options) + ' by('+byKey+""") fast

* Reinstate labels that collapse killed.
  foreach v of var """+commonPrefix+"""* {
 	label var `v' "(mean) `l`v''"
  }

                """

    else:
       foi
    return(outs)






###########################################################################################
###
def stataSystem(dofile, filename=None, mem=None,nice=True,version=None): # Give do file without .do
    ###
    #######################################################################################
    """
    This does a nice job of running a .do file (only in GNU/Linux so far?)

    If text containing a newline is passed as the first argument, it is interpreted as Stata code instead of a file.
    Stata's command line batch ability *stupidly* does not allow specification of where the log file goes.

    So change directory before running stata... hopefully this does not break something else (ie the .do file must use absolute pathnames always). Another method would be to find the local logfile, in a different path than the .do file... but I prefer forcing the log file to be where the do file is because in the RDC the do file is sometimes on a local disk while the local (bin) path is across a network.

    Returns the full name (path?) of the log file.

2010 Feb: Dealing with case of a period exists in the filename. Then Stata messes up naming the log file (sigh).


2012Aug: Now uses multiple cores if a list of dofiles or stata code is passed: if a list of strings with newlines is passed, and filename is also a list of strings, then they'll all be launched in parallel!

2012Aug: if filename is a path (or for now WP), it will look up the calling function (and file!?)'s names.

2013 Nov: "mem" is obselete, as modern Stata doesn't use it. As of now, it is ignored/deprecated.
    """

    if not dofile:
        print '   Skipping stataSystem: nothing to run '
        return('')

    if isinstance(dofile,list): # Invoke parallel (multiprocessing) behaviour!
      if not (isinstance(filename,list) and len(filename)==len(dofile)):
          if (isinstance(filename,list) and len(filename)==1):
              filename=filename[0]
          if (not isinstance(filename,list)):
              filename=[filename+'%02d'%idf for idf,df in enumerate(dofile)]

      #return(runFunctionsInParallelOLD([[stataSystem,df,filename[ii],mem,nice] for ii,df in enumerate(dofile)],names=filename))
      return(runFunctionsInParallel([[stataSystem,[dofi,filename[ii],mem,nice]] for ii,dofi in enumerate(dofile)],names=filename,expectNonzeroExit=True, parallel=defaults['server']['parallel']))



    if '\n' in dofile: # we were passed code, not a filename. Write the code to a tmp file.
        if not version:
            version=''
        if not filename:
            import sys
            tempfilename=WP+'make_'+ (sys._getframe(1).f_code.co_name).replace('<module>','unknownCaller')+'-'+version+'.do'  # Get calling (parent) functio name
            #import tempfile
            #tempfilename = tempfile.mktemp(suffix='.do')
        elif filename==WP:
            # also, by calling sys._getframe(1), you can get this information
            # for the *caller* of the current function.  So you can package
            # this functionality up into your own handy functions:
            import sys
            tempfilename=WP+'make_'+ sys._getframe(1).f_code.co_name+'-'+version+'.do'
        else:
            (root,ext)=os.path.split(filename)
            if not root:
                filename=WP+filename
            tempfilename=filename+'.do'
        fout=open(tempfilename,'wt')
        fout.write('* This tmp file generated by stataSystem \n')
        fout.write(dofile+'\n')
        fout.close()
        return(stataSystem(tempfilename, mem=mem,nice=nice))


    if not mem:
        mem=9999999#'500G'#defaults['maxRAM']

    assert not filename
    (root,ext)=os.path.splitext(dofile)
    if ext=='.do':# dofile[-3:]=='.do':
        dofile=root#dofile[0:-3]


    dodir,dofilenameNoSuffix=os.path.split(dofile)# re.split(r'\\|/',dofile)[-1]

    if not dodir:
        dodir=WP
    if '.' in dofilenameNoSuffix:
        cwarning('You have more than one period in your dofilenameNoSuffix: '+dofilenameNoSuffix+' : Please use function str2pathname when choosing filenames for use in  stataSystem')
        #assert 0 # Try to just replace these out before calling stataSystem...
        oldF=dofilenameNoSuffix
        dofilenameNoSuffix=str2pathname(dofilenameNoSuffix)#.replace('.','-')
        os.rename(dodir+'/'+oldF+'.do',dodir+'/'+dofilenameNoSuffix+'.do')
    logfile=dodir+'/'+dofilenameNoSuffix+'.log' # This is the global log path when it is made in the local directory at stata run time.

    # Obselete method here:
    if r'/' in dofile and 'leaveLogInLocalPath'=='yes':
        assert False
        dodir=r'/'.join(dofile.split(r'/')[0:-1]) # This is obselete; just write the .log file locally.
        logfile=r"`pwd`/"+ dofile.split(r'/')[-1]+'.log' # Local location for it. This might be a cleaner method of locating logfile, but as described above I prefer to force it to be in the dodir.
        logile=dofile+'.log' # Override above


    if defaults.get('cygwin',False):
        systemcom='/cygdrive/c/Program\ Files/Stata10/wsestata.exe /e /b do %s.do '%(dofile.replace('/cygdrive/k','k:')) #        stata -m1000 -b
        #systemcom='/home/ProgramFiles/Stata10/wsestata.exe /e /b do %s.do '%(dofile) #        stata -m1000 -b
        """
        But for subsequent commands, use a modified version of dofile in which directory is made readable for current OS:
        """
        dopath=defaults['dirChar'].join( re.split(r'\\|/',dofile)[0:-2] )
        dofile= re.split(r'\\|/',dofile)[-1]
    else:
        if os.path.exists(logfile):
            doSystem('rm %s'%logfile)
        niceString='nice -n 10 '*(nice==True)
        #if nice==False:
        #    niceString=''
        # Following seems to work! aug2010
        tmpDirCom='export TMPDIR='+WP #/home/cpbl/gallup/workingData' # or else be sure 20GB free on /tmp !

        if defaults.get('RDC',False):
            systemcom='cd %s && %s stata -v7000 -b do %s.do '%(dodir,niceString, dofile) #-m%d  mem
        else: 
            stataexec=['/usr/bin/stata14','/usr/bin/stata','/usr/local/stata12/stata-mp']
            stataexec=[ss for ss in stataexec if os.path.exists(ss)][0]
            if not stataexec:
                print(' **** STATA not found on this CPU. Aborting statasystem() call...')
                return
            systemcom=tmpDirCom+' && cd %s && %s %s  -b do %s.do '%(dodir,niceString,stataexec,dofile)
    print 'Initiating stata ...: '+systemcom+' with expected logfile at '+logfile

    if nice=='background':
        assert 0 # Not implemented yet.. All I have to do is put an ampersadnd, but ten I would need to fix up the log file afterwards.
    else:
        doSystem(systemcom)
    stataLogFile_joinLines(logfile) # Get rid of the stupid "\n> "s by changing the file on disk

    print 'Displaying end of log file: tail -n 20 %s '%logfile
    doSystem('tail %s'%logfile)
    #print 'Checking for Notes in output...: '
    doSystem('grep "\(Note\)\|\(Warning\)" %s |grep -v "Note:  Your site can add messages "|grep -v "Notes:"'%(logfile))
    #print 'Checking for cpbl warnings in output...: ',logfile
    doSystem('grep "CAUTION" %s | grep -v " di "'%(logfile))
    # Look for errors!!!!!!!!
    logtext=open(logfile,'rt').read()
    import re
    aa=re.findall('end of do-file\n(.*)\n',logtext) # Find errors, which follow "end of do file" lines.
    if aa:
        print 'Errors!! in do file log:',aa
        raw_input('Confirm... and continue')

    return(logfile)



##############################################################################
##############################################################################
#
def stataLogFile_joinLines(filename):
    ##########################################################################
    ##########################################################################

    """
    Get rid of the  "\n> "s by changing the file on disk
    """
    # AHA! Edit Stata's UGLY log file to get rid of the stupid line breakups!!!!
    # Should I also get rid of the periods? probably
    if filename and os.path.exists(filename):
        slft=   open(filename,'rt').read().replace('\n> ','').replace('\n. ','\n ')
        # Hey, let's also make things slightly more compact:
        slftMod= re.sub('\n *(\n *)+','\n\n',slft)
        if not slft==slftMod:
            # Only write if it's been changed! (or else write without changing the time stamp??
            open(filename,'wt').write(slftMod )
    else:
        woeiruowieur
    return()


###########################################################################################
###
def dta2tsv(filepath,keep=None,newpath=None):
    print "No. Just use (or modify/upgrade features of the loadStataDataForPlotting ..."
    1/0

###########################################################################################



###########################################################################################
def dtasaveold(pp,ff,ee='.dta', keep=None):
    ###
    """
    # Create stata 12 version of data :( since Pandas cannot read stata14
    for the moment, this must be a .dta file, not .dta.gz.
    """
    print('      Making stata 12 version of '+ff+ee+' ... ')
    stataSystem("""
   use """+pp+ff+""",clear
   """+('' if keep is None else ' keep ' + (keep if isinstance(keep,str) else ' '.join(keep)))+"""
   saveold """+paths['scratch']+'__tmpv12_'+ff+ee+""", replace version(12)
   """)
    pp=paths['scratch']+'__tmpv12_'
    return(pp+ff+'.dta')

###
def dta2dataframe(fn,noclobber=True,columns=None, filesuffix=None,
                  use_scratch=True):
    ###
    #######################################################################################
    """ For small files (at least),  this is MUCH faster for reload. It creates a temporary pandas file (huge compared with dta.gz) for future use.

For dta.gz files, it will create a .dta, needed for reading into pandas.

noclobber = True will allow this function to write to the same filename but with .pandas suffix. Otherwise, it will default to putting a "tmp_" prefix in front of the filename if the pandas file already exists.
That is, this function can now be used as the main way to create a pandas file from a dta file, even if you dn't want to load it.

columns : list or None
    Columns to retain.  Columns will be returned in the given order.  None
    returns all columns


N.B.: This uses pd.read_stata(); but it also makes a pandas file so it's faster for next time.
 What is wrong with loadStataDataForPlotting()?

.dta files and .pandas files are now created in scratch, unless use_scratch=False
    """
    
    if fn.endswith('.dta.gz'):
        ppff,ee=fn[:-7],fn[-7:]
        ee='.dta'
    elif fn.endswith('.dta'):
        not_supported_so_pass_dtagz
        ppff,ee=fn[:-4],fn[-4:]
    else:
        ppff,ee=fn,''
    pp,ff=os.path.split(ppff)
    pp= paths['working'] if pp in [''] else pp+'/' # Sorry; this line may be out of date now (201802)
    # sp is the path to use for all written files
    sp = paths['scratch'] if use_scratch else pp
        
        
    ####pp,ff,ee=[os.path.split(fn)[0] ] +    list(os.path.splitext(os.path.split(fn)[1])) 
    assert ee in ['','.dta','.dta.gz']
    assert ee in ['','.dta']
    if ee in ['']:
        'Not sure what to do here. Find dta or dta.gz...'
    import pandas as pd
    pdoutfile= (sp+ff if noclobber is False or not os.path.exists(sp+'tmp_'+ff+'.pandas') else sp+'tmp_'+ff)+{None:''}.get(filesuffix,filesuffix)+'.pandas' 
    if fileOlderThan(pdoutfile, pp+ff+'.dta.gz'):
        print('    ' +fn+' --> '+ os.path.split(pdoutfile)[1]+' --> DataFrame: using original Stata file...')
        if fn.endswith('.dta.gz') and fileOlderThan(sp+ff+'.dta',fn):
            os.system('gunzip -c {} > {}.dta'.format(fn,sp+ff))
        print('        read_stata '+pp+ff+ee)

        #if float(pd.__version__[2:]) < 17.0:
        #    ppffee=dtasaveold(sp,ff,ee)
        #    df=pd.read_stata( sp+ff+ee,convert_categoricals=False, columns=columns)#, encoding='utf-8')
        #else:
        if 1:
            try:
                df=pd.read_stata( sp+ff+ee,convert_categoricals=False, columns=columns)#, encoding='utf-8')
            except:# Error as e:
                print(' Failed with {}. Trying saving dta to old format ...'.format(ff))
                oldppffee=dtasaveold(sp,ff,ee)
                try:
                    df=pd.read_stata( oldppffee,convert_categoricals=False, columns=columns)#, encoding='utf-8')

                except ValueError as e:
                    print e
                    print ('Possible problem (see error statement above): Your columns do not all exist. Better restrict the df after loading the whole DTA file?')
                except UnicodeDecodeError as e:
                    print e
                    ppffee=dtasaveold(sp,ff,ee)
                    print(' \n\n\n ****  RESORTED TO JUNK CHARACTERS FOR UNICODE, SINCE THE FILE HAS CORRUPTED  UNICODE. RECREATE IT USING Stata 14+?? *** \n\n')
                    df=pd.read_stata( ppffee,convert_categoricals=False, columns=columns)#, encoding='utf-8')
                    """
                print(' UnicodeDecodeError: if you are using Stata14, then the file is probably the problem. Maybe it needs re-creating using Stata14 from the source data. My advice is to use saveold to create a Stata version 12 version. At least then, it will have garbage for the high-bit characters, rather than expecting them to be valid unicode.')
                print e
                raw_input('acknowledge:')
                raise"""
        df.to_pickle(pdoutfile)
    else:
        print('    '+ fn+' --> '+ os.path.split(pdoutfile)[1]+' --> DataFrame: using existing Pandas file...')
        df=pd.read_pickle(pdoutfile)
    print('    ... Loaded')
    return(df)

    print(" Just use pd.read_stata for now")
    """
?pandas.read_stata
Type:       function
String Form:<function read_stata at 0x7f493d368c80>
File:       /usr/lib/python2.7/dist-packages/pandas/io/stata.py
Definition: pd.read_stata(filepath_or_buffer, convert_dates=True, convert_categoricals=True, encoding=None, index=None)
Docstring:
Read Stata file into DataFrame

Parameters
----------
filepath_or_buffer : string or file-like object
    Path to .dta file or object implementing a binary read() functions
convert_dates : boolean, defaults to True
    Convert date variables to DataFrame time values
convert_categoricals : boolean, defaults to True
    Read value labels and convert columns to Categorical/Factor variables
encoding : string, None or encoding
    Encoding used to parse the files. Note that Stata doesn't
    support unicode. None defaults to cp1252.
index : identifier of index column
    identifier of column that should be used as index of the DataFrame

    """
dta2df=dta2dataframe

def dataframe2dta(df,fn,forceToString=None, extraStata=None):
    """
    Feb 2013: This is a crude beginning to an analogue for writing a dataset when we may want to force Stata to see some numeric fields as strings.
    Yes, pandas does this already, but not on Apollo, and I don't always love its behaviour.

    2014Dec: look for things that ought to be strings.

   To do: 
      - only reset index if it's named?
      - automate forceToString a bit
    """


    if forceToString is not False: # look for automatic force-to-string unless we're told not to
        dfr=df.reset_index()
        fts=[cc   for cc in dfr.columns if isinstance(dfr[cc][0],str)]
        if fts:
            print('  dataframe2dta: Found string columns automatically: '+str(fts))
        if forceToString:
            forceToString=np.unique(fts+list(forceToString))
        else:
            forceToString=fts
    if forceToString not in [None,False,[]]:
        df.reset_index().append(pd.Series(dict([(fts,'dummy') for fts in forceToString])),ignore_index=True).to_csv(fn+'.tsv',sep='\t',header=True,index=False)
    else:
        df.to_csv(fn+'.tsv',sep='\t',header=True)
    tsv2dta(fn, extraStata=extraStata)
    print('  Saved a CPBL df->TSV->dta.gz version as'+fn+'.dta.gz')

    # Ultimately, we should transition to pandas's version. So that it's there for comparison, make a .dta (not .dta.gz) version using Pandas: 
    # REmaining issues iwth it: if there are -inf's in a column, the column ends up as string. File bug report?
    #for infvv in df.columns:
    #    df[infvv][np.isinf( df[invff])]=np.nan
    try:
        df.to_stata(fn+'.dta') # Still fails on Apollo, 2015. Put this in try/except.
        print('  Saved a pandas to_stata() version as '+fn+'.dta')
    except ValueError:
        print( '     FAILED to use built-in Pandas writer to Stata...  (but succeeded in one by pystata method)')
        
    return

###########################################################################################
###
def df2dta(df,filepath=None,index=False,             forceToString=None,sortBy=None,drop=None,keep=None,newdir=None,newpath=None,renameVars=None,labelVars=None,forceUpdate=True,extraStata=None,csv=False, encoding='utf-8'):
    ###
    #######################################################################################
   """ Save a pandas dataframe to dta. N.B.! Default index=False means do not include the index. So run reset_index() before calling this...
   If df is a file with extension .pandas or .h5, then this will convert a .pandas  or .h5 file to a .dta.
   If df is a file without either extension, we will assume .pandas

   Call as: 
   
   df2dta(pd dataframe, dta.gz filename)
   df2dta(pandas filename)

   Note: If this is run on Apollo, the old method below uses a tsv intermediate file, and is yucky.

See the previous (draft?) function; does that provide a simpler way of forcing to string for after Apollo gets a pandas upgrade?
Dec 2014: This is now worse than dataframe2dta, which, like this, uses tsv's to get to dta, but unlike this one, does automatic string-variable finding.

   """
   import pandas as pd
   if isinstance(df,basestring):
       if df.endswith('.h5'): #Assume hd5 format (large file)
           df=df[:-3]
           assert(os.path.exists(df+'.h5'))
           from cpblUtilities import loadLargePandas
           pddf=loadLargePandas(df+'.h5')
           df2dta(pddf, df)
           return
       if df.endswith('.pandas'): # Otherwise, just assume it's short for a filename with .pandas extension
           df=df[:-7]
       assert(os.path.exists(df+'.pandas'))
       if fileOlderThan(df+'.dta.gz',df+'.pandas'):
           pddf=pd.read_pickle(df+'.pandas')
           df2dta(pddf,df)
       return
   else:
       assert isinstance(filepath,basestring)
       if filepath.endswith('.h5'): #Assume hd5 format (large file)
           filepath=filepath[:-3]
       if filepath.endswith('.pandas'): # Otherwise, just assume it's short for a filename with .pandas extension
           filepath=filepath[:-7]


   if 1: # 2014 July: I'm skipping df.to_stata: I don't know how to force things to string with it. Also forcing update to true, below.
       if any([' ' in cc for cc in  df.columns]):
           print(" Warning: found spaces in column names. Replacing them with underscores in df2dta")
           df.columns =  [cc.replace(' ','_') for cc in df.columns]
       df.to_csv(filepath+'_tmp.tsv',sep='\t',index=index,     encoding=encoding)
       return(tsv2dta(filepath+'_tmp',forceToString=forceToString,sortBy=sortBy,drop=drop,keep=keep,newdir=newdir,newpath=filepath,renameVars=renameVars,labelVars=labelVars,forceUpdate=True,extraStata=extraStata,csv=csv))


   try:  #   if pd.__version__ >= 13.0:
       df.to_stata(filepath+'.dta')
       # july 2014: This is still not ideal. my len()=5 string becomes len 244 in Stata! However, that doesn't hurt.
       if extraStata:
           import random
           import string
           stataSystem('use '+filepath+"""
           """+extraStata+"""
           """+stataSave(filepath),filename=paths['scratch']+'tmp_df2dta_'+''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(5)))
           os.system('rm  '+filepath+'.dta')
       else:
           os.system('gzip --force '+filepath+'.dta')
       print("  Used Pandas built-in df.to_stata")
   except (TypeError, AttributeError) as e:  # Apollo doesn't have to_stata. And on my machine, it doesn't like some contents (TypeError)
       repr( e )
       print(' df.to_stata() Failed! Falling back to awful .tsv method ')
       df.to_csv(filepath+'_tmp.tsv',sep='\t',index=index, encoding=encoding)
       return(tsv2dta(filepath+'_tmp',forceToString=forceToString,sortBy=sortBy,drop=drop,keep=keep,newdir=newdir,newpath=filepath,renameVars=renameVars,labelVars=labelVars,forceUpdate=forceUpdate,extraStata=extraStata,csv=csv))




###########################################################################################
###
def tsv2dta(filepath,forceToString=None,sortBy=None,drop=None,keep=None,newdir=None,newpath=None,renameVars=None,labelVars=None,keyRow=0,dataRow=1,labelRow=None,forceUpdate=False,extraStata=None,csv=False,  encoding='utf-8'): # Specify filepath without the .tsv extension
    ###
    #######################################################################################
    """ Make a dta version of data in a tsv file. This works even for Stata 9, which converts all variables to lower case (!).
    forceUpdate now can override the default behaviour, which is only to call Stata if the tsv file is older than the dta. [July 2009]

    It now has an option of specifying columns for  which should Stata be forced to treat it as a string.  In this case, the file is modified before giving it to Stata... Sigh.

    forceToString can be a list of integers (column numbers (0 based)) or a list of strings.
           Nov 2009: For fixed tsv files, I often just have the second line be used to force some things to string (by putting a string there, so stata sees at least one element is a string). Usually in this case the first field is "dummy" (ie it is one of the strings). So this program now checks the second line to see if there is "dummy" in there. If so, it drops it!


    newdir puts the new .dta file in a different directory (stripping old path off the filepath)

    newpath is an alternative to newdir (ie do not use both). It puts the new .dta file in a different directory and with a different filename. Do not include the .dta extension.

    renameVars is a dict of name translations. (or a list of pairs). Those translated to blank ('') will be dropped.

    keep takes a string listing variables to keep. All others will be dropped.

    labelVars is a dict of labels, with (renamed) (??) variable names as keys. It is an alternative to labelRow, which specifies the line in the file which holds labels. labelVars is not yet implemented.


    extraStata is a kludge to allow other Stata commands before saving. For instance, collapsing: "collapse (first) CTuid,by(DAuid) "

    csv looks for a file named .csv AND assumes that it is comma-separated! N.B. If you just avoid saying either "tab" or "comma", insheet does fine guessing.


    """
    assert labelVars==None # Not implemented yet.
    tsv,insheetOptions,csplit='.tsv',' tab ','\t'
    if csv:
        tsv,insheetOptions,csplit='.csv',' comma ',','

    if filepath[-4:]==tsv:
        filepath=filepath[0:-4]

    dirpath,filenameNoSuffix=os.path.split(filepath)
    if 0:
        filenameNoSuffix= re.split(r'\\|/',filepath)[-1]
        dirpath= r'/'.join(re.split(r'\\|/',filepath)[0:-1] )+r'/'

    # Choose an output .dta filename and filepath.
    assert not (newdir and newpath)
    if newdir==None and newpath==None: # Put dta file as same name (just different extension) as tsv
        newpath=filepath
    elif newpath==None: # Put dta file as same name but in a different location
        newpath=newdir+filenameNoSuffix###r'/'+     re.split(r'\\|/',filepath)[-1]
    logfilenameNoSuffix=filenameNoSuffix
    if newpath:
        logfilenameNoSuffix=os.path.split(newpath)[1]
    #assert not '.' in newpath # CAUTION: Stata will dumbly chop off everyting after the first period and append ".log" to make the log file


    if not forceUpdate and not fileOlderThan(newpath+'.dta.gz', filepath+tsv):
        if 0:
            print ('   tsv2dta: Skipping unneccesary re-creation of %s.dta.gz...'%newpath)
        return(newpath+'.dta.gz')

    # Convert renameVars to a dict
    if renameVars and (isinstance(renameVars,list) or isinstance(renameVars,tuple)):
        renameVars=dict(renameVars)
    #Name ones we do not want as "dropMe" (crude!)

    if not renameVars:
        renameVars={}

    rvn=1
    for rv in renameVars:
        if not renameVars[rv]:
            renameVars[rv]='dropMe%04d'%rvn
            rvn+=1
    # Set to drop any vars which are renamed null
    # (Actually, no. Drop is a string. But we've just set to null names of things we dont want)
    #if renameVars  and drop==None:
    #  drop=[rv for rv in renameVars if not renameVars[rv]]

    print 'tsv2dta: Transforming %s.tsv into .dta.gz, possibly with options specified'%filepath
    # Following line before keyRow option existed...
    #cVars=open(filepath+tsv,'rt').readline().strip().split(csplit)
    if 0 and defaults['mode'] in ['gallup','rdc']:
        from rdc_make import cpblRequire
        cpblRequire(filepath+tsv)
    ffl=open(filepath+tsv,'rt')
    firstFewLines=''
    for rml in range(max([keyRow,labelRow,dataRow])+2):
        firstFewLines+=ffl.readline()
    ffl.close()
    firstFewLines=firstFewLines.split('\n') # Or could it be '\r'?
    cVars=firstFewLines[keyRow].strip().split(csplit)
    firstVariable=[VVV for VVV in open(filepath+tsv,'rt').readline().split(csplit) if VVV][0]

    if firstFewLines[dataRow].startswith('dummy'): # This could be generalised to any field??
        dropFirstVarDummy='"dummy"'
    elif firstFewLines[dataRow].startswith('-9999'):
        dropFirstVarDummy='-9999'
    else:
        dropFirstVarDummy=False



    if renameVars: # Below is clunky; there's a fast way
        # Update renameVars to include unchanged columns:
        for cv in cVars:
            renameVars.setdefault(cv,cv)
        # Rename the columns:
        cVars=[renameVars[cv] for cv in cVars]

    if labelRow:
        labels=firstFewLines[labelRow].strip().split(csplit)
        labelLookup=dict(zip(cVars,labels))

    # Dec 2008: if not dataRow==1, we also need to do this...
    # If we need to rename some variables/columns before importing them with Stata, or if we need to force Stata to consider something as a string, we need to make a temporary, modified version of the file still in tsv form.
    if not forceToString:
        forceToString=[]
    if forceToString or renameVars:#not forceToString == None or not renameVars==None:
        dropDummies=[]
        for ifts,fts in enumerate(forceToString): # Convert the list forceToString to all strings, rather than column indices (it can contain both)
            if isinstance(fts,int):
                forceToString[ifts]=cVars[fts]
        # So now forceToString is a list of header names
        fout=open(os.path.split(newpath)[0]+'/tmpTmpTEMP'+os.path.split(newpath)[1]+tsv,'wt')
        fout.write(csplit.join(cVars)+'\n')
        if forceToString:
            dummies=[ "0" for vv in cVars]
            for ic,cv in enumerate(cVars):
                if cv in forceToString:
                    dummies[ic]='dummy'
                    dropDummies+=[cv]
            fout.write(csplit.join(dummies)+'\n')
        fout.write('\n'.join(open(filepath+tsv,'rt').readlines()[dataRow:]) + '\n')
        fout.close()
        outs=insheetStata9(os.path.split(newpath)[0]+'/tmpTmpTEMP'+os.path.split(newpath)[1]+tsv,opts=insheetOptions, encoding=encoding)
        if dropDummies:
            outs+='\ndrop if %s=="dummy"\n'%(dropDummies[0])
    elif not dataRow==1:
        fout=open(os.path.split(newpath)[0]+'/tmpTmpTEMP'+os.path.split(newpath)[1]+tsv,'wt')
        fout.write(csplit.join(cVars)+'\n')
        fout.write('\n'.join(open(filepath+tsv,'rt').readlines()[dataRow:]) + '\n')
        fout.close()
        outs=insheetStata9(os.path.split(newpath)[0]+'/tmpTmpTEMP'+os.path.split(newpath)[1]+tsv,opts=insheetOptions , encoding=encoding)
    else:
        outs=insheetStata9(filepath+tsv,opts=insheetOptions  , encoding=encoding)
        #outs+='\ndrop if %s=="dummy"\n'%(firstVariable) # In case the file came with its own dummy line

    #outs='insheet using "%s.tsv" , clear\n'%filepath
    #for vv in cVars:
    #    if not vv==vv.lower():
    #        outs+='rename %s %s\n'%(vv.lower(),vv)


    if dropFirstVarDummy:
        #if '"' not in dropFirstVarDummy:
        #    dropFirstVarDummy
        outs+="""
capture drop if %s==%s
***capture drop if s=="s" * Do not do this!! It can get rid of all blanks, which I may not want! ie if s==""value"" causes a bug in Stata.
"""%(firstVariable,dropFirstVarDummy)#,firstVariable,dropFirstVarDummy)


    for rv in renameVars:
        outs+='label variable %s "%s"\n'%(renameVars[rv],rv)
    # At this point, the renameVars which were seto be renamed to "" are still available, and are labelled nicely with their original column heading.

    if labelRow:
        for rv in labelLookup:
            outs+='label variable %s "%s"\n'%(rv,labelLookup[rv])

    if isinstance(drop,list):
        drop=' '.join(drop)
    if drop:
        outs+='drop  %s\n'%drop
    if renameVars:#not drop==None:
        outs+='capture drop dropMe*\n'

    if sortBy==None:
        sortBy=firstVariable

    if keep:
        if sortBy not in keep:
           keep+=' '+sortBy
        if isinstance(keep,list):
           keep=' '.join(keep)
        outs+='keep  %s\n'%keep


    outs+='sort %s\n'%sortBy # Better put this before extraStata, in case names change
    if extraStata:
        outs+='\n'+extraStata+'\n'

    outs+=stataSave(newpath)

    stataSystem(outs,filename=paths.get('scratch',paths['working'])+"tmp_statado_%s"%logfilenameNoSuffix)
    return(newpath+'.dta.gz')


###########################################################################################
###
def fixCaseStata9(afile): # This is because Stata9 does not offer the "case" option for insheet. #:(((
    ###
    #######################################################################################
    # So make insheet command and then follow it up with the output of this function.
    if os.path.exists(afile):
        headerVars=open(afile,'rt').readline().strip().split('\t')
        return('\n'+ '\n'.join(['rename %s %s'%(hv.lower(),hv) for hv in headerVars if not hv.lower()==hv]) +'\n')
    else:
        print ' WARNING! Stata will fail: %s does not exist\n'%afile
        return('\n*  WARNING! Stata will fail: %s does not exist\n'%afile)
###########################################################################################
###
def insheetStata9(afile,double=False,opts='', encoding='utf-8'): # This is used for all versions after Stata9, too...
    ###
    #######################################################################################
    sdouble=' double '*double
    if defaults['server']['stataVersion'] in ['linux9','linux12']:
        return('\n insheet using %s, name clear %s %s'%(afile,sdouble,opts)  +fixCaseStata9(afile)  +'\n')
    else:
        assert opts in ['',' tab ']
        return('\n  import delimited '+afile+', clear case(preserve) delimiter(tab) '+ 'asdouble'*double+' encoding("'+encoding+'") \n')
        # Old command:
        return('\n insheet using %s,  name clear case %s %s'%(afile,sdouble,opts)  +'\n')


###########################################################################################
###
def substitutedNames(names, subs=None,newCol=1):
    ###
    #######################################################################################
    """
    this does not change the original. The next function is meant to do that.

    newCol=1 gives a LaTeX-appropriate output

    newCol=2 gives a text-appropriate output (?)

    2012 June: shouldn't the latex class hae a version of this!?
    2013 March: Integers now converted to strings. [Motivation: when using i.category in Stata, variables can be numbers]
    """
    names=deepcopy(names)
    if subs==None:
        subs=standardSubstitutions

    def isstringlike(ss):
        return(isinstance(ss,basestring) or isinstance(ss,unicode))

    lookup=dict([sss[0:2] for sss in subs if len(sss)>3 and sss[3] == EXACT])
    substringReplace=[sss for sss in subs if len(sss)<4 or not sss[3] == EXACT]
    if isstringlike(names) and names in lookup:
        return(lookup[names])
    if isstringlike(names):
        for ps in substringReplace:
            names=names.replace(ps[0],ps[newCol])
        return(names)

    if isinstance(names,list):
        return([substitutedNames(aname, subs=subs,newCol=newCol) for aname in names])
    if names.__class__ in [int]: # Added March 2013: convert numbers to strings
        return(substitutedNames(str(names), subs=subs,newCol=newCol))
    assert 0 # Not finished (Aug 2009: implementing the exact matches, above. Okay done now but not checked)
    for iname in range(len(names)):
        if names[iname] in lookup:
            names[iname]=lookup[names[iname]]
        else:
            for ps in substringReplace:
                names[iname]=names[iname].replace(ps[0],ps[newCol])
    return(names)

#try:
#    from pystata.codebooks import stataCodebookClass
#except ImportError:
#    print(__file__+": Unable to find (or unable to import) pystata.codebooks module, part of pystata package")

global globalGroupCounter
globalGroupCounter=1 # This is used to label groups of models with a sequence of cell dummies.


#below: a t-distribution with infinitely-many degrees of freedom is a normal distribution...
TstatsSignificanceTable=[
[-0.1,    0.00001], # Backstop
[0.0,    0.00001],
[0.5,0.674],
[0.6, 0.841],
[0.7, 1.036],
[0.80, 	 1.28155 ],
[0.90, 	1.64485],
[0.95, 	1.95996],
[0.96,2.054],
[0.98, 	2.32635],
[0.99, 	2.57583],
[0.995, 	2.80703],
[0.998, 	3.09023],
[0.999, 	3.29052],
]
significanceTable=[
    # Latex format, t-ratio, tolerance percentage
[r'',0 ,100.0 ]  ,
[r'\signifTenPercent', 	1.64485, 10.0],
[r'\signifFivePercent', 	1.95996, 5.0],
[r'\signifOnePercent', 	2.57583, 1.0],
[r'\wrapSigOneThousandth{', 	3.291,0.1],
#r'', 999999999999999999999999999
]
significanceTable=[
    # Latex format, t-ratio, tolerance percentage
[r'',0 ,100.0 ]  ,
[r'\wrapSigTenPercent{', 	1.64485, 10.0],
[r'\wrapSigFivePercent{', 	1.95996, 5.0],
[r'\wrapSigOnePercent{', 	2.57583, 1.0],
[r'\wrapSigOneThousandth{', 	3.291,0.1],
#r'', 999999999999999999999999999
]
tsvSignificanceTable=[# for spreadsheet (tsv/csv) format: ie just text
    # stars, t-ratio, tolerance percentage
[r'',0  ]  ,
[r'*', 	1.64485, 10],
[r'**', 	1.95996, 5],
[r'***', 	2.57583, 1],
[r'****', 	3.291,0.1],
#r'', 999999999999999999999999999
]
"""
    Here are t-stats for one-sided and two sided.
    One Sided	75%	80%	85%	90%	95%	97.5%	99%	99.5%	99.75%	99.9%	99.95%
    Two Sided	50%	60%	70%	80%	90%	95%	98%	99%	99.5%	99.8%	99.9%
               0.674	0.842	1.036	1.282	1.645	1.960	2.326	2.576	2.807	3.090	3.291

    """



# this below is obselete?
# Maybe the following "significanceLevels" could be set externally by a call to this object/module.
significanceLevels=[90,95,99] # This is used for the command below, as well as for the colour/star replacement and corresponding legend!
significanceLevels=[100-ss[2] for ss in significanceTable[1:]] # This is used for the command below, as well as for the colour/star replacement and corresponding legend!

# This just hard-codes the relationship between some geographic scales in Canada.


doHeader="""
    * This file automatically generated by pystata.py. DO NOT EDIT!!!!
    * (~/ado/personal should be a hyperlink to ~/bin/ado, by the way.)
    * Ensure there's no open log file
    capture noisily log close
    clear
    capture noisily clear matrix
    capture noisily clear all
    *set maxvar 7000,permanently
    set more off
    matrix drop _all
* following is okay except on small machine on Stata 12? temp'ly turned off:
    *set matsize 11000
""" # For old stata versions:    * It appears that 500000 is the maximum allowed?! for scrollbufsize    ** set scrollbufsize 500000


# The following is currently used to choose variable ordering in regression tables when it is not specified. This feature should probably be disabled for non-CPBL users; obviously below is very custom, and it overrides the natural order which is Stata's: ie the order in which variables are used in the regressions constituting a table.
dvoprefixes=['da','dam','ct','ctm','a15','a15m','a50','a50m','csd','csdm','cma','cmam','hr','pr','prm']
defaultVariableOrder=r'w_meanClouds7days w_meanClouds7daysSquared w_diffClouds7days w_cloudCover w_maxtemp_c w_mintemp_c w_rain_mm w_snow_cm lnIndivIncome lnHHincome lnAdjHHincome  lnRIndivIncome lnRHHincome lnRAdjHHincome lowHHincome highHHincome '
defaultVariableOrder+=''.join([''.join([' %s%sHHincome '%(a,b) for b in ['lnav','ln','lnadj','lnMean','lnMdn','lnStd','lnRav','al_ln','ag_ln','vm_ln','gini']]) for a in ['']+[pf+'_' for pf in dvoprefixes]])+' '
defaultVariableOrder+=''.join([' %s '%b+''.join([' %s_%s '%(a,b) for a in dvoprefixes]) for b in r'CMA~prices $\sum\beta_{\rm{inc}}$ HHincomerank mortgagePayment lnhouseValue houseRooms age age100 age100sq agesq100 ageSquared agecu100 age100t3 agefo100 age100t4 age65up male  marriedAsMarried married asmarried asMarried  sepdivwid sepdiv separated divorced widowed  educHighSchool educStartedCollege educUnivDegree health workStress importedTrust  trustBool trustNeighbour  walletNeighbour walletStranger trustColleagues noColleagues  anySeeColleagues lnFreqSeeColleagues lnFreqSeeFamily anySeeFamily lnFreqSeeFriends anySeeFriends anyTalkFamily lnFreqTalkFamily anyTalkFriends lnFreqTalkFriends    lnCloseFriends lnCloseFamily lnOtherFriends     nCloseFamily nCloseFriends nOtherFriends lnOtherFriends      noReligion godImportance student employed domestic  unemployed retired mastery  confidencePolice dHHsize1 dHHsize2 dHHsize3 dHHsize4 dHHsize5 dHHsizeGT5  dHHsize5up constant cons_ controls mnth~f.e. stn~f.e. mnthStn~f.e.  PR~f.e. HR~f.e. CMA~f.e. CSD~f.e. CT~f.e. clustering $\tau_{\rm{neigh}}\geq$10yr $\tau_{\rm{city}}\geq$10yr citizen lnTenureHouse  lnTenureNeighbourhood lnTenureCity movedHouse1yr movedHouse5yr movedHouse10yr movedCity1yr movedCity5yr firstLangFrench frc_firstLang_french bornHomeProv foreignBorn foreign~born vismin belongCommunity belongProvince belongCountry valueSocial valueCoEthnic valueOtherEthnic      own~house'.split(' ') if b])
#defaultVariableOrder+='  survey    e(N) N e(r2) r2 e(r2-a) r2_a e(r2-p) r2_p e(ll) ll e(N-clust) N_clust r(p)'
defaultVariableOrder+='  survey    jp widstat idp  e(N) N e(r2) r2 e(r2-a) r2_a e(r2-p) r2_p ll e(N-clust) N_clust r(p) e(F)'
defaultVariableOrder=[vv for vv in     defaultVariableOrder.split(' ') if vv]





###########################################################################################
###
def toBoolVar(newname,oldname,surveyName=''):
    ###
    #######################################################################################
    " Generate Stata code to transform a variable into a boolean , and put it in the codebook "
    # Set unknown values to 0 rather than "missing"!!
    #outs="gen %s=0\n"%newname # It needs  already to exist
    outs=''
    outs+="replace %s=1 if %s==1\n"%(newname,oldname)

    if 1:
        # Copy the label from oldvar to new:
        outs+="local tmplabel: variable label %s\n"%oldname
        outs+="""label variable %s "[bool,.=0]: `tmplabel'"\n"""%(newname)
    #else:
    #    outs+="""label variable %s "[bool,.=0]: %s"\n"""%(newname,prompt)
    addJointCodebookEntry(surveyName,oldname,newname,'[bool,.=0]: ')
    #codebookEntry(newname,sn,prompt)
    return(outs)




###########################################################################################
###
def older_composeSpreadsheetRegressionTable(modelNames,modelNums,coefrows,extrarows,tableFormat=None,greycols=None,suppressSE=False,substitutions=None,modelTeXformat=None,transposed=None,tableTitle=None,caption=None,comments=None,landscape=None,rowModelNames=None,hideRows=None):
    ###
    #######################################################################################
    """
    (older?! but still used 2011 May!)(and 2014?!)


    This writes one or more .csv files (not a LaTeX file) for the given tabular information.
    It does not return anything.


    Possible formats:

    (1)    variables are rows; models are pairs of columns because s.e's are to the right of their coefficient
    [table3,4, tstats have stars](2)    variables are pairs of rows; models are columns because s.e's are below their coefficient
    [table6,stats,no stars](3)   variables are pairs of columns; models are rows, because s.e's are to the right of their coefficient
    (4)

    And subformats:
    (tstat) show tstats
    (se) show s.e.s
    (p) show p-values

    And subformats: what to decorate with stars
    () nothing
    (coef)
    (tstata/se/p)



    See comments for composeLaTeXtable, since this was adapted from it.
    Sept 2008.

    There's no "auto" for transposed. Well, there should be no "transposed". It's just different formats.


    """



    if tableFormat and tableFormat.get('csvMode',None)=='all': # isinstance(tableFormat,basestring) and tableFormat=='all':

        tableFormat={}
        tableFormat['columns']='variables'#'models'
        tableFormat['SEposition']='beside'#'below'
        tableFormat['SEtype']='tstat'#tratio, se, pvalue
        tableFormat['decorate']='none'
        older_composeSpreadsheetRegressionTable(modelNames,modelNums,coefrows,extrarows,substitutions=substitutions,tableTitle=tableTitle,caption=caption,comments=comments,rowModelNames=rowModelNames,tableFormat=tableFormat)

        tableFormat={}
        tableFormat['columns']='models'#'variables'#
        tableFormat['SEposition']='below'#'beside'#
        tableFormat['SEtype']='tstat'#tratio, se, pvalue
        tableFormat['decorate']='coef'#'tstat'
        older_composeSpreadsheetRegressionTable(modelNames,modelNums,coefrows,extrarows,substitutions=substitutions,tableTitle=tableTitle,caption=caption,comments=comments,rowModelNames=rowModelNames,tableFormat=tableFormat)

        tableFormat={}
        tableFormat['columns']='models'#'variables'#
        tableFormat['SEposition']='below'#'beside'#
        tableFormat['SEtype']='tstat'#tratio, se, pvalue
        tableFormat['decorate']='tstat'
        older_composeSpreadsheetRegressionTable(modelNames,modelNums,coefrows,extrarows,substitutions=substitutions,tableTitle=tableTitle,caption=caption,comments=comments,rowModelNames=rowModelNames,tableFormat=tableFormat)
        return

    assert tableFormat['columns'] in ['models','variables'] and    tableFormat['SEposition'] in ['below','beside'] and    tableFormat['SEtype'] in ['tstat'] and    tableFormat['decorate'] in ['tstat','none','coef']


    modelNames=deepcopy(modelNames)
    modelNums=deepcopy(modelNums)
    coefrows=deepcopy(coefrows)
    extrarows=deepcopy(extrarows)


    if len(coefrows)==0:
        cwarning("All the regressions in this table were carried out but FAILED due to lack of values or etc. So we'll skip making the table.")
        return(None)


    if rowModelNames == None:
        rowModelNames=deepcopy(modelNames)

    if tableTitle==None:
        tableTitle=caption#'A cpblTable table'

    if isinstance(coefrows[0][0],list):
        pairedrows=coefrows
    else:
        pairedrows=[[coefrows[ii],coefrows[ii+1]] for ii in range(0,len(coefrows),2)]
    nmodels=len(pairedrows[0][0])-1
    coefrows=None # Safety
    if not modelNames:
        modelNames=['']*nmodels
    if not modelNums:
        modelNums=['']*nmodels


    assert(len(modelNames)==len(modelNums))
    assert(len(modelNames)+1==len(pairedrows[0][0]))
    # Do not bother with hiding rows or columns. It's easy to manipulate in a spreadsheet.

    subs=substitutions

    # Fill in any unfilled third columns:
    _addThirdColToSubs(subs)


    #for ps in subs:
    if 1:
        for icol in range(len(modelNames)):
            modelNames[icol]=substitutedNames(modelNames[icol],subs,newCol=2)#.replace(ps[0],ps[2])
        for pair in pairedrows:
            pair[0][0]=substitutedNames(pair[0][0],subs,newCol=2)#pair[0][0].replace(ps[0],ps[2])
        for irow in  range(len(extrarows)): # At least the Stata-generated summary statistics rows need sub'bing:
            extrarows[irow][0]=substitutedNames(extrarows[irow][0],subs,newCol=2)#extrarows[irow][0].replace(ps[0],ps[2])



    # Construct a matrix of formatted cells, so it can be used in transposed or standard layout:
    # Note that modelNums and modelNames are not yet formatted.
    nmodels=len(pairedrows[0][0])-1
    cellsbeta=[[[] for i in range(nmodels+1)] for j in range(len(pairedrows) +len(extrarows))]
    # The first column and the extralines cells will remain blank
    cellsse=[[[] for i in range(nmodels+1)] for j in range(len(pairedrows) +len(extrarows))]
    # And make a copy to tratios:
    cellstratio=[['' for i in range(nmodels+1)] for j in range(len(pairedrows) +len(extrarows))]
    # And make a copy to hold significance stars:
    cellsSignif=[['' for i in range(nmodels+1)] for j in range(len(pairedrows) +len(extrarows))]
    # The first column  will remain blank. This is the same thing but
    # with the colour significance level commands too. Normally, in
    # non-transposed tables we do not want coloured SEs, but in
    # transposed we do.
    # There's a problem with that: when stars, not colours, are being used, we certainly do not want it to act on both coeffs and SE. So for now get rid of colour on SE's altogether:
    cellssewc=[[[] for i in range(nmodels+1)] for j in range(len(pairedrows) +len(extrarows))]
    for ipair in range(len(pairedrows)):
        pair=pairedrows[ipair]
        significanceString=[[] for i in range(len(pair[0]))]
        for i in range(len(pair[0])):
            significanceString[i]=''
        rowname=pair[0][0]
        cellsbeta[ipair][0]= pair[0][0]# rowname in first column
        cellsse[ipair][0]= ''
        cellssewc[ipair][0]= ''

        # Now populate parallel matrix of significance stars
        if 1:
            for icol in range(1,len(pair[0])):
                # Safety: so far this is only because of line "test 0= sumofincomecoefficients": when that fails, right now a value is anyway written to the output file (Aug 2008); this needs fixing. In the mean time, junk coefs with zero tolerance:
                if pair[1][icol]<1e-10: #==0 or : # Added sept 2008...
                    pair[0][icol]=''
                if isinstance(pair[0][icol],float) and not str(pair[0][icol])=='nan':# and not pair[1][icol]==0:
                    cellstratio[ipair][icol]=abs(pair[0][icol]/pair[1][icol])
                    cellsSignif[ipair][icol]=([' ']+[tt[0] for tt in tsvSignificanceTable if cellstratio[ipair][icol]>= tt[1]])[-1]

                cellsbeta[ipair][icol]=chooseSFormat(pair[0][icol],noTeX=True)
                cellsse[ipair][icol]=chooseSFormat(pair[1][icol],noTeX=True)
                #cellssewc[ipair][icol]=chooseSFormat(pair[1][icol],ifconditionalWrapper=[significanceString[icol]+r'\coefse{','}'+'}'*(not not significanceString[icol])])

                # OVerwrite this for now, as explained above
                #cellssewc[ipair][icol]=chooseSFormat(pair[1][icol],ifconditionalWrapper=[r'\coefse{','}'])  +  greyString[icol]

    # Format row names and format extrarows:
    for irow in range(len(extrarows)):
        for icol in range(len(pair[0])):
            cellsbeta[len(pairedrows)+irow][icol]=extrarows[irow][icol]
            cellsse[len(pairedrows)+irow][icol]=''
            cellssewc[len(pairedrows)+irow][icol]=''
##     # Format model names and numbers:
##     if any(modelNames):
##         fmodelnames=[[r'\sltheadername{%s}'%modelNames[idv],r'\sltheadername{%s}\aggc'%modelNames[idv]][int(idv+1 in greycols)] for idv in range(len(modelNames))]
##     else:
##         fmodelnames=modelNames
##     if any(modelNums):
##         fmodelnums= [[r'\sltheadernum{%s}'%modelNums[idv],r'\sltheadernum{%s}\aggc'%modelNums[idv]][int(idv+1 in greycols)] for idv in range(len(modelNums))]
##     else:
##         fmodelnums=modelNums

    # Now output appropriate format(s)
    elimChars=r" \ (){}-,."



    varNames=[cb[0] for cb in cellsbeta]

    if  tableFormat['columns']=='variables' and    tableFormat['SEposition']=='beside' and    tableFormat['SEtype']=='tstat' and    tableFormat['decorate'] in ['tstat','none']:

        # This is a "transposed" format


        tsvOut=open(defaults['paths']['tex']+''.join([ss for ss in tableTitle if ss not in elimChars])+'_'+'_'.join(tableFormat.values())+'.csv','wt')

        # Header is two-cell-wide each variables.
        tsvOut.write('modelName\t'+'\t'.join([''.join([cc for cc in cn if cc not in elimChars])+'\tse'+''.join([cc for cc in cn if cc not in elimChars]) for cn in varNames])+'\n')
        # Make a set of coeff / t-stat labels
        tsvOut.write('\t'+'\t'.join(['Coeff.\tt-stat' for cn in varNames])+'\n')
        # Output coefs and tstats
        for imodel in range(len(modelNames)):
            if tableFormat['decorate'] =='tstat':
                tsvOut.write(modelNames[imodel]+'\t'+ '\t'.join([cellsbeta[icb][imodel+1]+'\t'+chooseSFormat(cellstratio[icb][imodel+1],conditionalWrapper=['[',']'],noTeX=True)+cellsSignif[icb][imodel+1] for icb in range(len(cellsbeta))])+'\n')
            elif tableFormat['decorate'] =='none':
                tsvOut.write(modelNames[imodel]+'\t'+ '\t'.join([chooseSFormat(cellsbeta[icb][imodel+1])+'\t'+chooseSFormat(cellstratio[icb][imodel+1],conditionalWrapper=['',''],noTeX=True) for icb in range(len(cellsbeta))])+'\n')


        tsvOut.close()


    elif  tableFormat['columns']=='models' and    tableFormat['SEposition']=='below' and    tableFormat['SEtype']=='tstat' and    tableFormat['decorate'] in ['tstat','coef']:

        tsvOut=open(defaults['paths']['tex']+''.join([ss for ss in tableTitle if ss not in elimChars])+'_'+'_'.join(tableFormat.values())+'.csv','wt')

        # Header is one cell wide: model name
        tsvOut.write('\t'+'\t'.join([''.join([cc for cc in cn if cc not in elimChars]) for cn in modelNames])+'\n')

        # Output coefs and tstats, one variable at a time (two rows per variable)
        for iVar in range(len(cellsbeta)):
            if tableFormat['decorate'] =='tstat':
                tsvOut.write('\t'.join(chooseSFormat(cellsbeta[iVar]))+'\n')
                tsvOut.write('\t'.join([chooseSFormat(cellstratio[iVar][im],conditionalWrapper=['[',']'],noTeX=True)+cellsSignif[iVar][im] for im in range(len(cellstratio[iVar]))])+'\n')
            elif tableFormat['decorate'] =='coef':
                tsvOut.write('\t'.join([chooseSFormat(cellsbeta[iVar][im])+cellsSignif[iVar][im] for im in range(len(cellstratio[iVar]))])+'\n')
                tsvOut.write('\t'.join(chooseSFormat(cellstratio[iVar],conditionalWrapper=['[',']'],noTeX=True))+'\n')
                #tsvOut.write('\t'.join([chooseSFormat(cellstratio[iVar][im],conditionalWrapper=['[',']'],noTeX=True) for im in range(len(cellstratio[iVar]))])+'\n')


        tsvOut.close()

    else:
        print 'Do not know this format for spreadsheet output'
        fooooey


    return


###########################################################################################
###
def composeLaTeXregressionTable(models,tableFormat=None,suppressSE=False,showFlags=None, showStats=None,substitutions=None,modelTeXformat=None,transposed=None,multirowLabels=True,showOnlyVars=None,hideVars=None):
    ### retired arguments:,variableOrder=None
    #######################################################################################
    """ CPBL, March 2008: This is part of a package to produce latex
    tables of regression coefficients, using Stata as an engine. 

    This function composes the main parts of the tabular output for all formats of LaTeX table.

    It could be used on its own, since it starts from well after Stata results stage. See regressions-demo for an example.

    This assesses significance for coefficients and errors, assuming normality (!).
    It substitutes names of variables to readable ones.
    It formats numbers nicely, with vaguely smart number of sig figs.
    It returns a string which constitutes a complete latex table.
    Possibly turns some columns a different colour if desired (as in greycols)

    The coefrows can be submitted as a list of pairs or as an even numbered list of rows.

    If there are many columns, the table will be enclosed in a command to allow extra small fonts.

    3 April:

    18 March 2008: Robert would have been 22 tomorrow. This function returns: a string of Stata code, a string of LaTeX code which defines a table and includes the tabular file.

    Transposed versions are saved with a modified filename, to facilitate having both options.

    14 March 2008: added transposed feature: try to have regression
    models as rows rather than columns. Then a longtable permits as
    many models as I like, and descriptions of variables can be long.
    This involved major recoding, so that cells are formatted in
    matrices before outputting to one kind of table or another.

    modelTeXformat is used directly for the non-transposed form, but ends up being parsed simply to find where to put hlines in the transposed form.

Dec 2008: I am adding multirow capability for coefrows when in normal orientation.. April 2010: Making multirow actually work... in cpblTableCAC formats.

    """

    """
    multirowLabels: sets first column to be fixed width, wrapped ? requires...

    rowModelNames-?

    showFlags = list of flags (or extra blank lines) to included, in addition to regressors and stats. Unrecognised flags will be included as blanks.

    showStats = list of which regression stats (r^2 etc) to show. Unrecognised stats will be excluded. So will stats with empty values for all models.



    should tableFormat include hideVars? Yes, it can be used to fill in the value...


Nov 2010: Trying to add much smarter top row headers, using multi-col, etc, facultative rotation, etc.
The logic should be:
- This applies only if vars as rows, ie models are columns.
- if no columns are named, put no header except column numbers, not rotated
- If adjacent colums have the same name, do not rotate any numbers, and combine column headers with the same name. (Still rotate non-repeated!?!?) No, do not rotate any.
Done. Nice.
NOT DONE: I also want to use simpletable rather than longtable, when clearly appropriate, and in that case to make the legend go outside the caption.
Hm... but this doesn't yet include multi-level labels, right? tpyical application: all columns have same depvar, so horiz title over all cols, then \cline{2-n}, then a couple of groups each spanning multiple, then column numbers.
 - 2015July: added yet another header row, modelGroupName, to go above names.


May 2011: adding different treatment for suestTests values, which just have a p-value.

June 2011: Done: updated this to use new cpblTableC ability to have both transposed and normal in one file! So now transposed can have value "both". And if one or other is specified, the opposite is still included in the cpbltablec file...

    """

    assert not tableFormat==None
    if tableFormat==None:
        tableFormat={}

    if 'title' not in tableFormat and 'caption' in tableFormat:
        tableFormat['title']=tableFormat['caption']

    if 'hideVars' in tableFormat and hideVars==None:
        hideVars=tableFormat['hideVars']


    # Make .csv output copy for the same data:
    tsvTableFormat = deepcopy(tableFormat)
    tsvTableFormat.update({'csvMode':'all'})
    composeTSVregressionTable(models, substitutions=substitutions, tableTitle=tableFormat['title'], caption=tableFormat['caption'],comments=tableFormat.get('comments',''),tableFormat=tsvTableFormat)




    # May 2011: try this:
    if tableFormat.get('hideModelNames',False):
      for mm in models:
        if 'texModelName' in mm:
           mm.pop('texModelName')
        mm['name']=''



    # Use the code from modelsToPairedRows to order the variables... and start by using modelResultsByVar to get the right lists of vars (in three categories)
    byVar,byStat,byTextraline= modelResultsByVar(models)#,tableFilename=tableFilename)

    #chooseDisplayVariables(models,variableOrder=variableOrder,
    variableOrder=tableFormat.get('variableOrder',None)
    assert variableOrder
    if variableOrder==None:
        variableOrder=defaultVariableOrder
    if isinstance(variableOrder,basestring):
        variableOrder=[vv for vv in variableOrder.split(' ') if vv]

    # In order to ensure the constant term comes last... let's append all variables known from substitutions to the end of variable order:
    # Following line fails, since const substition is part of substitutions, and could be early...
    variableOrder+=[vvv[0] for vvv in substitutions]

    # Agh, shoot: need to massage hidvars: [Not always; look both for e(stat) and stat.
    hideStats=[sv for sv in byStat.keys() if 'e(%s)'%sv in hideVars or sv in hideVars]###'r2','r2_a','r2_p','N','p','N_clust'

    coefVars=orderListByRule(byVar.keys(),variableOrder,dropIfKey=hideVars)
    statsVars=orderListByRule(orderListByRule(byStat.keys(),['r2','r2_a','r2_p','N','p','N_clust']),variableOrder,dropIfKey=hideStats)
    flagsVars=orderListByRule(byTextraline.keys(),variableOrder,dropIfKey=hideVars)

    if showOnlyVars: # In which case variableOrder, variableOrder will have no effect:
        coefVars=[vv for vv in showOnlyVars if vv in coefVars]#orderListByRule(vars,showOnlyVars) if vv in showOnlyVars]
        statsVars=[vv for vv in showOnlyVars if vv in statsVars]#orderListByRule(vars,showOnlyVars) if vv in showOnlyVars]
        flagsVars=[vv for vv in showOnlyVars if vv in flagsVars]#orderListByRule(vars,showOnlyVars) if vv in showOnlyVars]


    # Choose the format for the table, where some choice is left
    # Oct 2009: it seems "none" is not getting this far. It's already being converted to True somewhere. So use 'auto' or fix it.
    # June 2011: This should just be used for choosing which one to display, since both should be built in to tex file ...
    if transposed==None or (isinstance(transposed,basestring) and transposed=='auto'):
        transposed=True#False

        # 30 across long dimension (11") by 20 across short dimension (8.5") is pretty packed. So decide here whether to do non-transposed.
        # Begin here various heuristics....
        if len(coefVars)+len(statsVars)+len(flagsVars) > 30 and len(models) <=20:
            transposed=False
        elif len(coefVars)+len(statsVars)+len(flagsVars) > 20 and len(models) <=10:
            transposed=False

    subs=substitutions


    modelsAsRows=transposed==True
    varsAsRows= transposed==False



    r2names=['e(r2-a)','e(r2)','e(r2-p)','r2','r2_a','r2-a','r2_p','r2-p']
    def formatEstStat(model,estat):
        """
        pre-format these so that we can do 3 sig digs for r2:
        """
        if estat in r2names:
            return(chooseSFormat(dgetget(model,'eststats',estat,fNaN),lowCutoff=1.0e-3,threeSigDigs=True))#,convertStrings=True
        else:
            return(chooseSFormat(dgetget(model,'eststats',estat,fNaN)))#lowCutoff=1.0e-3,convertStrings=True,threeSigDigs=True)



    # Some strings can be set regardless of transposed or conventional layout:
    tableLabel=r'tab:%s'%(''.join([s for s in tableFormat.get('caption','') if s not in ' ,.~()-']))

    landscape=False # This maybe used to be more automated, depending on ntexcols, ntexcols. I've set it to False because I tend to have one continuous landscape environment for the whole tex file now.


    # huh? this section used be after the big transposed if! Weird.
    if 0:
        ntexrows,ntexcols= 1+(1+int(suppressSE))*len(models),   2+len(coefVars+statsVars+flagsVars)

        formats='lc*{%d}{r}'%(ntexcols-2) # or: 'l'+'c'*nvars
        if multirowLabels:
            formats='lp{3cm}*{%d}{r}'%(ntexcols-2) # or: 'l'+'c'*nvars

        ###assert not '&' in [cellsvmmodel[0] for cellsvmmodel in cellsvm] # This would be a mistake in regTable caller?
        headersLine='\t&'.join(['','']+[r'\begin{sideways}\sltcheadername{%s}\end{sideways}'%substitutedNames(vv,substitutions) for vv in coefVars+flagsVars+statsVars])+'\\\\ \n'+r'\hline'####cellsvmmodel[0] for cellsvmmodel in cellsvm])+'\\\\ \n'+r'\hline'#\cline{1-\ctNtabCols}'
        headersLine1=headersLine+'\\hline\n'#r'\cline{1-\ctNtabCols}'+'\n'
        headersLine2=headersLine+'\n'


    # $$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
    # First, do preparaation as though vars as rows:
    # $$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$

    #varsAsRows=True
    body=''
    for vv in coefVars:
        pValues=None
        # Caution! I'm introducing here May 2011: if there is any suestTest in the table, then all p-values given by Stata will be used, even though they are often "0.0". But hopefully 0.0 corresponds to smaller than 10^3 or whatever my most stringent level is. (since otherwise, I've been using the t-stat, which as more precision, to calculate the p-value category myself).
        # N.B. for varsAsRows, using "byVar" has already selected "p" as the display coefficient for any suestTest columns.
        if any([mm.get('special','') in ['suestTests'] for mm in models]):
             pValues=[None]+byVar[vv]['p']

        ##        if model.get('special','') in ['suestTests']:
        ##         displayEst='p' # For OLS etc
        ##         displayErr='nothing!'
        ##         estValues=[r'\sltheadernum{'+model.get('texModelNum','(%d)'%(model.get('modelNum',0)))+'}',
        ##     			  r'\sltrheadername{'+ model['tmpTableRowName']+'}']+[dgetget(model,'estcoefs',vv,displayEst,fNaN) for vv in coefVars]+[dgetget(model,'textralines',vv,fNaN) for vv in flagsVars]+[formatEstStat(model,vv) for vv in statsVars]
        ##         errValues=['','']+[dgetget(model,'estcoefs',vv,displayErr,fNaN) for vv in coefVars]+['' for vv in flagsVars]+['' for vv in statsVars]
        ##         pValues=['','']+[dgetget(model,'estcoefs',vv,'p',fNaN) for vv in coefVars]+['' for vv in flagsVars]+['' for vv in statsVars]

        ##         tworows=formatPairedRow([estValues,errValues],
        ##                                 greycells='tableshading' in model and model['tableshading'] in ['grey'],
        ##                                 pValues=pValues)
        assert  '_' not in substitutedNames(vv,substitutions)
        tworows=formatPairedRow(  [[r'\sltrheadername{%s}'%substitutedNames(vv,substitutions)]+byVar[vv]['coefs'],
                                ['']+byVar[vv]['ses']] ,pValues=pValues)
        #    ['']+[dgetget(model,'estcoefs',vv,displayErr,fNaN) for vv in coefVars]+['' for vv in flagsVars]+['' for vv in statsVars]],greycells='tableshading' in model and model['tableshading'] in ['grey'])#,modelsAsRows=True)
            #tworows=tworows[0:(2-int(suppressSE))]  # Include standard errors?
        body+= '\t& '.join([cc for cc in tworows[0]])+'\\\\ \n'+r'\showSEs{'+\
                        '\t& '.join([cc for cc in tworows[1]]) +' \\\\ }{}\n'
    body+=r'\hline '+'\n' # Separate the coefs from extralines..
    for vv in flagsVars:
        body+= '\t& '.join([substitutedNames(vv,substitutions)]+byTextraline[vv])+'\\\\ \n'
    for estat in statsVars:
        lowCutoff,threeSigDigs=        (1.0e-3,True) if estat in r2names else                (1.0e-5,False) if estat in ['widstat','jp','idp']        else (None,False)
        body+= '\t& '.join([substitutedNames(estat,substitutions)]+[chooseSFormat(cc,lowCutoff=lowCutoff,threeSigDigs=threeSigDigs) for cc in byStat[estat]])+'\\\\ \n'
        #assert not 'idp' == estat

    ntexrows,ntexcols=   1+len(coefVars+statsVars+flagsVars),1+(1+int(suppressSE))*len(models) # ?????NOT CHECKED
    formats='l*{%d}{r}'%(ntexcols-1) # or: 'l'+'c'*nvars
    if any(['|' in mm['format'] for mm in models]):
        formats='l'+''.join([mm['format'] for mm in models]) # N.b. this is rewritten below for use in multicolum headers.

    def smartColumnHeader(colgroups,colheads,colnums,colformats=None):
        """
        See description for main function, above.
        returns headersline1,headersline2
See also 201709 single_to_multicolumn_fixer() in cpblUtilities/textables
        """
        if not any(colheads):
            assert  not any(colgroups) # It would be silly to have group names but no names: If you just want one row, use names. (?)
            return('\t&'.join(['']+[r'\sltcheadername{%s}'%(model.get('texModelNum','(%d)'%(model.get('modelNum',0)))) for model in models])+'\\\\ \\hline \n',r'\ctFirstHeader')
        #  Now, loop through and find consecutive groups...
        if colformats is None:
                colformats=['c' for xx in colheads]
        def findAdjacentRepeats(colnames,cformats): # Build list of possibly-multicolumn headers for one row.
            hgroups=[]
            for ih,hh in enumerate(colnames):
               if ih>0 and hh==hgroups[-1][0]:
                    hgroups[-1][1]+=1
                    hgroups[-1][2]='c'+'|'*(cformats[ih].endswith('|'))# Multicolumn headings should all be centered.
               else:
                    hgroups+=[[hh,1,cformats[ih]]]
            return(hgroups)

        # I'm calling the top header hgroup1, the lower one hgroup0.  So in the future, we could simply accept an array of names, or call them name, name1, etc.
        hgroups1=None if not any(colgroups) else findAdjacentRepeats(colgroups,colformats)
        hgroups0=findAdjacentRepeats(colheads,colformats)
        rotateNames= not any(colgroups) and not any([hh[1]>1 for hh in hgroups0])
        if rotateNames:
             headersLine='\\cpbltoprule\n'+ '\t&'.join(['']+[r'\begin{sideways}\sltcheadername{%s}\end{sideways}'%substitutedNames(model.get('texModelName',model.get('name','')),substitutions) for model in models])+'\\\\ \n'
             # IF there are numbers, too, then show them as a second row!
             if any(['modelNum' in model or 'texModelNum' in model for model in models]):
                headersLine+='\t&'.join(['']+[r'\begin{sideways}\sltcheadername{%s}\end{sideways}'%(model.get('texModelNum','(%d)'%(model.get('modelNum',0)))) for model in models])+'\\\\ \\hline \n'
             return(r'\ctSubsequentHeaders \hline ',headersLine)                

        headersLine='\\cpbltoprule\n'
        if any(colgroups):
            headersLine+= '\t&'.join(['']+[r'\multicolumn{%d}{%s}{\sltcheadername{%s}}'%(hh[1],hh[2],hh[0]) for hh in hgroups1])+'\\\\ \n'
        headersLine+= '\t&'.join(['']+[r'\multicolumn{%d}{%s}{\sltcheadername{%s}}'%(hh[1],hh[2],hh[0]) for hh in hgroups0])+'\\\\ \n'
        # IF there are numbers, too, then show them as a second row
        if any(colnums):#['modelNum' in model or 'texModeulNum' in model for model in models]):
            headersLine+='\t&'.join(['']+[r'\sltcheadername{%s}'%nns for nns in colnums])+'\\\\ \n'
        return(r'\ctSubsequentHeaders \hline ',headersLine)
        #            for ih,hh in enumerate(colheads):
        #               if ih>0 and hh==hgroups[-1][0]:
        #                    hgroups[-1][1]+=1
        #                    hgroups[-1][2]='c'+'|'*(colformats[ih].endswith('|'))# Multicolumn headings should all be centered.
        #               else:
        #                    hgroups+=[[hh,1,colformats[ih]]]
        #
        #            if any([hh[1]>1 for hh in hgroups]):
        #                """ Do not rotate any numbers or headings. Use multicolumn: since there are repeated headers."""
        #                headersLine='\\cpbltoprule\n'+ '\t&'.join(['']+[r'\multicolumn{%d}{%s}{\sltcheadername{%s}}'%(hh[1],hh[2],hh[0]) for hh in hgroups])+'\\\\ \n'
        #                # IF there are numbers, too, then show them as a second row
        #                if any(colnums):#['modelNum' in model or 'texModeulNum' in model for model in models]):
        #                    headersLine+='\t&'.join(['']+[r'\sltcheadername{%s}'%nns for nns in colnums])+'\\\\ \n'
        #            else:
        #                 headersLine='\\cpbltoprule\n'+ '\t&'.join(['']+[r'\begin{sideways}\sltcheadername{%s}\end{sideways}'%substitutedNames(model.get('texModelName',model.get('name','')),substitutions) for model in models])+'\\\\ \n'
        #                 # IF there are numbers, too, then show them as a second row!
        #                 if any(['modelNum' in model or 'texModelNum' in model for model in models]):
        #                    headersLine+='\t&'.join(['']+[r'\begin{sideways}\sltcheadername{%s}\end{sideways}'%(model.get('texModelNum','(%d)'%(model.get('modelNum',0)))) for model in models])+'\\\\ \\hline \n'
        #
        #return(r'\ctSubsequentHeaders \hline ',headersLine)
        # So we have colgroups AND colheads defined


    if 0: # March 2015: I think the following lines are all obseleted by the smartColumnHeader call:
        headersLine='\t&'.join(['']+ [r'\begin{sideways}\sltcheadername{%s}\end{sideways}'%substitutedNames(model.get('texModelName',model.get('name','')),substitutions) for model in models])+'\\\\ \n'
        # IF there are numbers, too, then show them as a second row
        if any(['modelNum' in model or 'texModelNum' in model for model in models]):
            headersLine+='\t&'.join(['']+[r'\begin{sideways}\sltcheadername{%s}\end{sideways}'%(model.get('texModelNum','(%d)'%(model.get('modelNum',0)))) for model in models])+'\\\\ \n'
        headersLine1=headersLine+r'\hline'+'\\hline\n'#r'\cline{1-\ctNtabCols}'+'\n'
        headersLine2=headersLine+r'\hline'+'\n'
    headersLine1,headersLine2=smartColumnHeader([substitutedNames(model.get('modelGroupName',''),substitutions) for model in models],
                                                [substitutedNames(model.get('texModelName',model.get('name','')),substitutions) for model in models],
                                                [model.get('texModelNum','(%d)'%(model.get('modelNum',0))) for model in models],
                                                colformats=[mm['format'] for mm in models])
    varsAsRowsElements= deepcopy(cpblTableElements(body=body,cformat=formats,firstPageHeader=headersLine1,otherPageHeader=headersLine2,tableTitle=tableFormat.get('title',None),caption=tableFormat.get('caption',None),label=tableLabel, ncols=ntexcols,nrows=ntexrows,footer=colourLegend()+' '+tableFormat.get('comments',None),tableName=tableFormat.get('title',None),landscape=landscape))

    # $$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
    # Second, do preparaation as though models as rows:
    # $$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
    #modelsAsRows:
    """
        Main loop over models, adding appropriately to output array of LaTeX entries.
        Add a row or paired row
        """
    body=''
    # Decide whether to show just model numbers for rows, or model numbers and names:
    for model in models:
        model['tmpTableRowName']=model.get('texModelName', substitutedNames(str(model.get('name','')),substitutions))
    if all([model['tmpTableRowName']==models[0]['tmpTableRowName'] for model in models]):
        # IF all the row(model) names are the same, let's not show them. Rather, just put a comment in the comments.
        for model in models:
            model['tmpTableRowName']=''
        tableFormat['comments']=tableFormat.get('comments','')+' N.B.: All models/rows were named %s. '%(models[0].get('texModelName',''))
        multirowLabels=False

    # Decide whether to separate models by showing their group names as mostly-blank rows:
    mgns=[mm.get('modelGroupName','') for mm in models] # unused???
    latestModelGroupName = ''

    # Loop over models, creating a pair of rows for each (coefficients and standard errors)
    for model in models:
        assert 'estcoefs' in model or 'separator' in model # means not yet programmed
        if 'flags' in model: # flags must have been turned into a dict or a list of pairs
            assert 'textralines' in model
            # Above replaces lines below, since now the reformatting of flags has been done in textralines:
            #model['flags']=dict(model['flags'])
        if 'estcoefs' in model: # This is an estimate, not a mean, not a spacer
            mgn=model.get('modelGroupName','' if latestModelGroupName == '' else '------------')
            if not latestModelGroupName == mgn:
                latestModelGroupName = mgn
                body+= r'\multicolumn{2}{l}{' +  substitutedNames(mgn,substitutions)+ ':}'+   '\t& '.join(['' for vv in coefVars+statsVars])+' \\\\ \n'
            if model.get('special','') in ['suestTests']:
                displayEst='p' # For OLS etc
                displayErr='nothing!'
                estValues=[r'\sltheadernum{'+model.get('texModelNum','(%d)'%(model.get('modelNum',0)))+'}',
                                      r'\sltrheadername{'+ model['tmpTableRowName']+'}']+[dgetget(model,'estcoefs',vv,displayEst,fNaN) for vv in coefVars]+[dgetget(model,'textralines',vv,fNaN) for vv in flagsVars]+[formatEstStat(model,vv) for vv in statsVars]
                errValues=['','']+[dgetget(model,'estcoefs',vv,displayErr,fNaN) for vv in coefVars]+['' for vv in flagsVars]+['' for vv in statsVars]
                pValues=['','']+[dgetget(model,'estcoefs',vv,'p',fNaN) for vv in coefVars]+['' for vv in flagsVars]+['' for vv in statsVars]

                tworows=formatPairedRow([estValues,errValues],
                                        greycells='tableshading' in model and model['tableshading'] in ['grey'],
                                        pValues=pValues)

            else:
                displayEst='b' # For OLS etc
                displayErr='se'

                tworows=formatPairedRow([
                    [r'\sltheadernum{'+model.get('texModelNum','(%d)'%(model.get('modelNum',0)))+'}',
                                      r'\sltrheadername{'+ model['tmpTableRowName']+'}']+[dgetget(model,'estcoefs',vv,displayEst,fNaN) for vv in coefVars]+[dgetget(model,'textralines',vv,fNaN) for vv in flagsVars]+[formatEstStat(model,vv) for vv in statsVars],
            ['','']+[dgetget(model,'estcoefs',vv,displayErr,fNaN) for vv in coefVars]+['' for vv in flagsVars]+['' for vv in statsVars]
                    ],greycells='tableshading' in model and model['tableshading'] in ['grey'])#,modelsAsRows=True)

            #multiRow=r'\multirow{2}{*}{\hspace{0}'
            #multiRowEnd='}'


            #print [[multiRow,r'\sltheadernum{',model.get('texModelNum','(%d)'%(model.get('modelNum',0))),'}',multiRowEnd,multiRow, model.get('texModelName',str(model.get('name',''))),multiRowEnd],[dgetget(model,'estcoefs',vv,displayEst,fNaN) for vv in coefVars],[dgetget(model,'textralines',vv,fNaN) for vv in flagsVars],[formatEstStat(model,vv) for vv in statsVars],  ['',''],[dgetget(model,'estcoefs',vv,displayErr,fNaN) for vv in coefVars],['' for vv in flagsVars],['' for vv in statsVars]]
            # BIG BUG IS HERE/BELOW. UNFIXED OCT 2009.

            #tworows=tworows[0:(2-int(suppressSE))]  # Include standard errors?
            if 'special' in model:#any(['special' in mm for mm in models]):
                pass

                #for icol in enumerate(tworows[0]):
                #    tworows[0][icol]=r'\rowcolor{caggNormal} '+ tworows[0][icol].replace(r'\aggc','')
                #    tworows[1][icol]=r'\rowcolor{caggNormal} '+ tworows[1][icol].replace(r'\aggc','')

            if r'\aggc' in tworows[0][0]:
                # APRIL 2010 KLUUUUUUUUUUDGE to get colortbl working with multirow: switch partly to rowcolor! models as cols not done yet...
                # Use awful kludge so as not to lose the text of second line...  Can just do this for all rows, even not shaded??
                assert 'sltrheadername' in tworows[0][1]
                tworows[1][1]=tworows[0][1].replace('sltrheadername','sltrbheadername')
                tworows[0][1]=''


                body+= r'\rowcolor{caggNormal} ' +   ('\t& '.join([cc for cc in tworows[0]])).replace(r'\aggc','')+'\\\\ \n'+  r'\rowcolor{caggNormal} '  + r'\showSEs{'+\
                    '\t& '.join([cc for cc in tworows[1]]) +' \\\\ }{}\n'
            else:
                body+= ('\t& '.join([cc for cc in tworows[0]]))+'\\\\ \n'+   r'\showSEs{'+\
                    '\t& '.join([cc for cc in tworows[1]]) +' \\\\ }{}\n'

            if model['format'].endswith('|'):
                body+='\\bottomrule\n' # or should it be: (r'\cline{1-\ctNtabCols}'+' \n')
        else:
            assert 0

    ntexrows,ntexcols= 1+(1+int(suppressSE))*len(models),   2+len(coefVars+statsVars+flagsVars)

    formats='lc*{%d}{r}'%(ntexcols-2) # or: 'l'+'c'*nvars
    if multirowLabels:
        formats='lp{3cm}*{%d}{r}'%(ntexcols-2) # or: 'l'+'c'*nvars

    ###assert not '&' in [cellsvmmodel[0] for cellsvmmodel in cellsvm] # This would be a mistake in regTable caller?
    # Unlike for non-transposed, we aren't using smartHeaders function here...
    headersLine='\t&'.join(['','']+[r'\begin{sideways}\sltcheadername{%s}\end{sideways}'%substitutedNames(vv,substitutions) for vv in coefVars+flagsVars+statsVars])+'\\\\ \n'####cellsvmmodel[0] for cellsvmmodel in cellsvm])+'\\\\ \n'+r'\hline'#\cline{1-\ctNtabCols}'
    headersLine1='\\cpbltoprule \n'+headersLine+'\\hline\n'#r'\cline{1-\ctNtabCols}'+'\n'
    headersLine2='\\hline \n '+headersLine+r'\hline'+'\n'


    modelsAsRowsElements=deepcopy(cpblTableElements(body=body,cformat=formats,firstPageHeader=headersLine1,otherPageHeader=headersLine2,tableTitle=tableFormat.get('title',None),caption=tableFormat.get('caption',None),label=tableLabel, ncols=ntexcols,nrows=ntexrows,footer=colourLegend()+' '+tableFormat.get('comments',None),tableName=tableFormat.get('title',None),landscape=landscape))




    # Now, let's always put the non-transposed as the default orientation inthe .tex file
    #includeTeX,callerTeX=cpblTableStyC(cpblTableElements(body=body,cformat=formats,firstPageHeader=headersLine1,otherPageHeader=headersLine2,tableTitle=tableFormat.get('title',None),caption=tableFormat.get('caption',None),label=tableLabel, ncols=ntexcols,nrows=ntexrows,footer=colourLegend()+' '+tableFormat.get('comments',None),tableName=tableFormat.get('title',None),landscape=landscape))
    includeTeX,callerTeX=cpblTableStyC(tableElements=varsAsRowsElements,tableElementsTrans=modelsAsRowsElements,showTransposed=transposed)
    if multirowLabels:
        callerTeX=r"""\renewcommand{\sltrheadername}[1]{\multirow{2}{3cm}{\hspace{0pt}#1\vfill}}
\renewcommand{\sltrbheadername}[1]{\multirow{-2}{3cm}{\hspace{0pt}#1\vfill}}
"""+callerTeX

    return(includeTeX,callerTeX,transposed)


###########################################################################################
###
def composeTSVregressionTable(models,tableFormat=None,greycols=None,suppressSE=False,substitutions=None,modelTeXformat=None,transposed=None,tableTitle=None,caption=None,comments=None,landscape=None,rowModelNames=None,hideRows=None):
    ###
    #######################################################################################
    """ Sep 2009: This will just use the old function, older_composeSpreadsheetRegressionTable, since I've no time to rewrite just now....? So create what's needed to call it.

    Note: this kludge gets by, but various things have changed so the result is not perfect. Still, hopefully good enough for sending people spreadsheet results. [Sept 2009] [Improved a bit Dec 2009!: variables now ordered. decoration can go on coefs.]

Hm... why are variable names already somewhat transformed??...  well, i guess i might need to find a way to fix that so that the non-LaTeX substitutions are used here... or not bother.

    To Do: incorporate / implement /recognize the modelGroupName parameter of model? It's supposed to be super-header (another header above the names)
    """

    modelNames=[mm['name'] for mm in models]
    modelNums=[mm['modelNum'] for mm in models]
    byVar,byStat,byTextraline= modelResultsByVar(models)#,tableFilename=tableFilename)
    coefRows=[]

    if tableFormat==None:
        tableFormat={}

    # Add in reordering (Dc 2009):
    variableOrder=tableFormat.get('variableOrder',None)
    if variableOrder==None:
        variableOrder=defaultVariableOrder
    if isinstance(variableOrder,basestring):
        variableOrder=[vv for vv in variableOrder.split(' ') if vv]
    varOrder=orderListByRule(byVar.keys(),variableOrder)
    statOrder=orderListByRule(byStat.keys(),variableOrder)
    ###cellsbeta=orderListByRule(cellsbeta,variableOrder,listKeys=[cb[0] for cb in cellsbeta])




    for vv in varOrder:
        coefRows+=[[vv]+byVar[vv]['coefs']]
        coefRows+=[['']+byVar[vv]['ses']]

    older_composeSpreadsheetRegressionTable(modelNames,modelNums,coefRows,[[vv]+byStat[vv] for vv in statOrder],substitutions=substitutions,tableTitle=tableTitle,caption=caption,comments=comments,rowModelNames=rowModelNames,tableFormat=tableFormat)


###########################################################################################
###
def latexFormatEstimateWithPvalue(x,pval=None,allowZeroSE=None,tstat=False,gray=False,convertStrings=True,threeSigDigs=None):
    ### Why is this in pystata.py? Becuase it needs significanceTable.
    #######################################################################################
    """
    This is supposed to encapsulate the colour/etc formatting for a single value and, optionally, its standard error or t-stat or etc. (take it out of formatpairedrow?)

    It'll do the chooseSformat as well.

    May 2011.
    Still needs to learn about tratios and calculate own p...! if tstat==True
    """
    yesGrey=gray
    if isinstance(x,list):
        assert len(x)==2
        est,ses= x # Primary estimate, and secondary t-stat/se/p-value
        singlet=False
    else:
        singlet=True
        est=x###chooseSFormat(x,convertStrings=convertStrings,threeSigDigs=threeSigDigs)

    assert isinstance(pval,float) or pval in [] # For now, require p to be passed!

    if 0 and ses<1e-10 and not allowZeroSE:
        pair[0]=''
        pair[1]='' # Added Aug 2009... is not this right? It covers the (0,0) case.
    if pval not in [None,fNaN]: # This is if we specified p-values directly: then don't calculate it from t-stat, etc!
        significanceString=(['']+[tt[0] for tt in significanceTable if pval<= tt[2]*1.0/100.0])[-1]

    if significanceString and yesGrey:
            significanceString=r'\agg'+significanceString[1:]
    if not significanceString and yesGrey:
            significanceString=r'\aggc{'
    if yesGrey:
        greyString=r'\aggc'
    if singlet:
        return(significanceString+chooseSFormat(est,convertStrings=convertStrings,threeSigDigs=threeSigDigs)+'}'*(not not significanceString))
    # By default, I don't think we want the standard errors/etc to contain the colour/significance formatting.
    if 0:
        return([significanceString+chooseSFormat(est,convertStrings=convertStrings,threeSigDigs=threeSigDigs)+'}'*(not not significanceString),
           significanceString+chooseSFormat(ses,convertStrings=convertStrings,threeSigDigs=threeSigDigs,conditionalWrapper=[r'\coefp{','}'+'}'*(not not significanceString),])])
    else:
        return([significanceString+chooseSFormat(est,convertStrings=convertStrings,threeSigDigs=threeSigDigs)+'}'*(not not significanceString),
           chooseSFormat(ses,convertStrings=convertStrings,threeSigDigs=threeSigDigs,conditionalWrapper=[r'\coefp{','}',])])


def formatPairedRow_DataFrame(df, est_col, se_col, prefix=None ):
    """
    The name of this function is not great, but it simply applies formatPairedRow to two columns in a dataframe, returning the df with two new formatted string columns. The formatting is for use in cpblTables.

2017: What about a tool to take every other column and stick them as alternate rows? See interleave_columns_as_rows in cpblutils

    """
    #assert df[est_col].notnull().all()
    #assert df[est_col].notnull().all()
    #a,b = formatPairedRow([df[est_col].fillna('.').values.tolist(), df[se_col].fillna('.').values.tolist()])
    a,b = formatPairedRow([df[est_col].values.tolist(), df[se_col].values.tolist()])
    if prefix is None: prefix ='s'
    assert prefix+est_col not in df
    assert prefix+se_col not in df
    df[prefix+est_col] = a
    df[prefix+se_col] = b
    return(df)


###########################################################################################
###
def formatPairedRow(pair,pValues=None,greycells=None,modelsAsRows=None,varsAsRows=None,allowZeroSE=False):
    ###
    #######################################################################################

    """ August 2009.

    Takes a pair of entries. First in each row of pair is a label; typicall that in the second row (label for s.e.'s) is blank. Returns pair of lists of LaTeX strings.


Takes care of significance marking; grey shading, and formatting row/column headers. (maybe.. not implemented yet.  For the latter, it would need to know whether rows or cols..)

pairedRows were conventionally one model? one variable?

greycells: can list column numbers? can be True ie for all in this model.

needs to be in charge of making row/model header grey too, if greycells==True  [done!]

    Dec 2009: allowZeroSE: set this to true when the values passed are sums, etc, which may be exact (is SE=standard error  is 0).


? April 2010. Trying to get multirow to work with colortbl.  Why was I not using rowcolor{} ?? Try to implement that now/here... hm.. no, kludging it in the calling function for now?


May 2011: can now also send an array of pvalues. This avoids calculating p categories from t-stats. Also, there may not be t-stats, as in the case of suestTests: ie test results.

May 2011: I'm trying to remove some of the logic from here to a utility, latexFormatEstimateWithPvalue(x,pval=None,allowZeroSE=None,tstat=False,gray=False,convertStrings=True,threeSigDigs=None)
    """

    from pylab import isnan
    if not greycells:
        greycells=[]
    if greycells==True:
        greycells=range(len(pair[0]))

    outpair=deepcopy(pair)
    coefs=pair[0]
    ses=pair[1]
    def isitnegative(obj):
        if not isinstance(obj,float): return False
        return obj<0
    assert not any([isitnegative(ss) for ss in ses])
    
    # If it's not regression coefficients, we may want to specify the p-values (and thus stars/colours) directly, rather than calculating t values here (!!). Indeed, aren't p-values usually available, in which case they should be used anyway? hmm.
    if pValues is None:
       pValues=[None for xx in coefs]
    assert len(pValues)==len(coefs)

    # Is following redundant?!
    significanceString,greyString=[[] for i in range(len(pair[0]))],   [[] for i in range(len(pair[0]))]
    for i in range(len(pair[0])):
        significanceString[i], greyString[i]='',''
    for icol in range(len(pair[0])):
        yesGrey=icol in greycells or greycells==True
        if isinstance(coefs[icol],basestring) or isinstance(coefs[icol],unicode) or isnan(coefs[icol]):
            if coefs[icol] in ['nan',fNaN] or (isinstance(coefs[icol],float) and isnan(coefs[icol])):
                outpair[0][icol],outpair[1][icol]=r'\aggc'*yesGrey,r'\aggc'*yesGrey
            else:
                outpair[0][icol],outpair[1][icol] = coefs[icol]+r'\aggc'*yesGrey,ses[icol]+r'\aggc'*yesGrey
            continue
        # So we have floats
        # Aug 2012: Agh.. It's in principle possible to have an int, with 1e-16 s.e., etc.
        assert isinstance(outpair[0][icol],float) or isinstance(outpair[0][icol],int)
        assert isinstance(outpair[1][icol],float) or isinstance(outpair[0][icol],int)

        # Safety: so far this is only because of line "test 0= sumofincomecoefficients": when that fails, right now a value is anyway written to the output file (Aug 2008); this needs fixing. In the mean time, junk coefs with zero tolerance:
        if ses[icol]<1e-10 and not allowZeroSE: #==0 or : # Added sept 2008...
            pair[0][icol]=''
            pair[1][icol]='' # Added Aug 2009... is not this right? It covers the (0,0) case.
        if isinstance(coefs[icol],float) and not str(coefs[icol])=='nan':# and not ses[icol]==0:
            tratio=abs(coefs[icol]/ses[icol])
            # Ahh. May 2010: why is there a space below, rather than a nothing? Changning it.
            #significanceString[icol]=([' ']+[tt[0] for tt in significanceTable if tratio>= tt[1]])[-1]
            significanceString[icol]=(['']+[tt[0] for tt in significanceTable if tratio>= tt[1]])[-1]

        if pValues[icol] not in [None,fNaN]: # This is if we specified p-values directly: then don't calculate it from t-stat, etc!
            significanceString[icol]=(['']+[tt[0] for tt in significanceTable if pValues[icol]<= tt[2]*1.0/100.0])[-1]

        if significanceString[icol] and yesGrey:
                significanceString[icol]=r'\agg'+significanceString[icol][1:]
        if not significanceString[icol] and yesGrey:
                significanceString[icol]=r'\aggc{'
        if yesGrey:
            greyString[icol]=r'\aggc'

        # Changing line below: May 2011. Why did I put a ' ']
        #outpair[0][icol]= significanceString[icol]+chooseSFormat(coefs[icol])+'}'*(not not significanceString[icol])

        outpair[0][icol]= significanceString[icol]+chooseSFormat(coefs[icol])+'}'*(not not significanceString[icol])
        #debugprint( 'out0=',        outpair[0][icol],
        #'   signStr=',(not not significanceString[icol]),significanceString[icol],
        #'   tratio=',tratio,coefs[icol],ses[icol])

        # This catches a 2017 bug:
        ###NO!assert all([isitnull(outpair[0][ii]) == isitnull(coefs[ii])  for ii in range(len(outpair[0]))])

        if ses[icol]<1e-10 and allowZeroSE: # Added Dec 2009
            ses[icol]=0


        outpair[1][icol]=chooseSFormat(ses[icol],conditionalWrapper=[r'\coefse{','}'])  +  greyString[icol]
        # Shoot. May 2011, following line suddently started failing (regressionsQuebec.py: nested models). Can't fiure it out. I'm disabling this for the moment!! I guess try some asserts instead.
        # Okay, I fixed it by rephrasing using "in": [may 2011]
        # May 2011: Following FAILS to detect nan's. need to use isinstnace float and isnan as another option. Also, this should not be triggered for suestTests.
        if ses[icol] in ['',float('nan')] and not coefs[icol] in ['',float('nan')]: #isnan(ses[icol]) and not isnan(coefs[icol]):
            outpair[0][icol]= chooseSFormat(coefs[icol])
            outpair[1][icol]='?'
            print ' CAUTION!! VERY STRANGE CASE OF nan FOR s.e. WHILE FLOAT FOR COEF '
            assert 0
    return(outpair)


def texheader(margins='default',startDocument=True, allow_underscore=True):
    if margins==None:
        mmm=r'\usepackage[left=0cm,top=0cm,right=.5cm,nohead,nofoot]{geometry}\n'
    else:
        mmm=''
    settings=r"""
%% This file created automatically by CPBL's latexRegressionFile class
\usepackage{amsfonts} % Some substitions use mathbb
\usepackage[utf8]{inputenc}
\usepackage{lscape}
\usepackage{rotating}
\usepackage{relsize}
\usepackage{colortbl} %% handy for colored cells in tables, etc.
\usepackage{xcolor} %% For general, v powerful color handling: e.g simple coloured text.
%%\usepackage[svgnames]{xcolor} %% svgnames clashes with Beamer?
\usepackage{geometry}
\usepackage{siunitx}
\usepackage[colorlinks]{hyperref}
"""+r'\usepackage{underscore}'*allow_underscore+r"""

% If multirow is invoked, row labels will span the variable and its standard error.
\usepackage{multirow}
%\newcommand{\rowLabelWidth}{2cm}
%\newlength{\rowLabelWidth}
%\setlength{\rowLabelWidth}{2cm}

%% Make a series of capsules to format tables different ways:

\usepackage{cpblTables} % If you do not have this, just google for cpblTables.sty...
%\usepackage{cpblRef}
% Below I will uglyly stick varioius things from cpblRef or etc so that if that package is not included, they will at least be defined:
\ifdefined\cpblFigureTC
\else
% The "TC" in this command means there are two caption titles: one for TOC, one for figure.
\newcommand{\cpblFigureTC}[6]{%{\begin{figure}\centerline{\includegraphics{#1.eps}}
% Arguments: 1=filepath, 2=height or width declaration, 3=caption for TOC, 4=caption title, 5=caption details, 6=figlabel
\begin{figure}
  \begin{center}
    \includegraphics[#2]{#1}\caption[#3]{{\bf #4.} #5\label{fig:#6}\draftComment{\\{\bf label:} #6 {\bf file:} #1}}
  \end{center}
\end{figure}
}
\fi

\usepackage{xspace}
\ifdefined\draftComment
\else
\newcommand{\draftComment}[1]{{ \footnotesize\em\color{green} #1}\xspace}
\fi

%%  \useColourBoldForSignificance

\renewcommand{\ctDraftComment}[1]{{\sc\scriptsize ${\rm #1}$}} % Show draft-mode comments
\renewcommand{\ctDraftComment}[1]{{\sc\scriptsize #1}} % Show draft-mode comments

"""+r"""\newcommand{\texdocs}{%s}
"""%defaults['paths']['tex']

    return(startDocument*r"""    \documentclass{article}
        """+settings+startDocument*r"""
        \geometry{verbose,letterpaper,tmargin=1cm,bmargin=1cm,lmargin=1cm,rmargin=1cm}
        %

\usepackage{chngcntr} %This is for counterwithin command, below. amsmath and numberwithin would be an alternative.
        \begin{document}
        \title{Regression results preview}\author{CPBL}\maketitle
%TOC:\tableofcontents
%LOT:\listoftables
%LOF:\listoffigures
\counterwithin{table}{section}
\counterwithin{figure}{section}
% Following would require amsmath, instead of chngcntr:
%\numberwithin{figure}{section}
%\numberwithin{table}{section}
        \pagestyle{empty}%%\newpage
        \begin{landscape}
    """)




def transposeLaTeXtableCells(rows):
    """
Dec 2009:  This takes a list of lists each of which contain cell info, and they can include '\\' and '\hline's and tries to transpose the whole thing!
Very crude at first, for testing.
To do:
- hline to |
- fill in missing/short rows?
- accept strings with '&' as alternative to cells.
- modify this to be able to transpose an entire LaTeX table body as a single string!
"""
    from pylab import array
    transRows=array(deepcopy(rows)).transpose()
    replaceStrings=[
        [r'\begin{sideways}',''],
        [r'\end{sideways}',''],
        [r'\hline',''],
        [r'\\',''],
        ]
    for rr in transRows:
        for icc in range(len(rr)):
            for srepl in replaceStrings:
                rr[icc]=rr[icc].replace(srepl[0],srepl[1])
        rr[-1]+=r'\\' # Add newline to end of row.
    colFormats='c'*len(transRows[0])
    return(transRows,colFormats)

def subSampleAccounting(LL,mods,argss): # Need to wrap this member function up in ordre to have it available to pass as a followupFcn. Cannot pass a member function!
    return(LL.subSampleAccounting(mods,argss))



# This should go in  pystata?? Maybe in regtable class. This is used by functions that are defined to make a particular plot. These functions are typically passed as pointers into regtable for plotting and inclusion in pdf output, etc.
def _oldmode_plotPairedRow(ax,pairedRows,x=None,xerr=None,coef=None,imodels=None,models=None,label=None,color=None):
    """
    So far, not Stata-specific.

    If x is not specified, ie numeric values aren't given, then the names of each regression from models will be used instead.

    AUG 2009: NEEDS TO BE REWRITTEN SO IT DOESN'T USE PAIRED ROWS! BUT INSTEAD USES BYVAR, ETC
    """

    # Kludge for backwards-compatibility: LATER!! CAN CHANGE PAIREDROWS TO MODELS LATER EVERYWHERE
    if isinstance(pairedRows,list):
        pairedRows=_modelsToPairedRows(models)#
    if all([isinstance(ppp,basestring) for ppp in pairedRows[0][1:]]):
        assert 0
        print "FOUND OLD-FORMAT PAIRED ROW... SHOULD UPDATE THIS TO NEW BYVAR, ETC"
        pairedRows=tonumeric(pairedRows)

    if len(imodels)==2:
        imodels=range(imodels[0],imodels[1])

    useXlabels=False
    if x==None:
        x=imodels
        useXlabels=True

    pp=[ppp for ppp in pairedRows if ppp[0][0].replace('_','-')==coef.replace('_','-')]

    if not pp:
        debugprint('Could not find %s in pairedRows!!! Skipping this coefficient in plotPairedRow'%coef)
        return()
    assert len(pp)==1
    pp=pp[0]

    y=[[yyy for yyy in pp[0][1:]][im] for im in imodels]
    dy=[[2*yyy for yyy in pp[1][1:]][im] for im in imodels]

    if useXlabels:
        ax.set_xticks(imodels)
        ax.set_xticklabels([models[im]['name'] for im in imodels]) # ##.replace('$','')
        xlabels = pylab.gca().get_xticklabels()
        pylab.setp(xlabels, 'rotation', 90)


    prh=ax.errorbar(x,y,xerr=xerr,yerr=dy,label=label)
    if color:
        pylab.setp(prh,'color',color)
    return(pp,y,dy,prh)


# This should go in  pystata?? Maybe in regtable class. This is used by functions that are defined to make a particular plot. These functions are typically passed as pointers into regtable for plotting and inclusion in pdf output, etc.
def plotPairedRow(ax,models,x=None,xerr=None,coef=None,imodels=None,label=None,color=None):
    """
    So far, not Stata-specific.

    If x is not specified, ie numeric values aren't given, then the names of each regression from models will be used instead.


ax: an axis to plot on

models: a list of model dicts (of type sent to regTable())

imodels: list of indices to models to use. Optional. It can be a range, ie start and end  indices, rather than a list.

coef: the name of the coefficient to find and plot. Is this mandatory, then??

xerr:

label:

color:

    """
    import pylab

    if not imodels:
        imodels=range(len(models))
    if len(imodels)==2:
        imodels=range(imodels[0],imodels[1])


    assert coef #debugprint('Could not find %s in pairedRows!!! Skipping this coefficient in plotPairedRow'%coef) return()
    assert isinstance(coef,basestring)

    byVar,byStat,byTextraline= modelResultsByVar(models)

    if not coef in byVar:
        print ' plotPairedRow: %s not found in this model! --- Skipping this plot'%coef
        ax.plot([0],[0])
        return(None)

    if imodels==None:
        imodels=range(len(byVar[coef]['coefs']))

    y=pylab.array(byVar[coef]['coefs'])[imodels]
    dy=2*pylab.array(byVar[coef]['ses'])[imodels]


    useXlabels=False
    if x==None:
        x=imodels
        useXlabels=True

    if useXlabels:
        ax.set_xticks(imodels)
        assert all(['name' in mmm for mmm in models]) # Doesn't yet deal with separators etc in models?
        ax.set_xticklabels([models[im]['name'] for im in imodels]) # ##.replace('$','')
        xlabels = pylab.gca().get_xticklabels()
        pylab.setp(xlabels, 'rotation', 90)


    prh=ax.errorbar(x,y,xerr=xerr,yerr=dy,label=label)
    if color:
        pylab.setp(prh,'color',color)
    return(y,dy,prh) # pp used to be first return value.



def basicCoefPlot(latex,models,followupArgs):
    """
    This is a simple followupFcn which just
    can be used for simple cases of plot one line of all models...

    """
    import pylab
    global figureNumber


    varstp=models[0]['estcoefs'].keys()
    figureNumber+=1
    fign=figureNumber
    fig = pylab.figure(fign)
    fig.clear()
    ax = fig.add_subplot(111)
    #x,xerr=[pylab.mean(xx[2]) for xx in dCats],[(max(xx[2])-min(xx[2]))/2 for xx in dCats]
    x=None # This turns on the xticklabelling in place of x values!
    xerr=None

    for vv in varstp:
        h1=plotPairedRow(ax,models,imodels=range(len(models)),coef=vv)#,x=x,xerr=xerr,coef=coefName,imodels=range(len(models)))

    ax.plot(ax.get_xlim(),[0,0],'k--')

    return(fign)


# This should really be in the latex class, sort of, but this way it can be called without knowledge of an object....
# Is this used? yes, I suspect so...
def plotKernelRegression(pairedRows,models,cVars=None,title=None):
    """ Kernel regression, eh.. okay, but I also have a quantile regression function now!"""
    import pylab
    pylab.figure(3)
    pylab.hold(False)
    legendVars=[]
    legendLines=[]
    cVars=[v for v in cVars if cVars]
    for covari in [pr for pr in pairedRows if '*' not in pr[0][0] and  '(' not in pr[0][0] and (cVars==None or pr[0][0] in cVars)]:
        # This says: for every model in the output file which has a non-blank estimate for this variable, record the estimate, its standard error, and the x value and width of the box defining this bin/group. The latter two numbers come from the model "name".
        ydyxdx=[[float(covari[0][1:][iy]), float(covari[1][1:][iy].strip('()')), float(models[iy]['name'].split('=')[1].split(r'\pm')[0].replace('$','')), float(models[iy]['name'].split('$')[-1]) ] for iy in range(len(covari[0][1:])) if covari[0][1:][iy]]
        legendLine,=    pylab.plot([z[2] for z in ydyxdx],[z[0] for z in ydyxdx])
        legendLines+=[legendLine]
        pylab.hold(True)
        pylab.plot([z[2] for z in ydyxdx],[z[0]+2*z[1] for z in ydyxdx],legendLine.get_color()+':')
        pylab.plot([z[2] for z in ydyxdx],[z[0]-2*z[1] for z in ydyxdx],legendLine.get_color()+':')
        legendVars+=[covari[0][0]]

    pylab.xlabel(models[0]['kernel']['kernelVar']),
    pylab.xlabel('%s [bin width: %s]'%(models[0]['kernel']['kernelVar'],chooseSFormat(ydyxdx[0][3]*2)))
    leg=pylab.legend(legendLines,legendVars,shadow=False)
    if leg:
        leg.get_frame().set_alpha(0.5)

    pylab.title(title)
    return(3)



def colourLegend():
    useColours=1
    if useColours:
        outs=r'\footnotesize \cpblColourLegend '
        # This has now been moved to a definition in the preamble. In fact, that has now moved to cpblTables.sty...

        #outs='Significance: \n\\begin{tabular}{' + 'c'*len(significanceLevels) +'}\n' +  ' & '.join([str(ss[2])+'\%'+ss[0] for ss in significanceTable[1:][::-1]]) +r' \end{tabular}'+'\n' # \\
        #        ' & '.join([str(100-significanceLevels[isL])+r'\%\signif'+['One','Two','Three','Four'][isL] for isL in range(len(significanceLevels))[::-1]]) +'\\\\ \\end{tabular}\n\n'
        return(outs)


#def signifDefinitions():

def stripdtagz(dfp):
    assert not dfp.endswith('.dta.dta')
    if dfp.endswith('.dta.gz'):
        dfp=os.path.splitext(os.path.splitext(dfp)[0])[0]
    if dfp.endswith('.dta'): # No; all are compress now!
        dfp=os.path.splitext(dfp)[0]
    return(dfp)

################################################################################################
################################################################################################
def modelResultsByVar(modelResults,tableFilename=None):
################################################################################################
################################################################################################
    """
    This is useful for creating table-like organisation of estimation results which are stored in lists of "model" dicts.
    Returned values are numeric and reflect given order of models.

    This assumes that no "nan" values are left in eststats and estcoefs?

    May 2011:

    """
    nullValues2=['.','','0',tonumeric('')]



    # Get list of all
    import operator
    allvarsM=uniqueInOrder(    reduce(operator.add, [mm['estcoefs'].keys() for mm in modelResults], []))
    allstatsM=uniqueInOrder(    reduce(operator.add, [mm['eststats'].keys() for mm in modelResults], []))
    allTextralinesM=uniqueInOrder(    reduce(operator.add, [mm['textralines'].keys() for mm in modelResults if 'textralines' in mm], []))

    #create dict with rows:
    byVar={}
    for vv in allvarsM:
        vvname=vv
        #if vvname.startswith('z_'):
        #    vvname=vvname[2:]
        displayCoef=[['b','p'][int(mmm.get('special','') in ['suestTests'] )] for mmm in modelResults]
        byVar[vvname]={'coefs':[mmm['estcoefs'].get(vv,{}).get(displayCoef[imm],fNaN) for imm,mmm in enumerate(modelResults)],
                       'ses':[mmm['estcoefs'].get(vv,{}).get('se',fNaN) for mmm in modelResults],
                       'p':[mmm['estcoefs'].get(vv,{}).get('p',fNaN) for mmm in modelResults]
    }
    byStat={}
    for vv in allstatsM:
        byStat[vv]=[mmm['eststats'].get(vv,fNaN) for mmm in modelResults]





    """ What if something exists as a stat in one model but as a textraline in a different model? In this case, the textraline should be moved to stats for all models.
    (  This may only be for N_clust)
    """
    for vv in allTextralinesM: # Anything that is a textraline in ANY model
        if vv in byStat: # Anything that is a stat in ANY model
            for mmm in modelResults:
                # First, we should fail if there are conflicts for this model:
                assert not dgetget(mmm,['textralines',vv],'') or not dgetget(mmm,['eststats',vv],'') or dgetget(mmm,['textralines',vv],'') == dgetget(mmm,['eststats',vv],'')
                # Otherwise, let's move this from textralines to stats in this model:
                if dgetget(mmm,['textralines',vv],''):
                    mmm['eststats'][vv]=dgetget(mmm,['textralines',vv],'')
    	    mmm['textralines'][vv]='' # Rather than deleting it, set it to blank? It'll get dropped anyway.
    	    print '    textralines: Moved '+vv+' to stats '
            assert not any([dgetget(mmm,['textralines',vv],'')  for mmm in modelResults])
            # Now, remove this item from the textralines that will be displayed!
            allTextralinesM=[tlm for tlm in allTextralinesM if not tlm==vv]
            # Note that in general I do not clean up empty textralines, except in this case, because they might be specified on purpose to put an empty space in a table? hmm, no: I could use "~" for that.



    # Clean up empty rows (unused regressors):
    kk=byVar.keys()
    droppedNames=[]
    for vv in kk:
        isVal=[btp not in nullValues2 for btp in byVar[vv]['coefs']]
        if not any(isVal):
            del byVar[vv]
            droppedNames+=[vv]
    if droppedNames:
        if tableFilename:
            print " modelResultsByVar: Dropping variables with no table entries from %s!: "%os.path.split(tableFilename)[1],droppedNames



    # Construct the "extra lines", ie the attributes that are not simple regressors:
    # First, get a list of attribute pairs specified for each model; ie parse the various ways they can be listed (done, above)
    byTextraline={}
    for vv in allTextralinesM:
        byTextraline[vv]=[dgetget(mmm,'textralines',vv,'') for mmm in modelResults]


    # Should this be here? Sept 2009. It's other places too, right now..
    # Drop r2 if we have r2_a:
    if 'r2_a' in byStat and all(byStat['r2_a']) and 'r2' in byStat:
        del byStat['r2']
        debugprint('Dropping r2 in favour of r2_a.')

    from pylab import isnan
    assert 'N_clust' not in byStat or byStat['N_clust'][0]>1 or isnan(byStat['N_clust'][0]) #Bug check. ? against what?
#    assert not any([kk in byTextraline for kk in byStat])

    return(byVar,byStat,byTextraline)


################################################################################################
################################################################################################
def _modelsToPairedRows(models,tableFilename=None,variableOrder=None,showOnlyVars=None,hideVars=None):
################################################################################################
################################################################################################
    """
    This makes variable-ordered paired rows.. apparently this is what I used in original regTable code? Can't really remember why. Anyway, pairedRows could be model-ordered instead, I guess.
    """
    byVar,byStat,byTextraline= modelResultsByVar(models,tableFilename=tableFilename)
    pairedRows=[]
    # Order the rows by the way they were in the file originally.
    vars=[vv for vv in byVar.keys() if not hideVars or vv not in hideVars]
    if variableOrder:
        vars=orderListByRule(vars,variableOrder)
    if showOnlyVars: # In which case variableOrder, above, will have no effect:
        vars=[vv for vv in showOnlyVars if vv in vars]#orderListByRule(vars,showOnlyVars) if vv in showOnlyVars]
    for vv in vars:
        pairedRows+=[[[vv]+byVar[vv]['coefs'],  ['']+byVar[vv]['ses']]] # vv..replace('_','-')
    return(pairedRows)



################################################################################################
################################################################################################
def doNLregression(name,eq=None,datafile=None,plotTitle=None,execStata=True,forceUpdate=False,getFileNameOnly=False):#,skipPlots=False,options='',simultaneous=False,substitutions=None):
    ############################################################################################
    ############################################################################################
    """
If eq is specified (equation, if, weights, options), then the explicit equation syntax is used. Otherwise, one could also call a function and list the variables.name=None,
"""
    import numpy as np
    assert name
    name=''.join([ch for ch in name if ch.isalpha() or ch.isdigit() or ch in '-'])

    doText=''
    if datafile:
        doText+=stataLoad(datafile)

    # Make a do file:
    doFile=WP+name+'-'+'NL'
    logFile=doFile
    if getFileNameOnly:
        return(logFile+'.pyshelf')

    assert eq # Others not programmed yet. See header footer flags, below, etc.

    from pylab import arange

    # In following, I've added "log" option to list estimates as we go...
    doText+="""
log using """+logFile+""".log, text replace
* CPBL BEGIN NL EQ REGRESSION MODEL
nl """+eq+' ,'*(',' not in eq)+""" log
estimates table , varwidth(49) style(oneline) b se p stats(r2  r2_a r2_p N  N_clust)
* CPBL END NL EQ REGRESSION MODEL
* CPBL Finished successfully
log close
"""

    if not execStata:
        return(doText)

    # Read the result:
    if not os.path.exists(logFile+'.log'):
        print doFile+' does not exist yet: running Stata...'
        stataSystem(doText, filename=doFile) # Give do file without .do
    elif forceUpdate:
        print doFile+' exists but forceUpdate is true: running Stata...'
        stataSystem(doText, filename=doFile) # Give do file without .do
    if "CPBL Finished successfully" not in open(logFile+'.log','rt').read():
        print doFile+' failed. Trying agiain...'
        stataSystem(doText, filename=doFile) # Give do file without .do

    if fileOlderThan(logFile+'.pyshelf',logFile+'.log'):
        results=parseNLregression(logFile)
        shelfSave(logFile+'.pyshelf',results)
    #else:
    #    results=shelfLoad(logFile+'.pyshelf')
    return(logFile+'.pyshelf')


################################################################################################
################################################################################################
def parseNLregression(logFile):#,plotTitle='%(rhsv)s',name=None,skipPlots=False,substitutions=None):
    ############################################################################################
    ############################################################################################
    """
Jan 2013: I'm not yet integrating this into my latex class because I cannot get the functions syntax to work properly.
So, instead, I'll be running these outside of latexclass for now, and using the explicit equation syntax. 

This parses the output resulting from doNLregression.
    """

    if '\n' in logFile: # logfile text must have been passed.
        logTxt=logFile
    else:
        logTxt=open(logFile+'.log','rt').read() # Should already have >\n's removed by stataSystem...
        print ' Parsing '+logFile+'.log'

    if 0:
        regs=re.findall(r"""\s*.\s+CPBL BEGIN NL EQUATION REGRESSION
    (.*?)
    \s*.\s+CPBL END NL EQUATION REGRESSION""",logTxt,re.DOTALL)
        assert len(nlregs)==1
        nlreg=nlregs[0]

    regs=re.findall(r"""CPBL BEGIN NL EQ REGRESSION MODEL(.*?)CPBL END NL EQ REGRESSION MODEL""",logTxt,re.DOTALL)
    assert len(regs)>0

    results=[]
    vars=[]
    for areg in regs:
        results+= [readStataEstimateResults(areg)]

    return(results)

################################################################################################
################################################################################################
def do_mlogit_notwrittenyet(name,eq=None,datafile=None,plotTitle=None,execStata=True,forceUpdate=False,getFileNameOnly=False):#,skipPlots=False,options='',simultaneous=False,substitutions=None):
    ############################################################################################
    ############################################################################################
    """
If eq is specified (equation, if, weights, options), then the explicit equation syntax is used. Otherwise, one could also call a function and list the variables.name=None,
"""
    import numpy as np
    assert name
    name=''.join([ch for ch in name if ch.isalpha() or ch.isdigit() or ch in '-'])

    doText=''
    if datafile:
        doText+=stataLoad(datafile)

    # Make a do file:
    doFile=WP+name+'-'+'NL'
    logFile=doFile
    if getFileNameOnly:
        return(logFile+'.pyshelf')

    assert eq # Others not programmed yet. See header footer flags, below, etc.

    from pylab import arange

    # In following, I've added "log" option to list estimates as we go...
    doText+="""
log using """+logFile+""".log, text replace
* CPBL BEGIN NL EQ REGRESSION MODEL
nl """+eq+' ,'*(',' not in eq)+""" log
estimates table , varwidth(49) style(oneline) b se p stats(r2  r2_a r2_p N  N_clust)
* CPBL END NL EQ REGRESSION MODEL
* CPBL Finished successfully
log close
"""

    if not execStata:
        return(doText)

    # Read the result:
    if not os.path.exists(logFile+'.log'):
        print doFile+' does not exist yet: running Stata...'
        stataSystem(doText, filename=doFile) # Give do file without .do
    elif forceUpdate:
        print doFile+' exists but forceUpdate is true: running Stata...'
        stataSystem(doText, filename=doFile) # Give do file without .do
    if "CPBL Finished successfully" not in open(logFile+'.log','rt').read():
        print doFile+' failed. Trying agiain...'
        stataSystem(doText, filename=doFile) # Give do file without .do

    if fileOlderThan(logFile+'.pyshelf',logFile+'.log'):
        results=parseNLregression(logFile)
        shelfSave(logFile+'.pyshelf',results)
    #else:
    #    results=shelfLoad(logFile+'.pyshelf')
    return(logFile+'.pyshelf')

################################################################################################
################################################################################################
def parse_mlogit_notwrittenyet(logFile):
    ############################################################################################
    ############################################################################################
    """
Not yet integrated into latex class

This parses the output resulting from do_mlogit.
    """

    if '\n' in logFile: # logfile text must have been passed.
        logTxt=logFile
    else:
        logTxt=open(logFile+'.log','rt').read() # Should already have >\n's removed by stataSystem...
        print ' Parsing '+logFile+'.log'

    if 0:
        regs=re.findall(r"""\s*.\s+CPBL BEGIN NL EQUATION REGRESSION
    (.*?)
    \s*.\s+CPBL END NL EQUATION REGRESSION""",logTxt,re.DOTALL)
        assert len(nlregs)==1
        nlreg=nlregs[0]

    regs=re.findall(r"""CPBL BEGIN NL EQ REGRESSION MODEL(.*?)CPBL END NL EQ REGRESSION MODEL""",logTxt,re.DOTALL)
    assert len(regs)>0

    results=[]
    vars=[]
    for areg in regs:
        results+= [readStataEstimateResults(areg)]

    return(results)

def parseStataComments(txt):
    """
    Look for certain of my format of Stata comments, and extract them:
    """
    extraFields={}
    precode=''
    unparsed=''
    for aline in txt.split('\n'):
        aline=aline.strip()
        if aline.startswith('*name:'): # Syntax to add a flag to next model
            precode+=aline+'\n'
            extraFields['name']=':'.join(aline.split(':')[1:])
        elif aline.startswith('*storeestimates:'): # Syntax to use Stata's "estimates store" after the regression [May 2011]
            precode+=aline+'\n'
            sname=aline.split(':')[1]
            if 'name' in extraFields:
                sname=''.join([cc for cc in extraFields['name'] if cc.isalpha() or cc.isdigit()])
            assert sname
            #assert not dgetget(defaultModel,['code','testsAfter'],'')
            extraFields['testsAfter']="""
            estimates store """+sname+"""
            """
            extraFields['stataStoredName']=sname
        elif aline.startswith('*autoExcludeVars:'): # Syntax to allow a non-missing variable to be missing for all in the sample.
            extraFields['autoExcludeVars']=aline.split(':')[1]
        elif aline.startswith('*meanGroupName:'): # Syntax to allow grouping of estimates for calculating group mean coefficients
            extraFields['meanGroupName']=aline.split(':')[1]
        elif aline.startswith('*flag:'): # Syntax to add a flag to next model
            precode+=aline+'\n'
            aflag=aline[6:]
            extraFields['flags']=extraFields.get('flags',{})
            if '=' in aflag:
                extraFields['flags'][aflag.split('=')[0]]=aflag.split('=')[1]
            else:
                extraFields['flags'][aflag]=1
        elif aline.startswith('*flags:'): # Syntax to add a flag to next model
            # Example with three flags: *flag:CR=foo:thisone=yes:robust
            # This means you cannot have a colon in a flag value. Oh no. I think I should retract that feature. Okay, I'm changing it so that you can use "flags" if you want more than one, but none with a colon.
            for aflag in aline.split(':')[1:]:
                extraFields['flags']=extraFields.get('flags',{})
                if '=' in aflag:
                    extraFields['flags'][aflag.split('=')[0]]=aflag.split('=')[1]
                else:
                    extraFields['flags'][aflag]=1
        elif aline.startswith('*compDiffBy:'): # Syntax to invoke an extra line of compensating differentials
            precode+=aline+'\n'
            assert len(aline.split(':'))==2
            assert ' ' not in aline.split(':')[0]
            extraFields['compDiffBy']=aline.split(':')[1]
        else:
            #debugprint( 'str2models: assuming line starting with "%s" is NOT a regression command!!!'%method)
            #precode+='* str2models: assuming line starting with "%s" is NOT a regression command!!!\n'%method
            unparsed+=aline+'\n'
    if unparsed:
        extraFields['unparsed']=unparsed
    if precode:
        extraFields['precode']=precode
    return(extraFields)
                

def statameans_parse(logFile):
    if '\n' in logFile: # logfile text must have been passed.
        logTxt=logFile
    else:
        logTxt=open(logFile+'.log','rt').read() # Should already have >\n's removed by stataSystem...
        print ' Parsing '+logFile+'.log'
    singles='CPBL BEGIN MEAN SINGLE' in logTxt
    multis='CPBL BEGIN MEAN LIST MULTI' in logTxt
    assert not (singles and multis)
    means=[]
    if singles:
        regs=re.findall(r"""CPBL BEGIN MEAN SINGLE(.*?)CPBL END MEAN SINGLE""",logTxt,re.DOTALL)
        for reg in regs:
            fields= parseStataComments(reg)
            #pieces=re.findall('-------\+-+\n(.*?)\n------',reg,re.DOTALL)
            #findall(r'\s*(\w*)\s*\|\s*([^\s]*)\s*([^\s]*)\s*([^\s]*)\s*([^\s]*)',pieces[0])
            Ns=re.findall('Number of obs\s*=\s*([^\s]*)',reg)
            assert len(Ns)==1

            rows=re.findall(r'\s*(\w*)\s*\|\s*([^\s]*)\s*([^\s]*)\s*([^\s]*)\s*([^\s]*)\s*\n',reg,re.DOTALL)
            for rr in rows:
                amean=dict([[kk,vv] for kk,vv in parseStataComments(reg).items() if kk in ['name']])
                amean.update({'depvar':rr[0], 'mean':float(rr[1]), 'sem':float(rr[2]), 'N':int(Ns[0].replace(',',''))})
                
                means+=[amean]

    return(means)

    
################################################################################################
################################################################################################
def readSuestTests(logtxt,command=None):
    ############################################################################################
    ############################################################################################
    """
    May 2011:

    e.g. (but F could be replaced with chi^2, depending on the degrees of freedom, etc)

    *CPBLWaldTest:belongCountry
         test [GSS17redux =  GSS22redux]: belongCountry

Adjusted Wald test

( 1)  [GSS17redux]belongCountry - [GSS22redux]belongCountry = 0

F(  1,     9) =   10.82
            Prob > F =    0.0094

*CPBLWaldTest:widowed
...
    """
    from pylab import isnan
    suesttxt=re.findall('\*BEGIN SUEST TESTS TWOMODELS\n(.*?)\*END SUEST TESTS TWOMODELS',logtxt,re.DOTALL)
    assert len(suesttxt)==1
    # Find all Wald tests:
    walds=logtxt.split('*CPBLWaldTest:')[1:]
    #walds=re.findall('\*CPBLWaldTest:(.*?)\*',logtxt+'\n *CPBLNullTest',re.DOTALL)
    estcoefs={}
    for iw,awald in enumerate(walds):
        varname=awald.split('\n')[0]
        stats= re.findall('([^\n]*).*?\n\s*([Fchi2]*)\([0-9, ]*\) =\s*([^\s]+)\s*\n\s*Prob > ([Fchi2]*) =\s*([^\s]+)\n',awald,re.DOTALL)
        assert len(stats)==1 or iw==len(walds)-1 # Only the last result of split() should have extra stuff.
        nn,Fchi2,FF,Fchi2again,pp=stats[0]
        estcoefs[nn]={'p':pp,'F':FF,'b':Fchi2,}#'se':''}
    return(dict(estcoefs=estcoefs,eststats={'N':'','r2_p':''}))

################################################################################################
################################################################################################
def readEstimatesTable(logtxt,command=None,   removeFactorVariables=True):
    ############################################################################################
    ############################################################################################
    """
    Estimates table is currently (version 11) the only way to get results out without truncated variable names. In Stata 11, there is no way to do this for matrices.
    Prior to Jan 2010 I had this working for OLS and quantile regression. I am now generalising it to deal with results from oaxaca command too (maybe).

    This was first designed for OLS. Right now it still ignores the cut-points for ologit etc results. They end up in statss

    Maybe I should have a "di e(cmd)" in there so that it knows what command it's dealing with...
    Or allow the command (mode) to be passed....?

    2013March: when I include dummies like i.year#i.country in the output, there will be a space in the variable name... I'm now going to try to implement that.

    removeFactorVariables=True: will remove from the results the coefficients for variables included using the i.variable syntax. 
             ((We only need to do this because of the "0*" in 0*('drop('+dropIndicators+')'  in latexRegressions.py. The drop() option was removed in 2016 July (see git 80b89fb6026c980dd9e05f8563331e56f8d1ef4a for the ostensible reason) but maybe it should be back in there. It is true that the more general approach is to leave fixed effect dummies in the output, and then just filter them out here.))

    Here's an example from Stata 14 with both cut points and factor variables: How to deal with this??
estimates table , varwidth(49) style(oneline) b se p stats(F r2  r2_a r2_p N  N_clust ll r2_o ) 

----------------------------------------------------------------
                                         Variable |   active    
--------------------------------------------------+-------------
SWL                                               |
                                          married |  .23595471  
                                                  |  .01574041  
                                                  |     0.0000  
                                    hr_lnHHincome | -.64860233  
                                                  |  .04908245  
                                                  |     0.0000  
                                                  |
                                           HHsize |
                                       2 PERSONS  |  .24075706  
                                                  |  .02066331  
                                                  |     0.0000  
                                       3 PERSONS  |  .22229913  
                                                  |  .02342867  
                                                  |     0.0000  
                                       4 PERSONS  |  .31645499  
                                                  |  .02399174  
                                                  |     0.0000  
                                  5 OR + PERSONS  |   .3524778  
                                                  |  .03059288  
                                                  |     0.0000  
--------------------------------------------------+-------------
cut1                                              |
                                            _cons |  -8.962363  
                                                  |  .54262659  
                                                  |     0.0000  
--------------------------------------------------+-------------
cut2                                              |
                                            _cons | -8.7136119  
                                                  |   .5418395  
                                                  |     0.0000  
--------------------------------------------------+-------------
Statistics                                        |             
                                                F |             
                                               r2 |             
                                             r2_a |             
                                             r2_p |  .01396873  
                                                N |      75031  
                                          N_clust |             
                                               ll | -126776.13  
                                             r2_o |             
----------------------------------------------------------------
                                                  legend: b/se/p


    """
    from pylab import isnan
    parts=re.findall('Variable\s*\|\s*active\s*\n--------------------[-+-]*\n(.*?)\n\s*legend:(.*?)\n',logtxt,re.DOTALL)
    if len(parts)==0:
        print 'CAUTION!! Found no estimates-like table in log txt for  this section '
        return({})


    assert len(parts)==1 # Only one estimates table found for the text given
    legendstats=parts[0][1].strip().split('/')

    def _pStatsSection_estTab(statss):
        # Deal with the final section, stats.
        #    For logit etc output, the cut points are in statss so far (oops). Also, in oaxaca, the label exists too.
        if 'Statistics' in statss:
            statsWithoutCutpoints=re.findall('(Statistics.*)',statss,re.DOTALL)[0]
        else:
            statsWithoutCutpoints=statss
        stats=tonumeric(dict([[n,v] for n,v in re.findall('\s*([^\s]+)\s*\|(.*?)\n',statsWithoutCutpoints) if v.strip() ]))
        return(stats)

    def _move_cut_points_to_front(secs):
        """  One way to deal safely with cutpoints is to remove them or to clean them up and place them at the beginning, so that they don't mess up any factor variable sections."""
        for ii,asec in reversed(list(enumerate(secs))[1:]):
            if not asec.startswith('cut'): continue
            if re.search('^cut([0-9]*) [ \n|]+_cons \\| [\\d\\-.\n ]*$',  asec, re.MULTILINE):
                secs[0]= re.sub('^cut([0-9]*) [ \n|]+', ' '*20+r'   cut\1', asec) + secs[0]
        return(secs)

    # Split up into sections:
    sections=re.split(r'----+\+---+\n',parts[0][0])
    #if command in ['ologit','oprobit']:
    sections=_move_cut_points_to_front(sections)
        
    # There will be two or more sections separated by "---" lines. In case of Oaxaca, each section has a title, identifable by no space at beginning of first line of section:

    if '\n nl ' in '\n'+logtxt[:20]: # NL regression
        """
	    Last section is statistics. Rest are estimates.
	    The format is screwy. Why does each line say _cons? Come on, Stata...

e.g. 
alpha                                             |
                                            _cons |  5.6311031  
                                                  |  .59830168  
                                                  |     0.0000  
beta                                              |
                                            _cons |  .01532016  
                                                  |  .02262896  
                                                  |     0.4984  
sigma                                             |
                                            _cons |  .65753306  
                                                  |   .1390233  
                                                  |     0.0000  

	    """  
        varsS,statss=''.join(sections[:-1]),sections[-1]

        # do the strip()'ing right in the regexp, although it makes it less readable:
        coefss=re.findall('\s*([^\s]+)\s*\|\s*_cons\s*\|(.*?)\n'+''.join((len(legendstats)-1)*'\s*\|(.*?)\n'),varsS)
        coefOrder=[c[0] for c in coefss]
        coefs=dict([[cc[0],dict(zip(legendstats,cc[1:]))] for cc in coefss])
    elif len(sections)==2 or '\n\nOrdered probit regression' in logtxt or '\n\nOrdered logistic regression' in logtxt or '\n nl ' in '\n'+logtxt[:20]:
        # This is OLS, quantile reg, oprobit, ologit, ...

        if len(sections)==2:
            assert sections[0].startswith(' ') # ie there should be no section titles for OLS or quantile reg
            assert command in [None,'OLS','ols','rreg', 'reg','regress','qreg','ivregress 2sls','ivreg2']
            #print 'OLS etc'
            varsS,statss=sections[0],sections[1]
        elif command in ['xtreg']:
            print 'Parsing xtreg as though it were OLS, ie ignoring some variance info....'
            varsS,statss=sections[0],sections[1]
        elif '\n\nOrdered probit regression' in logtxt:
            assert command in [None,'oprobit']
            print 'Parsing oprobit, saving/renaming cutpoints ...'
            varsS,statss=sections[0],sections[-1]
        elif '\n\nOrdered logistic regression' in logtxt:
            assert command in [None,'ologit']
            print 'Parsing ologit, saving/renaming cutpoints ...'
            assert 'lnHHincome' in sections[0]
            varsS,statss=sections[0],sections[-1]            

        if 0: # Following used until March 2013:
            # do the strip()'ing right in the regexp, although it makes it less readable:
            coefss=re.findall('\s*([^\s]+)\s*\|(.*?)\n'+''.join((len(legendstats)-1)*'\s*\|(.*?)\n'),varsS)

        # Deal with possibility that we have a set of fixed effects (i.var) in the output. If we do, optionally throw away all those results (if you want to keep them, specify the variables explicitly). Note that any  cutpoint constants are already hidden/renamed to look like normal variables, so should be safe from this regexp match.
        if re.search('\n *\\|\n',varsS) and removeFactorVariables:
            print('    Doing kludge for i.var regressors... (removeFactorVariables=True)')
            gg=re.split('\n *\\|\n', varsS) # Sections are separated by a line with nothing but |
            #gg=varsS.split('  |\n')
            for ii,asxn in enumerate(gg):
                if not asxn.split('\n')[0].split('|')[1].strip(): # Does the first line contain a coefficient?
                    gg.pop(ii)
            assert gg
            varsS='\n'.join(gg)

        # March 2013:  I'm doing the same but allowing spaces in the variable name! This works, and is better:
        coefss=re.findall('\s*(.*?)\s*\|(.*?)\n'+''.join((len(legendstats)-1)*'\s*\|(.*?)\n'),varsS)
        coefOrder=[c[0] for c in coefss]
        coefs=dict([[cc[0],dict(zip(legendstats,cc[1:]))] for cc in coefss])

    
    elif sections[0].startswith('overall') or  sections[0].startswith('Differential'):  # 2015June: I think format has changed in recent stata.
        debugprint('Looks like Oaxaca')
        assert command in [None,'oaxaca']
        statss=sections[-1]
        oaxaca={}
        # I assume below that coefOrder is same in each section...?
        for section in sections[0:-1]:
            sectionName=section.split('\n')[0].strip(' |')
            varsS='\n'.join(section.split('\n')[1:])
            # do the strip()'ing right in the regexp, although it makes it less readable:
            coefss=re.findall('\s*([^\s]+)\s*\|(.*?)\n'+''.join((len(legendstats)-1)*'\s*\|(.*?)\n'),varsS)
            coefOrder=[c[0] for c in coefss]
            coefs=dict([[cc[0],dict(zip(legendstats,cc[1:]))] for cc in coefss])
            oaxaca[sectionName]=coefs

        outModel={'oaxaca':oaxaca,'eststats':_pStatsSection_estTab(statss)}#,'estCoefOrder':coefOrder}

        return(tonumeric(outModel))
    else:
        assert not 'Unknown command output! Could be ologit, etc'










    stats=_pStatsSection_estTab(statss)
    outModel={'estcoefs':coefs,'eststats':stats,'estCoefOrder':coefOrder}
    assert outModel['estcoefs']
    return(outModel)


################################################################################################
################################################################################################
def readStataEstimateResults(logtxt):
    ############################################################################################
    ############################################################################################
        """
        This is a wrapper which mostly relies on readEstimatesTable (the previous method, above) but also reads other output, such as a covariance matrix, etc.

        This used to be a part of the following function, read a log file. But it also works for quantile regression, which is parsed separately.

        This was first designed for OLS. Right now it ignores the cut-points for ologit etc results. They end up in statss

        May 2011: Adding suest tests
        2016 Jan: add ivreg2 tests
        """
        from pylab import isnan
##         
        outModel=None

        """
        May 2011

        Okay... if there's a suest section, it will confuse readEstimatesTable, since it shows a 3-section table.
        So if it looks like there are suest tests, do not even call readEstimatesTable.
        """

        if not '*BEGIN SUEST TESTS TWOMODELS' in logtxt:
            outModel=readEstimatesTable(logtxt)


        # THIS COULD BE A SUEST TEST SET, NOT AN ESTIMATE...
        if '*BEGIN SUEST TESTS TWOMODELS' in logtxt:
            assert outModel is None
            outModel=readSuestTests(logtxt)

        # READ ANY COVARIANCE MATRICES:
        if 'matrix list e(V)' in logtxt:
            covar=readStataCoefficientCovarianceMatrix(logtxt)
            outModel.update({'estCovar':covar})

        # READ AN ALL-SAMPLE CORRELATION MATRIX OF VARIABLES: (now with pweights)
        if 'matrix list sampleIndepCorr' in logtxt:
            covar=readStataVariablesCovarianceMatrix(logtxt)
            outModel.update({'variableCorr':covar})

        # READ ANY SUB-SAMPLE SUMS:
        if 'BEGIN SUM LIST MULTI' in logtxt:
            outModel.update({'subSums':read_postEstimate_sums_by_condition(logtxt) })

        # Always save the raw output right in the model dict
        outModel['rawLogfileOutput']=logtxt
        return(outModel)


################################################################################################
################################################################################################
def readStataRegressionLogFile(logFilename,output='models',dropIfStartsWith=['dCountry'],dropVars=None,models=None):
    ############################################################################################
    ############################################################################################
    """
    It might be useful to have dropModels dropped here etc because then any regressors not used in the remaining ones can be taken out already. No! Too complex. I can recreate the byVar etc later, and have that drop any that are empty.

But! This should not return nan values for variables/stats. They should simply be absent in a model if no value exists.

So this function deals with everything that might fit inside regTable().  So far, that excludes quantile regressions and oaxaca.


N.B. It is important that this function returns None or a string containing      'run Stata and try again'  if there is something wrong with the log file. That signals the caller to run stata...

May 2011: Adding suest tests. Or maybe tests in general???

    """

    if not os.path.exists(logFilename):
        return(None)

    txt=open(logFilename,'rt').read().replace('\n> ','')
    print ' Reading stata regression log file: '+logFilename

    # Ensure there's exactly one table contained:

    atable=re.findall('CPBL BEGIN TABLE:([^\n]*):(.*?)CPBL END TABLE:([^\n]*):',txt,re.DOTALL)
    assert len(atable)==1
    tableName=atable[0][0]
    assert atable[0][2]==tableName

    emodels=re.findall('CPBL BEGIN MODEL:([^\n]*):(.*?)CPBL END MODEL:([^\n]*):',atable[0][1],re.DOTALL)
    if not len(emodels)>=1:
        cwarning('THERE ARE NO MODEL RESULTS IN THE LOG FILE! SKIPPING THIS TABLE! (Rerun Stata).\n See %s'%logFilename)
        return(None)







    modelResults=[readStataEstimateResults(mmm[1]) for mmm in emodels]
    print '             (Found %d raw model results in %s)'%(len(modelResults),logFilename)
    if any([not mmm for mmm in modelResults]):
        cwarning( '\nWARNING!!!  Dropping %d empty model results out of %d!!!!!!!\n'%(len([mmm for  mmm in modelResults if not mmm]),len(modelResults)))
        modelResults=[mmm for  mmm in modelResults if mmm]

    # Choose a sensible order for combining the variables from a number of estimates:
    coefOrder=[]
    for mmm in modelResults:
        coefOrder=uniqueInOrder(coefOrder+mmm.get('estCoefOrder',[]))

    # Drop any regressors that we are not interested in (Oh?? Could be done more easily later, byVars?)
    if dropIfStartsWith:
        for mm in modelResults:
            if not mm:
                continue
            kk=mm['estcoefs'].keys()
            for vvv in kk:
                for disw in dropIfStartsWith:
                    if vvv.startswith(disw):
                        del mm['estcoefs'][vvv]
                        continue
                    elif dropVars and  vvv in dropVars:
                        del mm['estcoefs'][vvv]
                        continue


    # unfortunately, a "0" is given by Stata for coefficients that were not fit
    # Turn these into blanks: (if not for the zeros, I could just use tonumeric for the entire dict! oh? So maybe I should just start by changing all 0's to ''s and then use tonumeric?)
    for immm,mmm in enumerate(modelResults):
        kk=mmm['estcoefs'].keys() # Variables reported for this model
        nullValues=['.','','0',fNaN,'(omitted)','(empty)']
        todel=[]
        for vv in kk:
            # isVal tests whether this model has an estimate for this variable. b=1 for dummy regressions
            # Oct 2009: For my beta regressions (zscore), I find that the _cons gets an estimate when nothing else exists.... ? Ah, that's becuase I have a loop that sets them all to "1" if they don't exist... but I am temporarily deactiving that now that I have reinstituted z_dSample. It is important only to call the algorithm with variables that are available, obviously.
            isVal=[mmm['estcoefs'][vv][btp].strip() not in nullValues+['1']  for btp in mmm['estcoefs'][vv]]
            #assert all(isVal) or not any(isVal) or not forceShowVars==None
            """ 201710 update: Stata, without other warning, does sometimes give a value for the constant's coefficient but not for its se or p.  
            """
            weirdCaseSeemingStataBug=False
            if (not all(isVal) and any(isVal)):# and forceShowVars==None):
                weirdCaseSeemingStataBug=True
                if mmm.get('special','')=='suestTests':
                    print 'weirdCaseSeemingStataBug! for suestTests. Check svyset?'
                elif mmm['estcoefs'][vv]['se'].strip()=='0':
                    print "weirdCase: %s: Stata gave a coefficient, but no standard error. Did the whole regression fail? I don't think so. Maybe it guessed at this coefficient even though it's a dummy with very little variation (likely a singleton value associated with dummies). In fact, it may be that if you try  non-robust standard errors, you get a s.e. estimate "%vv
                elif vv=='_cons' and  mmm['estcoefs']['_cons']['b'].strip() not in ['.',''] and float(mmm['estcoefs']['_cons']['b'].strip())<1e-10:
                    todel+=['_cons'] # For my normalized regs, this has started happening. Just drop the constant?
                else:
                    print 'weirdCaseSeemingStataBug!'
            if not any(isVal) or weirdCaseSeemingStataBug:
                todel+=[vv] # ie, no estimate for this variable, so remove it completely for this model
                #todel=mmm['estcoefs'][vv].keys()
                #for estval in todel:
                #    del mmm['estcoefs'][vv][estval]
        for vv in todel:
            if vv in mmm['estcoefs']:  del mmm['estcoefs'][vv]

        # Okay, so now let's work with numbers:
        mmm['estcoefs']=tonumeric(mmm['estcoefs'])
        mmm['eststats']=tonumeric(mmm['eststats'])


        # What if an entire regression model failed? Then the coefficients etc will be dealt with, above, but the eststats will still exist.
    if 0:
        assert modelResults[0]['eststats']['r2']>0

    #byVar=tonumeric(byVar)
    #byStat=tonumeric(byStat)


    # If the original model dicts used for making Stata calls are supplied, put the estimates into those
    assert models  # Actually, models almost MUST be supplied! Turn it into a mandatory argument -->[]

    if models:
        if not len(models)==len(modelResults):
            if 0 and self.skipStataForCompletedTables: # Huh!? May 2010, shortly after writing the following, I think: this is impossible: there is no "self" here. We don't know about this setting.
                print '******** YOU PROBABLY WANT TO TURN OFF skipStataForCompletedTables, otherwise the following problem will not be fixed upon your next execution of Stata!!:'
            return(r' $\Longrightarrow$ Aborting processing of Stata output for %s because %d=nEstimates != len(models)=%d. So run Stata and try again.'%(os.path.split(logFilename)[1],len(modelResults),len(models))+'\n')

        assert len(models)==len(modelResults)
        for im in range(len(models)):
            models[im].update(modelResults[im])
        modelResults=models

        for mmm in models:
            if '_cons' in mmm['estcoefs'] and abs(mmm['estcoefs']['_cons']['b'])<1e-16 and 'beta' in mmm['model']:
                mmm['estcoefs'].pop('_cons')
                print '   Dropped constant for beta estimate '
                #assert not any([abs(vv['b'])<1e-9 for vv in mmm['estcoefs'].values()])

            # Update model objects with the name of their source log file, and with the entire source text
            mmm['logFilename']=logFilename


    #################### TROWS: A MODE FOR BACKWARDS COMPATIBILITY
    # Replace '_' in var names.
    # Leave things as strings, not numeric
    # What about _cons?
    # reorder as in file (not model?)
    if output=='trows':

        # Start by creating a variable-organised dict of all coefs:
        # Get list of all available regressors and stats:

        byVar,byStat,byTextraline=modelResultsByVar(modelResults,tableFilename=logFilename)


        def tostr(LL):
            from math import isnan
            if isinstance(LL,list):
                return([tostr(Li) for Li in LL])
            if isinstance(LL,unicode):
                return(unicode(LL).strip())
            elif isinstance(LL,float) and isnan(LL):
                return('')
            else:
                return(str(LL).strip())

        trows=[]
        # Order the rows by the way they were in the file originally.
        #orderListByRule(orderListByRule(byVar.keys,defaultVariableOrder),coefOrder)
        for vv in orderListByRule(byVar.keys(),coefOrder):

            trows+=[[vv.replace('_','-')]+tostr(byVar[vv]['coefs']),  ['']+tostr(byVar[vv]['ses'])]
        # Drop r2 if we have r2_a:
        if 'r2' in byStat and 'r2_a' in byStat \
               and all([byStat['r2_a'][im] not in nullValues or byStat['r2'][im]  in nullValues for im in range(len(byStat['r2']))]):
            del byStat['r2']
            debugprint('Dropping r2 in favour of r2_a.')
        # Add the stats as the last trows
        for vv in orderListByRule(byStat.keys(),['r2','r2_a','N','p','N_clust']):
            if vv in ['r2','r2_a','N','p','N_clust']:
                vvn='e(%s)'%(vv.replace('_','-'))
            else:
                vvn=vv
            trows+=[[vvn]+tostr(byStat[vv])]
        return({'trows':trows})


    return({'models':modelResults})
    assert 0
##     if 0:









def stataSumMulti(a,b=None):
    print('********* STATASUMMULTI HAS BEEN RENAMED generate_postEstimate_sums_by_condition() ********')
    return(generate_postEstimate_sums_by_condition(a,ifs=b))
################################################################################################
################################################################################################
def generate_postEstimate_sums_by_condition(vars, ifs=None):
    ############################################################################################
    ############################################################################################
    """
    this creates code to be read by read_postEstimate_sums_by_condition. This used to be called stataSumMulti
    oh-oh. the means must be done separately, since if multiple variables are given together, the smalleest common N will be used!  I could make a flag for doing them together...? agh. This is now ugly, and collapse would be better.?

2015July: the issue seems to be that this has gone down an awkward path: because it seems I became unclear as to whether I wanted to get stats on the set of rows for which all variables exist, or to get stats on each variable independently (within the sample used in  the last regression command (sample identified by cssaSample))

    """
    if ifs is None:
        ifs=[' 1 ']
    assert isinstance(ifs,list)
    #if isinstance(vars,list):
    #    vars=' '.join(vars)
    if isinstance(vars,basestring):
        vars=[vv for vv in vars.split(' ') if vv]

    return('\n'.join(['\n'.join(["""
                *BEGIN MEAN LIST MULTI
 mean """+var+""" [pw=weight] if cssaSample & ("""+anif+"""),
                *END MEAN LIST MULTI
                """ for var in vars])+"""
                *BEGIN SUM LIST MULTI
 sum """+' '.join(vars)+""" [w=weight] if cssaSample & ("""+anif+"""), separator(0) """+(defaults['server']['stataVersion']=='linux11')*"""nowrap"""+"""
                *END SUM LIST MULTI
""" for anif in ifs]))



################################################################################################
################################################################################################
def read_postEstimate_sums_by_condition(txt):
    ############################################################################################
    ############################################################################################
    """
    When you can get by passing several variables at once to get sum info for a subset of a sample (e.g. using e(sample) etc.
    Text passed in here is currently a log excerpt which has already had replace('\n> ','') done.
    2010 Jan update: This now looks for both "sum" and "mean" commands, since both (or at least the latter??) is needed. Well.. not yet.

    Oct 2011: the retired v1 version may be revived, if I'm changing the original focus. But I'm completely rewriting this to accept means being split up by variable but sums not. makes use of dgetget and dsetset
"""

    from pylab import sqrt

    print ' Following probably needs optional nowrap, since I added that May 2010. ie should be able to read either version, with or without nowrap (v11).'
    #""" +(defaults['stataVersion']=='linux11')*"""nowrap"""+"""
    sumCommands=re.findall(""".\s+.BEGIN SUM LIST MULTI
.\s+sum ([^\n]*?) \[w=weight\] if ([^,]*),([^\n]*)
(.*?)
-----------.*?
(.*?)
.\s+.END SUM LIST MULTI""",txt,re.DOTALL)
    meanCommands=re.findall(""".\s+.BEGIN MEAN LIST MULTI
.\s+mean (.*?) \[pw=weight\] if ([^,]*)([^\n]*)

Mean estimation  +Number of obs +=([^\n]*)

---*
([^\n]*)
---[+-]*
(.*?)
---*

.\s+.END MEAN LIST MULTI""",txt,re.DOTALL)
    #print '45678',sumCommands
    sums={}

    assert sumCommands
    assert meanCommands
    assert (not sumCommands and not meanCommands) or ( sumCommands and  meanCommands) #Could this be disabled for some old log files?...


    # Now, possibly OVERWRITE some elements with the correct values from

    # STill need to compare N's from sum and mean .... hmmmmm ******************* !!!!!!!!!!!!!!!!!!!!!

    """
    mean health [pweight=weight]

Mean estimation                     Number of obs    =   24911

--------------------------------------------------------------
             |       Mean   Std. Err.     [95% Conf. Interval]
-------------+------------------------------------------------
      health |   .6849366   .0018781      .6812553    .6886178
--------------------------------------------------------------

"""



    from cpblUtilities import dsetset, dgetget
    for sc in meanCommands: # There could be more than one...
        # Find variable names from the calling command (so they must be called as full names... hmm and no wildcards!)
        assert '*' not in sc[0] # No wildcards allowed
        vvars=[ss for ss in sc[0].split(' ') if ss]
        rows=[ss for ss in sc[5].split('\n') if ss]
        condition=sc[1]
        assert len(rows)==len(vvars)
        N=tonumeric(sc[3])
        assert N
        amean={}
        #dsetset(sums,[condition],amean)

        cols=['mean','seMean','ciL','ciH']
        for irow in range(len(rows)):
            onerow=tonumeric([ss for ss in rows[irow].split('|')[1].split(' ') if ss])
            for icol,col in enumerate(cols):
                assert dgetget(sums,[condition,vvars[irow],col],None) is None
                dsetset(sums,[condition,vvars[irow],col], onerow[icol])
                        #tonumeric(dict(zip(cols,
            assert dgetget(sums,[condition,vvars[irow],'N'],None) is None
            dsetset(sums,[condition,vvars[irow],'N'],   N)


    # Now also get the stddev, the min, and the max from the "sum" command, and add these statistics in to the same dict... Nothing from the "mean" command should be overwritten, and the "N" should be identical for each.  AGH No: 2011 Oct: N will not be the same, since if there are multiple variables given in one sum called, the lowest common N will be used.


    for sc in sumCommands: # There could be more than one...
        # Find variable names from the calling command (so they must be called as full names... hmm and no wildcards!)
        vvars=[ss for ss in sc[0].split(' ') if ss]
        #print vvars
        rows=[ss for ss in sc[4].split('\n') if ss]
        #print rows
        condition=sc[1]
        assert len(rows)==len(vvars)

        cols=['checkN','junkWeight','junkMean','stddev','min','max']
        #if not meanCommands:
        #    cols=['N','weight','mean','stddev','min','max']
        #    print 'CAUTION!!!!!!!!!!!!!!!! this is a very old .. rerun stata'
        for irow in range(len(rows)):
            #asum[vvars[irow]].update(tonumeric(dict(zip(cols,[ss for ss in rows[irow].split('|')[1].split(' ') if ss]))))
            onerow=tonumeric([ss for ss in rows[irow].split('|')[1].split(' ') if ss])
            for icol,col in enumerate(cols):
                assert dgetget(sums,[condition,vvars[irow],col],None) is None
                dsetset(sums,[condition,vvars[irow],col], onerow[icol])

            asum=sums[condition]
            assert asum[vvars[irow]]['N']==asum[vvars[irow]]['checkN'] # Every variable should have the same count, and it should be the same as that from the mean command.

            if not meanCommands:
                asum[vvars[irow]]['junkseMean']=asum[vvars[irow]]['stddev']/sqrt(asum[vvars[irow]]['N'])
                print ' CAUTION! Using incorrectly weighted stddev for calculation of mean s.e. because mean list multi does not exist... (rerun Stata?) '
            if asum[vvars[irow]]['N']==1:
                asum[vvars[irow]]['junkseMean']=0.0 # We don't know further properties of the single value, so assume no s.e.

    for condition in sums:
      for avar in sums[condition]:
         pass
    return(sums)











################################################################################################
################################################################################################
def stataElicitMatrix(matrixName):
    ############################################################################################
    ############################################################################################
    """
    This is what gets read by readStataLablledMatrix, eventually. So far it's probably only matrixName='e(v)'
    """
    return("""
matrix list %(mn)s,nohalf
* MID: matrix list %(mn)s
mat %(mns)s=%(mn)s
local names%(mns)s: colnames(%(mns)s)
display "`names%(mns)s'"
* END: matrix list %(mn)s
"""%{'mn':matrixName,'mns':'_'+''.join(cc for cc in matrixName if cc not in '()')})


################################################################################################
################################################################################################
def readStataLabelledMatrix(txt,matrixName=None):
    ############################################################################################
    ############################################################################################
    """
    August 2009.
    This is one (strange) way to get a matrix out of Stata. The "matrix list" command is nice because it doesn't truncate variable names. [AGH! It didn't until Stata 11 came along!]
So this is useful for reading a matrix with named rows and columns. It reads it into a lookup dict rather than an array.
It gets called by wrapper functions that seek a coefficient covariance matrix (e(V)) or a variable covariance matrix...


This function expects to find only ONE covariance matrix in the txt supplied.

2013 FEb: It's started including omitted variables from a regression, which messes up the format as well as interpretation. :(
Need to post to a Stata list to get help fixing this. 
Worse: it no longer (!) includes full-length variable names (for rows, at least). So my kludges below fix the first problem but not the second.

2013 Feb: Solution: rewrite this from scratch. Now requires log to have been created using stataElicitMatrix, above. Separately take the colnames, then the full matrix. And use a pandas DF to capture the matrix!
New plan: concatenate the segments into a single text matrix. Then convert spaces to tabs. Then load it straight into a matrix. Then cleaning out the bad rows/columns can be done pretily.
    """

    ev=re.findall(r"""matrix list (.*?),nohalf

symmetric [^[]*.(\d*),(\d*).(.*?)MID: matrix list .*?display "`names_.*?\n(.*?)\n.*?END: matrix list""",txt,re.DOTALL)

    from cpblUtilities import cwarning,tonumeric
    assert len(ev)<2
    if len(ev)==0:
        print (' readStataLabelledMatrix: Skipping this model since I cannot find the covariance matrix %s. Might the log file have been written prior to Feb 2013?'%matrixName)
        assert 0
        return(None)
    ev=ev[0]
    matrixN,nCols,n2,colnames=ev[0],int(ev[1]),int(ev[2]),ev[4].split()
    assert nCols==n2
    #matrixN=ev[0]
    if matrixName: # Here is the only place we make sure we're getting the right matrix?
        assert matrixName==matrixN

    segments=re.findall(r'\s*([\s]*.*?)\n\n',ev[3],re.DOTALL)

    # The segments are whatever Stata has split the table up into. Now just need to read them all in. Segments don't necessarily have the same number of rows OR columns! But in the end we end up with a dict with nCols keys, each of which gives a dict with nCols keys.


    covar={}

    omittedVars=[]
    # Remove all lines that are just "o."'s.  Also, replace all whitespace with single tabs:
    # Using: '\t'.join(rr.split()) replaces all multi-white space with tabs. :)
    tsegments=['\n'.join(['\t'.join(rr.split()) for rr in segment.split('\n') if not rr.replace('o.','').strip()=='']) for segment in segments]
    cells=tonumeric([
        [re.split('\t',rr.strip()) for rr in segment.split('\n') if not rr.replace('o.','').strip()=='']
        for segment in tsegments])
    # Ensure all segments have the same number of rows:
    nL=len(cells[0])
    assert all( len(segm) ==nL for segm in cells)

    # Drop first column on 2nd and later segments:
    matr=deepcopy(cells[0])
    for iseg in range(len(segments))[1:]:
        matr[0]+=cells[iseg][0]
        for iline in range(nL)[1:]:
    	    matr[iline]+=cells[iseg][iline][1:]
    import pandas as pd
    df=pd.DataFrame([row[1:] for row in matr[1:]],columns=colnames,index=colnames)

    # Now we have a matrix. Let's remove the variables which got omitted from the regression:
    omittedvars= [cn for cn in colnames if cn.startswith('o.')]
    df=df.drop(omittedvars).drop(omittedvars,axis=1)
    return(df)

    uiuyuiuyuiuiuiu

    for segment in segments:
        segment='\n'.join(rr for rr in segment.split('\n') if not rr.replace('o.','').strip()=='')
        rows=segment.split('\n')
        cols=[cc for cc in rows[0].split(' ') if cc]
        for col in cols:
            if col not in covar:
                covar[col]={}
        for row in rows[1:]:
            entries=[ss for ss in row.split(' ') if ss]
        checkvar=entries[0].strip()
        if checkvar.startswith('o.'):
            entries[0]=entries[0].strip()[2:]
    	    omittedVars+=[entries[0]]
            if 0 and checkvar in covar:
    	        covar.pop(checkvar)
            continue
            assert len(entries)==1+len(cols) # Hm. This may happen with time series names?? Or, when I've mistakenly listed a variable twice, Stata? puts an "o." prefix on the second copy, and this part of the name can get wrapped? or form a separate column? or something... Try deleting the log file and fixing the duplicate variable.
            for icol in range(len(cols)):
                if entries[1+icol]=='0':
                    entries[1+icol]=''
                covar[cols[icol]][entries[0]] = tonumeric(entries[1+icol])
                if entries[0] not in covar:
                    covar[entries[0]]={}
                covar[entries[0]][cols[icol]] = tonumeric(entries[1+icol])
    	
    assert nCols==len(covar)
    # Now (2013 updated: behaviour has changed):
    for ov in uniqueInOrder(omittedVars):
        covar.pop(ov)
    return(covar)


################################################################################################
################################################################################################
    ############################################################################################
    ############################################################################################
def readStataVariablesCovarianceMatrix(txt):
    """
    August 2009. Now relies on a more general matrix-reading functoin.
    See pystata.latexRegressions.py for function(s) producing this..
    """
    ev=re.findall("""(matrix list sampleIndepCorr,nohalf.*?END: matrix list)""",txt,re.DOTALL)
    assert len(ev)<2
    return(readStataLabelledMatrix(ev[0],matrixName='sampleIndepCorr'))


################################################################################################
################################################################################################
    ############################################################################################
    ############################################################################################
def readStataCoefficientCovarianceMatrix(txt):
    """
    August 2009. Will be useful for compensating differentials
    This is one (strange) way to get a matrix out of Stata. The "matrix list" command is nice because it doesn't truncate variable names.
    This function gets the covariance matrix as a lookup table rather than a matrix.
This function expects to find only ONE covariance matrix in the txt supplied.
Now relies on a more general matrix-reading functoin
    """

    ev=re.findall("""(matrix list e\(V\),nohalf.*?END: matrix list)""",txt,re.DOTALL)
    assert len(ev)<2
    return(readStataLabelledMatrix(ev[0],matrixName='e(V)'))


    # Old / redundant code, now in the more general function above:




    ev=re.findall("""matrix list e\(V\),nohalf

symmetric e\(V\).(\d*),(\d*).(.*?)END: matrix list""",txt,re.DOTALL)
    from cpblUtilities import cwarning
    assert len(ev)<2
    if len(ev)==0:
        print (' readStataCoefficientCovarianceMatrix: Skipping this model since I cannot find the covariance matrix.')
        return(None)
    ev=ev[0]
    nCols,n2=int(ev[0]),int(ev[1])
    assert nCols==n2
    segments=re.findall(r'\s*([\s]*.*?)\n\n',ev[2],re.DOTALL)

    # The segments are whatever Stata has split the table up into. Now just need to read them all in. Segments don't necessarily have the same number of rows OR columns! But in the end we end up with a dict with nCols keys, each of which gives a dict with nCols keys.

    covar={}
    for segment in segments:
        rows=segment.split('\n')
        cols=[cc for cc in rows[0].split(' ') if cc]
        for col in cols:
            if col not in covar:
                covar[col]={}
        for row in rows[1:]:
            entries=[ss for ss in row.split(' ') if ss]
            assert len(entries)==1+len(cols)
            for icol in range(len(cols)):
                if entries[1+icol]=='0':
                    entries[1+icol]=''
                covar[cols[icol]][entries[0]] = tonumeric(entries[1+icol])
                if entries[0] not in covar:
                    covar[entries[0]]={}
                covar[entries[0]][cols[icol]] = tonumeric(entries[1+icol])


    assert nCols==len(covar)

    return(covar)



################################################################################################
################################################################################################
    ############################################################################################
    ############################################################################################
def ensureUnzippedStataFile(fn,outfn=None):
    """
Sept 2009: Switched all Stata files to .dta.gz only to find that I am then stuck for "merge".

So before merging anything, use Stata command:
shell ensureUnzippedDTA


DO NOT USE THIS IN PYTHON CODE DIRECTLY, SINCE YOU WANT IT TO HAPPEN AT STATA-RUNTIME!

"""

    if outfn==None:
        outfn=fn
    if not os.path.exists(fn+'.dta.gz'):
        print 'CAUTION! Failing: '+ fn+'.dta.gz does not exist! So should not proceed: CPBL uses .gz versions as copies of record.'
        assert 0
        return

    if not os.path.exists(outfn+'.dta') or fileOlderThan(outfn+'.dta',fn+'.dta.gz'):
        doSystem('gunzip --stdout %s.dta.gz > %s.dta'%(fn,outfn))


"""
The following suite of merge/save/load is needed while gzsave, etc is still being improved. It also allows clever choice between network vs processing optimisation for large files. ie by wrapping the Stata behaviour in functions here I can choose whether or not to compress based on filesize, location, etc.
"""
################################################################################################
################################################################################################
    ############################################################################################
    ############################################################################################
def stataMerge(key,filename,opts='',options=''): # options and opts are alternatives
    if options:
      assert not opts
      opts=options
    dfp=filename
    # Deal with extensions
    assert not dfp.endswith('.dta.dta')
    dfp=stripdtagz(dfp) # Strip .dta/dta.gz suffix
    if 0: # This is for when gzmerge is broken! and for before it existed, 2009 late.
        # Deal with pathnames for uncompression
        pp,ff=os.path.split(dfp)
        dta=WP+'uncompressed/'+ff
        if not os.path.isdir(WP+'uncompressed'):
            os.mkdir(WP+'uncompressed')
        #*shell """+defaults['binPath']+"""ensureUnzippedDTA.py %(dfp)s %(dta)s
    else:
        dta=''

    # Identify the merge result indicator variable; it may be specified in options.
    if '_merge' in opts:
        mergevar=re.findall('_merge\((.*?)\)',opts)[0]
    else:
        mergevar='_merge'

    #if defaults['mode'] in ['gallup','rdc']:
    #    from cpblMake import cpblRequire
    #    cpblRequire(dfp+'.dta.gz')

    # Clean up after ourselves (drop _merge) unless the _merge variable has been specified explicitly. :)
    return("""
    capture noisily drop %(mv)s
sort %(k)s
gzmerge %(k)s using "%(dfp)s.dta.gz", %(opts)s sort
tab %(mv)s
"""%{'k':key,'dta':dta,'dfp':dfp,'opts':opts.replace('sort',''),'mv':mergevar}+('_merge' not in opts)*("""
drop %s
"""%mergevar))

################################################################################################
################################################################################################
    ############################################################################################
    ############################################################################################
def stataAppend(filename,opts=None):
    if opts==None:
        opts=''
    if 0:
        return("""
        shell """+defaults['binPath']+"""ensureUnzippedDTA.py %(fn)s
        append using %(fn)s, %(opts)s
        """%{'fn':fn,'opts':opts})
    dfp=filename
    # Deal with extensions
    assert not dfp.endswith('.dta.dta')
    if dfp.endswith('.dta.gz'):
        dfp=os.path.splitext(os.path.splitext(dfp)[0])[0]
    if dfp.endswith('.dta'): # No; all are compress now!
        dfp=os.path.splitext(dfp)[0]
    # Deal with pathnames for uncompression
    pp,ff=os.path.split(dfp)
    dta=WP+'uncompressed/'+ff
    if not os.path.isdir(WP+'uncompressed'):
        os.mkdir(WP+'uncompressed')

    if defaults['mode'] in ['gallup','rdc']:
        from cpblMake import cpblRequire
        cpblRequire(dfp+'.dta.gz')

    return(#0*("""
   # *shell """+defaults['binPath']+"""ensureUnzippedDTA.py %(dfp)s %(dta)s""")+
        """
gzappend using %(dfp)s.dta.gz, %(opts)s
"""%{'dta':dta,'dfp':dfp,'opts':opts})


################################################################################################
################################################################################################
    ############################################################################################
    ############################################################################################
def stataSave(fn):
    dfp=fn#deepcopy(fn)
    assert not dfp.endswith('.dta.dta')
    if dfp.endswith('.dta.gz'):
        dfp=os.path.splitext(os.path.splitext(dfp)[0])[0]
    if dfp.endswith('.dta'): # No; all are compress now!
        dfp=os.path.splitext(dfp)[0]
    return("""
gzsave %s.dta.gz,replace
"""%(dfp))

################################################################################################
################################################################################################
    ############################################################################################
    ############################################################################################
def stataLoad(fn,onlyvars=''):
    dfp=fn#deepcopy(fn)
    assert not dfp.endswith('.dta.dta')
    if dfp.endswith('.dta.gz'):
        dfp=os.path.splitext(os.path.splitext(dfp)[0])[0]
    if dfp.endswith('.dta'): # No; all are compress now!
        dfp=os.path.splitext(dfp)[0]

    if defaults['mode'] in ['gallup','rdc']:
        from cpblMake import cpblRequire
        cpblRequire(dfp+'.dta.gz')
    if not onlyvars:
        return("""
        gzuse %s.dta.gz,clear
        """%(dfp))
    else:
        if isinstance(onlyvars,list):
            onlyvars=' '.join(onlyvars)
        return("""
        gzuse %s using %s.dta.gz,clear
        """%(onlyvars,dfp))

        # Oct 2009: "using" format not yet available.....
        dta=WP+'uncompressed_'+os.path.split(dfp)[1]
        return("""
    shell """+""" /home/cpbl/bin/rdc/ensureUnzippedDTA.py """+dfp+' '+dta+"""
    use """+onlyvars+' using '+dta+"""
""")

################################################################################################
################################################################################################
def stataSafeOrder(varlist=None):
    ############################################################################################
    ############################################################################################
    if varlist==None:
        varlist=defaultVariableOrder
    if isinstance(varlist,basestring):
        varlist=varlist.split(' ')

    varlist=[vv for vv in varlist if vv and not any([cc in vv for cc in r'()$.~-{}\ '])]
    return("""
foreach var in """+' '.join(varlist[::-1])+""" {
capture order `var'
}
    """)

################################################################################################
################################################################################################
def stataSafeKeep(varlist):
    ############################################################################################
    ############################################################################################
    if isinstance(varlist,list):
        varlist=' '.join(varlist)
    return("""
    checkfor2 """+varlist+"""  , nosum tolerance(100)
    keep `r(available)'
    """)

################################################################################################
################################################################################################
def stataSafeDrop(varlist=None):
    ############################################################################################
    ############################################################################################
    if isinstance(varlist,basestring):
        varlist=varlist.split(' ')

    varlist=[vv for vv in varlist if vv and not any([cc in vv for cc in r'()$.~-{}\ '])]
    return("""
foreach var in """+' '.join(varlist[::-1])+""" {
capture drop `var'
}
    """)
    #return('\n'+'\n'.join(['capture drop %s'%vv for vv in varlist])+'\n')




################################################################################################
################################################################################################
def doLinearPostestimationTests(tests,datafile=None,name=None):
    ############################################################################################
    ############################################################################################
    """ Very preliminary / basic
    May 2011

    i think right now this just adds code to be included in a log file.
    so then name should be unique in the file

    In fact, this should be inocrporated as an postestimation option to regtable. then this thing can be called to parse results and to generate code.

    """
    doText="""

* CPBL BEGIN POSTESTIMATION TESTS:%(nn)s
%(tt)s
* CPBL BEGIN POSTESTIMATION TESTS:%(nn)s
"""%{'nn':name,'tt':'\n'.join(['test '+tt for tt in tests])}
    return(doText,results)



################################################################################################
################################################################################################
def doQuantileRegression(themodel,datafile=None,nQuantiles=None,quantiles=None,name=None,plotTitle=None,execStata=False,skipPlots=False,options='',simultaneous=False,substitutions=None):
    ############################################################################################
    ############################################################################################
    """
"themodel" is the depvar plus all the RHSvars.  No weight if it's sqreg!

This can just return some Stata code, or it can be left to also run stata and parse the results! (execStata=True)

the simultaneous flag determines whether it's sqreg or a bunch of qregs... very different!

"""
    assert name
    name=''.join([ch for ch in name if ch.isalpha() or ch.isdigit() or ch in '-'])


    doText=''
    if datafile:
        doText+=stataLoad(datafile)##WP+"microGSS17Dec2009")

    #SWL  age100 age100sq male married asMarried separated divorced widowed lnHHincome belongCommunity highHHincome educHighSchool educStartedCollege educUnivDegree
    # Make a do file:
    doFile=WP+name+'-'+'s'*simultaneous+'quantile'
    logFile=doFile
    from pylab import arange
    assert not quantiles
    quantiles=arange(0.1,0.99,.1)

    if simultaneous:
        doText+="""
log using """+logFile+""".log, text replace
* CPBL BEGIN SQUANTILE REGRESSION SERIES
sqreg """+themodel+""" , quantiles("""+' '.join([str(qq) for qq in quantiles])+""") """+options+"""
* CPBL END SQUANTILE REGRESSION SERIES
log close
"""
    else:
        doText+="""
log using """+logFile+""".log, text replace
* CPBL BEGIN QUANTILE REGRESSION SERIES
"""+'\n'.join(["""
* CPBL BEGIN MODEL
qreg """+themodel+' [w=weight] , quantile('+str(qq)+') '+options+"""
estimates table , varwidth(49) style(oneline) b se p stats(r2  r2_a r2_p N  N_clust)
* CPBL END MODEL
""" for qq in quantiles])+"""
* CPBL END QUANTILE REGRESSION SERIES
log close
"""

    if not execStata:
        return(doText)
    #print doText
    # Read the result:
    if not os.path.exists(logFile+'.log'):
        print doFile+' does not exist yet: running Stata...'
        stataSystem(doText, filename=doFile) # Give do file without .do


    if not plotTitle:
        plotTitle=name + '(%(rhsv)s)'

    if simultaneous:
        return(parseSimultaneousQuantileRegression(logFile,plotTitle=plotTitle,name=name,skipPlots=skipPlots))
    else:
        return(parseQuantileRegression(logFile,plotTitle=plotTitle,name=name,skipPlots=skipPlots,substitutions=substitutions))



################################################################################################
################################################################################################
def parseSimultaneousQuantileRegression(logFile,plotTitle='%(rhsv)s',name=None,skipPlots=False,substitutions=None):
    ############################################################################################
    ############################################################################################
    """
     N.B.! sqreg does not allow weights! Doing a series of qregs yourself allows weights...

     This parses output from Stata's sqreg.


I may be able to do this much more robustly using my matrix reading function. Right now, if any variable is dropped as colinear, this function fails with an important assert.
Or... i may be able to get a list of the non-excluded variables, at least, from ereturn.

    """

    if '\n' in logFile: # logfile text must have been passed.
        logTxt=logFile
    else:
        logTxt=open(logFile+'.log','rt').read() # Should already have >\n's removed by stataSystem...

   #
    qSequences=re.findall(r""".\s+CPBL BEGIN SQUANTILE REGRESSION SERIES
\s*sqreg\s+(\w*)(.*?),\s*quantiles\((.*?)\)[^\n]*
(.*?).\s+CPBL END SQUANTILE REGRESSION SERIES""",logTxt,re.DOTALL)
    r"""-----------+
 [^\n]*
 [^\n]*
--------[+-]*
"""

    assert len(qSequences)==1
    qSequence=qSequences[0]
    depvar=qSequence[0]
    # Drop everything after ' if ' or [w=weight] and split up the regressors:
    RHS=substitutedNames([vv for vv in qSequence[1].split(' if ')[0].split('[')[0].split(' ') if vv])+['constant']
    quantiles=[qq for qq in qSequence[2].split(' ') if qq]

    qregs=re.findall(r"""
q(\w*)\s+\|.*?
(.*?)
--------[+-]*""",qSequence[3],re.DOTALL)

    assert len(qregs)==len(quantiles)
    cols=['coef','se','t','p','ciL','ciH']
    sqReg={'quantiles':quantiles}
    vvars=RHS
    for iqreg in range(len(qregs)):
        qreg=qregs[iqreg]
        rows=qreg[1].split('\n')
        q=tonumeric(qreg[0]) # Quantile value
        assert len(rows)==len(vvars)
        for irow in range(len(rows)):
            sqReg[vvars[irow]]=sqReg.get(vvars[irow],{})
            ests=tonumeric(dict(zip(cols,[ss for ss in rows[irow].split('|')[1].split(' ') if ss])))
            for kk in ests: # Vectorise: place each estimate in its proper location in an array of length len(quantiles)
                sqReg[vvars[irow]][kk]=sqReg[vvars[irow]].get(kk,[])
                sqReg[vvars[irow]][kk]+=[ests[kk]]

            #amean[vvars[irow]]['N']=N

    # Now we have a data structure that contains all the estimates. Make a plot for each variable?
    import pylab as plt
    import matplotlib as mpl

    from cpblUtilities.mathgraph import plotWithEnvelope, savefigall

    plt.ioff() # Do not show plots

    for ivv in range(len(RHS))*int(not skipPlots):
        RHSvar=RHS[ivv]

        x=tonumeric(sqReg['quantiles'])
        y=sqReg[RHSvar]['coef']
        ciL,ciH=sqReg[RHSvar]['ciL'],sqReg[RHSvar]['ciH']

        plt.figure(ivv+1)
        plt.clf()
        ax=plt.gcf().add_subplot(111)

        ax.plot([min(x),max(x)],[0,0],'k') # Plot the zero line.
        plotWithEnvelope(x,y,ciL,ciH)#yLow,yHigh,facecolor='g',alpha=0.5):

        plt.axis('tight')
        plt.title(plotTitle%{'rhsv':RHSvar})
        plt.ylabel('Coefficient')
        plt.xlabel('quantile')
        assert name
        pfn=[ch for ch in name+'-'+RHSvar if ch.isalpha() or ch.isdigit() or ch in '-']####.replace(' ','')+'-'+''.join([ch for ch in RHSvar if (ch>='a' and ch<='z') or (ch>='A' and ch<='Z') or ch in '0123456789'])
        #plt.savefig(pfn+'.pdf',transparent=True)
        #plt.savefig(pfn+'.png')
        savefigall(pfn)

    return({'sqReg':sqReg})


























################################################################################################
################################################################################################
def parseQuantileRegression(logFile,plotTitle='%(rhsv)s',name=None,skipPlots=False,substitutions=None):
    ############################################################################################
    ############################################################################################
    """
    This is for single qreg, not sqreg (already written, separately).

     This parses output from Stata's qreg. It can deal with a string of them, giving a sequence of quantiles.


I may be able to do this much more robustly using my matrix reading function. Right now, if any variable is dropped as colinear, this function fails with an important assert.
Or... i may be able to get a list of the non-excluded variables, at least, from ereturn.

    """

    if '\n' in logFile: # logfile text must have been passed.
        logTxt=logFile
    else:
        logTxt=open(logFile+'.log','rt').read() # Should already have >\n's removed by stataSystem...
        print ' Parsing '+logFile+'.log'
   #

    qSequences=re.findall(r"""\s*.\s+CPBL BEGIN QUANTILE REGRESSION SERIES
(.*?)
\s*.\s+CPBL END QUANTILE REGRESSION SERIES""",logTxt,re.DOTALL)
    assert len(qSequences)==1
    qSequence=qSequences[0]

    regs=re.findall(r"""CPBL BEGIN MODEL.*?CPBL END MODEL""",qSequence,re.DOTALL)

    results={}
    vars=[]
    for areg in regs:
        checks= re.findall(r"""
\s*qreg\s+(\w*)(.*?),\s*quantile\((.*?)\)[^\n]*
.*?
([^\n]*) regression\s+Number of obs =\s+([^\n]*)
""",areg,re.DOTALL)
        assert len(checks)==1
        #print checks[0]
        quantile=tonumeric(checks[0][2])
        depvar=checks[0][0]
        #assert quantile==tonumeric(checks[0][3])
        results[quantile]= readStataEstimateResults(areg)
        vars+=results[quantile]['estcoefs'].keys()

    vars=uniqueInOrder(vars)
    quantiles=sorted(results.keys())
    qReg={'quantiles':quantiles}

    from pylab import array
    for rhsv in vars:
        vnew=substitutedNames(rhsv,subs=substitutions)
        qReg[vnew]={}
        for astat in ['b','p','se']:
            qReg[vnew][astat]=array(tonumeric([results[qq]['estcoefs'][rhsv][astat] for qq in quantiles]))
        qReg[vnew]['coef']=list(qReg[vnew]['b'])
        qReg[vnew]['ciH']=list(qReg[vnew]['coef']+qReg[vnew]['se']*1.96)
        qReg[vnew]['ciL']=list(qReg[vnew]['coef']-qReg[vnew]['se']*1.96)


    RHS=substitutedNames(vars,subs=substitutions)
    # Now we have a data structure that contains all the estimates. Make a plot for each variable?
    import pylab as plt
    import matplotlib as mpl

    from cpblUtilities.mathgraph import plotWithEnvelope, savefigall

    plt.ioff() # Do not show plots

    for ivv in range(len(RHS))*int(not skipPlots):
        RHSvar=RHS[ivv]

        x=tonumeric(qReg['quantiles'])
        y=qReg[RHSvar]['coef']
        ciL,ciH=qReg[RHSvar]['ciL'],qReg[RHSvar]['ciH']

        plt.figure(ivv+1)
        plt.clf()
        ax=plt.gcf().add_subplot(111)

        ax.plot([min(x),max(x)],[0,0],'k') # Plot the zero line.
        plotWithEnvelope(x,y,ciL,ciH)#yLow,yHigh,facecolor='g',alpha=0.5):

        plt.axis('tight')
        plt.title(plotTitle%{'rhsv':RHSvar})
        plt.ylabel('Coefficient')
        plt.xlabel('quantile')
        assert name
        pfn=name.replace(' ','')+'-'+''.join([ch for ch in RHSvar if ch.isalpha() or ch.isdigit()])#(ch>='a' and ch<='z') or (ch>='A' and ch<='Z') or ch in '0123456789'])
        #plt.savefig(pfn+'.pdf',transparent=True)
        #plt.savefig(pfn+'.png')
        savefigall(pfn)

    assert qReg
    return({'qReg':qReg})





################################################################################################
################################################################################################
def combineRegionsQuantileRegressionPlot(sqRegs,fileprefix=''):
    ############################################################################################
    ############################################################################################
    """
Plot the results of quantile regressions from possibly more than one model (region), to compare them.

"""

    if 1:

        # Now, make a figure showing all regions together for each variable... Here I adapt code from the parse sqreg code:
        regions=sqRegs.keys()
        from cpblUtilities import flattenList
        RHS=flattenList([[kk for kk in sqRegs[region].keys() if not kk=='quantiles'] for region in regions],unique=True)

        print '  Combining variables (',RHS,') and regions (',regions,')'
        assert len(regions)<6 # Or need to add more colours.
        fcolors=dict(zip(regions,'brgmc'[0:len(regions)]))
        # Now we have a data structure that contains all the estimates. Make a plot for each variable?
        import pylab as plt
        import matplotlib as mpl

        from cpblUtilities.mathgraph import plotWithEnvelope, savefigall

        plt.ioff() # Do not show plots

        for ivv in range(len(RHS)):
            """ Caution: maybe not all regions/models have this variable!"""
            RHSvar=RHS[ivv]
            x=tonumeric(sqRegs[sqRegs.keys()[0]]['quantiles'])
            plt.figure(ivv+1)
            plt.clf()
            ax=plt.gcf().add_subplot(111)
            ax.plot([min(x),max(x)],[0,0],'k') # Plot the zero line.

            LLs,PPs=[],[]
            regionsThisVar=[rr for rr in regions if RHSvar in sqRegs[rr]]
            for region in regionsThisVar:
                sqReg=sqRegs[region]
                if RHSvar not in sqReg:
                    continue

                y=sqReg[RHSvar]['coef']
                ciL,ciH=sqReg[RHSvar]['ciL'],sqReg[RHSvar]['ciH']


                LL,PP=plotWithEnvelope(x,y,ciL,ciH,facecolor=fcolors[region],alpha=0.3,label=region)#yLow,yHigh,facecolor='g',alpha=0.5):
                LLs+=[LL]
                PPs+=[PP]
            plt.axis('tight')
            plt.title(RHSvar)
            plt.ylabel('Coefficient')
            plt.xlabel('quantile')
            #plt.legend()
            plt.figlegend(PPs,regionsThisVar,'lower left')

            pfn=fileprefix+'all-'+''.join([ch for ch in RHSvar if ch.isalpha() or ch.isdigit()])#(ch>='a' and ch<='z') or (ch>='A' and ch<='Z') or ch in '0123456789'])
            savefigall(pfn)



def parseOaxacaCoefficientsAndMeans(logSection,expectVariableOrder=None):
    """
    used by parseOaxca to get supplementary info, ie parse the "xb" option of oaxaca command.

Coefficients (b) and means (x)
------------------------------------------------------------------------------
             |      Coef.   Std. Err.      z    P>|z|     [95% Conf. Interval]
-------------+----------------------------------------------------------------
b1           |
  lnHHincome |   .3831932   .0602414     6.36   0.000     .2651223    .5012641
highHHincome |  -.0994822   .0976263    -1.02   0.308    -.2908261    .0918618
        male |  -.1475246   .0614258    -2.40   0.016     -.267917   -.0271323
       _cons |          1          .        .       .            .           .
------------------------------------------------------------------------------

estimates table , varwidth(49) style(oneline) b se p stats(r2  r2_a N  N_1 N_2)

"""
    section=re.findall("""Coefficients .b. and means .x.(.*?)-------------------------+\n\n *estimates table """,logSection,re.DOTALL)
    assert expectVariableOrder # Don't yet have a default behaviour..
    assert len(section)==1
    pieces=re.findall('-------\+-+\n(.*?)\n------',section[0],re.DOTALL)
    bAndX={}
    for aKind in pieces: # Split into b1, b2, x1, x2, etc
        thekind=aKind.split('\n')[0].split(' ')[0]
        bAndX[thekind]={}
        for ii,aline in enumerate(aKind.split('\n')[1:]):
            words=[www for www in aline.split(' ') if www not in ['','|']]
            fullVarName=(expectVariableOrder+['_cons'])[ii]
            assert fullVarName.startswith(words[0].split('~')[0])

            bAndX[thekind][fullVarName]=dict(zip(['b','se','z','P','bmin','bmax'],words[1:]))
    return(tonumeric(bAndX))



################################################################################################
################################################################################################
def parseOaxacaDecomposition_statav13(logFile,plotTitle='%(rhsv)s',name=None,skipPlots=False,substitutions=None,titles=None,commonOrder=True,fileSuffixes=None,latex=None):
    ############################################################################################
    ############################################################################################
    """
    commonOrder=True means make the order of components the same as the first plot, if there are multiple plots.

    titles and fileSuffixes give lists of titles and filename suffixes for as many decompositions as are in the file.


    This is the function which makes a plot of the explained portion of the difference in a LHS variable between two groups, broken down by explanatory variables. It uses coefficients from a pooled model. The "explained" component is that due to differences in mean values, assuming common coefficients.

    June 2015: It seems the Oaxaca output has changed format at some point. I'm using Stata 14 now, so this is an update for recent versions 

    Stata oaxaca command: Using "pooled detail" options gives the breakdown we want to plot.
Rather than do the grouping by hand here, just use the dlist() option in the oaxaca command, which affects the "detail" output.

    """


    if '\n' in logFile: # logfile text must have been passed.
        logTxt=logFile
    else:
        stataLogFile_joinLines(logFile+'.log')
        logTxt=open(logFile+'.log','rt').read() # Should already have >\n's removed by stataSystem...
        print ' Parsing '+logFile+'.log'
   #

    qSequences=re.findall(r"""\s*.\s+CPBL BEGIN OAXACA DECOMPOSITION
(.*?
)\s*.\s+CPBL END OAXACA DECOMPOSITION""",logTxt,re.DOTALL)
    assert len(qSequences)>=1

    oax=[]
    for qSequence in qSequences:
        # Extract expected variable order (for stupid Stata truncation) from the regression call:
        expectedOrder=[ww for ww in qSequence.strip().split('\n')[0].split('[')[0].replace('(','').replace(')','').split(' ') if ww and not ww.endswith(':')][2:]
        oax+=[readEstimatesTable(qSequence)]
        #oax+=[readStataEstimateResults(logTxt)]
        checks= re.findall(r"""
\s*oaxaca\s+(\w*)(.*?),\s*by\(([^)]*?)\)([^\n]*)
.*?
\s*estimates table""",'\n'+qSequence,re.DOTALL)
        oax[-1]['oaxaca'].update({'options':checks[0][3],'depvar':checks[0][0]})

        # Record values of b and x from option "bx"
        oax[-1]['oaxaca'].update(parseOaxacaCoefficientsAndMeans(qSequence,expectVariableOrder=expectedOrder))


    assert titles==None or len(titles)==len(oax)
    if not fileSuffixes:
        fileSuffixes=['%d'%nn for nn in range(len(oax))]

    for ioaxaca in range(len(oax)):
        oaxaca=oax[ioaxaca]['oaxaca'] # Just one for now...
        if 'explained' in oaxaca:
            strExplained='explained'
        elif 'endowments' in oaxaca:
            strExplained='endowments'
        else:
            strExplained=None#'2015Unknown_oaxaca_stata'
        explained={}

        for kk in oaxaca[strExplained]:
            explained[substitutedNames(kk,subs=substitutions)]=deepcopy(oaxaca[strExplained][kk])

        model={'tableName':'test','modelNum':-1}
        depvar=oaxaca['depvar']
        subsamp='group1'
        basecase='group0'
        diffpredictions,sediffpredictions={subsamp:{}},{subsamp:{}}
        rhsvars=explained.keys()
        varsMovedToGroup=[]
        plotparams={}
        tooSmallToPlot={subsamp:[]}

        signSwitch= -2*( 'swap' in oaxaca['options']) +1


        difflhs={subsamp:signSwitch*oaxaca['overall']['difference']['b']}
        sedifflhs={subsamp:oaxaca['overall']['difference']['se']}
        from cpblUtilities.mathgraph import categoryBarPlot, savefigall, figureFontSetup
        from pylab import array
        diffpredictions[subsamp][depvar]=signSwitch*oaxaca['overall'][strExplained]['b']
        sediffpredictions[subsamp][depvar]=oaxaca['overall'][strExplained]['se']
        for vv in rhsvars:
            diffpredictions[subsamp][vv]=signSwitch*explained[vv]['b']
            sediffpredictions[subsamp][vv]=explained[vv]['se']


            diffpredictions[subsamp][depvar]=signSwitch*oaxaca['overall'][strExplained]['b']


        if 1:

            # NOW MAKE A PLOT OF THE FINDINGS: SUBSAMPLE DIFFERENCE ACCOUNTING
            import pylab as plt
            plt.ioff()
            figureFontSetup()
            plt.figure(217)
            plt.clf()
            if 1: # this seems redundant with plotvars!! get rid of rhsvars below????
                rhsvars.sort(key=lambda x:abs(diffpredictions[subsamp][x]))#abs(array([diffpredictions[subsamp][vv] for vv in rhsvars])))
                rhsvars.reverse()



            """
            What is the logic here? I want to
            - eliminate "constant".
            - order variables according to magnitude of effect, except if showvars specified.
            - let "showvars" specify order?? No. Order is always determined by magnitude.
            - include the grouped variables and not their contents
            """
            plotvars=[vv for vv in sediffpredictions[subsamp].keys() if not vv in varsMovedToGroup+[depvar,'constant']]#[vv for vv in rhsvars if vv not in varsMovedToGroup]+)#list(set(model['estcoefs'].keys())-(set(['_cons',])))

            #tooSmallToPlot=[abs(difffracs[subsamp][vv])<.05 for vv in rhsvars])

            #plotvars=[cv for cv in model['estcoefs'].keys()]
            # if 'hideVars' in plotparams:
            plotvars=[cv for cv in plotvars if cv not in plotparams.get('hideVars',[])]
            ###plotvars=[cv for cv in plotvars if cv not in ['constant']]
            #plotvars=[cv for cv in plotvars if cv not in plotparams['hideVars']]
            plotvars.sort(key=lambda x:abs(diffpredictions[subsamp][x]))#abs(array([diffpredictions[subsamp][vv] for vv in plotvars])))
            plotvars.reverse()
            if 'showVars' in plotparams:
                assert not 'groupVars' in plotparams # Haven't dealt wit hthis yet... If soeone is specifying groupings of variabesl in the plot, shall I ignore showvars???
                plotvars=[cv for cv in model['estcoefs'].keys() if cv in plotparams['showVars'] ]


            cutoffTooSmallToPlot=.01 # If you change this, change the %.2f below, too
            tooSmallToPlot[subsamp]+=[vv for vv in rhsvars if (abs(diffpredictions[subsamp][vv]) + 2*abs(sediffpredictions[subsamp][vv])) / abs(difflhs[subsamp]) < cutoffTooSmallToPlot and vv not in ['constant'] and vv in plotvars]

            omittedComments=''
            if tooSmallToPlot[subsamp]:
                omittedComments=' The following variables are not shown because their contribution was estimated with 95\\%% confidence to be less than %.2f of the predicted difference: %s. '%(cutoffTooSmallToPlot,'; '.join(tooSmallToPlot[subsamp]))
                plotvars=[cv for cv in plotvars if cv not in tooSmallToPlot[subsamp]]


            if commonOrder and ioaxaca>0:
                plotvars=lastPlotVars
            else:
                lastPlotVars=plotvars

            labelLoc='eitherSideOfZero'
            labelLoc=None#['left','right'][int(difflhs[subsamp]>0)]
            cbph=categoryBarPlot(array([r'$\Delta$'+depvar,r'predicted $\Delta$'+depvar]+plotvars),
        array([difflhs[subsamp],diffpredictions[subsamp][depvar]]  +  [diffpredictions[subsamp][vv] for vv in plotvars]),labelLoc=labelLoc,sortDecreasing=False,
        yerr=array( [sedifflhs[subsamp],sediffpredictions[subsamp][depvar]]+[sediffpredictions[subsamp][vv] for vv in plotvars])   ,barColour={r'$\Delta$'+depvar:defaults['colors']['darkgreen'],r'predicted $\Delta$'+depvar:defaults['colors']['green']})
            #plt.figlegend(yerr,['SS','ww'],'lower left')
            assert depvar in ['SWL','ladder','{\\em nation:}~ladder','lifeToday'] # depvar needs to be in the two lookup tables in following two lines:
            shortLHSname={'SWL':'SWL','lifeToday':'life today','ladder':'ladder','{\\em nation:}~ladder':'ladder'}[depvar]
            longLHSname={'SWL':'satisfaction with life (SWL)','lifeToday':'life today','ladder':'Cantril ladder','{\\em nation:}~ladder':'Cantril ladder'}[depvar]
            # Could put here translations

            xxx=plt.legend(cbph['bars'][0:3],[r'$\Delta$'+shortLHSname+' observed',r'$\Delta$'+shortLHSname+' explained','explained contribution'],{True:'lower left',False:'lower right'}[abs(plt.xlim()[0])>abs(plt.xlim()[1])])
            xxx.get_frame().set_alpha(0.5)

            #plt.setp(plt.gca(),'yticks',[])
            # Could you epxlain the following if??
            if plotparams.get('showTitle',False)==True:
                plt.title(model['name']+': '+subsamp+': differences from '+basecase)
                plt.title("Accounting for %s's life satisfaction difference from %s"%(subsamp,basecase))
                title=''
                caption=''
            else:
                title=r"Accounting for %s's life satisfaction difference from %s \ctDraftComment{(%s) col (%d)}"%(subsamp,basecase,model['tableName'],model['modelNum'])

                caption=title
            plt.xlabel(r'$\Delta$ %s'%shortLHSname)
            #plt.subtitle('Error bars show two standard error widths')

            plt.xlabel('mean and explained difference in '+longLHSname)
            plt.ylim(-1,len(plotvars)+3) # Give just one bar space on top and bottom.
            #plt.ylim(array(plt.ylim())+array([-1,1]))

            if commonOrder and ioaxaca>0:
                plt.xlim(lastPlotXlim)
            else:
                lastPlotXlim=plt.xlim()
            # Save without titles:
            # Plots need redoing?
            needReplacePlot=fileOlderThan(paths['graphics']+name+'-%s.png'%fileSuffixes[ioaxaca],logFile+'.log')
            # May 2011: logic below not well tested! Well, I don't think it does anything, and skipstata is inappropriate use.
            if latex is None and needReplacePlot:
                savefigall(paths['graphics']+name+'-%s'%fileSuffixes[ioaxaca])
            elif needReplacePlot or not latex.skipStataForCompletedTables:

                latex.saveAndIncludeFig(name+'-%s'%fileSuffixes[ioaxaca],caption=None,texwidth=None,title=None, # It seems title is not used!
                          onlyPNG=False,rcparams=None,transparent=False,
                          ifany=None,fig=None,skipIfExists=False,pauseForMissing=True)
            if titles:
                plt.title(titles[ioaxaca])
            #self.saveAndIncludeFig(figname=str2pathname('%s-%02d%s-%sV%s'%(model['tableName'],model['modelNum'],model['name'],subsamp,basecase)),title=title,caption=caption+'.\n '+r' Error bars show $\pm$1 s.e.  '+plotparams.get('comments','')+vgroupComments+omittedComments,texwidth='1.0\\textwidth') #model.get('subSumPlotParams',{})

            # And store all this so that the caller could recreate a custom version of the plot (or else allow passing of plot parameters.. or a function for plotting...? Maybe if a function is offered, call that here...? So, if regTable returns model as well as TeX code, this can go back to caller. (pass pointer?)
            if 'accountingPlot' not in model:
                model['accountingPlot']={}
            model['accountingPlot'][subsamp]={'labels':array(rhsvars+['predicted '+depvar,depvar]),
        'y':array( [diffpredictions[subsamp][vv] for vv in rhsvars]+[diffpredictions[subsamp][depvar],difflhs[subsamp]]),
        'yerr':array( [sediffpredictions[subsamp][vv] for vv in rhsvars]+[sediffpredictions[subsamp][depvar],sedifflhs[subsamp]])
        }


def compareMeansByGroup(vars,latex=None):
    pass # Placeholder for now; see cpblstatalatex.


def oaxacaThreeWays_generate(model,
            groupConditions,
            groupNames,
            referenceModel=None,
            referenceModelName=None,
            oaxacaOptions=None,
            dlist=None,                             ):
    # Used/called by latex.oaxacaThreeWays(
    statacode="""
    capture drop oaxGroup
    """
    if not oaxacaOptions:
         oaxacaOptions=' '
    outs="""
    capture drop oaxGroup
    """
    #assert len(groupConditions)== len(groupNames)
    assert len(groupNames)==2
    if len(groupConditions)==1:
        outs+="""
        * Groups: """+str(groupNames)+"""
        gen oaxGroup = 1+ ~("""+groupConditions[0]+""")
        """
    else:
        assert len(groupConditions)==2
        outs+="""
        * Groups: """+str(groupNames)+"""
        gen oaxGroup = 1 if """+groupConditions[0]+"""
        replace oaxGroup = 2 if """+groupConditions[1]+"""
        """
    depvar=[vv for vv in model.split(' ') if vv][0]
    weightstring= re.findall('\[.*?\]',model)
    weightstring= '' if not weightstring else weightstring[0]
    outs+="""
    * CPBL BEGIN MEAN SINGLE
    *name:"""+groupNames[0]+"""
    mean """+ depvar+ ' if oaxGroup ==1 '+weightstring+ """
    * CPBL END MEAN SINGLE
    * CPBL BEGIN MEAN SINGLE
    *name:"""+groupNames[1]+"""
    mean """+ depvar+ ' if oaxGroup ==2 '+weightstring+ """
    * CPBL END MEAN SINGLE
    """


    dlist='' if dlist is None else '(%s)'%dlist
    # 2015June: added "detail" below, which in Stata14 gives the breakdown of explained components by RHS variable. Isn't this what I always intended, ie what was given before by default?
    outs+="""
    """+'\n'.join(["""
* CPBL BEGIN BLINDER-OAXACA DECOMPOSITION
*flag:Reference model="""+name+"""
oaxaca """+model+""", by(oaxGroup) xb %s %s                       detail%s

estimates table , varwidth(49) style(oneline) b se p stats(r2  r2_a N  N_1 N_2)
* CPBL END BLINDER-OAXACA DECOMPOSITION
"""%(options,oaxacaOptions,dlist) for options,name in [['pooled','pooled'],['',groupNames[0]],['swap',groupNames[1]]]])+"""
"""
    # Note: in above, default (no pooled/omega/swap arguments) is the "threefold decomposition from the viewpoint of group 2"
    if referenceModel:
        assert referenceModelName
        outs+="""
* Reference model for subsequent Blinder-Oaxaca:"""+referenceModelName+"""
capture estimates drop oaxEstStore
reg """+referenceModel+"""
estimates store oaxEstStore
* CPBL BEGIN BLINDER-OAXACA DECOMPOSITION
*flag:Reference model="""+referenceModelName+"""
oaxaca """+model+""", by(oaxGroup) xb reference(oaxEstStore) """+oaxacaOptions+"""
estimates table , varwidth(49) style(oneline) b se p stats(r2  r2_a N  N_1 N_2)
* CPBL END BLINDER-OAXACA DECOMPOSITION
"""

    return(outs)

def oaxacaThreeWays_parse(logFile,latex=None,substitutions=None):#substitutions):#,skipPlots=False,
    """
To do:
  - Need to reimplement (some? any? of) the options that used to be in this call. Ideally, these should be encoded into the log file rathre than passed around.

#          oaxx=parseOaxacaDecomposition(logFile,plotTitle='%(rhsv)s',name=name,skipPlots=False,substitutions=substitutions,titles=[groupNames[0]+' vs '+groupNames[1]+' using %s estimates'%ss for ss in ['pooled',groupNames[0],groupNames[1]]+(not referenceModel ==None)*[referenceModelName]],fileSuffixes=['using'+nn.replace(' ','') for nn in ['pooled',groupNames[0],groupNames[1]]+(not referenceModel ==None)*[referenceModelName]],commonOrder=commonOrder,latex=latex)


    # Used/called by latex.oaxacaThreeWays()
    Parse Stata output for code made by oaxacaThreeWays_generate(), almost certainly via latex.oaxacaThreeWays()
    """
    # Some not-yet-implemented options which need implementing into the log file...
#    plotTitle='%(rhsv)s'    ,,titles=[groupNames[0]+' vs '+groupNames[1]+' using %s estimates'%ss for ss in ['pooled',groupNames[0],groupNames[1]]+(not referenceModel ==None)*[referenceModelName]],fileSuffixes=['using'+nn.replace(' ','') for nn in ['pooled',groupNames[0],groupNames[1]]+(not referenceModel ==None)*[referenceModelName]],commonOrder=commonOrder,

    
    if '\n' in logFile: # logfile text must have been passed.
        logTxt=logFile
    else:
        stataLogFile_joinLines(logFile+'.log')
        logTxt=open(logFile+'.log','rt').read() # Should already have >\n's removed by stataSystem...
        print ' Parsing blinder-oaxacaThreeways file '+logFile+'.log'


    # Parse MEANS by group:
    means=statameans_parse(logFile)
    meansbyn=dict([[DD['name'],DD ] for DD in means])

    # Parse three Blinder-Oaxaca estimates:
    qSequences=re.findall(r"""\s*.\s+CPBL BEGIN BLINDER-OAXACA DECOMPOSITION
(.*?
)\s*.\s+CPBL END BLINDER-OAXACA DECOMPOSITION""",logTxt,re.DOTALL)
    if not  len(qSequences)>=1:
        print('  BLINDER-OAXACA FAILED to parse the log file. Stata may have failed. INVESTIGATE. Aborting...')
        return([])

    oax=[]
    for qSequence in qSequences:
        extrafields=parseStataComments(qSequence)
        # Extract expected variable order (for stupid Stata truncation) from the regression call:
        expectedOrder=[ww for ww in qSequence.strip().split('\n')[1].split('[')[0].replace('(','').replace(')','').split(' ') if ww and not ww.endswith(':')][2:]
        estT=readEstimatesTable(qSequence) # This comes back with most measures buried in 'oaxaca' field. Collapse levels (there should be no overwriting...):
        assert not any([kk in estT for kk in estT['oaxaca'].keys() ])
        estT.update(estT['oaxaca'])
        oax+=[dict([[kk,vv] for kk,vv in estT.items() if not kk=='oaxaca'])]
        #oax+=[readStataEstimateResults(logTxt)]
        checks= re.findall(r"""
\s*oaxaca\s+(\w*)(.*?),\s*by\(([^)]*?)\)([^\n]*)
.*?
\s*estimates table""",'\n'+qSequence,re.DOTALL)
        oax[-1].update({'options':checks[0][3],'depvar':checks[0][0]})

        # Record values of b and x from option "bx"
        oax[-1].update(parseOaxacaCoefficientsAndMeans(qSequence,expectVariableOrder=expectedOrder))

        oax[-1]['Reference model']=extrafields['flags']['Reference model']


    #assert titles==None or len(titles)==len(oax)
    #if not fileSuffixes:
    #   fileSuffixes=['%d'%nn for nn in range(len(oax))]

    # Stata output has changed by version.
    stataws={'older': {'version':'older',
                       'overall':'overall',
                       'difference':'difference',
                       'explained':'explained',
                       'endowments':'endowments',
                       'predictedDifference':'explained',
                       },
             'v14': {'version':'14+',
                     'overall':'Differential',
                       'difference':'Difference',
                       'explained':'Explained',
                       'endowments':'Endowments',
                       'predictedDifference':'Difference',
                       }
             }
    stataws=stataws['v14'] # newer version, ie iff 'Explained' in oaxaca

    models=[]

    for ioaxaca in range(len(oax)):
        oaxaca=oax[ioaxaca] # Just one for now...
        if stataws['explained'] in oaxaca: # For "pooled" (or omega) option in oaxaca command
            strExplained=stataws['explained']
        elif stataws['endowments'] in oaxaca: # For non-"pooled" (or omega) option case in oaxaca command
            strExplained=stataws['endowments']
        else:
            strExplained=None#'2015Unknown_oaxaca_stata'

        explained={}
        for kk in oaxaca[strExplained]:
            explained[substitutedNames(kk,subs=substitutions)]=deepcopy(oaxaca[strExplained][kk])
            ###explained[kk]=deepcopy(oaxaca[strExplained][kk])

        model={'name':oaxaca['Reference model'],'modelNum':-1,'means':means}
        depvar=oaxaca['depvar']
        subsamp='group1'
        basecase=oaxaca['Reference model'] # 'group0'
        diffpredictions,sediffpredictions={subsamp:{}},{subsamp:{}}
        rhsvars=explained.keys()
        varsMovedToGroup=[]
        plotparams={}
        tooSmallToPlot={subsamp:[]}
        
        signSwitch= -2*( 'swap' in oaxaca['options']) +1

        if 0: print( [[kk,oaxaca[kk].keys()] for kk in oaxaca if isinstance(oaxaca[kk],dict)])

        # Get the overall explained component of the LHS variable:
        #difflhs={subsamp:signSwitch*oaxaca[stataws['overall']][stataws['difference']]['b']}
        #sedifflhs={subsamp:oaxaca[stataws['overall']][stataws['difference']]['se']}
        from cpblUtilities.mathgraph import seSum
        difflhs,sedifflhs=seSum([means[0]['mean'], -means[1]['mean']],    [means[0]['sem'],means[1]['sem']])

        
        from cpblUtilities.mathgraph import categoryBarPlot, savefigall, figureFontSetup
        from pylab import array
        #diffpredictions[subsamp][depvar]=signSwitch*oaxaca[stataws['overall']][stataws['predictedDifference']]['b']
        #sediffpredictions[subsamp][depvar]=oaxaca[stataws['overall']][stataws['predictedDifference']]['se']
        for vv in rhsvars:
            diffpredictions[subsamp][vv]=signSwitch*explained[vv]['b']
            sediffpredictions[subsamp][vv]=explained[vv]['se']

        model.update({'depvar':depvar, 'subsamp':subsamp,'basecase':basecase,
                  'diffLHS':difflhs, 'diffLHS_se':sedifflhs,'diffpredictions':diffpredictions,'diffpredictions_se':sediffpredictions, 'rawdetails':oax[ioaxaca]})
        models+=[model]
    return(models)

    
def oaxacaThreeWays_pre2015(model,groupConditions,groupNames,name=None,preamble='',referenceModel=None,referenceModelName=None,savedModel=None,oaxacaOptions=None,dlist=None,rerun=True,substitutions=None,commonOrder=True,latex=None):
    """
    This makes the call and parses the results for oaxaca decomposition.
    groupConditions can be a single condition c, in which case (not c) is the other group. Or it can be a list of two conditions, in which case the first is the base case.

    What about a fourth way, which is to use a global regression larger than the two groups?? If savedModel is specified, then the saved coefficients from that will be used. (not done yet).  If referenceModel is specified, then the model will be run, coefficients saved and used as a reference, in the fourth case.

    May 2011: added latex=None, takes a latexregressions object

    May 2011: Now I'm after comparing means for two groups in a table (hm, and ultimately testing whether they're different. Is Oaxaca an easy way to do this? Well, no. For simplicity (?) / independence, I'm just going to do it by calling many many means. and tests?

    June 2015: It seems in StataV14 we no longer get the mean SWL reported by groups. So I need to do that separately.
    The new approach here is going to be to separate creating Stata code from both parsing the log and making plots (just like for other regressions). So any time the log file parser comes across a Oaxaca, it should make a plot of decomposition.
    In this approach, as for regression tables, a log file corresponds solely to the contents of this function.   As  a result, it should become standard practice to include the loading of data as part of each table code, so that the file loading is always in the same log as the table.
    Ultimately, we should separate the creation of the Stata code from the parsing of the log files. So this "oaxacaThreeWays" should depend on oaxacaThreeWays_generate and oaxacaThreeWays_parse. This paired function pattern should exist for regressions, means, etc too.
    """
    if not oaxacaOptions:
         oaxacaOptions=' '
    logFile=defaults['paths']['tex']+name
    outs=preamble+"""
    capture drop oaxGroup
    """
    #assert len(groupConditions)== len(groupNames)
    assert len(groupNames)==2
    if len(groupConditions)==1:
        outs+="""
        * Groups: """+str(groupNames)+"""
        gen oaxGroup = ~("""+groupConditions[0]+""")
        """
    else:
        assert len(groupConditions)==2
        outs+="""
        * Groups: """+str(groupNames)+"""
        gen oaxGroup = 1 if """+groupConditions[0]+"""
        replace oaxGroup = 2 if """+groupConditions[1]+"""
        """

    dlist='' if dlist is None else '(%s)'%dlist
    # 2015June: added "detail" below, which in Stata14 gives the breakdown of explained components by RHS variable. Isn't this what I always intended, ie what was given before by default?
    outs+="""
    """+'\n'.join(["""
* CPBL BEGIN OAXACA DECOMPOSITION

oaxaca """+model+""", by(oaxGroup) xb %s %s                       detail%s

estimates table , varwidth(49) style(oneline) b se p stats(r2  r2_a N  N_1 N_2)
* CPBL END OAXACA DECOMPOSITION
"""%(options,oaxacaOptions,dlist) for options in ['pooled','','swap']])+"""


"""
    if referenceModel:
        assert referenceModelName
        outs+="""
* Reference model for next oaxaca: """+referenceModelName+"""
capture estimates drop oaxEstStore
reg """+referenceModel+"""
estimates store oaxEstStore
* CPBL BEGIN OAXACA DECOMPOSITION
oaxaca """+model+""", by(oaxGroup) xb reference(oaxEstStore) """+oaxacaOptions+"""
estimates table , varwidth(49) style(oneline) b se p stats(r2  r2_a N  N_1 N_2)
* CPBL END OAXACA DECOMPOSITION
"""


    if latex is None or not latex.skipStataForCompletedTables:
        stataSystem(outs)
        
    if os.path.exists(logFile+'.log'):
      oaxx=parseOaxacaDecomposition(logFile,plotTitle='%(rhsv)s',name=name,skipPlots=False,substitutions=substitutions,titles=[groupNames[0]+' vs '+groupNames[1]+' using %s estimates'%ss for ss in ['pooled',groupNames[0],groupNames[1]]+(not referenceModel ==None)*[referenceModelName]],fileSuffixes=['using'+nn.replace(' ','') for nn in ['pooled',groupNames[0],groupNames[1]]+(not referenceModel ==None)*[referenceModelName]],commonOrder=commonOrder,latex=latex)
      # Now here do a table of all three for comparison. Also do table for b' and x'



    # If Stata has been run, parse the results. Then make a plot.
    parseOaxacaDecomposition(logFile,plotTitle='tmppp',name='Decomposition of mean difference')#,plotTitle='%(rhsv)s',name=None,skipPlots=False,substitutions=None,titles=None,commonOrder=True,fileSuffixes=None,latex=None)




    fooooooooooo
    if not os.path.exists(logFile+'.log') or (latex is None and rerun) or (latex is not None and latex.skipStataForCompletedTables==False):
      #stataSystem(outs,filename=logFile)
      return(outs)


    return('')



def loadStataDataNumpy(DTAfile,onlyVars=None,forceUpdate=False,ifClause=None,suffix=None,allowNonexistingVariables=False,extraStataCode='',dtypeoverrides=None):#treeKeys=None,vectors=False,singletLeaves=False,
    """
    Needs editing to finish transform to numpy.

    Since I've learned about structured lists in numpy, my dictTrees (or at least) vectors are obselete. So this should replace loadStataDataForPlotting, although they could be merged to give dict option still.

    Normal call for this function will be:

    df=pd.DataFrame(loadStataDataNumpy(WP+'tmp-allCCHS-somedetails1'))

Ahh! This now allows overrides of format for variables that are tricky, e.g. strings. Hm, but my tonumeric used to do that before...  is this really better? I could always use my old code, but put the result into a structured array.

I think my solution is that if I want to have a smarter method, I can do the double-loading trick, ie write a wrapper around from_txt that loads once without specifying dtypes, and then only overrides ones that are chosen (or even uses my tonumeric to determine it, if you like!)

Jan 2013: testing new pandas routine without dataoverrieds... let's see how it does.

2013: March : I need an option for it to treat blanks as a blank for strings, not a nan.?
    """

    import numpy as np

    #assert not singletLeaves or treeKeys
    ifClause=' ' if ifClause is None else ' if '+ifClause
    if not onlyVars:
        onlyVars=''
    elif isinstance(onlyVars,basestring):
        onlyVars=' '.join(uniqueInOrder([vv for vv in onlyVars.split(' ') if vv]))
    elif isinstance(onlyVars,list):
        onlyVars=' '.join(uniqueInOrder(onlyVars))
    sSuffix=''
    if not suffix==None:
        sSuffix=('-')*(not suffix.startswith('-'))+suffix
    import random
    randomsuffix=(forceUpdate=='parallel') * ('-TMP'+ ''.join(random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ') for x in range(6)))

    tsvF=WP+'TMP-'+stripWPdta(DTAfile)+sSuffix+randomsuffix+'.tsv'
    #shelfF=WP+'TMP-'+stripWPdta(DTAfile)+sSuffix+'.pyshelf'
    npF=WP+'TMP-'+stripWPdta(DTAfile)+sSuffix+'.pandas' # This will be compressed in the future!
    #if isinstance(treeKeys,basestring):
    #	    treeKeys=treeKeys.split(' ')

    if defaults['mode'] in ['gallup','rdc']:

        from cpblMake import cpblRequire
        cpblRequire(WPdta(DTAfile))

    import pandas as pd 
    # If anything needs updating, do it all: create text from Stata, and pandas from text:
    if fileOlderThan([tsvF],WPdta(DTAfile)) or forceUpdate:
        stataSystem(stataLoad(WPdta(DTAfile))+'\n'+extraStataCode+"""
        capture drop _merge*
        """+allowNonexistingVariables*('\n'.join(['capture noisily gen %s=.'%ovv for ovv in onlyVars.split(' ')]))+"""
        outsheet """+onlyVars+ifClause+""" using """+tsvF+""", noquote replace nolabel
        """,filename='dta2tsv'+sSuffix+'-'+stripWPdta(DTAfile))

    if fileOlderThan([npF],WPdta(DTAfile)) or forceUpdate:

        #indata=np.genfromtxt(tsvF, delimiter='\t',names=True,dtype=None)
        dataDF=pd.read_table(tsvF)
        if dtypeoverrides:
            dt=dict(dataDF.dtypes)
            dtypeoverrides=dict([kk,np.dtype(vv)] for kk,vv in dtypeoverrides.items())
            dt.update(dtypeoverrides)
            dataDF=pd.read_table(tsvF,dtype=dt)
            """
           dd=indata.dtype
           print dd
           dd=[(name,dtypeoverrides.get(name,dd[name])) for name in dd.names]
           print dd
           indata=np.genfromtxt(tsvF, delimiter='\t',names=True,dtype=dd)

           labels = np.genfromtxt(tsvF, delimiter='\t', dtype=None)  # Find default types.
            raw_data = np.genfromtxt('data.txt', delimiter=',')[:,1:]
            data = {label: row for label, row in zip(labels, raw_data)}
            """

        dataDF.to_pickle(npF)#np.save(npF,indata)
        returnVal=dataDF
    else:
        print 'Loading '+npF+'...',
        returnVal=pd.read_pickle(npF)#np.load(npF)  # DataFrame.
        print ' [Done] '
    return(returnVal)



def loadStataDataForPlotting(DTAfile,treeKeys=None,onlyVars=None,vectors=False,forceUpdate=False,singletLeaves=False,ifClause=None,suffix=None,allowNonexistingVariables=False,extraStataCode=''):
    """

(JAn 2013): Don't I usually want data in pandas format? So see new loadStataDataNumpy, which is not yet equally as good.

(April2010:  See loadMacroData in masterPrepareSurveys!!! Which stuff should go in pystata and which in masterPrepareSurveys???)

    Export DTA as TSV and load into Python for matplotlib....
    March 2010

So, this is a useful general tool for loading a Stata file, and so it should be in pystata.py. However, whenever you are loading macro data from standard surveys with some CR details and for years for which I have full census infos, you should instead use the loadMacroData() function in masterPrepareSurveys, which is more specific but nicer.

(Hm, Why am I treating the DTA as the file of record? I should just make sure that tsvs get made for census and survey means...)

forceUpdate=False means that if the tmp file already exists and is newer than the DTA, don't remake it from the DTA!!  I am using this to load data straight from the micro survey file now (May 2010) in order to calculate/plot CDFs straight in Python. forceupdate='parallel' means assume we're running on a very parallel machine, and must protect against any multiple-use of filenames for tsv or shelve.

singletLeaves changes each leaf from a single-element list of dict to the single dict. So it had better be that the "treeKeys" are specified and fully separate (identify) each record!

suffix is used to specify a filename suffix to differentiate the derived files from any other derived files from the same DTAfile.

August 2010: Make extra facility for using shelve? Should make it only use this if file big.

August 2010: Also, to avoid danger of using same tsv file to with different treeKeys, do not allow reuse of Shelf file if "suffix" has not been specified!!

May 2011: Adding robustness to non-existence of some variables ie. any requested variable is created as NaNs if it doesn't exist. . Uh.. no, make this a default-off option, actually.. allowNonexistingVariables=False):

2012 Aug: this is dangerous if parallel processing is being used, because tsv and shelf files could be written simultaneously.

    """
    assert not singletLeaves or treeKeys
    ifClause={None:''}.get(ifClause,ifClause)
    if not onlyVars:
        onlyVars=''
    elif isinstance(onlyVars,basestring):
        onlyVars=' '.join(uniqueInOrder([vv for vv in onlyVars.split(' ') if vv]))
    elif isinstance(onlyVars,list):
        onlyVars=' '.join(uniqueInOrder(onlyVars))
    sSuffix=''
    if not suffix==None:
        sSuffix=('-')*(not suffix.startswith('-'))+suffix
    import random
    randomsuffix=(forceUpdate=='parallel') * ('-TMP'+ ''.join(random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ') for x in range(6)))
    tsvF=WP+'TMP-'+stripWPdta(DTAfile)+sSuffix+randomsuffix+'.tsv'
    shelfF=WP+'TMP-'+stripWPdta(DTAfile)+sSuffix+'.pyshelf'
    if isinstance(treeKeys,basestring):
        treeKeys=treeKeys.split(' ')

    if defaults['mode'] in ['gallup','rdc']:

        from cpblMake import cpblRequire
        cpblRequire(WPdta(DTAfile))

    if fileOlderThan([tsvF,shelfF],WPdta(DTAfile)) or forceUpdate:
        stataSystem(stataLoad(WPdta(DTAfile))+'\n'+extraStataCode+"""
        capture drop _merge*
        """+allowNonexistingVariables*('\n'.join(['capture noisily gen %s=.'%ovv for ovv in onlyVars.split(' ')]))+"""
        outsheet """+onlyVars+' '+ifClause+""" using """+tsvF+""", noquote replace nolabel
        """,filename='dta2tsv'+sSuffix+'-'+stripWPdta(DTAfile))

        # If the file is big, proceed (not yet implemented)
        if 1:
            uidheaders=[hh for hh in open(tsvF,'rt').readline().strip().split('\t') if hh.endswith('uid')]
            #print uidheaders
            # Agh!! I changed dataRow=2 to dataRow=1 in April 2010. Why was it =2??
            print 'Parsing '+tsvF+'...'
            returnVal=tonumeric(tsvToDict(tsvF,keyRow=0,dataRow=1,formatRow=None,vectors=vectors,replaceHeaders=[],utf8=False,treeKeys=treeKeys,singletLeaves=singletLeaves),skipkeys=uidheaders,nokeys=True)  #headerFormats=dict([[hh,'%s'] for hh in uidheaders])
            #from pylab import isfinite

        if (fileOlderThan(shelfF,tsvF) or forceUpdate or suffix==None) and forceUpdate not in ['parallel']:
            print 'Creating '+shelfF+'...'
            shelfSave(shelfF,returnVal)
    else:
            print 'Loading '+shelfF+'...'
            returnVal=shelfLoad(shelfF)
    return(returnVal)

def runBatchSet(sVersion,rVersion,stataCodeFunction,dVersion=None,mainDataFile=None,compileLaTeX=True, skipStataForCompletedTables=False,variableOrder=None,substitutions=None,parallel=None,offsetsSeconds=None,forceStata=False, autoYes=False): #,runStata=None):
    """
April 2010:  do the generic sequence of running code, compiling, etc.
This is poorly named so far...

So this takes a function which produces stata code and pystata's stataLaTeXclass objects and generates a PDF with pretty tables of the results.


mainDataFile: this is a .dta.gz file that will be used for desc stats.

sVersion:
rVersion:
dVersion:

June 2010: Add a feature... if latexfile set up


Aug 2012: Implmenting parallel processing to do all the functions, and then all their Stata code, in parallel on large multiprocessor server.   I don't think I can pass instances of latexStataclass around (something in there is not pickleable??!) through Queues, so I've built another way to compile the TeX code from functions that are run separately; each gets its own latexregressionfile instance, and then the TeX bodies get put together into one central latexregressionfile instance. It's working rather nicely!

Aug 2012: This is already a mess. Rewrite a parallel version from scratch, in which stata code gets launched as soon as a funciton is done (if desired, by asking in advance, or by the auto decision option), but the tex code gets collected appropriate to make a single PDF. That needs queues...?

Aug 2012. If a list of statacode is returned, rather than a string, then they should be treated as parallelizable.
"""


    def stataCodeWrapper(SCF,sVersion,rVersion,substitutions,runCode=False): # Agh. I'm making this so as to avoid passing latex objects through the Queue, since they cannot !?!? be pickled. It simply wraps a runBatchSet-eligible function and gives it its own, unique latexRegressionFile object.
        alatex=latexRegressionFile('tablesPreview',modelVersion=sVersion,regressionVersion=rVersion,substitutions=substitutions,texNameSuffix=SCF.func_name)
        statacodeout=SCF(alatex)
        if runCode:
            print(' Process %s: Starting Stata ..'%SCF.func_name)
            stataSystem(statacodeout,filename='regressions-%s-%s-%s'%(sVersion,rVersion,SCF.func_name))

        return(statacodeout*(not runCode),alatex.fpathname,alatex.getTeXcode())


    if not dVersion:
        dVersion=''
    if parallel is None:
        parallel = defaults['server']['parallel']


    texNameSuffix=''

    if not isinstance(stataCodeFunction,list):
        stataCodeFunction=[stataCodeFunction]

    def updateLF(LF):
        LF.captureNoObservations=True # This is now costless, a no brainer..
        if mainDataFile:
            LF.updateSettings(mainDataFile=mainDataFile,recreateCodebook=None)
        if skipStataForCompletedTables:
            LF.skipStataForCompletedTables=True
        if variableOrder is not None:
            LF.variableOrder=variableOrder

        if len (stataCodeFunction)>3:
          LF.compactPreview=False
          LF.append(r'\tableofcontents'+'\n')
        else:
          LF.append(r"""
          Functions included:
          \begin{itemize}
          """+'\n'.join([r'\item '+str2latex(fff.func_name) for fff in stataCodeFunction])+"""
          \end{itemize}
          """)

    # Create a latexfile instance for all output. (or one per function if we're doing them in parallel!)
    from .latexRegressions import latexRegressionFile
    latexfile=latexRegressionFile( 'tablesPreview',modelVersion=sVersion,regressionVersion=rVersion,substitutions=substitutions,texNameSuffix=texNameSuffix)
    updateLF(latexfile)
    lastLF='0'
    latexfiles={'0':latexfile}

    stataDone=False
    if  parallel  and isinstance(stataCodeFunction,list) and  len(stataCodeFunction)>1:
        runCode= latexfile.skipStataForCompletedTables or forceStata
        rfip=runFunctionsInParallel([[stataCodeWrapper,[fff,sVersion,rVersion,substitutions],{'runCode':runCode}] for fff in stataCodeFunction],names=[fff.func_name for fff in stataCodeFunction],offsetsSeconds=offsetsSeconds,expectNonzeroExit=True)
        success,stataCodesAndTex=rfip
        if runCode:
            stataDone=True
        print ' --- Finished all parallel jobs; working on processing ---'
        for isscc, sscc in enumerate(stataCodesAndTex):
            if sscc is None:
                stataCodesAndTex[isscc]='','','(Parallel run of this function failed.)'
        stataCodes=[([doHeader+asc for asc in sscc[0]] if isinstance(sscc[0],list) else doHeader+sscc[0]) if sscc[0] else '' for sscc in stataCodesAndTex ]
        latexfiles=[sscc[1] for sscc in stataCodesAndTex]
        latexCode=['\n\n'+r'\section{%s}'%str2latex(stataCodeFunction[iii].func_name)+sscc[2] for iii,sscc in enumerate(stataCodesAndTex)]
        latexfile.append('\n'.join(latexCode))

    else:
        stataCodes=[]
        for fff in stataCodeFunction:
            if not latexfile.compactPreview:
                latexfile.append('\n\\section{'+str2latex(fff.func_name)+'()}\n')
            print( 'Run-Batch-Set initiating function: ',fff)
            stataCodes.append(fff(latexfile))

    if mainDataFile and not parallel: # !!! Not implemented yet for parallel case...
        print latexfiles[lastLF].addDescriptiveStatistics(dataFile=mainDataFile,logname='someStats-testing',codebook=None,showVars=latexfile.variablesUsed+' lnGDPpc  SWL lifeToday donatedMoney cannotAffordFood ',weightVar=None,ifcondition=' 1',forceUpdate=False)#,mainSurvey=None)

    if compileLaTeX:
        latexfile.closeAndCompile()
    else:
        latexfile.closeAndCompile(closeOnly=True)

    if  latexfile.usingDisclosedData:
        print 'Not running Stata, since latex object is is usingDisclosedData mode '
        return()
    if latexfile.skipStataForCompletedTables:
            print '   Automatically running Stata, since skipStataForCompletedTables==True and it might be quite fast!'

    if not stataDone and ((latexfile.skipStataForCompletedTables  and not latexfile.usingDisclosedData )  or (defaults['server']['islinux'] and (autoYes or ('yes'==raw_input('Run stata as batch?  (say "yes")'))))): #or runStata
        if parallel:
            funcNames=[fff.func_name for fff in stataCodeFunction]
            offsets=deepcopy(offsetsSeconds)

            runFunctionsInParallel([ [stataSystem,[stataCodes[iii]],{'filename':'regressions-%s-%s-%s-%s'%(sVersion,rVersion,dVersion,fff.func_name)}] for iii,fff in enumerate(stataCodeFunction)], names=[fff.func_name for fff in stataCodeFunction],offsetsSeconds=offsetsSeconds, expectNonzeroExit=True)
        else:
            stataSystem(stataCodes,filename='regressions-%s-%s-%s'%(sVersion,rVersion,dVersion))
    return()


















def WPdta(ff):
    """ put prefix and suffix onto a filename"""
    if not os.path.split(ff)[0]:
        ff=WP+ff
    if not os.path.splitext(ff)[1] or os.path.splitext(ff)[1] not in ['.tsv','.csv','.dta','.txt','.gz']:
        ff+='.dta.gz'
    return(ff)
def stripWPdta(ff):
    """ ensure path (not just WP?) and suffix are stripped from a filename"""
    assert not os.path.split(ff)[0] or ff.startswith(WP)
    ff= os.path.split(ff)[1]
    if ff.endswith('.dta.gz'):
        ff=ff[:-7]
    return(ff)
def WPpd(ff):
    """ put prefix and suffix onto a filename"""
    if not os.path.split(ff)[0]:
        ff=WP+ff
    if not os.path.splitext(ff)[1] or os.path.splitext(ff)[1] not in ['.tsv','.csv','.dta','.txt','.gz','pd','pandas','pyshelf']:
        ff+='.pandas'
    return(ff)




############################################################################################################
#
def estimateGini(stataFile,subsetVar=None,subsetValues=None,incomeVars=None,giniPrefix='gini',outfile=None,opts=None):#,giniVar=None
    #
    ##########################################################################
    """
August 2010: these estimates are incredibly slow (bootstrapping errors??), so I had better do them separately.  Thus I intend to replace my "addGini" with this, which will make a new macro file. I'm also getting rid of giniVar, in favour of giniPrefix.


CPBL. summer 2010.
subsetVar=None:  If not specified, ginis will be calculated for entire dataset. Otherwise, you'll get them calculated for each value of the subsetVar (or those specified by subsetValues).
subsetValues=None:  Can specify explicitly which values the subsetVar takes, or leave this unspecified to use all of them.
incomeVars=None: This is the list of variables for which to calculate ginis. (poorly named). e.g. lnHHincome, SWL, etc.
####giniVar=None: This seems to be a name for the resulting gini value (only one!?)
opts=None: No longer used. Aug 2010
    """
    if incomeVars==[]:
        1/0
        return('')
    if incomeVars==None:
        incomeVars=['AdjHHincome','HHincome']
    print 'inc vars',incomeVars
    if opts==None:
        opts=''
    if subsetValues:
        assert subsetVar
        for isv,sv in enumerate(subsetValues):
            if isinstance(sv,basestring):
                subsetValues[isv]='"'+sv+'"'


    # Add gini, calculated for each Province or etc.

    print ' (addGini): This gini function needs to find a new way to do it that creates valid s.e.s, maybe with bootstrapping...'
    outs=''
    for incVar in incomeVars:
        assert not incVar.startswith('ln') and not incVar.startswith('log') # It should be income, not log income!
        theginiVar=giniPrefix+incVar

        if subsetValues:
            giniIfs = [' if %s==%s '%(subsetVar,str(vv)) for vv in subsetValues]
            for giniIf in giniIfs:
                outs+="""
                * Following line requires svyset already set, and seems to require ngp somewhat less than number of values in tabulate, otherwise it gives a "no observations" error. #:(((
                *svylorenz %(vv)s, %(opts)s
                * Agh, I cannot get SEs to work. tryied ineqerr, svylorenz, etc.
                ineqdeco %(vv)s %(ifs)s [w=weight]
                capture gen gini%(vv)s=.
                capture gen se_gini%(vv)s=.
                replace gini%(vv)s= r(gini) %(ifs)s
                replace se_gini%(vv)s= r(se_gini) %(ifs)s
                replace se_gini%(vv)s=0 %(ifs)s
            """%{'opts':opts,'ifs':giniIf,'vv':incVar,}

        elif not subsetVar: # Just do ginis on the whole set:
            outs+="""
            capture noisily drop """+theginiVar+"""
            capture noisily drop se"""+theginiVar+"""
            gen """+theginiVar+"""=.
            gen se"""+theginiVar+"""=.
            quietly ineqdeco """+incVar+""" [pw=weight]
            replace """+theginiVar+"""=r(gini)
            replace se_"""+theginiVar+"""=r(segini)
            }
            """
        else: # This is now the normal: just specify the subsetVar, and ginis will be calculated separately for ALL values of it, using a Stata loop
            outs+="""
            *levelsof """+subsetVar+""",local(tmpGiniLevels)
            *foreach l of local tmpGiniLevels {
            *di `l'
            *ineqdeco """+incVar+""" if CMAuid==`l'  [pw=weight]
            *capture gen dd=.
            *replace """+theginiVar+"""=r(gini) if CMAuid==`l'
            *replace se_"""+theginiVar+"""=r(segini) if CMAuid==`l'
            *}

            capture noisily drop """+theginiVar+"""
            capture noisily drop se_"""+theginiVar+"""
            capture  drop tmpGgroup
            gen """+theginiVar+"""=.
            gen se_"""+theginiVar+"""=.
            egen tmpGgroup = group("""+subsetVar+""")
            su tmpGgroup, meanonly
            forvalues i = 1/`r(max)' {
            di "gini of """+incVar+""" for """+subsetVar+""" group `i' "
            capture noisily {
            quietly ineqdeco """+incVar+""" if tmpGgroup==`i'
            replace """+theginiVar+"""=r(gini) if tmpGgroup==`i'
            replace se_"""+theginiVar+"""=r(segini) if tmpGgroup==`i'
            }
            }

       """ #'`"
    outs+="""
    collapse *"""+giniPrefix+"""*, by("""+subsetVar+""") fast
    keep if ~missing("""+subsetVar+""")
    """
    macroFN=WP+stripWPdta(stataFile)+giniPrefix
    if outfile:
        macroFN=outfile
    if fileOlderThan(WPdta(macroFN),WPdta(stataFile)):
        stataSystem(stataLoad(stataFile)+outs+stataSave(macroFN),filename=macroFN)
    else:
        print '   (skipping estimateGini: no need to update %s from %s...'%(macroFN,stataFile)
    return(macroFN)


############################################################################################################
#
def stataAddMeansByGroup(groupVar,meanVars,weightExp='[pw=weight]',groupType=str):#stataFile,subsetVar=None,subsetValues=None,incomeVars=None,giniPrefix='gini',opts=None):
    #
    ##########################################################################
    """

This is REALLY inefficient compared with collapsing with preserve/restore...
[But collapse doesn't allow pweights for calculating semean !?][oct2011]
* Oct 2011
* Huh! I still don't know how to make means. Collapse doesn't allow pw weights for semean!
* So use stataAddMeansByGroup ? or sumMulti?   or collapse?
*  For now, this is by far the easiest, and the only limit is the weighting...
* collapse [w=weight] and mean [pw=weight] give the same mean but different se's. :((( similar enough, though...?well...
* I gues the function below is the only way to do it, but only if I expand it to be abel to take multiple groupvars!!



Sept 2010: may need to specify if grouptype is str or "numeric"! I'm doing this for addCoefs... [not fully implemented yet]

2012 May: Wow, I still haven't figured this out for two/three group vars!?  See docs for collapse; it justifies (but I don't get it) why you can't use pweights for semean.

2012May: Okay, I made it for two group vars.   and three. But oops, then I realized I sould have used egen groups!
"""
    outS=''
    if ' ' not in groupVar:
        for meanVar in meanVars:
            strs={'mv':meanVar,'gv':groupVar,'we':weightExp}
            outS+="""
            gen mean%(mv)sBy%(gv)s=.
            gen sem%(mv)sBy%(gv)s=.
            levelsof %(gv)s, local(levels)
            foreach l of local levels {
               di "-> %(gv)s = `: label (%(gv)s) `l''"
               capture quietly {
                 mean %(mv)s %(we)s if %(gv)s == `l' & ~missing(%(gv)s), noheader
                 matrix tmpM=e(b)
                 matrix tmpSE=e(V)
                 replace mean%(mv)sBy%(gv)s=tmpM[1,1]  if %(gv)s == `l' & ~missing(%(gv)s)
                 replace sem%(mv)sBy%(gv)s=sqrt(tmpSE[1,1])  if %(gv)s == `l' & ~missing(%(gv)s)
                 }
               }
            """%strs
        return(outS)
    gv=groupVar.split(' ')
    if len(gv)==2:
        for meanVar in meanVars:
            strs={'mv':meanVar,'gv':''.join(groupVar),'gv1':gv[0],'gv2':gv[1],'we':weightExp}
            outS+="""
            gen mean%(mv)sBy%(gv)s=.
            gen sem%(mv)sBy%(gv)s=.
            levelsof %(gv1)s, local(levels1)
            levelsof %(gv2)s, local(levels2)
            foreach l1 of local levels {
               di "-> %(gv1)s = `: label (%(gv1)s) `l1''"
               foreach l2 of local levels2 {
                 di "-> %(gv2)s = `: label (%(gv2)s) `l2''"
                    capture quietly {
                    mean %(mv)s %(we)s if %(gv1)s == `l1' & ~missing(%(gv1)s) & %(gv2)s == `l2' & ~missing(%(gv2)s), noheader
                    matrix tmpM=e(b)
                    matrix tmpSE=e(V)
                    replace mean%(mv)sBy%(gv)s=tmpM[1,1]  if %(gv1)s == `l1' & ~missing(%(gv1)s) & %(gv2)s == `l2' & ~missing(%(gv2)s)
                    replace sem%(mv)sBy%(gv)s=sqrt(tmpSE[1,1]) if %(gv1)s == `l1' & ~missing(%(gv1)s) & %(gv2)s == `l2' & ~missing(%(gv2)s)
                }
            }
            """%strs
        return(outS)
    elif len(gv)==3:
        for meanVar in meanVars:
            strs={'mv':meanVar,'gv':''.join(groupVar),'gv1':gv[0],'gv2':gv[1],'gv3':gv[2],'we':weightExp}
            outS+="""
            gen mean%(mv)sBy%(gv)s=.
            gen sem%(mv)sBy%(gv)s=.
            levelsof %(gv1)s, local(levels1)
            levelsof %(gv2)s, local(levels2)
            levelsof %(gv3)s, local(levels3)
            foreach l1 of local levels {
               di "-> %(gv1)s = `: label (%(gv1)s) `l1''"
               foreach l2 of local levels2 {
                 di "-> %(gv2)s = `: label (%(gv2)s) `l2''"
                   foreach l3 of local levels3 {
                   di "-> %(gv3)s = `: label (%(gv3)s) `l3''"
                    capture quietly {
                    mean %(mv)s %(we)s if %(gv1)s == `l1' & ~missing(%(gv1)s) & %(gv2)s == `l2' & ~missing(%(gv2)s) & %(gv3)s == `l3' & ~missing(%(gv3)s), noheader
                    matrix tmpM=e(b)
                    matrix tmpSE=e(V)
                    replace mean%(mv)sBy%(gv)s=tmpM[1,1]  if %(gv1)s == `l1' & ~missing(%(gv1)s) & %(gv2)s == `l2' & ~missing(%(gv2)s) & %(gv3)s == `l3' & ~missing(%(gv3)s)
                    replace sem%(mv)sBy%(gv)s=sqrt(tmpSE[1,1]) if %(gv1)s == `l1' & ~missing(%(gv1)s) & %(gv2)s == `l2' & ~missing(%(gv2)s) & %(gv3)s == `l3' & ~missing(%(gv3)s)
                }
            }
            """%strs
        return(outS)
    assert 0

def meansByMultipleCategories(groupVars,meanVars,meansFileName,weightExp='[pw=weight]',forceUpdate=False,sourceFile=None,precode='',useStataCollapse=False):
    """
    Actually! Rather than using the previous function (just above), make a new one here, from scratch! Use  egen group(varlist) [, missing label lname(name) truncate(num)]    and then levelsof!

    Assume the stata data are loaded. But I'll only do these calculations if I need to!

    sourceFile is optional; set it if you want to make updating more automatic.
    Ahhh. no. Let's make sourceFile mandatory for now, so this function calls Stata immediately. It's for generating datasets, not doing estimations...


I'm building in a much faster alternative into this same function! useStataCollapse=True will just screw up the standard errors (maybe) but at least get a quick result.
(Don't I want to use my with-labels collapse function? nov2012)

    """
    strs={'mv':meanVars,'mvs':meanVars,'gv':''.join(groupVars.split(' ')),'we':weightExp,'gvs':groupVars}
    if not useStataCollapse:
        sout=stataLoad(sourceFile,onlyvars='weight '+groupVars+' '+meanVars)+precode+"""
        egen _groupVars=group(%(gvs)s)
    *, missing label lname(name) truncate(num)]
    """%strs
        sout+="""
        foreach mv of varlist %(mv)s {
          gen mean`mv'ByVarious=.
          gen sem`mv'ByVarious=.
          }
        levelsof _groupVars, local(levels)
        foreach l of local levels {
          di "-> %(gv)s =  `l'"
            foreach mv of varlist %(mv)s {
              capture quietly {
                mean `mv' %(we)s if _groupVars == `l' & ~missing(_groupVars), noheader
                matrix tmpM=e(b)
                matrix tmpSE=e(V)
                replace mean`mv'ByVarious=tmpM[1,1]  if _groupVars == `l' & ~missing(_groupVars)
                replace sem`mv'ByVarious=sqrt(tmpSE[1,1])  if _groupVars == `l' & ~missing(_groupVars)
              }
            }
        }
        *Hm.. But now I have not collapsed yet! Collapse the identical means:

        collapse mean* sem* by(%(gvs)s)
        foreach mv of varlist %(mv)s {
          rename mean`mv'ByVarious `mv'
          rename sem`mv'ByVarious sem_`mv'
                """%strs+stataSave(meansFileName)+"""
        outsheet  *By*  """+groupVars+' using '+meansFileName+""".tsv , replace noquote nolabel
                """ #'
        if (sourceFile is not None and fileOlderThan(WPdta(meansFileName),sourceFile)) or forceUpdate:
            stataSystem(sout,filename='do'+meansFileName)
            return('')
        else:
            return(sout)


    if useStataCollapse:
        sout=stataLoad(sourceFile,onlyvars='weight '+groupVars+' '+meanVars)+precode+"""
        preserve
        collapse (mean) %(mvs)s %(we)s, by(%(gvs)s) fast
        """%strs + stataSave(WPdta(meansFileName+'.TMPmeans'))+"""
        restore
        collapse (sem) """%strs+' '.join(['sem_%s=%s'%(vv,vv) for vv in meanVars.split(' ')])+""" , by(%(gvs)s) fast
        """%strs+stataMerge(groupVars,WPdta(meansFileName+'.TMPmeans'))+"""
                """%strs+stataSave(meansFileName)+"""
        outsheet   """+groupVars+' using '+meansFileName+""".tsv , replace noquote nolabel
        """
        if (sourceFile is not None and fileOlderThan(WPdta(meansFileName),sourceFile)) or forceUpdate:
            stataSystem(sout,filename='do'+meansFileName)
            return('')
        else:
            return(sout)
#stataAddMeansByGroup(groupVars,meanVars,weightExp='[pw=weight]',groupType=str)

def genWeightedMeansByGroup(oldvar,group,prefix=None,newvar=None,weight='weight',se=False,label=None):
    """
2014 Oct: calculate weighted mean (and, todo, s.e.m.). without collapse, etc.: ie, preserve micro dataset while adding macro versions of them.

group is a string of space-separated variables to group by.

Can easily add se_ from weighted variance
Other stats similar, e.g. weighted median:r(p50)
Here we use w, not pw, because pw is not allowed for mean.

TODO: make a pystataCodebook version of this
TODO: add s.e.m. option (easy)
TODO: consolidate this with the two functions above: I've written nearly the same thing a few times.

Is this extremely slow compare to collapse? If you're doing many variables, yes, I think so.

And can we note why not use mean ..., over() ? You can't capture output from it?
    """
    groups=[gg for gg in group.split(' ') if gg] # List of levels to cycle over.
    if newvar is None:
        if prefix is not None:
            newvar=prefix+oldvar
        else:
            newvar='_'.join(groups)+'_'+oldvar
    # Following will need to be in quotes for string variables!! So encode to numeric first. :(
    ifs= ' & '.join(["%s == `l%d' "%(gg,ii) for ii,gg in enumerate(groups)])
    outs=("""
* Calculate weighted means of %(oldvar)s by %(group)s:
gen %(newvar)s = .                               
"""+'\n'.join(['levelsof '+gg+', local(levels%d) '%ii for ii,gg in enumerate(groups)])+"""
"""+'\n'.join([' '*2*ii+"qui foreach l%d of local levels%d { "%(ii,ii) for ii,gg in enumerate(groups)])+"""
      summarize %(oldvar)s [w=%(weight)s] if """+ifs+"""  , detail 
      replace %(newvar)s =  r(mean) if """+ifs+"""
      """+'\n'.join([' '*2*ii+' }'  for ii in range(len(groups))[::-1] ])+"""
    """)%{'weight':weight,'newvar':newvar,'oldvar':oldvar,'group':group}
    if label is not None:
        outs+="""
        label variable %s "%s" 
        """%(newvar,label)
    return(outs)


############################################################################################################
#
def makeEstimateCoefsByGroup(groupVar,whichCoef,themodel,coefName,inputFilename=None,macroFilename=None,forceUpdate=False):
    #
    ##########################################################################
    """ Attempt 2 (to replace addEstimateCoefsByGroup): this time use my existing infrastructure, since I need to make betas as well. :( So now the groupvar has to be numeric.
     So, horrid hybrid kludge: just load up the data, find out what the group values are, and then use Stata to do all the regressions....
"""

    print "makeEstimateCoefsByGroup",groupVar,whichCoef,themodel,coefName,inputFilename
    fnbase='tmp-'+os.path.split(inputFilename)[1]+groupVar+coefName
    fnbase='tmp-'+os.path.split(macroFilename)[1]+groupVar+coefName

    # Get an up-to-date set of the groupvar values, the ugly way(!)
    # Suffix is used in following to ensure that different calls to this function get the correct result exported from Stata, etc, (see notes in fcn below).
    getgvs=loadStataDataForPlotting(inputFilename,onlyVars=groupVar,forceUpdate=forceUpdate,suffix=fnbase,vectors=True)
    from cpblUtilities import finiteValues,dictToTsv,NaN
    gvValues=finiteValues(uniqueInOrder(getgvs[groupVar]))
    gvValues.sort()

    # Now run my latexStata code package to run and then post-process many regressions:
    print 'makeEstimateCoefs...: WARNING: I THINK THE SKIPSTATA MAY NOT WORK HERE, SO THAT TEXFILES/LOG IS NOT BEING OVERWRITTEN...'
    qlatexfile=latexRegressionFile(os.path.split(macroFilename)[1],modelVersion='auto',regressionVersion='tmp')
    qlatexfile.skipStataForCompletedTables=not forceUpdate
    modelbits=themodel.split('[')

    qmodels=qlatexfile.str2models('\n'.join(["""
*name:"""+str(gvv)+'\n'+ modelbits[0]+' if '+groupVar+' == '+str(gvv)+' & ~missing('+groupVar+') ['+modelbits[1]                    for gvv in gvValues]))

    stataCode=doHeader+stataLoad(inputFilename)+qlatexfile.regTable(fnbase, qmodels,returnModels=True,captureNoObservations=True)

    # ARgh.. we don't actually want any latex output.
    qlatexfile.closeAndCompile(launch=False)#closeOnly=True)
    if 'estcoefs' not in qmodels[0]:
        stataSystem(stataCode,filename=fnbase+'tmpdo')
        qlatexfile=latexRegressionFile(fnbase,modelVersion='auto',regressionVersion='tmp')
    qlatexfile.skipStataForCompletedTables=not forceUpdate
    stataCode=doHeader+stataLoad(inputFilename)+qlatexfile.regTable(fnbase, qmodels,returnModels=True,captureNoObservations=True)
    qlatexfile.closeAndCompile(closeOnly=True,launch=False)#)#compileOnly=True)#closeOnly=True)
    # And anyway, do it a couple more times to make the PDF, while we're at it:
    for iii in 0*[1,2]:
        qlatexfile=latexRegressionFile(fnbase,modelVersion='auto',regressionVersion='tmp')
    qlatexfile.skipStataForCompletedTables=True
    stataCode=doHeader+stataLoad(inputFilename)+qlatexfile.regTable(fnbase, qmodels,returnModels=True,captureNoObservations=True)
    qlatexfile.closeAndCompile(launch=False,compileOnly=True)#closeOnly=True)

    # Ensure that we have up to date Stata runs and that we have successfully caught some coefficients:
    assert 'estcoefs' in qmodels[0] and finiteValues([dgetget(qm,['estcoefs',whichCoef,'b'],NaN)  for qm in qmodels]).any()

    # okay... Now, write these to a file.
    writeData=[{groupVar:qm['name'],
    	    coefName:dgetget(qm,['estcoefs',whichCoef,'b'],NaN),
    	    'se'+coefName:dgetget(qm,['estcoefs',whichCoef,'se'],NaN),
    	    'r2'+coefName:dgetget(qm,['eststats','r2_a'],NaN)
 } for qm in qmodels]
    dictToTsv(writeData,macroFilename+'.tsv',snan='')


    return()


############################################################################################################
#
def __addEstimateCoefsByGroup(groupVar,themodel,coefName,whichCoef=1,inputFilename=None,macroFilename=None,forceUpdate=False,groupType=str):
    #
    ##########################################################################
    """
DEPRECATED! FOR NOW, SEE PREVIOUS FUNCTION, makeEst...
Do an estimate within each group. Store results (coef).


If inputFilename is specified, it will run Stata (if needed)

Sept 2010: need to specify if grouptype is str or "numeric"! Since the Stata code (ugh) is different

Sept 2010: oops. I may want "beta" too...  Can't see how to do that in a parallel (ereturn) way. So just do it myself in Python!?

"""

    # Split the model so can insert if condition

    assert ' if ' not in themodel
    assert '[' in themodel
    modelbits=themodel.split('[')

    outS=''
    if inputFilename:
        outS+=doHeader+stataLoad(inputFilename)

    strs={'gv':groupVar,'mb1':modelbits[0],'mb2':'['+modelbits[1],'wc':whichCoef,'cn':coefName}
    if groupType=='numeric':
        outS+="""
        gen %(cn)s=.
        gen se%(cn)s=.
        gen r2%(cn)s=.

        gen beta%(cn)s=.
        gen sebeta%(cn)s=.

        levelsof %(gv)s, local(levels)
        foreach l of local levels {
           di "-> %(gv)s = `: label (%(gv)s) `l''"
           capture noisily {
    *         quietly:
     {
    	 %(mb1)s  if %(gv)s == `l' & ~missing(%(gv)s)   %(mb2)s

    	 matrix tmpB=e(b)
    	 matrix tmpSE=e(V)

    	 replace %(cn)s=tmpB[1,%(wc)d]  if %(gv)s == `l' & ~missing(%(gv)s)
    	 replace se%(cn)s=sqrt(tmpSE[%(wc)d,%(wc)d])  if %(gv)s == `l' & ~missing(%(gv)s)
    	     }
    	 * For univariate, beta is sqrt of r2
    	 replace r2%(cn)s=e(r2)  if %(gv)s == `l' & ~missing(%(gv)s)


    	 }
           }


        """%strs
    elif groupType==str:
        outS+="""
        gen %(cn)s=.
        gen se%(cn)s=.
        gen r2%(cn)s=.

        levelsof %(gv)s, local(levels)
        foreach l of local levels {
           di "-> %(gv)s = `l'"
           capture noisily {
    *         quietly:
     {
    	 %(mb1)s  if %(gv)s == "`l'" & ~missing(%(gv)s)   %(mb2)s

    	 matrix tmpB=e(b)
    	 matrix tmpSE=e(V)

    	 replace %(cn)s=tmpB[1,%(wc)d]  if %(gv)s == "`l'" & ~missing(%(gv)s)
    	 replace se%(cn)s=sqrt(tmpSE[%(wc)d,%(wc)d])  if %(gv)s == "`l'" & ~missing(%(gv)s)
    	     }
    	 * For univariate, beta is sqrt of r2
    	 replace r2%(cn)s=e(r2)  if %(gv)s == "`l'" & ~missing(%(gv)s)
    	 }
           }


        """%strs
    # '
    if 1:
        outS+="""
        collapse %(cn)s  se%(cn)s r2%(cn)s ,by(%(gv)s)

    """%strs
    if macroFilename:
        outS+=stataSave(macroFilename)

    if inputFilename:
        assert macroFilename
        if fileOlderThan(WPdta(macroFilename),WPdta(inputFilename)) or forceUpdate:
    	    stataSystem(outS,filename='doRegsBy'+groupVar+stripWPdta(inputFilename).split('.')[0])
    else:
        assert not forceUpdate

    return(outS)




##############################################################################
##############################################################################
#
def generateRankingData(stataFile,inVars,quantilesOf ,theData=None,varsByQuantile=None,byGroup=None,weightVar='weight',suffix='',skipPlots=True,rankfileprefix=None,ginifileprefix=None,returnFilenamesOnly=False,forceUpdate=False,groupNames=None,ginisOf=None,loadAll=None,parallelSafe=None):
    #
    ##########################################################################
    ##########################################################################
    """

This is a

Sept 2010: Now this generates Ginis too. gini in here too?! So, all the "varsByQuantile" will also get ginis calculatred for them !  I guess the other gini functions are obselete? At least for Gallup 2010 inequality...

August 2010: Fed up with Stata routines. Can't use weights for ranking. Do quantile generation etc in Python (!)
BUT THS DOES NOT USE WEIGHTS.. [It does, now, but it doesn't use any of the parameterised algorithms for estimating the quantile locations...] [hmmm.. double check that Stata 12 does not takes weights for ranking!?]
 {btw, if you dn't need weights, just use:
egen tmprank=rank(lnGDPpc)
sum tmprank
gen rankGDPpc=(tmprank-r(min))/(r(max)-r(min))
}

Sept 2010: Hm, Also calculate coefficients here?... for regression on rankIncome. Agh , no cannot figr out how to export betas in bloody stata.

Sep 2010: I'm changing skip plots to true, since the better plotting function is now separate. It reloads the shelf file. see regressionsinequality

Sep 2010: Ginis are now only created if all of the "wealth" data are nonnegative. e.g. I want this to make ranking of affectBalance (but not Gini). uhhh no, i'm just making a toggle for doing gini. oh, there already is one. oops. oh. bug?: making gini for byquantile vars??  New parameter: ginisOf. only a subset of these will be made ginis. Im too sleep to be sure I'm doig the right thing... check logic

2012 Aug: You cannot use shelve files with parallel processing / threading... so this is  dangerous because it uses loadStataDataForPlotting. Now, we could use  forceUpdate, which means the resulting shelf files are MORE likely to be corrupted, but they won't be read, or we could wing it for now....  Instead, I can have an option here called parallelSafe (or randomsuffix?) which appends a random string to the suffix for the tsv and shelf..  --> Done

stataFile: file name of Stata data.
theData: Option: in stead of loading from stataFile, this could be a dict of the data, already in the desired forma.I thought this would be useful for when using parallel computation, but ... NOT IMPLEMENTED.
inVars: variables to load from Stata
quantilesOf: variables of which to calculate quantiles (continuous percentile rank; AND discrete quantile groups)
varsByQuantile: should calculate means of these variables,
byGroup=None:
suffix='tmp': Give each different use a different file suffix so that all the chosen variables are included in the export from Stata?
groupNames= a dict which translates the byGroup variable to a name, e.g. wp5 to country name...
loadAll: [aug2012] when loading data from a stata file... Use "loadAll" to assure that the pyshelf which is created, and used (unless forceUpdate is set) contains everything in the stata file.

2013 Jan: I'm starting over with a new one which uses pandas DFs and the groupby, since this seems much cleaner...  I'm putting it in cpblUtilitiesMath, since it will not be stata specific anymore.

    """

    doGini=ginifileprefix != None
    assert ginifileprefix==None or doGini

    from numpy import isfinite
    from pylab import figure,plot,show,clf,arange,floor,array,find,logical_and,where,isfinite,xlabel,ylabel,cumsum,subplot,rcParams
    rcParams.update({'text.usetex': False,}) #Grrr. need it for plusminus sign, but can't deal with all foreign characters in country and region names?!
    from scipy import stats
    import numpy as np
    from cpblUtilities import plotWithEnvelope,transLegend,savefigall,sortDictsIntoQuantiles,finiteValues
    from cpblUtilities.mathgraph import shelfSave,shelfLoad
    # Because numpy and scipy don't have basic weight option in mean, sem !!!
    from cpblUtilities.mathgraph import wtmean,wtsem,wtvar
    from inequality import ineq,cpblGini



    if byGroup==None:
        byGroup=''
    if varsByQuantile==None:
        varsByQuantile==[]
    if suffix:
        suffix='-'+suffix
    assert isinstance(byGroup,basestring)
    #tsvFile=WP+stripWPdta(stataFile)+'-qtlInput'+suffix+'.tsv'
    microQuantFile=WP+stripWPdta(stataFile)+'-qtlData'+suffix+'.tsv'
    macroQuantFileShelf=WP+stripWPdta(stataFile)+'-qtlData-'+byGroup+suffix+'.pyshelf'
    macroQuantFile=WP+stripWPdta(stataFile)+'-qtlData-'+byGroup+suffix+'.tsv'
    macroGiniFile=WP+stripWPdta(stataFile)+'-gini-'+byGroup+suffix+'.tsv'
    plotfileprefix=WP+'graphics/TMPRANK'
    if rankfileprefix:
        microQuantFile=rankfileprefix+'-'+byGroup+'.tsv'
        macroQuantFileShelf=rankfileprefix+'-'+byGroup+'.pyshelf'
        macroQuantFile=rankfileprefix+'-'+byGroup+'.tsv'
    plotfileprefix=WP+'graphics/'+stripWPdta(rankfileprefix)+byGroup
    if ginifileprefix:
        macroGiniFile=ginifileprefix+'-'+byGroup+'.tsv'
    if not fileOlderThan([microQuantFile,macroQuantFileShelf]+doGini*[macroGiniFile],WPdta(stataFile)) and not forceUpdate:
        print '    (Skipping generateRankingData; no need to update %s/%s from %s...)'%(microQuantFile,macroQuantFileShelf,stataFile)
        return(os.path.splitext(microQuantFile)[0],os.path.splitext(macroQuantFileShelf)[0])
        #return(microQuantFile,macroQuantFileShelf)

    # Suffix is used in following to ensure that different calls to this function get the correct result exported from Stata, etc, (see notes in fcn below).
    # Caution! if
    onlyVars=None
    if not loadAll:
        onlyVars=' '.join(uniqueInOrder(inVars+[byGroup, quantilesOf]+varsByQuantile+[weightVar]))
    # If parallelSafe, Make the following force-updated, to avoid using shelve/shelf files simultanously by different processes!!
    dddT=loadStataDataForPlotting(stataFile,onlyVars=onlyVars,treeKeys=[byGroup],forceUpdate='parallel' if parallelSafe else forceUpdate,suffix=suffix)#vectors=True)#False,forceUpdate=False,singletLeaves=False):

    # Testing functionality aug 2012 to make this robust to weight variable not existing for all in dataset:
    for kk in dddT:
       if not kk:
          continue
       plen=len(dddT[kk])
       dddT[kk]=[rrrr for rrrr in dddT[kk] if isfinite(rrrr[weightVar])]
       if not len(dddT[kk])==plen:
          print('CAUTION: I found and ditched some (%d/%d) individuals without weight %s for group "%s" in generateRankingData'%(plen-len(dddT[kk]),plen,weightVar,kk))
          assert (plen-len(dddT[kk])) / plen < .6
    if 0:
        kk=ddd.keys()
        #for byKey in byGroup
        print 'Sorting by key...'
        dddT=dictTree([dict([[akey,ddd[akey][irow]] for akey in kk]) for irow in range(len(ddd[kk[0]]))],[byGroup])

    # Now.. Order these and assign ranking (between 0 and 1):  This should take into account the weights, properly.
    print '%d elements have no group (%s).'%(len(dddT.get('',[])),byGroup)
    rankGroups=[]
    macroStats=[]
    macroInequalities={}
    if not skipPlots:
        figure(126)
        clf()
        figure(124)
    for agroup in sorted(dddT.keys()):#.keys()[0:10]:
        if not agroup:
            continue
        groupD=dddT[agroup]
        weightD=array([respondent[weightVar] for respondent in groupD])
        groupDfinite=[xx for xx in groupD if isfinite(xx[quantilesOf]) ]
        # Hm, does the following fail if I include the nan's!?
        groupDfinite.sort(key=lambda x:x[quantilesOf])
        if doGini:
            macroInequalities[agroup]={byGroup:agroup}

        if 0: # I'm eliminating the following, unweighted ranking for now.
            if len(groupDfinite)==0:
                continue
            if len(groupDfinite)==1:
                groupDfinite[0]['rank'+quantilesOf]=0.5
            else:
                for iRank,respondent in enumerate(groupDfinite):
                    # THIS IS WRONG!!!!!!!!!! IT IGNORES WEIGHT. I SHOULD BE USING WEIGHTED RANK. I DO THIS BELOW. CANNOT FIND scipy ROUTINE TO DO QUANTILES WITH SAMPLE WEIGHTS.
                    respondent['rank'+quantilesOf]=iRank*1.0/(len(groupDfinite)-1)
                    x=array([respondent['rank'+quantilesOf] for respondent in groupDfinite])
        y=array([respondent[quantilesOf] for respondent in groupDfinite])
        w=array([respondent[weightVar] for respondent in groupDfinite])


        # Now, I also need to section these up into groups, in order to calculate other variables by quantile. How to do this? I could use a kernel smoothing, to estimate y(I), where, e.g. y is SWB and I is income.  OR I could calculate quantiles. e.g. qtlY(I) would be the mean y amongst all those in the ith quantile. I'll do the latter. This means that curves will NOT represent y(I), since it's mean(y) but i<I.
        minN=20
        nQuantiles=min(25,floor(len(y)/minN))
        pQtl=(1.0+1.0*arange(nQuantiles))/nQuantiles
        assert len(pQtl)==nQuantiles

        assert all(isfinite(w))  # Really? Couldn't I make this robust... [aug2012: okay, i have, above, by modifying ddTT]

        # Use my nifty sort-into-quantiles function
        minN=20
        if len(y)<minN/2:
            print ' SKIPPING '+agroup+' with only %d respondents...'%len(y)
            continue
        nQuantiles=max(2,min(25,floor(len(y)/minN)))
        # The following function ALSO fills in a new element of the weighted rank of each individual.
        byQtl=sortDictsIntoQuantiles(groupD,sortkey=quantilesOf,weightkey=weightVar,approxN=25,)#nQuantiles=min(25,floor(len(y)/minN)))
        pQtl=sorted(byQtl.keys())
        print '   Quantiles: parsing for group %s=%20s,\t with %d respondents,\t with %d having rank variable;\t therefore using %d quantiles...'%(byGroup,agroup,len(groupDfinite),len(finiteValues(y)),len(pQtl))


        # So since sortDictsIntoQ... filled in individual ranks, I can now plot these:
        x=array([respondent['rank'+quantilesOf[0].upper()+quantilesOf[1:]] for respondent in groupDfinite])
        if not skipPlots:
            figure(126)
            clf()
            subplot(121)
            plot(y,x,hold=True)
            xlabel(substitutedNames(quantilesOf))
            ylabel('Quantile')
        print 'More up to date plots are made by a custom function using the .shelf data, in regressionsInequality'

        #print [stats.mean([gg['lnHHincome'] for gg in byQtl[qq]])  for qq in pQtl]
        #print [stats.mean([gg['lifeToday'] for gg in byQtl[qq]])  for qq in pQtl]


        # Cool! That worked nicely, and is even quite efficient.

        # I wonder how byQtl.keys() compares with the unweighted measure below...    (uses approximately quantile unbiased (Cunnane) parameters)
        yQtl2=stats.mstats.mquantiles(y, prob=pQtl, alphap=0.40000000000000002, betap=0.40000000000000002, axis=None, limit=())


        # Now calculate weighted means for variables of interest within each quantile group:
        qtlStats={'qtl':pQtl,'group':agroup}
        # Also save in the output any variables which are uniform within this group (ie markers of a group in which this is a subgroup):
        if 0:
            for vvv in [vv for vv in inVars if vv not in [byGroup]]:
                if all(array([respondent[vvv] for respondent in groupDfinite])==groupDfinite[0][vvv]): # ah, this variable is uniform within the group
                    qtlStats[vvv]=groupDfinite[0][vvv]

        qtlStats['n']=[ len(
                        finiteValues(array([respondent[quantilesOf] for respondent in byQtl[qtl]]))
                        )             for qtl in pQtl]
        for iv,vname in enumerate(varsByQuantile+[quantilesOf]):
            # Use values with weights:
            vvww=[  finiteValues(array([respondent[vname] for respondent in byQtl[qtl]]),
    			   array([respondent[weightVar] for respondent in byQtl[qtl]])
    			   ) for qtl in pQtl]

            #qtlStats['uw_'+vname]=[np.mean(
            #            finiteValues(array([respondent[vname] for respondent in byQtl[qtl]]))
            # )                    for qtl in pQtl]
            qtlStats[vname]=[wtmean(vv,weights=ww) for vv,ww in vvww]
            #qtlStats['uw_se'+vname]=[stats.sem(
            #            finiteValues(array([respondent[vname] for respondent in byQtl[qtl]]))
            #            )             for qtl in pQtl]
            qtlStats['se'+vname]=[wtsem(vv,ww) for vv,ww in vvww]

        # Ugly kludge:
        if vname in ['SWL','lifeToday']:

            vvall,wwall=finiteValues(array([respondent[vname] for respondent in groupDfinite]),
                                     array([respondent[weightVar] for respondent in groupDfinite]))
            from pylab import histogram,array
            qtlStats['hist'+vname]=histogram(vvall,bins=-0.5+array([0,1,2,3,4,5,6,7,8,9,10,11]),weights=wwall)


        # Shall I also calculate Gini here? It seems it may be much faster than Stata's version. #:(, Though I won't have a standard error for it.
        if doGini and (ginisOf is None or vname in ginisOf):
                # n.b. I don't just want the ones with finite rankVar. So go back to groupD:
                xxV=array([respondent[vname] for respondent in groupD])
    	macroInequalities[agroup]['gini'+vname]= cpblGini(weightD,xxV)


    	#print "             %s=%s: Gini=%f"%(byGroup,agroup,inequality.Gini)

        # ne=where(logical_and(logical_and(isfinite(x),isfinite(y)),logical_and(isfinite(yLow),isfinite(yHigh))))


        #vQtl=array([stats.mean(finiteValues(
        #            vv[find(logical_and(y<=yQtl[iq] , y>=([min(y)]+yQtl)[iq]))]      )) for iq in range(len(yQtl))])
        #sevQtl=array([stats.sem(finiteValues(
        #            vv[find(logical_and(y<=yQtl[iq] , y>=([min(y)]+yQtl)[iq]))]      )) for iq in range(len(yQtl))])


        if (not skipPlots) and vname in varsByQuantile:
            figure(126)
            subplot(122)
            colors='rgbckm'
            vQtl= array(qtlStats[vname])
            sevQtl= array(qtlStats['se'+vname])
            pQtl=array(pQtl)
            plotWithEnvelope(pQtl,vQtl,vQtl+sevQtl,vQtl-sevQtl,linestyle='.-',linecolor=None,facecolor=colors[iv],alpha=0.5,label=None,lineLabel=None,patchLabel=vname,laxSkipNaNsSE=True,laxSkipNaNsXY=True,ax=None,skipZeroSE=True) # Why do I seem to need both lax flags?
            plot(pQtl,vQtl,'.',color=colors[iv],alpha=0.5)
            xlabel(substitutedNames(quantilesOf) +' quantile')

        ##ylabel(vname)
        from cpblUtilities import str2pathname
        if not skipPlots:
            transLegend(comments=[groupNames.get(agroup,agroup),r'$\pm$1s.e.'],loc='lower right')
            savefigall(plotfileprefix+'-'+str2pathname(agroup))
        rankGroups+=groupDfinite
        macroStats+=[qtlStats]


    if 0*'doRankCoefficients':
    	groupVectors=dict([[kk,[gd[kk] for gd in groupDfinite ]] for kk in groupDfinite[0].keys()])
    	from cpblUtilities import cpblOLS
    	x=cpblOLS('lifeToday',groupVectors,rhsOnly=[ 'rankHHincome'],betacoefs=False,weights=groupVectors['weight'])
    	foioi

        # assert not 'afg: Kabul' in agroup
        # Add the quantile info for this group to the data. Also, compile the summary stats for it.

#[, 0.25, 0.5, 0.75]
        # Centre a series of quantiles
        """
    No. Create 20 quantiles. Assign. if none there, weight nearest?

    e.g. 1  2 10 13


    scipy.stats.mstats.mquantiles

    scipy.stats.mstats.mquantiles(data, prob=[, 0.25, 0.5, 0.75], alphap=0.40000000000000002, betap=0.40000000000000002, axis=None, limit=())

    """


    from cpblUtilities import dictToTsv
    dictToTsv(rankGroups,microQuantFile)
    tsv2dta(microQuantFile)
    if doGini:
        dictToTsv(macroInequalities.values(),macroGiniFile)
    tsv2dta(macroGiniFile)

    shelfSave(macroQuantFileShelf,macroStats)
    if 0: # whoooo... i think this was totally misguided. it's not a macro file..
        dictToTsv(macroStats,macroQuantFile)
        tsv2dta(macroQuantFile)

    #vectorsToTsv(qtlStats,macroQuantFile)
    #tsv2dta(macroQuantFile)

    #inequality,redundancy,equality,variation,thesum,absolute=ineq(zip(popn,wealth))

    return(os.path.splitext(microQuantFile)[0],os.path.splitext(macroQuantFileShelf)[0])
    #return(microQuantFile,macroQuantFileShelf)


def doBootStrapStat_cpbl1(model,statistic,N=100):
    boptions=' '
    if 'xtreg' in model:
        return( """
%(bm)s

matrix observe = e(%(st)s)

*Step 2
capture program drop myboot
program define myboot, rclass
 preserve
  bsample
%(bm)s
  return scalar %(st)s = e(%(st)s)
 restore
end

*Step 3
simulate %(st)s=r(%(st)s), reps(%(N)d) seed(12345): myboot

*Step 4
* I have no idea what to put for n
bstat, stat(observe) n(149)
estat bootstrap, all
bstat, stat(observe) n(451)
estat bootstrap, all


"""%{'bm':model,'st':statistic,'N':N,'bopt':boptions})

    if ',' in model and 'cluster' in model.split(',')[1]:
        # Move it to bootstrap options
        clust=re.findall('(cluster\(.*?\))',model)[0]
        model=model.replace(clust,'')
        boptions+=clust
    return("""
    bootstrap %(st)s ,reps(%(N)s) %(bopt)s: %(bm)s
    """%{'bm':model,'st':statistic,'N':N,'bopt':boptions})


def stataLpoly2df(stataFile,xvar,yvars,outfilename=None,outfilenameSuffix='',precode='',forceUpdate=False,weight='weight'):
    """
    Produce a Pandas dataframe from the relatively nice-looking output of Stata's polynomial regression to generate non-parametric fits. 
    Output vectors x,y,seL,seU are returned and also saved in shelf file (or pandas file: old code will need to be updated)

    Should write a version using locfit (or etc) in rpy?

    2013: use shelf=True to invoke the old mode, with four return values and shelf file saving.

    95% confidence envelope is shown/calculated by default

    2014: yvar can be a list of variables (not in old, shelf option). Incidentally, lpoly with gen() is weird! It creates its N new points as variables in the existing rowspace, though they have nothing to do with those existing rows. Only makes sense if you drop everything else after creating them. Convenient, though.

2014:Oct: It looks like you can do this all in numpy now: they have CI for nonparametric methods, using bootstraps. Oh, it may be beta and hard to install? pyqt_fit

    If forcenew is false, then lpolys for a given (xvar,yvars,precode) will be saved to a unique temporary file, to be reused instead of recalculating next time.  (This means that if a loop is called with only the precode changing, values will not be reused inappropriately).
    """
    import pandas as pd
    if isinstance(yvars,basestring):
        yvars=[yvars]
    if stataFile.endswith('.dta.gz'): stataFile=stataFile[:-7]
    if outfilename is None:
        outfilename=paths['scratch']+'stataLpoly-'+'-'.join([   os.path.split(stataFile)[1],xvar,]+yvars+[str(abs(hash(precode)) % (10 ** 8))])+ outfilenameSuffix

    if outfilename.endswith('.pandas'): outfilename=outfilename[:-7]
       
    pyfile=outfilename+'.pandas'
    DOLPOLY="""
    capture drop xxxx
    capture drop yyyy
    * If weight variable is not specified, and there is no variable "weight", we assume no weighting (ie, weight=1)
    capture noisily gen weight=1
    capture noisily {
        lpoly %(yvar)s %(xvar)s [aw=%(weight)s], gen(xxxx yyyy) se(s1) nogr
        gen seU%(yvar)s=yyyy+invnormal(.975)*s1
        gen seL%(yvar)s=yyyy-invnormal(.975)*s1
        gen se_%(yvar)s=invnormal(.975)*s1
        drop %(yvar)s
        rename yyyy %(yvar)s
    }
    """
    #yvar=yvars[0] # HORRID KLIDGE 2014 oct: I don't think I'm doing multiple yvars yet...
    if fileOlderThan(pyfile,WPdta(stataFile)) or forceUpdate:
        stout=stataLoad(stataFile)+'\n'+precode+DOLPOLY%{'yvar':yvars[0],'xvar':xvar,'weight':weight}
        if len(yvars)>1: print("  N.B. stataLpoly(): The order of variables you provide matters. Make sure that the first is the most continuous, as its x-fit values will be used for the others.")
        for yvar in yvars[1:]:
            stout+="""
            capture drop s1
            capture drop x2
            """+DOLPOLY%{'yvar':yvar,'yvars':' '.join(yvars),'xvar':xvar,'weight':weight,'ofn':outfilename+'.tsv'}
        stout+="""
        capture noisily {
        keep if ~missing(xxxx)
        drop %(xvar)s
        rename xxxx %(xvar)s

        outsheet %(xvar)s %(yvars)s  se_* seU* seL* using %(ofn)s, replace
        }
        """%{'yvars':' '.join(yvars),'xvar':xvar,'weight':weight,'ofn':outfilename+'.tsv'}
        stataSystem(stout, filename=paths['scratch']+'stataLpoly_'+os.path.split(outfilename)[1])
        # This could use pd.read_stata?
        if  os.path.exists(outfilename+'.tsv'):
            lpoly=pd.read_csv(outfilename+'.tsv',sep='\t')
        else:
            lpoly=pd.DataFrame()
        lpoly.to_pickle(outfilename+'.pandas')

    else:
       lpoly=pd.read_pickle(outfilename+'.pandas')
    #assert len(lpoly)
    return(lpoly)

    """
    lpoly lifeToday gwp_rankAdjHHincome [aw=weight], gen(x y) nogr
    loc b=r(bwidth)
    lpoly  lifeToday gwp_rankAdjHHincome [aw=weight], nogr at(x) bw(`b') gen(y1) se(s1)
    lpoly lifeToday cardd  [aw=weight], nogr at(x) bw(`b') gen(y0) se(s0)
    g u1=y1+invnormal(.975)*s1
    g l1=y1-invnormal(.975)*s1
    g u0=y0+invnormal(.975)*s0
    g l0=y0-invnormal(.975)*s0
    tw rarea l0 u0 x||rarea l1 u1 x||line y0 x||line y1 x

    # Python:

        x,y,seU,seL=
    l1, u1, u0, l0, x, y1, y0=[lpoly[v] for v in ['l1', 'u1', 'u0', 'l0', 'x', 'y1', 'y0']]

    from pylab import *

    close('all')
    for vv in ['l1', 'u1', 'u0', 'l0', 'y1', 'y0']:
        plot(x,lpoly[vv],label=vv)
    transLegend()

    """

def graphexport(fn,format='pdf'):
    """
    2014June:
Here are two methods for POSIX systems: (to implement here; not finished)

graph export mygraph.eps, replace
! convert mygraph.eps mygraph.png

and for pdf:

graphexport pdf mygraph, dropeps

N.B. This is used by latex.saveAndIncludeStataFig(self,figname,caption=None,texwidth=None):

    """
    pp,ff,ee=[os.path.split(fn)[0] ] +    list(os.path.splitext(os.path.split(fn)[1])) 
    if pp in ['']: pp=paths['graphics']
    assert ee in ['','.pdf'] # This needs more work! see format=, above
    print('Invoking :     graphexportpdf '+pp+'/'+ff+',  dropeps')
    return("""
    set scheme s1rcolor 
    graphexportpdf """+pp+'/'+ff+""",  dropeps
    """)


def models2df(models,latex=None):
    """ Correct way to put all models' estimates together is with a multiindex. 
    """
    collected=[]
    indexlist=['modelNum','name','method','depvar']
    rhsvar='xvar'#'rhsvar' # What should we call the regressors?
    for mm in models:
        if 'estcoefs' not in mm: continue
        # add some key items from the model to each estcoefs variable dict; collect them all!
        for vv in mm['estcoefs']:
            collected+=[dict(  mm['estcoefs'][vv].items() + [[aa,bb] for aa,bb in mm.items() if aa in indexlist]+[(rhsvar,vv)] )]
            # Also add the flags for this model (rather than construct and merge a DataFrame at the model level (rather than the regressor/coefficient level)):
            collected[-1].update(mm.get('flags',{}))
            
    import pandas as pd
    if not collected:
        return(pd.DataFrame())

    coefsdf=pd.DataFrame(collected).set_index(indexlist+[rhsvar])
    return(coefsdf)


    # Below is another method which gives a different, more derived, less useful, version.

    """ Convert some fields of the dicts in a list of model dicts to a pandas dataframe.
    2014 July 2: To get a df of a particular model estimates is easy (pd.DataFrame(smodels[-2]['estcoefs']) but this makes a dataframe of coefficients for all models in the table, with the model name (and number, etc) just another column in the DF.
    [  I think this functionneed not be a member of the class, strictly speaking, but a separate utility function, if it acts on models, not latexRF objects.]

    I could use latex object's substitutions to build in a label for each variable?
To do: implement meanGroupName property here?
    """
    grouped=[]
    for mm in models:
        ec=mm['estcoefs']
        amod={        'name':mm['name'],
                      'modelNum':mm['modelNum'],
                      'method':mm['method'],
                      }
        for avar in ec:
            amod.update({avar:ec[avar]['b'], 'se_'+avar:ec[avar]['se'],'p_'+avar:ec[avar]['p'],
                  })
        grouped+=[amod]

    import pandas as pd
    return(pd.DataFrame(grouped).set_index('modelNum',drop=False))

def numericIndicatorCoefficientsFromModel(models,variableNamesToNumeric,xname='x',yname='b'):
    """
    variableNamesToNumeric is a dict that gives a list of regressors which relate to a sequence of some value, e.g. {'dAgeYear40': 40, 'dAgeYear41': 41, 'dAgeYear42': 42, 'dAgeYear43': 43,}

    coefsdf is the output of latex.models2df [Could also just be models list?]

    xname is the name for the collection of values given in variableNamesToNumeric
    yname, se_yname, p_yname will be the names of the estimates
    
    """
    indexlist=['modelNum','name','method']
    v2n=variableNamesToNumeric

    if isinstance(models,list):
        models=models2df(models) # Get heirarchical list version of all models' estimates.
    import pandas as pd
    import numpy as np
    if models.empty: return(pd.DataFrame())

    df=models.reset_index()
    if 0:
        print len(v2n)
        v2n = dict([[cc,vv] for cc,vv in v2n.items() if cc in df]) # Should report any that are missing
        print len(v2n)

    # Get numeric values for the coefficients names matching our lookup:
    df[xname]=df.apply(lambda adf: np.nan if adf['xvar'] not in v2n else v2n[adf['xvar']]   ,  axis=1)
    df[yname]=df['b']
    df['se_'+yname]=df['se']
    df.sort(['modelNum',xname,],inplace=True)
    return(df[indexlist+[xname,yname,'se_'+yname]].dropna())
    oiuoiu



    dfs=df.stack()
    df2=df.copy()[v2n.keys()]
    df2.columns=[v2n.get(cc,cc) for cc in df2.columns]
    df3=df2.stack()
#    ages=pd.wide_to_long(df,['dAgeYear','se_dAgeYear','p_dAgeYear'],i='modelNum',j='age').reset_index(drop=False)
#    ages=pd.wide_to_long(df,['dAgeYear'],i='modelNum',j='age').reset_index(drop=False)
    assert df3.index.names[0]=='modelNum'
    df3.index.names=df3.index.names[:1]+[xname]
    DD=dict(zip(df3.index.names,zip(*(df3.index.tolist()))))
    DD.update({yname:df3.values})
    dfout=pd.DataFrame(DD).set_index('modelNum',drop=False)
    fier

def asinh_truncate(fromvar,tovar,truncate=True):
    """
    Transform currency or etc variables from pos/neg log-large ranges, or from zeros and large pos ranges, to something tractable in a linear/parametric regression:
    We do two things:
    Use arg sinh (asinh^{-1}) transform to deal with zeros and negatives
    Truncate to +/- 99% percentile to get rid of extremes
    """
    return("""
    * Create log version (using argsinh transform first, to deal with zeros: (Burbidge, Magee, and Robb 1988; MacKinnon and Magee 1990; Pence 2006):
    gen %(tv)s= ln(%(fv)s + sqrt(%(fv)s^2+1))
    * Truncate %(tv)s to its 99th percentile, so I can use it linearly:
        quietly su %(tv)s,d
        scalar per99=r(p99)
        scalar per01=r(p1)
        replace %(tv)s = per99 if %(tv)s>per99 & ~missing(%(tv)s)
    * If %(fv)s also has negative values, let's truncate those too:
    *if min(%(fv)s) <0 {
        replace %(tv)s = per01 if %(tv)s<per01 & ~missing(%(tv)s)
    * }
    sum %(fv)s %(tv)s
    """%{'fv':fromvar,'tv':tovar})
#log_asinh_truncate=asinh_truncate  # This is deprecated! Misnamed!




# This moved somewhere else??? to pca.py , I guess.
#def stataPCA(df, weight=None, tmpname=None, scratch_path=None, method='cor', package='stata'):
#    """ Pandas interface to Stata's PCA function.
#    Returns dict including: coefficients, eigenvalues, cumulative fraction variance explained, the PCA vectors, correlation matrix
#    
#    """
#    
#    assert package in ['stata','scipy','jake']
#    dfnn=df.dropna()
#    if not len(dfnn) == len(df):
#        raise Exception(' WARNING: stataPCA dropped {} NaN observations (out of {}).'.format(-len(dfnn)+len(df),len(df)))
#        df=dfnn
#    if weight is None:
#        assert 'wuns' not in df.columns
#        df.loc[:,'wuns'] = 1
#        weight='wuns'
#    pcvars = [cc for cc in df.columns if cc not in [weight]]
#    if package =='stata':
#        df.to_stata(scratch_path+tmpname+'.dta')
#        statado = """
#        capture ssc inst pcacoefsave
#
#        use {fn},clear
#        pca {pcvars} {ww} , {method}
#        predict {PCAvlist}, score
#        outsheet {PCAvlist} using {SP}{fn}_score.tsv, replace  noquote        
#
#        use {fn},clear
#        pca {pcvars} {ww} , {method}
#        pcacoefsave using {SP}{fn}_pca_coefs, replace
#        mat eigenvalues = e(Ev)
#        gen eigenvalues = eigenvalues[1,_n]
#        egen varexpl=total(eigenvalues) if !mi(eigenvalues)
#        replace varexpl=sum((eigenvalues/varexpl)) if !mi(eigenvalues)
#        gen component=_n if !mi(eigenvalues)
#        keep varexpl eigenvalues component 
#        keep if ~missing(component)
#        list
#        outsheet using {SP}{fn}_varexpl.tsv, replace  noquote
#        u {SP}{fn}_pca_coefs, clear
#        outsheet using {SP}{fn}_pca_coefs.tsv, replace noquote
#        """.format(PCAvlist= ' '.join(['PCA{}'.format(ii+1) for ii in range(len(pcvars))]), method = method, fn=tmpname, SP=scratch_path, pcvars = ' '.join(pcvars), ww = '' if weight is None else '[w='+weight+']')
#        with open(scratch_path+tmpname+'.do','wt') as fout:
#            fout.write(statado)
#        os.system(' cd {SP} && stata -b {SP}{fn}.do'.format(SP=scratch_path, fn=tmpname))
#        df_coefs = pd.read_table(scratch_path+tmpname+'_pca_coefs.tsv')
#        df_varexpl = pd.read_table(scratch_path+tmpname+'_varexpl.tsv')
#        df_varexpl['cumvarexpl'] = df_varexpl['varexpl'].values
#        df_varexpl['varexpl'] = df_varexpl['cumvarexpl'].diff()
#        df_varexpl.loc[0,'varexpl'] = df_varexpl['cumvarexpl'][0]
#        df_score = pd.read_table(scratch_path+tmpname+'_score.tsv')
#    elif package == 'scipy':
#        #from sklearn.decomposition import PCA as spPCA    
#        from statsmodels.multivariate.pca import PCA as smPCA
#        ss=smPCA(df[pcvars], standardize=True) # No sample weights available; the weights argument weights variables!
#        return ss
#        foo
#    elif package =='jake':
#        from wpca import PCA, WPCA, EMPCA
#        stopp
#        def plot_results(ThisPCA, X, weights=None, Xtrue=None, ncomp=2):
#            # Compute the standard/weighted PCA
#            if weights is None:
#                kwds = {}
#            else:
#                kwds = {'weights': weights}
#
#            # Compute the PCA vectors & variance
#            pca = ThisPCA(n_components=10).fit(X, **kwds)
#
#        
#    assert  package in ['stata']
#    # Diagnostic plot
#    plt.figure(456789876)
#    fig, ax1 = plt.subplots()
#    ax1.plot(df_varexpl.component, df_varexpl.varexpl, 'b', label='Explained variance')
#    ax1.set_xlabel('PCA component')
#    # Make the y-axis label, ticks and tick labels match the line color.
#    ax1.set_ylabel('Explained variance', color='b')
#    ax1.tick_params('y', colors='b')
#    ax1.grid()
#    ax2 = ax1.twinx()
#    ax2.plot(df_varexpl.component, df_varexpl.eigenvalues,'b', label='Eigenvalue')
#    ax2.set_ylabel('Eigenvalue', color='b')
#    ax2.tick_params('y', colors='b')
#    fig.tight_layout()
#    plotfn=scratch_path+tmpname+'diagnostic-plot.pdf'
#    plt.savefig(plotfn)
#
#    # Calc vectors:
#    df_cmat=df_coefs.pivot(index='PC', columns='varname', values='loading').dropna()
#    df_cmat.index = df_cmat.index.map(lambda nn:'PCA'+str(nn))
#    assert not pd.isnull(df_cmat).any().any()
#    def _normalize(s):        return (s-s.mean())/s.std()
#    def _demean(s):        return (s-s.mean())
#    dfstd = df[pcvars].std()
#    dfmean = df[pcvars].mean()
#    if method.lower().startswith('cor'):
#        # If the method is "corr", then Stata's coefficients are for demeaned original data values:
#        dfnorm = df[pcvars].apply(_demean, axis=0)
#        # No! It seems still to be the normalized version
#        dfnorm = df[pcvars].apply(_normalize, axis=0)
#    elif method.lower().startswith('cov'):
#        # If the method is "cov", then Stata's coefficients are for the normalized (demeaned and divided by std) values:
#        dfnorm = df[pcvars].apply(_normalize, axis=0)
#    else:
#        raise Exception(" What is the method? Not cov or cor")
#    pcs = df_cmat[pcvars].dot(dfnorm[pcvars].T).T  # Nice: name-checking matrix multiplication
#    assert not pd.isnull(pcs).any().any()
#
#    # Calc correlations of df with principal components:
#    pccorr = pd.DataFrame(index = pcvars+df_cmat.index.tolist(), columns = df_cmat.index)
#    for pcv in pccorr.columns:
#        for ov in pcvars:
#            pccorr.loc[ov,pcv] = weightedPearsonCoefficient(df[ov].values, pcs[pcv].values, df[weight].values)
#        for pcv2 in pccorr.columns:
#            pccorr.loc[pcv2,pcv] = weightedPearsonCoefficient(pcs[pcv2].values, pcs[pcv].values, df[weight].values)
#            
#    # pcs is a df with the new vectors, along with the original index of df (so use df.join if you wish to merge)
#    results= {'coefs':df_cmat, 'loadingStata':df_coefs, 'explained':df_varexpl, 'corr':pccorr, 'plot':plotfn, 'vectors':pcs,  'vectorsStata':df_score, 'fig':fig}
#    #'vectorsN':pcsN,
#    return results
#

if __name__ == '__main__':
    #pass
    # parseSimultaneousQuantileRegression()

    load_text_data_using_SAS_syntax(sasfile='/home/cpbl/rdc/inputData/GSS27/Syntax_Syntaxe/GSS27SI_PUMF.sas',datafile='/home/cpbl/rdc/inputData/GSS27/Data/C27PUMF.txt')
    foo
    #parseQuantileRegression('/home/cpbl/gallup/workingData/qGWP-slim-WesternEuropeandNorthAmerica-quantile',name='test-')

    if 0:
        logFile=WP+'tmpRO'

        parseOaxacaDecomposition(logFile,plotTitle='%(rhsv)s',name=None,skipPlots=False,substitutions=None)



