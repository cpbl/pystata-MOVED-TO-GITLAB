#from pystata import *
import re, os
from .pystata_config import defaults, paths
WP = paths['working']
from pylab import array, flatten, arange
import pandas as pd
import pylab as plt
from copy import deepcopy

from pystata_core import *  # Should I be removing this line for style reasons??
from .pystata_core import standardSubstitutions, substitutedNames, readStataRegressionLogFile, texheader, defaultVariableOrder  # Or import it as stata??
from .pystata_core import *

from codecs import open  # I need to do this just to get encoding= option in open() ?.
if 'stata' not in defaults[
        'paths']:  # This is actually for sprawl's analysis.py, feb2014
    defaults['paths']['stata'] = defaults['paths']
from cpblUtilities import debugprint, uniqueInOrder

from cpblUtilities.textables import chooseSFormat, tableToTSV

from cpblUtilities import transLegend, dfPlotWithEnvelope, str2pathname, flattenList, dgetget, NaN
from cpblUtilities.cpblunicode import str2latex
from cpblUtilities.color import getIndexedColormap
"""
To do:
 revise generate_postEstimate_sums_by_condition(rollingX,ifs) to give DataFrame return value
 revise semiRolling to build dataframes only.
"""


###########################################################################################
###
class latexRegressionFile():  #  # # # # #    MAJOR CLASS    # # # # #  #
    ###
    #######################################################################################
    """ Open a file and write some headers. The file will act as a .tex file with a regression table in it.
As a class, it's a wrapper for some of my python-stata-latex programs that convert Stata output to latex.
It also compiles the file when it is closed..

April 2008: the "suppressSE" argument throughout this class and etc just became obselete: LaTeX now uses a facultative \useSEs{}{} to choose between showing standard errors or not.

Dec 2009:
Allow specification of a "main survey" and a "main data file". This makes it easier to do a half-decent guess job at constructing the right descriptive statistics tables. That is, if we know a survey to use, we can look up the PDF codebook to find descriptions/questions.  If we know the the right data file, we can calculate stats using the right/final/regression-ready data. Because these ideas do not always make sense (multiple surveys or files.), one can also call descriptive stats tables along the way with these things specified.

"""

    # Caution: If you define variables here, before __init__, you can access them with latexinstance.avar , but those are common to the entire class, not to an instance.

    def __init__(self,
                 filename,
                 margins='default',
                 allow_underscore=True,
                 colour=True,
                 modelVersion=None,
                 regressionVersion=None,
                 compactPreview=True,
                 codebook=None,
                 mainSurvey=None,
                 mainDataFile=None,
                 recreateCodebook=None,
                 substitutions=None,
                 texNameSuffix=None):
        """
        codebook can be either a string (name of DTA file) or a codebook object. It's appropriate when there is one dataset for the whole file.. Nov 2009. I suppose I could add this functionality of making descriptive stats tables somehow at the table-level....
        """

        self.lfile = None
        self.lfileTeXbody = ''
        self.fname = None
        self.fpathname = None
        self.modelVersion = None
        self.regressionVersion = None
        self.compactPreview = True
        self.codebook = None  # Not implemented yet? Added only Dec 2009.. does this conflict with some other functionality?
        self.mainSurvey = None
        self.mainDataFile = None
        self.recreateCodebook = None  #This tells the codebook class whether to recreate the codebook of mainDataFile...
        self.captureNoObservations = None  # Dec 2010: update. This should really be default true, as there's no harm now. I use Stata's "capture noisily" to test whether we need to introduce a dummy regression when a regression fails with no samples.
        self.skipStataForCompletedTables = False  # This sets all regTable calls not to call Stata for any tables which have been completed, even if they are old. That is, either DO NOT TURN THIS ON or actually delete the Stata .log files in the texPath that you wish to update/overwrite. So this is also a debugging tool, basically, to focus on tables that are causing trouble when you may be doing many tables all in one program. The trick, then, if you're using large data files, is to make sure that the data files are loaded as part of the first model's "code" element, in order that it doesn't get called if the table is to be skipped... So there's a tradeoff if you're making many tables from the same data.
        self.skipSavingExistingFigures = None  # If not set, this will follow skipStataForCompletedTables. Otherwise, it can separately choose whether to update figures or not (saving is often the slowest part, and is often done through a call to this class).
        self.usingDisclosedData = False  # This means never run stata, since only log files are available, not data. (ie we're analysiing RDC disclosures). So this can just be used as a double check to enforce no stata. Not fully implemented yet. (2010 July)

        self.skipAllDerivedTables = False  # ie if True, ignore all table calls (or just output) whenevr "skipStata=True" flag is used. So this is for making a more compact PDF for exporting results from RDC. Conversely, when set to True it also ignores any skipLaTeX=True calls, since those might be the original/main regression call.  Also, it does not produce CRC tables unless forced to with "onlyCRC" or etc.
        self.variableOrder = None  # This is a default variable order to override what's in pystata module. This simplifies things so one doesn't need to specify it for every single table, though it can also be done per table.

        self.txtNamesUsed = []
        self.variablesUsed = ''  # Collect all variables from regressions, useful for choosing what to display as desc stats at end.

        if not modelVersion:
            modelVersion = ''
        if not regressionVersion:
            regressionVersion = ''
        self.modelVersion = modelVersion
        self.regressionVersion = regressionVersion
        self.compactPreview = compactPreview  # This just means not to show/use sections (function names) and subsections (table/figure names?) in output PDF?
        self.substitutions = standardSubstitutions
        if substitutions is not None:  # Can set default set of variable name translations for the entire latex instance.
            self.substitutions = substitutions
        self.txtNamesUsed = []
        self.updateSettings(
            codebook=codebook,
            mainSurvey=mainSurvey,
            mainDataFile=mainDataFile,
            recreateCodebook=recreateCodebook)

        if filename.endswith('.tex'):
            filename = filename[:-5]
        self.fname = filename + ('-' + self.modelVersion) * (
            not not self.modelVersion) + ('-' + self.regressionVersion) * (
                not not self.regressionVersion)
        if texNameSuffix is None:
            texNameSuffix = ''
        self.fname += texNameSuffix
        self.fpathname = defaults['native']['paths'][
            'tex'] + self.fname  # Native: since we just want to run stata on windows, not tex
        #print '  Initiating a latex file %s.tex with margins: %s'%(self.fpathname,margins)
        #lfile=open(self.fpathname+'.partial.tex','wt')
        thead = texheader(
            margins=margins, allow_underscore=allow_underscore).replace(
                '%LOT:', '').replace('%LOF:', '')
        if not self.compactPreview:
            thead = thead.replace('%TOC:', '')
        #lfile.write(thead)
        #lfile.close()
        self.lfileTeXwrapper = [
            thead, '\n' + r'\clearpage\newpage\end{landscape}' +
            ' End\n\\end{document}\n'
        ]
        #self.lfileTeX_original=self.lfileTeXbody+'' # Maybe obselete now, since I have body separate

    def updateSettings(self,
                       codebook=None,
                       mainSurvey=None,
                       mainDataFile=None,
                       recreateCodebook=None):
        self.mainSurvey = mainSurvey
        self.mainDataFile = mainDataFile
        self.codebook = codebook  # eithe filename or codebook object...
        self.recreateCodebook = recreateCodebook

    def append(self, string):
        self.lfileTeXbody += string
        #lfile=open(self.fpathname+'.partial.tex','at')
        #lfile.write(string)
        #lfile.close()

    ###########################################################################################
    ###

    def appendRegressionTable(
            self,
            models,
            suppressSE=False,
            substitutions=None,
            transposed=None,
            tableFilePath=None,
            tableFormat=None,
            sourceLogfile=None
    ):  # tableCaption=None, tableComments=None,modelTeXformat=None,extrarows,
        ###
        #######################################################################################
        """
        This takes estimation results (data) and makes a LaTeX output, adding it to the self.

        Aug 2009: Rewrote this function to use list of model dicts, rather than vectors of various attributes plus a "pairedrows".

        eliminated: colnames,colnums,coefrows, hiderows and landscape,...        rowmodelNams

        sourceLogfile: Nov 2010: Now it also accepts (should demand?) the filename of the source stata log file. This entire logfile is duplicated, commented out, inside any latex file created.

        June 2011: Needs to be altered to use new two-formats-in-one-tex-file ability of cpblTableC style. For instance, I could have it so that the automated choice of transposed or not still here still uses the cpblTableC files as untransposed as first (default) option, and simple changes the wrapper.
        """
        if sourceLogfile is not None:
            assert all([sourceLogfile == mm['logFilename'] for mm in models])
        if substitutions == None:
            substitutions = self.substitutions
        if 'version' == 'priorToJune2011':  # you can now pass "both" as value for transposed to appendRegressionTable, so that it doesn't duplicate the cpbltablec tex file.
            if isinstance(transposed, str) and transposed.lower() == 'both':
                self.appendRegressionTable(
                    models,
                    suppressSE=suppressSE,
                    substitutions=substitutions,  #modelTeXformat=modelTeXformat,
                    tableFilePath=tableFilePath,
                    tableFormat=tableFormat,
                    sourceLogfile=sourceLogfile,  #tableCaption=tableCaption, tableComments=tableComments,
                    transposed=True, )  #,hideRows=hideRows)
                if 1:
                    self.appendRegressionTable(
                        models,
                        suppressSE=suppressSE,
                        substitutions=substitutions,  #modelTeXformat=modelTeXformat,
                        tableFilePath=tableFilePath,
                        tableFormat=tableFormat,
                        sourceLogfile=sourceLogfile,  #tableCaption=tableCaption, tableComments=tableComments,
                        transposed=False)  #,hideRows=hideRows)
                return
        if tableFilePath == None:
            tableFilePath = defaults['paths']['tex'] + 'tmpMissingTableName.tex'
        if 0:
            if tableCaption == None:
                tableCaption = '(missing table caption)'
                tableCaption += ' ' + tableFilePath.split('/')[-1]
        if tableFilePath.endswith('.tex'):
            tableFilePath = tableFilePath[:-4]

        # Add either the whole logfile, if specified, or a concatenated version of each model output, if no logfile was specified.
        # Add all caution comments for this table to the table Caption.?
        if sourceLogfile is None:
            sourceLogfile = [
                LL + '\n'
                for LL in sum(
                    [mm['rawLogfileOutput'].split('\n') for mm in models], [])
            ]
        else:
            sourceLogfile = open(sourceLogfile, 'rt').readlines()

        twarnings = [
            r'\framebox{' + str2latex(LL) + '}' for LL in sourceLogfile
            if 'Warning' in LL or 'Caution' in LL or ("CAUTION" in LL and 'di '
                                                      not in LL)
        ]
        tableFormat['comments'] += r' ' + r' '.join(twarnings) if len(
            twarnings
        ) < 10 else r' \framebox{Warning!! More than TEN Cautions or Warnings were reported by Stata code for this estimate}'

        # Write the tabular or longtable latex file that the master LaTeX will include.

        #if not colnums:
        #    colnums=['' for cn in colnames]
        if transposed is None: transposed = 'both'
        assert transposed in ['both', True, False]
        includedTex, wrapperTex, transposedChoice = composeLaTeXregressionTable(
            models,
            suppressSE=suppressSE,
            substitutions=substitutions,
            tableFormat=tableFormat,
            transposed=transposed
        )  #,hideRows=hideRows),modelTeXformat=modelTeXformat,
        # {'comments':tableComments,'caption':tableCaption,}

        if {
                True: 'true',
                False: 'false'
        }.get(transposedChoice, transposedChoice).lower() in ['true', 'both']:
            assert 'BEGIN TRANSPOSED VERSION' in includedTex  # File must have two versions of the table if we're to include the second.

        if 'version' == "no... i'm changing things june 2011 to always use the same file, and fit both normal andtransposed in it.":
            if transposedChoice:  # NB: this "transposed" is reset by the call to composeLaTeXtable
                tableFilePath = tableFilePath + '-transposed'
        fout = open(tableFilePath + '.tex', 'wt', encoding='utf-8')
        fout.write(
            includedTex + '\n\n%' + '% '.join(sourceLogfile)
        )  # Append entire Stata log file to end of each LaTeX table file.
        fout.close()
        # 2010 Jan: Also create a .csv file *from* the .tex.
        ###from cpblUtilities import cpblTableToCSV
        fout = open(tableFilePath + '-tex.csv', 'wt')
        fout.write(tableToTSV(includedTex))
        fout.close()

        print ' Appended table: ' + tableFilePath

        ###################################################################################
        # Add this table as in include in a master LaTeX file that includes all the tables...
        # Do landscape, if desired. Decide this separately for each table.

        # Following lscape stuff should be moved to texopening/closing.: trash me/it
        #lscapeb,lscapee='',''
        #if landscape==True or (len(models)>9): # Choose it automatically. if not forced
        #    lscapeb,lscapee=r'\begin{landscape}',r'\end{landscape}'
        self.append(r'\newpage  ' + wrapperTex.replace(
            'PUT-TABLETEX-FILEPATH-HERE',
            tableFilePath.replace(defaults['paths']['tex'], r'\texdocs ')) +
                    '\n\n')

        return

    ###########################################################################################
    ###

    def old_forPairedRows_appendRegressionTable(
            self,
            colnames,
            colnums,
            coefrows,
            extrarows,
            greycols=None,
            suppressSE=False,
            substitutions=None,
            modelTeXformat=None,
            transposed=None,
            tableFilePath=None,
            tableCaption=None,
            tableComments=None,
            landscape=False,
            rowModelNames=None,
            hideRows=None
    ):  # landscape is deprecated: it's chosen automatically.
        ###
        #######################################################################################
        # Add this table as in include in a master LaTeX file that includes all the tables...
        # Do landscape, if desired. Decide this separately for each table.
        # Create the actual latex file that is to be included, as well, through a call to composeLaTeXtable
        """
        If rowModelNames is specified, use them for transposed tables only.
"""
        if isinstance(transposed, str) and transposed == 'both':
            self.old_forPairedRows_appendRegressionTable(
                colnames,
                colnums,
                coefrows,
                extrarows,
                suppressSE=suppressSE,
                substitutions=substitutions,
                modelTeXformat=modelTeXformat,
                tableFilePath=tableFilePath,
                tableCaption=tableCaption,
                tableComments=tableComments,
                landscape=landscape,
                transposed=True,
                rowModelNames=rowModelNames,
                hideRows=hideRows)
            self.old_forPairedRows_appendRegressionTable(
                colnames,
                colnums,
                coefrows,
                extrarows,
                suppressSE=suppressSE,
                substitutions=substitutions,
                modelTeXformat=modelTeXformat,
                tableFilePath=tableFilePath,
                tableCaption=tableCaption,
                tableComments=tableComments,
                greycols=greycols,
                landscape=landscape,
                transposed=False,
                rowModelNames=rowModelNames,
                hideRows=hideRows)
            return
        if tableFilePath == None:
            tableFilePath = defaults['paths']['tex'] + 'tmpMissingTableName.tex'
        if tableCaption == None:
            tableCaption = '(missing table caption)'
            tableCaption += ' ' + tableFilePath.split('/')[-1]
        if tableFilePath[-4:] == '.tex':
            tableFilePath = tableFilePath[:-4]

        # Write the tabular or longtable latex file that the master LaTeX will include.

        if not colnums:
            colnums = ['' for cn in colnames]
        #includedTex,texOpening,texClosing,transposedChoice  =
        includedTex, wrapperTex, transposedChoice = old_uses_pairedRows_composeLaTeXtable(
            colnames,
            colnums,
            coefrows,
            extrarows,
            suppressSE=suppressSE,
            substitutions=substitutions,
            modelTeXformat=modelTeXformat,
            caption=tableCaption,
            greycols=greycols,
            comments=tableComments,
            transposed=transposed,
            rowModelNames=rowModelNames,
            hideRows=hideRows,
            landscape=landscape)

        if transposedChoice:  # NB: this "transposed" is reset by the call to composeLaTeXtable
            tableFilePath = tableFilePath + '-transposed'
        fout = open(tableFilePath + '.tex', 'wt', encoding='utf-8')
        fout.write(includedTex)
        fout.close()
        debugprint('AppendTable: ', tableFilePath)

        ###################################################################################
        # Add this table as in include in a master LaTeX file that includes all the tables...
        # Do landscape, if desired. Decide this separately for each table.

        # Following lscape stuff should be moved to texopening/closing.: trash me/it
        #lscapeb,lscapee='',''
        #if landscape==True or (len(models)>9): # Choose it automatically. if not forced
        #    lscapeb,lscapee=r'\begin{landscape}',r'\end{landscape}'
        self.append(r'\newpage  ' + wrapperTex.replace(
            'PUT-TABLETEX-FILEPATH-HERE',
            tableFilePath.replace(defaults['paths']['tex'], r'\texdocs ')) +
                    '\n\n')
        ##         if 1: # 18 Marc 2008: seems to be a bug in my use of include, so I am eliminating it for now. #:(
        ##             self.append(wrapperTex''.join([ texOpening, tableFilePath , texClosing]))
        ##         else:
        ##             self.append('\n'.join([ texOpening, includedTex , texClosing]))
        return

    ###########################################################################################
    ###
    def toDict(self,
               line,
               depvar=None,
               regoptions=None,
               method=None,
               defaultValues=None):  # Used to be called regDict
        ###
        #######################################################################################
        """ This is a utility to convert from old string list form of a regression model to the newer dict format.
        defaultValues is an alternative form for setting fields that are explicitly listed as the other optional parameters.
        nov 2009: this is completely obselete, since the old format is no longer allowed. there are new methods and conversions for "do file format" (string) and for "defaultModel" in other... See regTable()...

        may 2010: Actually, not quite obselete. bySurvey() still uses it ...
        """

        # It might be easily identifiable as a list of old-format models:
        if isinstance(line, list) and isinstance(line[0], list):
            return ([self.toDict(LL) for LL in line])

        #if defaultValues==None:
        #    defaultValues={}
        defaultValues = [deepcopy(defaultValues), {}][defaultValues == None]

        # Incorporate other keywords into the defaultValues dict:
        for optparam, kk in [[depvar, 'depvar'], [regoptions, 'regoptions'],
                             [method, 'method']]:
            if optparam:
                defaultValues[kk] = depvar

        # And some fields may be considered mandatory:
        if 'flags' not in defaultValues:
            defaultValues['flags'] = []

##         if ....depvar:
##             dd['depvar']=depvar
##         if 'regoptions' not in dd and regoptions:
##             dd['regoptions']=regoptions
##         if method and 'method' not in dd:
##             dd['method']=method

        if isinstance(line, dict):  # It might not need converting:
            dd = deepcopy(line)
            #if 'flags' not in line:
            #    line['flags']=[]
        else:  # It does need converting from old list of strings,etc format:
            dd = dict()
            # It could be just a string, the really simplest format:
            if isinstance(line, str):
                line = ['', line]

            dd['name'] = line[0]
            dd['model'] = line[1]
            if len(line) > 2:
                #    line+=[[]]
                dd['flags'] = line[2]
            if len(line) > 3:
                dd['format'] = line[3]
            if len(line) > 4:
                dd['code'] = {'before': line[4], 'after': line[5]}
            if len(line) > 6:
                dd['regoptions'] = line[6]
            if len(line) > 7:
                dd['feGroup'] = line[7]

        # Now fill in any missing values that were specified separately
        for kk in defaultValues:
            if not kk in dd:
                dd[kk] = defaultValues[kk]

        return (dd)

    ###########################################################################################
    ###
    def withCellDummies(self,
                        lines,
                        cellVariables,
                        cellName=None,
                        nCounts=None,
                        clusterCells=True,
                        dropvars=None,
                        minSampleSize=300,
                        defaultModel=None):  #depvar=None,regoptions=None):
        ###
        #######################################################################################
        """

To test this:    
import pystata
L=pystata.latexRegressionFile('tmp1234')
mmm=L.withCellDummies([['','lsatis da_stuff etc if 1',[['survey','EDS']]],  ['','lsatis da_stuff etcother if 1',[['survey','GSS17']]]],['DAuid'])


           That is, I want to split data up into cells based on certain
        variables, for instance, geographic identifiers.

        I want to make sure there are at least a certain number of samples in
        each cell which have good values for all the regressors in the model,
        and eliminate the small cells.

        I want to possibly cluster on those cells...

Let this function work on just one line of a model. Then the byCR function can use it (it needs also to drop higher CR level vars), specifying just one CRuid as the cell var...

        Algorithm: look for "survey" attribute of the line (model),
        which must be in 3 or more element format, so that the third
        element is a list of attributes.

        Unless specified otherwise, clustering is turned on at the cell level, using the options-specification feature of regseries.

        16 April 2008: Adding a Stata "if" statement to condition the regression on successful generation of cell dummies.

        [2010: Really?? It looks like this comment is for withCR, not withCell] Ah, what the real problem is is that if the model includes
        other conditions ("if"s), they reduce the group size of some,
        so I am getting completely determined samples. (see notes for
        19 March 2008). Or, some variables may not be available for
        all samples, also reducing the number in a CR group. When
        forming CR/survey cells, must make sure that all regressors
        exist for those samples included. Well... no: only those variables which *ought* to exist for the given survey. This is very kludgey and specific now, but look to see if a survey is selected and if so, restrict the variables used for cell counts to those that we expect should be there.

    If surveys are specified as attributes, the cells will be only within those surveys; the surveys restriction can also exist in the if clause of the model description, though.


    Oh dear IO have to create a 5th element in model lines. this will be stata code which gets written before the regression is done...
    ugh.

Aug 2008: I am adding "depvar" as an option: you can specify a default depvar to fill in unfilled field depvar for each model. 
    
Oct 2008: I am adding "regoptions" as an option. Specify it here as a default. Note how valuable this is: since you cannot specify it as a default later, in regtable, since "regoptions" will already be populated  by this function, ie with a cluster option (for stata).

OCt 2008: Eliminated "depvar" and "regoptions" in favour of defaultModel, which can have the former two fields.
        """

        if cellName == None:
            cellName = 'cells'

        from copy import deepcopy
        if nCounts == None:
            nCounts = 5

        modelsout = []
        from pprint import pprint

        # Check for format of passed lines, and possibly recursively iterate. lines should really be called models, since it now can be a list of models/lists of models.
        if not lines or lines == [[]]:
            return ([])
        if isinstance(lines, dict):
            debugprint('Found dict')
            lines = [lines]
        elif isinstance(lines, list) and all([
                isinstance(onee, dict) or
            (isinstance(onee, list) and isinstance(onee[0], str))
                for onee in lines
        ]):
            debugprint(
                'Found list of nothing but ',
                len(lines),
                ' models (in dict or old format); so proceed with standard loop that will treat them as one group'
            )
            for mm in lines:
                mm = self.toDict(mm)
                #mm=self.convertMtoDict(mm)

        else:
            debugprint(
                'so must have a list of ',
                len(lines),
                ' lists/modelslists, or else the models are not in dict format?'
            )
            for lineOrGroup in lines:
                debugprint(
                    'For a linegroup ',
                    lineOrGroup,
                    ' generated ',
                    self.withCellDummies(
                        lineOrGroup,
                        cellVariables,
                        cellName=cellName,
                        nCounts=nCounts,
                        clusterCells=clusterCells,
                        dropvars=dropvars,
                        minSampleSize=minSampleSize,
                        defaultModel=defaultModel)
                )  #depvar=depvar,regoptions=regoptions))
                modelsout += self.withCellDummies(
                    lineOrGroup,
                    cellVariables,
                    cellName=cellName,
                    nCounts=nCounts,
                    clusterCells=clusterCells,
                    dropvars=dropvars,
                    minSampleSize=minSampleSize,
                    defaultModel=defaultModel
                )  #,depvar=depvar,regoptions=regoptions)

            debugprint(' Ended with ', modelsout)
            return (modelsout)

        # So now we are sure that we have just a list of models (in dict or old form), though the list could be length one.

        if not cellVariables:  # Facility for degenerate use of this function: e.g. a loop might have a case without any cell variables. Then just return what we got.
            return (lines)

        oneGroupModels = []
        for model in deepcopy(lines):
            if 'isManualEntry' in model:
                continue
            # Option to supply depvar in the function call: Do not override ones already specified.
            #if 'depvar' not in model and depvar:
            #    model['depvar']=depvar
            # Option to supply regoptions in the function call: Do not override ones already specified.
            #if 'regoptions' not in model and regoptions:
            #    model['regoptions']=regoptions
            if defaultModel:
                for field in defaultModel:
                    if field not in model:
                        model[field] = deepcopy(defaultModel[field])

            stataBeforeOut, stataAfterOut = '', ''
            # Find surveys, if there is one. Ignore "all~n" entries for "survey" attribute.
            if isinstance(model.get('flags', ''), dict):
                surv = dgetget(model, 'flags', 'survey', '')
            else:
                surv = [
                    aaa[1] for aaa in model.get('flags', [])
                    if aaa and isinstance(aaa, list) and aaa[0] == 'survey'
                ]
            surveys, dsurveys = [], ' 1 '  # ie "true" in an if condition
            if surv:
                surveys = [
                    sss for sss in surv[0].replace(' ', ',').split(',')
                    if not 'all~' in sss
                ]
                if len(surveys) > 0:
                    dsurveys = ' (' + ' | '.join(
                        ['d%s==1' % ss for ss in surveys]) + ') '
            # Surely the above is redundant. if the survey selection is already in the if clause. Why do this here?

            # Find regressors; find if conditions:
            if ' if ' not in model['model']:
                model['model'] += ' if 1'
            parts = model['model'].split(' if ')
            assert len(parts) < 3
            regressors = [pp for pp in parts[0].split(' ') if pp]
            # Construct appropriate dummy: for this specified set of variables ("cellVariables") and for this survey or these surveys:

            # Does not apply to this function.:
            # Also, remove any regressors which look like they are at this (or higher...) CR level:
            # useRegressors=[rr for rr in regressors if not rr[0:3].lower() in higherLevels[aCR] and not rr[0:4].lower() in higherLevels[aCR]]
            useRegressors = regressors
            if dropvars == None:
                dropvars = ''
            dropvars += ' ' + cellVariables
            if not dropvars == None:
                for dv in uniqueInOrder([
                        dvv for dvv in dropvars.split(' ')
                        if dvv and dvv in useRegressors
                ]):
                    useRegressors.remove(
                        dv)  #=useRegressors.replace(' '+dv+' ','  ')

            # Also, just for the dummy selection, remove any other variables which we do not think exist for any of the chosen surveys:
            expectedExistRegressors = ['1'] + [
                rr for rr in useRegressors if inanyCodebook(rr, surveys)
            ]
            droppedList = set(expectedExistRegressors) - set(
                useRegressors) - set(['1'])
            if droppedList:
                print('Ignoring existence of ', droppedList, ' for ', surveys)

            # Count how many people in each bin for the coming regression:
            stataBeforeOut+="""
            capture drop ttt_*
            capture drop tttvvv_*
            capture drop dummyOne
            gen dummyOne=1
            """  # Safely clear old counters (Could have used "capture" instead)
            if isinstance(cellVariables, list):
                cellVariables = ' '.join(cellVariables)
            # Following command is equivalent to use egen with group() and then counting??
            stataBeforeOut += '\n bysort ' + cellVariables + ': egen ttt_' + cellName + '=count(dummyOne)  if ' + parts[
                1] + ' & ' + dsurveys + ' & ' + ' & '.join(
                    ['%s<.' % rr for rr in useRegressors])
            # Also ensure (if depvar is known) that there is at least some variation in depvar within each cell
            if 'depvar' in model:
                stataBeforeOut += '\n bysort ' + cellVariables + ': egen tttvvv_' + cellName + '=sd(' + model[
                    'depvar'] + ')  if ' + parts[
                        1] + ' & ' + dsurveys + ' & ' + ' & '.join(
                            ['%s<.' % rr for rr in useRegressors])
            else:
                stataBeforeOut += '\n gen tttvvv_' + cellName + '=1'

            # 2013 Feb: btw, is it a simpler method to say: by year wp5:egen nSample =total(dummyOne)

            # Also must make some dummies myself here for these regions and this survey.
            #stataBeforeOut+='\n gen ddd_null=. \n drop ddd_* ' # Safely clear old dummies
            stataBeforeOut += """
            capture drop ddd_* 
            egen dcelltmp= group( """ + cellVariables + """)
            quietly: tab dcelltmp if ttt_""" + cellName + """ >= """ + str(
                nCounts
            ) + """ & tttvvv_""" + cellName + """>0 & ttt_""" + cellName + """ <. &  """ + parts[
                1] + """, gen(ddd_""" + cellName + """)
            drop dcelltmp
            """

            # Condition doing the regressions on success of this dummy generation.
            stataBeforeOut += "\n capture noisily confirm numeric variable ddd_" + cellName + "1, exact\n if _rc==0 & r(N)>" + '%d' % minSampleSize + " & r(r)>1  { * Condition on number of respondents, number of clusters, and existence of some " + cellName + " dummies\n"
            # If there are not enough samples, create a blank line in eventual output, showing number of samples. (In fact, the line below is safe to the possibility that ddd_cellname could not even be created.: in that case, the number of samples will be all-encompassoing)
            stataAfterOut += '\n }\n else { \n reg dummyOne dummyOne \n capture reg dummyOne dummyOne ddd_' + cellName + '* \n } \n matrix est=e(b) \n est\n'

            # Wrap up:
            # Aghhh. so far must be one survey exactly..

            model['model'] = ' ' + ' '.join(
                useRegressors) + ' ddd_' + cellName + '* if ' + parts[1]
            if isinstance(model.get('flags', ''), dict):
                model['flags'][cellName + '~f.e.'] = True
            else:
                model['flags'] = model.get('flags', []) + [cellName + '~f.e.']
            if 'code' not in model:
                model['code'] = dict(before='', after='')
            assert 'cellDummiesBefore' not in model['code']
            model['code']['cellDummiesBefore'] = stataBeforeOut
            model['code']['cellDummiesAfter'] = stataAfterOut
            if clusterCells:
                if 'regoptions' not in model and method not in ['rreg']:
                    model[
                        'regoptions'] = ', robust'  # Need to have comma, at least here...
                if 'cluster(' in model['regoptions']:
                    print "Warning!! I am not putting the cell variable in as cluster because you already have a cluster variable! ", model[
                        'regoptions']
                else:
                    model['regoptions'] += ' cluster(%s) ' % cellVariables
                    if isinstance(model.get('flags', ''), dict):
                        model['flags'][
                            'clustering'] = '{\smaller \smaller %s}' % cellName
                    else:
                        model['flags'] += [[
                            'clustering', r'{\smaller \smaller %s}' % cellName
                        ]]
            #print ' Revised model: ',model
            oneGroupModels += [model]
        #modelsout+=[oneGroupModels]

        return (oneGroupModels)

    ###########################################################################################
    ###
    def withCRdummies(self,
                      models,
                      CRs,
                      each=False,
                      nCounts=None,
                      clusterCRs=True,
                      minSampleSize=800,
                      defaultModel=None,
                      manualDrops=None):  # aka "byCR"
        ###
        #######################################################################################
        """
        What does this do? It replicates the given sets of models so that each is run with a series of sets of CR values / dummies included/excluded in order to isolate effects at each level.






        This makes use of withCellDummies, above. The only thing that should still be done here is dropping higher CR level vars. and iterating over CRs. [done]



to test this: same as prev function, except:
import pystata
L=pystata.latexRegressionFile('tmp1234')
mmm=L.withCRdummies([convertMtoDict(['','lsatis da_stuff pr_this csd_that if 1',[['survey','EDS']]]), convertMtoDict(  ['','lsatis da_stuff pr_this csd_that if 1',[['survey','GSS17']]]), ],['PR','CSD'])


or maybe: (two surveys, three CRs, and four regression models)
mmm=L.withCRdummies([
[convertMtoDict(['','lsatis da_stuff pr_this csd_that if 1',[['survey','EDS']]]),    convertMtoDict(['','lsatis da_stuff pr_this csd_that if 1',[['survey','GSS17']]]),],
[convertMtoDict(['','lsatis modelTwothings da_stuff pr_this csd_that if 1',[['survey','EDS']]]),    convertMtoDict(['','lsatis otherThings da_stuff pr_this csd_that if 1',[['survey','GSS17']]])],
[convertMtoDict(['','lsatis modelThreethings da_stuff pr_this csd_that if 1',[['survey','EDS']]]),    convertMtoDict(['','lsatis otherThings da_stuff pr_this csd_that if 1',[['survey','GSS17']]])],
[convertMtoDict(['','lsatis modelFourthings da_stuff pr_this csd_that if 1',[['survey','EDS']]]),    convertMtoDict(['','lsatis otherThings da_stuff pr_this csd_that if 1',[['survey','GSS17']]])],
],['PR','CSD','CT'])

        """
        """ This function removes any regressors that look like they
        are determined at the same CR level that is being controlled
        for, since Stata will randomly choose one of the available
        variables at the CR level to leave in, and we want it to be
        the dummy.

        This is rather specific and therefore probably finicky.


        If each=True, the idea is to keep collections of the CR
        dummies together, so we see the coefficients grouped by the
        rest of the model.

    Consider a set of modeles passed as:   [1,[2,3,4],[5,6]]. ie there are two sets of grouped ones (which regTable will takes means of) and one ungrouped one.
    How do I preserve this ordering?
    I want the result for, say, two CRs to be:  [1,1',[2,3,4],[2',3',4'],[5,6],[5',6']]
    if any of the top level list members is another list of lists (ie list of models), then do a recursive loop to parse them.
    Otherwise, parse as a group.

    So: this function can now take complex nested sets of models.
    Examples: 1 (not allowed);  [1];        [1,2,3];     [[1,2,3]]


May 2008: Adding a note of group names for each group of CR models...
Aug 2008: [Obselete] I am adding "depvar" as an option: you can specify a default depvar to fill in unfilled field depvar for each model. This is passed on to celldummies. 
Oct2 008: I am replacing "depvar" option with "defaultModel" option!

Aug 2010: Generalising so that if CR doesn't look like a CR, it may be a Gallup geographic level.  (or USA, in future?)

manualDrops = ??
    
    """
        from copy import deepcopy
        if nCounts == None:
            nCounts = 5
        if manualDrops is None:
            manualDrops = {}

        ##assert(isinstance(models[0],list))
        modelsout = []
        from pprint import pprint
        ###print len(models),len(models[0])#,len(models[1])
        #if any([isinstance(model,list) and isinstance(model[0],list)  for model in models]):

        debugprint('-------------werwerwe', models)

        # What object do we have?
        if isinstance(models, str):
            models = self.str2models(models, defaultModel=defaultModel)
        if isinstance(models, dict):
            debugprint('Found dict')
        elif isinstance(models, list) and all(
            [isinstance(onee, dict) for onee in models]):
            debugprint('Found list of nothing but dicts')
        #elif   any([isinstance(model,list) and (isinstance(model[0],list) or isinstance(model[0],dict))  for model in models]):
        #    debugprint('Found list of lists that are not models')
        else:
            debugprint(
                'so must have a list of lists, or else the models are not in dict format?'
            )

        # This will fail if models are passed not in dict form.!
        if not isinstance(models, dict) and not isinstance(models[0], dict):
            debugprint(
                'withCRdummies is recursively looping over %d elements\n' %
                len(models))
            for modelOrGroup in models:
                if isinstance(
                        modelOrGroup,
                        dict):  # or not isinstance(modelOrGroup[0],list):
                    debugprint('   withCRdummies entry: a single model!\n',
                               modelOrGroup)
                    modelOrGroup = [modelOrGroup]
                else:
                    debugprint('   withCRdummies entry: length %d \n' %
                               len(modelOrGroup))
                    pass
                modelsout += self.withCRdummies(
                    modelOrGroup,
                    CRs,
                    each=each,
                    nCounts=nCounts,
                    clusterCRs=clusterCRs,
                    minSampleSize=minSampleSize,
                    defaultModel=defaultModel,
                    manualDrops=manualDrops)
            return (modelsout)
        """
        if not isinstance(models,dict) and (\
               (isinstance(models,list) and isinstance(models[0],dict)) \
                or any([isinstance(model,list) and isinstance(model[0],list)  for model in models])):
            debugprint ('withCRdummies is recursively looping over %d elements\n'%len(models))
            for modelOrGroup in models:
                if isinstance(modelOrGroup,dict) or not isinstance(modelOrGroup[0],list):
                    debugprint( '   withCRdummies entry: a single model!\n',modelOrGroup)
                    modelOrGroup=[modelOrGroup]
                else:
                    debugprint ('   withCRdummies entry: length %d \n'%len(modelOrGroup))
                    pass
                modelsout+=self.withCRdummies(modelOrGroup,CRs,each=each,nCounts=nCounts)
            return(modelsout)
            """
        # Note: HR cannot be ranked this way, so including HR in below is a kludge for testing.this is a kludge for testing.
        higherLevels = {
            'CT': ['CT', 'A15', 'CSD', 'HR', 'CMA', 'PR'],
            'CSD': ['CSD', 'HR', 'CMA', 'PR'],
            'HR': ['HR', 'CMA', 'PR'],
            'CMA': ['CMA', 'PR'],
            'PR': ['PR'],
            'wp5': ['wp5'],
            'subregion': ['subregion', 'wp5'],
        }
        for aCR in higherLevels:  # Add underscores to these; I use them for variable prefixes.
            higherLevels[aCR] = [cc.lower() + '_' for cc in higherLevels[aCR]]

        if each == True:  #(...? huh?)
            #assert 0 # This assert added Setp2009 since it looks like this is a not-implemented feature?. Well, actually I'll leave it for now. Do not understand.
            return

        # Ensure all models are in the modern format:
        models = deepcopy(models)
        assert all([isinstance(model, dict)
                    for model in models])  # Otherwise out of date / impossible

        # Treat models as a group; cycle through each of them together before moving on to next CR:
        # By this point, single-model sets come looking like a group (ie as [[list]])
        dums = {}
        global globalGroupCounter
        """ This counter / CRgroups label will be the same for a group of models run over different surveys and also with different CR controls. Later on, the *averaged over surveys* version of these can be grouped based on this CRgroups marker to find how to collect coefficients from the means. Note that there is always one model (the first in a group) run without any CR fixed effects. This should also get the CRgroup marker.
        """
        globalGroupCounter += 1
        if isinstance(CRs, str):
            CRs = [CRs]
        # Following is a lookup that tells which CR coef is isolated by a given CR dummies set: ie it's one smaller than the set of dummies.
        topCoefficient = dict(
            [[CRs[iCR], (CRs[1:] + [''])[iCR]] for iCR in range(len(CRs))])

        for aCR in CRs:
            dummyStr = '%s~f.e.' % aCR
            ##             if aCR=='': # Make one copy with no dummies
            ##                 amodel=deepcopy(models)
            ##                 amodel['CRgroup']={'CR%03d'%globalGroupCounter:aCR}#+parts[1].replace(' ','')}
            ##                 modelsout+=[amodel]
            ##                 debugprint ('No change for this model\n')
            ##                 continue
            debugprint('   byCR: for %s, looping over the %d models.\n' %
                       (aCR, len(models)))
            oneGroupModels = []

            # Call the more general function to do most of the work:
            #models=self.withCellDummies(deepcopy(models),aCR,cellName=aCR.replace('uid',''),nCounts=nCounts,clusterCells=clusterCRs)
            for model in deepcopy(models):
                #!stataBeforeOut,stataAfterOut='',''
                #print '   byCR: Original model: ',model
                # Find surveys, if there is one. Ignore "all~n" entries for "survey" attribute.
                #!surv=[aaa[1] for aaa in model[2] if isinstance(aaa,list) and aaa[0]=='survey'][0]
                #!surveys=[sss for sss in surv.replace(' ',',').split(',') if not 'all~' in sss]
                #print 'Found survey: ',surveys
                #if ',' in surv or ' ' in surv:
                #    print "Multiple surveys in this model"
                #!dsurveys=' 1 ' # ie "true" in an if condition
                #!if len(surveys)>0:
                #!    dsurveys=' ('+ ' | '.join(['d%s==1'%ss for ss in surveys]) + ') '
                #dums= ' td%s_%s* '%(aCR,surv[0])

                # Find regressors; find if conditions:

                ######model['CRgroup']={'CR%03d'%globalGroupCounter:aCR}#+parts[1].replace(' ','')}
                model['CRgroup'] = {
                    'id': 'CR%03d' % globalGroupCounter,
                    'fixedeffects': aCR,
                    'takeCoef': topCoefficient[aCR],
                    'addend': len(models) > 1
                }  #,'isaddend':''}}

                if aCR == '':  # Make one copy with no dummies
                    if defaultModel:
                        for field in defaultModel:
                            if field not in model:
                                model[field] = deepcopy(defaultModel[field])

                    debugprint('No change for this model\n')
                    modelC = deepcopy(model)
                else:
                    if ' if ' not in model['model']:
                        model['model'] += ' if 1'
                    parts = model['model'].split(' if ')
                    assert len(parts) < 3

                    regressors = [pp for pp in parts[0].split(' ') if pp]
                    # Also, remove any regressors which look like they are at this (or higher...) CR level:
                    useRegressors = [
                        rr for rr in regressors
                        if not rr[0:3].lower() in higherLevels[aCR] and
                        not rr[0:4].lower() in higherLevels[aCR] and rr not in
                        manualDrops.get(aCR, [])
                    ]
                    model['model'] = ' '.join(
                        useRegressors) + ' if ' + parts[1]
                    if aCR in crlist:
                        acrsuffix = 'uid'
                    else:
                        acrsuffix = ''
                    modelC = self.withCellDummies(
                        [model],
                        aCR + acrsuffix,
                        cellName=aCR,
                        nCounts=nCounts,
                        clusterCells=clusterCRs,
                        minSampleSize=minSampleSize,
                        defaultModel=defaultModel)[0]

                oneGroupModels += [modelC]
            modelsout += [oneGroupModels]

        #pprint(modelsout)
        return (modelsout)

    ###########################################################################################
    ###
    def removeUnavailableVariables(self,
                                   indepvars,
                                   survey,
                                   forceKeepVars=None,
                                   forceDropVars=None):
        #                 withCRdummies=CRs,withCRdummiesCounts=None):
        ###
        #######################################################################################
        """
        ********* How does this relate to the fancier removeUnavailableVars, which is wave and country-dependent? I guess this just looks for vars that are completely unknown.

        """
        if 1:  # I think I must have lost a whole bunch of code right here, since I got an indenting error::
            if forceKeepVars == None:
                forceKeepVars = []
            if forceDropVars == None:
                forceDropVars = []
            # Clean up in case entire regression command was passed:
            indepvarsReg = indepvars.split(' if ')[0]  # Get rid of if clauses
            indepvarsReg = indepvarsReg.split('[')[0]  # Get rid of weights
            # Check for this explicity list
            unavailable = [
            ]  #[['unemployed',['GSS17','GSS19']],['mastery',['GSS19']],['lnhouseValue',['ESC2','GSS17']],['mortgagePayment',['ESC2','GSS17']],]
            removed = []
            for una in unavailable:
                if survey in una[1]:
                    indepvars = indepvars.replace(' ' + una[0] + ' ', '  ')
                    removed += [una[0] + '[%s]' % survey]
            # Check using more general check that might be flawed by missing some variables: ie drop too many:
            for var in [vv for vv in indepvarsReg.split(' ') if vv]:
                if var in forceDropVars or (not inanyCodebook(
                        var, survey) and not inanyCodebook(
                            var.replace('lnR', '').replace('ln', ''),
                            survey) and not isGeneralVar(var) and
                                            not var in forceKeepVars):
                    indepvars = indepvars.replace(' ' + var + ' ', '  ')
                    removed += [var + '[%s]' % survey]
            return (indepvars, removed)

    ###########################################################################################
    ###
    def addSeparator(self, models):
        ###
        #######################################################################################

        ' Simple tool to set the format field of the final model in a possibly-nested list of models so that a separator will appear in the table'
        if isinstance(models, list):
            if models:
                self.addSeparator(models[-1])
            return
        if isinstance(models, dict):
            if not 'format' in models:
                models['format'] = 'c'
            models['format'] += '|'
        return

    ###########################################################################################
    ###
    def flattenModelList(self, nestedModelList, separators=True):
        ###
        #######################################################################################
        """ One way to construct a big table with many models is to create a
        nested for loop (that is, if looping over several different types of
        variation in the model). You can then end up with a multidimensional
        list. But regTable requires a 1 or 2 dimension-deep list.

        This function flattens a list by one dimension (the highest-level one) and adds a separator at
        the end of it.
        
        """
        assert isinstance(nestedModelList, list)
        import operator
        flattened = reduce(operator.add, nestedModelList, [])
        if separators:
            self.addSeparator(flattened)
        return (flattened)

    ###########################################################################################
    ###
    def bysurvey(self,
                 surveys,
                 model,
                 includePooled=False,
                 eliminateMissing=True,
                 forceKeepVars=None):
        #                 withCRdummies=CRs,withCRdummiesCounts=None):
        ###
        #######################################################################################
        """
        This is just a helper tool for making calls to regTable. It does not really need to be in the class.

        It copies the model (column in a regression table) for each survey given and removes any RHS variables that are not available for each given survey.
        
        surveys is a list of surveys. 
        'Model' takes one line suitable for a model list in latex.reg~Table().  I believe it can take either old form (list of strings) or new form (dict) for each model.


        
        You do not need to use this helper tool: you can just put several rows together in a list in regseries, for instance if you want different conditions in each case...

        2008 July: If the dependent variable is also a regressor, the latter will be removed. This feature should not really be here. Should be in regTable.. Move it -->O

        2008 June: if the dependent variable is not in the survey data, the model will simply be dropped.

        2008 March 12: 

        March 2008: Now including a feature which could later be
        informed by the master codebook but is for the moment
        hardcoded: it removes unavailable variables from regression
        equations.
        
        March 2008: Adding an option to include a column with the
        listed surveys all thrown (pooled) together, not to be part of
        any average.

        It appears to return a list of lists of models. This is so that groups of models that vary only in survey can stay as groups, yet this function may return more than one: one pooled model plus a group of by-survey ones.

        """
        from copy import deepcopy
        model = deepcopy(model)
        if forceKeepVars == None:
            forceKeepVars = []
        """ Input model can actually now be a list of them. It can also be in different forms, still: """
        if isinstance(model, dict):
            " Good; this is what it's supposed to be. Proceed"
        elif isinstance(model, list) and isinstance(model[0], str):
            " This is a simple single model but in old fashioned format. Convert and proceed"
            return (self.bysurvey(
                surveys,
                self.toDict(model),
                includePooled=includePooled,
                eliminateMissing=eliminateMissing,
                forceKeepVars=forceKeepVars))
        elif isinstance(model, list) and isinstance(
                model[0], dict
        ):  # added late July 2008: dangerous.. this has been working for a while. Why now not?
            " This is a list of dicts. Convert each one to a set over surveys."
            fafa = self.bysurvey(
                surveys,
                model[0],
                includePooled=includePooled,
                eliminateMissing=eliminateMissing,
                forceKeepVars=forceKeepVars)
            return ([
                self.bysurvey(
                    surveys,
                    oneDict,
                    includePooled=includePooled,
                    eliminateMissing=eliminateMissing,
                    forceKeepVars=forceKeepVars)[0] for oneDict in model
            ])
        else:  #elif isinstance(model,list) and all([isinstance(mm,dict) for mm in model]): # Simple list of dicts
            " Some kind of list. Let recursion figure out what."
            modelsout = []
            for mm in model:
                modelsout += self.bysurvey(
                    surveys,
                    mm,
                    includePooled=includePooled,
                    eliminateMissing=eliminateMissing,
                    forceKeepVars=forceKeepVars)
            return (modelsout)
##         elif isinstance(model,list) and not isinstance(model[0],list): # This is a single, list-form model
##             model=convertMtoDict(model)
##         if isinstance(model,list) and not isinstance(model[0],str): # This is a single, list-form model
##             model=convertMtoDict(model)
##         if isinstance(model,list) and (isinstance(model[0],dict) or isinstance(model[0],list)): # This is a list of models
##             # So iterate recursively over them, and then return
##             modelsout=[]
##             for mm in model:
##                 modelsout+=self.bysurvey(surveys,mm,includePooled=includePooled,eliminateMissing=eliminateMissing,forceKeepVars=forceKeepVars)
##             return(modelsout)

        shortname = defaults['shortnames']
        # If model has three elements:
        #assert(len(model)==3)
        rows = []
        removed = []
        if isinstance(surveys, str):
            surveys = [surveys]

        for surv in surveys:
            # Skip full parsing of the various ways the third argument can be specified. Assume it's a list of pairs already.
            # Check that the dependent variable is available for this survey:
            if 'depvar' in model:
                if not inanyCodebook(model['depvar'].replace(
                        'lnR', '').replace('ln', ''),
                                     surv) and not isGeneralVar(
                                         model['depvar']) and not model[
                                             'depvar'] in forceKeepVars:
                    debugprint(
                        'Dropping this regression altogether! %s is not in %s'
                        % (model['depvar'], surv))
                    continue

            if ' if ' in model['model']:
                mm = model['model'].replace(' if ', ' if d%s==1 & ' % surv)
            else:
                mm = model['model'] + ' if d%s==1 ' % surv
            forceDropVars = []
            if 'depvar' in model:
                forceDropVars = model['depvar']
            if eliminateMissing:
                mm, removeda = self.removeUnavailableVariables(
                    mm,
                    surv,
                    forceKeepVars=forceKeepVars,
                    forceDropVars=forceDropVars)
                removed += removeda
            else:
                removed = []

            newrow = deepcopy(model)
            newrow['model'] = mm
            if 'flags' not in newrow:
                newrow['flags'] = []
            newrow['flags'] += [
                ['survey', surv]
            ]  # This "surv" will be translated later into a shortname version and in small font, but do not do it here, since this model liine may be parsed further.
            #rows+=[{'name':model['name'],'model':mm,'flags':model['flags']+[['survey',surv]]}        ]
            rows += [newrow]

        if removed:
            debugprint('    bysurvey: Removed: ', ','.join(removed))
        if includePooled and len(surveys) > 1:
            # Eliminate all variables not available in *all* surveys (!)
            conditionAny = ' | '.join(['d%s==1' % surv for surv in surveys])
            if ' if ' in model['model']:
                mma = model['model'].replace(' if ', ' if (%s) & ' %
                                             conditionAny)
            else:
                mma = model['model'] + ' if (%s) ' % conditionAny
            if eliminateMissing:
                for surv in surveys:
                    mma, removeda = self.removeUnavailableVariables(
                        mma, surv, forceKeepVars=forceKeepVars)
                    removed += removeda
            else:
                removed = []
            pooled = deepcopy(model)
            pooled['model'] = mma
            pooled['flags'] += [['survey', 'all~%d' % len(surveys)]]
            return ([pooled, rows])
        else:
            return ([rows])

    def _OBSELETE_DELETEME_readRegressionFile(self,
                                              tableFileName,
                                              useOUTREG2=False):
        assert 0  # This is obselete as of August 2009. Keep it around for a year. It could be renamed readOutreg2
        """
        Read regression results table made by Stata's outreg2 or Stata's est2tex...
        As of 2009 August, this is probably obselete, since I am moving to read the log files directly.
        
        """
        import os
        tableFilePathNoSuffix = defaults['paths']['tex'] + tableFileName
        if not os.path.exists(tableFilePathNoSuffix + '.txt'):
            print ' Missing %s... Rerun Stata' % str2latex(tableFileName)
            return (r'\newpage{ Missing %s... Rerun Stata}\newpage' %
                    str2latex(tableFileName))
            #self.append    (r'\newpage{\huge Missing $%s$... Rerun Stata}\newpage'%tableFileName)
            #return(outs)
        #print '  Reading '+defaults['paths']['tex']+tableFileName+'.txt  --> '+str(tableFileName)+' ['+str(produceOnly)+'] '+str(extraTexFileSuffix)+' in --> '+self.fpathname

        if not useOUTREG2 and len(
                open(tableFilePathNoSuffix + '.txt', 'rt').readlines()) > 97:
            print " Cannot use est2tex with more than 100 output lines. Stupid junk..."
            assert 0

        # Note the date that this regression was done.
        import time, os
        regressionDate = time.ctime(
            os.path.getmtime(tableFilePathNoSuffix + '.txt'))
        #comments+=' Regression carried out on '+regressionDate

        # Interim code: figure out whether it's new or old format. Remember, outreg2 is slow, so still use the other for now unless needed.
        infileUsedOutreg2 = open(tableFilePathNoSuffix + '.txt',
                                 'rt').readlines()[1][0:9] == 'VARIABLES'
        if not useOUTREG2 == infileUsedOutreg2:
            print(
                '************** OUTREG2 CHOICE DOES NOT MATCH!! SKIPPING THIS TABLE!'
            )
            print tableFileName + ': outreg2=' + str(useOUTREG2)
            return (None)  #return(outs)

        if not useOUTREG2:
            trows = [
                line.strip('\n\r').split('\t')[1:]
                for line in open(tableFilePathNoSuffix + '.txt', 'rt')
                .readlines()
            ][1:]  #Drop first row; drop first column of ech row
            """
1		c0	c1	c2	c3	c4	c5
1	cons	5.853	5.231	3.35	5.084	4.707	1.496
2		(.953)	(1.238)	(1.604)	(.806)	(1.524)	(1.728)
"""
        else:  # txt file was created by OUTREG2... Deal with it's differences
            trows = [
                line.strip('\n\r').split('\t')[0:]
                for line in open(tableFilePathNoSuffix + '.txt', 'rt')
                .readlines()
            ][3:
              -1]  #Drop first three rows and final ; drop first column of ech row
            # For outreg case, change some things so they're compatible with older version:
            trows = [tt for tt in trows if not tt[0] == 'R-squared']
            for tt in trows:
                tt[0] = tt[0].replace('Observations', 'e(N)').replace('_', '-')
            #  Above line does not change trows.?.?
            assert not any([tt[0] == 'R-squared' for tt in trows])
        if any([tt[0] in ['e(r2-a)', 'r2_a'] for tt in trows]):
            trows = [tt for tt in trows if not tt[0] == 'e(r2)']
            assert not any([tt[0] in ['e(r2)', 'r2'] for tt in trows])

        # Kludge: strip out z- prefix for beta mode:
        for row in trows:
            if row[0].startswith('z-'):
                row[0] = row[0][2:]

        # Strip out HERE ?.?. empty pairs??? (no, it's done later. If things seem buggy, maybe there are >100 variables)
            """
	(1)	(2)	(3)	(4)
VARIABLES	lifeToday	lifeToday	lifeToday	lifeToday
				
lnincomeh2	0.326***	0.309***	0.362***	0.389***
	(0.0576)	(0.0663)	(0.0534)	(0.0602)
"""
        return ({'trows': trows, 'regressionDate': regressionDate})

    def str2models(self, statacode, defaultModel=None, before='before'):
        """ Oct 2009: allow regTable to accept what is essentially a do-file of regressions......
        This started out accepting only 

Nov 2009: Now adding defaultModel as a way to add flags...


Dec 2009: add facility for statacode to be a list. some can be dicts (models), or '|', or strings of stata code..


2010 Feb: Added new option 'before' which can be used to specify which type of 'code' element the inter-regression text becomes.  For instance, you may very well want to set it to be 'loadData' to make it come before anything else.

2010 March: take new comment: *flag:string   at beginning of line sets "string" to True as a flag for the subsequent model.

2011 May: adding "*storeestimates:name" (if name: already given, will just use that. but colon needed no matter what)

I've added various other flag/settings specified starting with *.

"""
        if isinstance(statacode, list):
            lmodels = []
            for mss in statacode:
                if isinstance(mss, dict):
                    self.updateToDefaultModel(mss, defaultModel)
                    lmodels += [mss]
                elif mss == '|':
                    assert lmodels
                    self.addSeparator(lmodels)
                elif isinstance(mss, str):
                    lmodels += self.str2models(mss, defaultModel=defaultModel)
            return (lmodels)

        lines = [LL.strip('\n ') for LL in statacode.split('\n') if LL.strip()]
        models = []
        precode = ''
        moreCodes = {}
        extraFields = {}  # Some fields can be specified by string.
        if not defaultModel:
            defaultModel = {}
        for aline in lines:  #TOdo2015: Integrate use of parseStataComments(txt) here:
            if aline in ['|', '*|'
                         ]:  # Syntax to put a divider line between two models.
                #assert models
                self.addSeparator(models)
                continue

            words = [LL for LL in aline.split(' ') if LL]
            method = words[0]
            if method in [
                    'ivregress', 'ivreg'
            ]:  # These take a second word, typically "2sls". ivreg2 does NOT.
                method = ' '.join(words[0:2])
                words = [method] + words[2:]
            if method in [
                    'svy:reg', 'svy:regress', 'reg', 'areg', 'regress', 'rreg',
                    'ologit', 'glogit', 'oprobit', 'logit', 'probit', 'xtreg',
                    'ivregress 2sls', 'ivreg 2sls', 'ivreg2', 'glm'
            ]:
                depvar = words[1]
                therest = ' '.join(words[2:])
                if '[' in aline:
                    model, regoptions = therest.split('[')
                    regoptions = '[' + regoptions
                    if ',' not in regoptions:
                        regoptions += ' ,'
                elif ',' not in therest:
                    model, regoptions = therest, ''
                else:
                    model, regoptions = therest.split(',')
                if ',' not in regoptions:
                    regoptions = ', ' + regoptions
                if 'robust' not in regoptions and 'vce(' not in regoptions and not method.startswith(
                        'svy:') and not '[iw=' in regoptions and method not in [
                            'rreg'
                        ]:  # Stata says can't do robust if iw?
                    regoptions += ' robust '  # Safety... I do not think it ever hurts? 

                toaddmodel = deepcopy(defaultModel)
                assert before not in moreCodes
                toaddmodel.update({
                    'model': model,
                    'depvar': depvar,
                    'method': method,
                    'regoptions': regoptions,
                    'code': {
                        before: precode,
                        'after': '',
                    }
                })
                toaddmodel.update(extraFields)
                toaddmodel['code'].update(moreCodes)
                models += [toaddmodel]
                precode = ''
                loaddata = ''
                moreCodes = {}
                extraFields = {}
            #elif aline=='*|': 
            #    self.addSeparator(models)#       models+='|'

            # TO DO!!!! This section should use parseStataComments(txt) instead.

            elif method in ['gzuse', 'use']:
                if 'loadData' not in moreCodes:
                    moreCodes['loadData'] = ''
                moreCodes['loadData'] += aline + '\n'
            elif aline.startswith(
                    '*name:'):  # Syntax to add a flag to next model
                precode += aline + '\n'
                extraFields['name'] = ':'.join(aline.split(':')[1:])
            elif aline.startswith(
                    '*storeestimates:'
            ):  # Syntax to use Stata's "estimates store" after the regression [May 2011]
                precode += aline + '\n'
                sname = aline.split(':')[1]
                if 'name' in extraFields:
                    sname = ''.join([
                        cc for cc in extraFields['name']
                        if cc.isalpha() or cc.isdigit()
                    ])
                assert sname
                assert not dgetget(defaultModel, ['code', 'testsAfter'], '')
                moreCodes['testsAfter'] = """
                estimates store """ + sname + """
                """
                extraFields['stataStoredName'] = sname
            elif aline.startswith(
                    '*autoExcludeVars:'
            ):  # Syntax to allow a non-missing variable to be missing for all in the sample.
                extraFields['autoExcludeVars'] = aline.split(':')[1]
            # To do: Following feature started to be implented July 2015. Erase this when it's done.
            elif aline.lower().startswith(
                    '*groupname:'
            ):  # Syntax to allow, in non-transposed mode, another title row labeling individual or groups (if they're adjacent) of columns. The "*name:" parameter is still shown, in another row below.
                extraFields['modelGroupName'] = aline.split(':')[1]
            elif aline.startswith(
                    '*meanGroupName:'
            ):  # Syntax to allow grouping of estimates for calculating group mean coefficients
                extraFields['meanGroupName'] = aline.split(':')[1]
            elif aline.startswith(
                    '*flag:'):  # Syntax to add a flag to next model
                precode += aline + '\n'
                aflag = aline[6:]
                extraFields['flags'] = extraFields.get('flags', {})
                if '=' in aflag:
                    extraFields['flags'][aflag.split('=')[0]] = aflag.split(
                        '=')[1]
                else:
                    extraFields['flags'][aflag] = 1
            elif aline.startswith(
                    '*flags:'):  # Syntax to add a flag to next model
                # Example with three flags: *flag:CR=foo:thisone=yes:robust
                # This means you cannot have a colon in a flag value. Oh no. I think I should retract that feature. Okay, I'm changing it so that you can use "flags" if you want more than one, but none with a colon.
                for aflag in aline.split(':')[1:]:
                    extraFields['flags'] = extraFields.get('flags', {})
                    if '=' in aflag:
                        extraFields['flags'][aflag.split('=')[
                            0]] = aflag.split('=')[1]
                    else:
                        extraFields['flags'][aflag] = 1
            elif aline.startswith(
                    '*compDiffBy:'
            ):  # Syntax to invoke an extra line of compensating differentials
                precode += aline + '\n'
                assert len(aline.split(':')) == 2
                assert ' ' not in aline.split(':')[0]
                extraFields['compDiffBy'] = aline.split(':')[1]
            else:
                debugprint(
                    'str2models: assuming line starting with "%s" is NOT a regression command!!!'
                    % method)
                #precode+='* str2models: assuming line starting with "%s" is NOT a regression command!!!\n'%method
                precode += aline + '\n'
        assert not precode  # If it ends with code... I guess this could be put in "post" of the last model.
        return (models)

    ###########################################################################################
    ###
    def updateToDefaultModel(self, models, defaultModel):
        ###
        #######################################################################################

        # The following (Sept 2008) makes redundant a whole bunch of oother flags, like the "depvar" to follow, within regTable. In Dec 2009, I moved this section of code here so that str2models could also use it.
        """
        Have I overlooked this since??
        Do I need it to treat 'code' like 'flags'?
        """
        if isinstance(models, dict):
            models = [models]
        if 1:
            for amodel in models:
                for field in defaultModel:
                    assert (
                        field not in amodel or field == 'flags' or
                        amodel[field] == defaultModel[field]
                    )  # I am attempting to overwrite something. This is dangerous. Except that I allow extra "flags" to be specified this way.
                    if field == 'flags' and field in amodel:
                        defflags = parseFlags(defaultModel['flags'])
                        modelflags = parseFlags(amodel['flags'])
                        for ff in defflags:
                            assert ff not in modelflags  # You can use defaultModel to add extra flags, but not to overwrite existing flags.
                            modelflags[ff] = defflags[ff]
                        amodel['flags'] = modelflags
                    if field not in amodel:
                        amodel[field] = deepcopy(defaultModel[field])
        return (
        )  # I do not think it is necessary to return anything... The above should be written not to overwrite pointers.

    ###########################################################################################
    ###
    def generateLongTableName(self, tablename, skipStata=False):
        ###
        #######################################################################################
        # 2009Sept: Following section seems obselete now that I am not using est2tex. Let's keep the three-letter prefix anyway, but no longer truncate the rest of the filename. I'll do this just by changing the name length parameter from 25 to 100
        # Following section gives a semi-unique name for the table, but if ever the assert catches, I should just change code to  rename the output file when it's done (est2tex requires the file to have the same, length-limited name as the matrix...).  output .txt file then will get renamed to tablenamelongform when done.
        aa = 'ABCDEFGHIJKLMNOPQRSTUVWXZY'
        maxnamelength = 100
        tablePrefixes = [a for a in aa]
        for a in aa:
            for b in aa:
                tablePrefixes += [a + b + c for c in aa]
        # make a two-letter prefix which depends on exact *full* name, which will then be truncated:
        pref = tablePrefixes[sum([ord(a) ^ 2
                                  for a in tablename]) % len(tablePrefixes)]
        tablenamel = pref + '-' + ''.join(
            [c for c in tablename if c not in ' ():;"|-'
             ])[0:(maxnamelength - 3 - 1 - len(self.modelVersion) - len(
                 self.regressionVersion)
                   )] + '-' + self.modelVersion + self.regressionVersion
        tablenamelongform = ''.join(
            [c for c in tablename if c not in '():;"|']).replace(
                ' ', '-').replace(
                    '_',
                    '-') + '-' + self.modelVersion + self.regressionVersion
        assert tablenamel not in self.txtNamesUsed or skipStata == True  # If this occurs, you probably need to make sure you are reloading pystata each time you run your program. Aug 2010: no longer: i now reset it on each instance. so shouldn't happen.
        self.txtNamesUsed += [tablenamel]
        # Put a pointer in all models to let them know what table they're in (why? e.g. for subSampleAnalysis)
        return (tablenamel)

    ###########################################################################################
    ###
    def suestTests(self,
                   twomodels,
                   skipStata=False,
                   tablename=None,
                   modelSuffix=None):
        ### WaldCompareTwoModels
        #######################################################################################
        """ May 2011:
        use '*storeestimates' in str2models to store previous two models in Stata.
        Then call this to add a new model which will consist just of a bunch of tests: on each common coefficient and on all at once (Chow test)

        This should return a model to add to a list of models...
        
        twomodels (could be more?) should be able to be existing model dicts.

        If tablename is given, it will ... no...

        Okay, to make this work you need to use svy:reg. Otherwise it gets upset about using pweights OR clustering...

        modelSuffix: beats the hell out of me. Stata is inconsistent. Kludge. ah!

        (why wouldn't stataStoredName just be the same as stataModelName, which already exists?)
        """

        snames = [
            twomodels[0]['stataStoredName'], twomodels[1]['stataStoredName']
        ]
        m1, m2 = twomodels
        assert snames[0]
        assert snames[1]
        assert 'cluster' not in twomodels[0].get('regoptions', '')
        assert 'cluster' not in twomodels[1].get('regoptions', '')

        # Find commen variables. It would be nicest to do this from estcoefs, but that's maybe not available.
        vlists = [[
            mm for mm in twomodels[0]['model'].split(' if ')[0].split(' ')
            if mm not in ['cons']
        ], [
            mm for mm in twomodels[1]['model'].split(' if ')[0].split(' ')
            if mm not in ['cons']
        ]]
        depvars = [vlists[0][0], vlists[1][0]]
        assert depvars[0] == depvars[1]
        # Find common elements:
        regressors = list(set(vlists[0][0:]) & set(vlists[1][0:]))
        regressorsNoStars = [vv for vv in regressors if '*' not in vv]

        if modelSuffix is None:
            modelSuffix = ''
        if isinstance(modelSuffix, str):
            modelSuffix = [modelSuffix] * 2
        assert isinstance(modelSuffix, list) and len(modelSuffix) == 2

        ##suestTest() in pystata??
        statacode = ("""
        *BEGIN SUEST TESTS TWOMODELS
        suest %(sn0)s %(sn1)s
        """ + '\n'.join([
            """
        *CPBLWaldTest:""" + vv + """
        test [%(sn0)s%(sfx1)s]""" + vv + """ =  [%(sn1)s%(sfx2)s]""" + vv + """
        """ for vv in regressorsNoStars
        ]) + """
        *CPBLChowTest:
        test [%(sn0)s%(sfx1)s =  %(sn1)s%(sfx2)s]
        *estimates drop
        *END SUEST TESTS TWOMODELS
        """) % {
            'sn0': snames[0],
            'sn1': snames[1],
            'vvs': ' '.join(regressors),
            'sfx1': modelSuffix[0],
            'sfx2': modelSuffix[1]
        }

        commonFlags = dict([[a, b] for a, b in m1.get('flags', {}).items()
                            if a in m2.get('flags', {}) and b == m2['flags'][a]
                            ])

        assert not any(['ncome' in mm['depvar'] for mm in twomodels])
        print '  Creating SUEST TESTs for models %s  and %s ' % (m1['name'],
                                                                 m2['name'])

        return (dict(
            special='suestTests',
            name=r'$p$(equal)',
            flags=commonFlags,
            code={'after': statacode},
            method='suest',
            model=' '.join(regressors),
            depvar=depvars[0]))

    def duplicateAllModelsToDualBeta(self, models):
        """
        Add a normalized (beta) version of each model immediately following it: only if it's OLS or xtreg (That's a weird thing; it would be normalizing the underlying variables, before taking first differences, etc).
        """
        from copy import deepcopy
        if isinstance(models, basestring):
            models = self.str2models(models)
        for imm in range(len(models))[::-1]:
            newm = deepcopy(models[imm])
            assert isinstance(newm, dict)
            assert 'beta' not in newm['regoptions']
            if newm['method'] in [
                    'svy:reg', 'svy:regress', 'reg', 'regress', 'rreg', 'xtreg'
            ]:
                # For method in [rreg,xtreg], this "beta" will need to be removed later.
                newm['regoptions'] += ' beta'
                models.insert(imm + 1, newm)
        return (models)

    ###########################################################################################
    ###
    def regTable(
            self,
            tablename,
            models,
            method=None,
            depvar=None,
            regoptions=None,
            variableOrder=None,
            showonlyvars=None,
            hidevars=None,
            forceShowVars=None,
            extralines=None,
            comments='',
            substitutions=None,
            options='',
            attributes=None,
            landscape=False,
            transposed=None,
            combineRows=None,
            suppressSE=False,
            produceOnly=None,
            extraTexFileSuffix=None,
            doPcorr=False,
            stopForErrors=True,
            crcoefsVars=None,
            skipStata=False,
            skipLaTeX=False,
            hidePSumTest=False,
            defaultModel=None,
            hideModelNumbers=False,
            assignSaveCoefficientsPrefix=None,
            hideModels=None,
            showModels=None,
            hideModelNames=False,
            renumberModels=True,
            showFailedRegressions=False,
            multirowLabels=False,
            betas=False,
            followupFcn=None,
            followupArgs=None,
            showCompDiff=None,
            returnModels=False,
            postPlotFcn=None,
            postPlotArgs=None,
            autoCreateVars=True,
            captureNoObservations=None,
            skipReadingResults=False
    ):  # Do a set of regressions; output results to .tex and .txt files 

        # retired options: useOUTREG2=False,
        ###
        #######################################################################################
        if stopForErrors == False:
            print(
                '******************* WARNING!!!!!!! WHY WOULD YOU USE STOPFORERRORS=FALSE??? tHIS IS SUPPRESSING ALL OUTPUT, INCLUDING ERRORS AND WARNINGS, FROM REGRESSIONS!*********** Use the autoexcludevars flag in the model struct instead!!! April2010: No, use replaceFailsWithDummy. No, use the object-level or table-level captureNoObservations'
            )  # Well, it should be called dummiesForEmptyRegressions, which is better.: capture reg adn then if _rc==2000, do dummy. (or 2001, insufficient obs)
            1 / 0
        """
        This is a core part of the stata LaTeX class. It generates Stata code to perform a series of regressions and it manages production of LaTeX tables in various formats to present the results from Stata (the guts of the LaTeX code generation are in a separate function).
        Among its many features / abilities are:

        - can display the coefficients of two variables on the same line. e.g. if different models use real or nominal income, these could for compactness both be displayed on one line as income.

        - the order of displayed variables can be specified

        - the order of any housekeeping information rows (e.g. R^2, N, etc) can be specified

        - extra lines can be added to the table to be filled in by hand

        - comments can be placed in the table caption

        - more readable variable descriptions (including LaTeX code) can be substituted for the raw variable names

        - columns (rows) denoting characteristics of the different models in the table can be generated (attributes=). These could show checkmarks or X's or other words.  I do not understand what this parameter does. So I am deprecating it (Aug 2009)

        - landscape or standard orientation may be specified or automatically chosen

        - transposed or standard layout for the table (ie models as columns or rows) may be specified or automatically chosen

        - standard errors can be shown or suppressed.

        - P-values are calculated from standard errors and significance can be shown with stars or with coloured highlighting. This choice can be changed later (at any time) simply for an entire table through setting a LaTeX switch.

        - When a similar model is run separately on each of several datasets (surveys), the resulting coefficients can be averaged over the different datasets.  Output tables can be displayed in several modes: with or without the averages shown; with only averages shown, etc.

        - dividing lines can be specified to separate groups of regressions or groups of covariates.

        - can include special code to be run before or after each regression.

        - as a very specialised feature, it can optimally combine a series of models which have a "drilling-down" series of spatial dummies. That is, I may run a model with geographic dummies at province level, then with metro level dummies, then city level dummies, then CT level, etc.  This function can combine those into sensible inferred coefficients for an income effect at each level. This is obviously not a generally useful application, but it's built in here.

    The set of models to run can be specified in two formats (see regTableOldForm). The modern one is as a list of Python dicts, with fields as specified below.
    
The argument regoptions includes code that should come after the variables to regress: typically, a weight specification, possibly followed by a comma and some Stata options., e.g. "cluster" "beta"..

N.B. if the "beta" option is given to Stata in a reg command, it is intercepted here, all the variables are normalised, and a robust weighted regression is done to create beta coefficients in place of the normal regression output. This results in the same coefficients as Stata produces, but allows full standard error calculation, etc.

betas: Alternatively, an entire table can be turned into betas (if it is OLS) by giving the betas=True option.   If you want both raw and beta versions of each model, use the function     duplicateAllModelsToDualBeta()

The argument "models" is a list of [dicts and lists of dicts]. Dicts have the following tags (and maybe more):

'name': model name,
        If left blank, the dependent variable will be used for column headings in normal layout.
        In transposed layout, the row model label (rowmodelname) will be blank unless this value is specified.
        There's a "hideModelNames" switch, though not reimplemented yet may 2011: doing it now.
'model': variables and ifs,
'flags': dummy flags and condition names,
        Some examples:
        ['controls']         -> gets a check in controls field
        [['controls','some'] -> gets "some" in controls field
        [['controls',0]]     -> gets an "x" in controls field
        [['controls',0],'homeowners~only']
        (Actually, I think you can now send flags as a dict. -- nov2009)
'format': column format characters,
'code': with subfields: 'before', 'after', and others: Stata code to run before regression, Stata code to run after regression, but before exporting the results to a textfile with est2vec (now outreg2) (no, now raw log files). Subfield 'afterExport' can be used to run something else after the regression and export is complete. Subfield 'loadData' can be used to run code absolutely before anything else. So, keep track of rules regarding order here: ['loadData' < 'before' < 'afterExport'] and ['after',testsAfter,sumsAfter,existenceConditionAfter' (order of these?)] NEED TO INSERT HERE THE VARIOUS EXTRA STUFF THAT GETS ADDED: cell dummy code; beta code; etc, etc.
            model['code']['cellDummiesBefore']+=stataBeforeOut
            model['code']['cellDummiesAfter']+=stataAfterOut


'regoptions': Extra options to include in the regression command options (for instance, clustering).
'feGroup': contains the name/number of a collection of models to which progressively restrictive dummies have been added; the group should be analysed together to extract coefficients at each level. Actually, there can be whatever properties like this I want. U'm using "CRgroup"
'getSubSampleSums': a list of conditions, to be combined with "if e(sample)", for which to calculate sums of subsamples of the samples used in the estimation. These will get read from the Stata log file and be incorporated into the model dict as 'subsums' element, which can then be acted on by a followupFcn.

aspects like "depvar", "regoptions", "reg" can also be incorporated.
For now, there is a helper function above, to aid in the transition by translating to the dict form.

'compDiffBy'= incomeVariable :  this will solicit the covariance matrix from the regression and calculate compensating differentials for all variables except the one supplied. (Aug 2009)
'compDiffVars'= list or string list of variables for which comp diffs should be calculated and/or displayed. Note that regTable has a table-level parameter "showCompDiff" which decides whether/how comp diffs should be shown.

'autoExcludeVars'=None:  This says to fill in values (to -999) for all RHS variables which are missing for all records matching the regression's "if" condition. If a string is given in stead of None value, then that string will be used as teh if condition to fill in values.


#'skipNumber'=False: If set to true, this will not increment the latex-displayed number for this model.  So This is supposed to be useful if I have a standardized beta version of a raw coefficients equation following the raw equation. I may want the number to indicate equation number, not estimate number...

The list models is passed here with nested structure (list of lists) but is flattened at the beginning. The grouping (for taking means over multiple surveys) is recorded in combineColumns. Also, for those sets of groups which will all be combined based on CR dummies, the grouping is recorded in dict fields "CRgroup".

## This replaces the old form, in which each models was a list with six elements:
## model:
## [0]: model name,
##         If left blank, the dependent variable will be used for column headings in normal layout.
##         In transposed layout, the row model label (rowmodelname) will be blank unless this value is specified.
## [1]: variables and ifs,
## [2]: dummy flags and condition names,
##         Some examples:
##         ['controls']         -> gets a check in controls field
##         [['controls','some'] -> gets "some" in controls field
##         [['controls',0]]     -> gets an "x" in controls field
##         [['controls',0],'homeowners~only']
## [3]: column format characters,
## [4]: Stata code to run before regression,
## [5]: Stata code to run after regression
## [6]: Extra options to include in the regression command options (for instance, clustering).
## [7]: Extra properties, in the form of a dict. This is used to mark groups of models for CR fixed effects, for example: The dict will have an element {
## )
## I should *really* change the above list to a dict, so that each element can be there or not. Property 7 can grow to subsume all the others, for example.
## New format: (use convertMtoDict() to switch to new format)



The argument "produceOnly=" can specify a mode to restrict the number of output tables. Right now, several tables are created when there are models which are summed over.

    produceOnly='onlyraw' will make just one table per call: just the raw regressions.
    produceOnly='means' will make just two tables per call: one with everything and one with just means.
    produceOnly='withmeans' will produce just one table which shows everything.
    produceOnly='crc' makes just the table of CR dummy coefficients on income (What happened to onlyCRC and withCRC???)
    produceOnly='justmeans' does just means only.

The argument extralines is mostly used by other functions, rather than specifying by hand.. [jul2008].

crcoefsVars is an option to fine-tune the most exotic/specialised/obscure feature of this program, which is extracting cofficients from a series of regressions with different spatial dummies.

hideModels is a real low-level kludge which turns of post-Stata processing and LaTeX display of a subset of models. They are listed by their sequential index in the (otherwise) output, starting from 1. So between this and hidevars, one can simplify tables of disclosed results (ie I cannot rerun Stata once results are released from Statistics Canada, so I have to work with the output as is.)

7 April: Now a 6th element is code after the regression. For instance, to do a statistical test and add the results to r().
For the moment, I will just hardcode in here what I want it to do... the behaviour can be taken out of regseries and put into the 6th entry later.

4 April 2008: I've hardcoded "transposed=True" right now, but transposed='both' is default.

19 March 2008: a 5th element now exists: this is stata code to run before doing the regression..

# March 2008: Now a new 4th element of a model entry  corresponds to either '' or '|'. The latter puts a vertical line after that column. It can be passed as a row by itslef (['|']) in the list of models. 2009OCtober: reinstated parsing '|' in  list of models.

# MArch 2008: move hidevars functionality from stata to the reformatting. ie "showvars" can be used to pass extra things to stata, but only a subset of those (hidevars removed) will end up in python's latex output. Previously the stata est2vec call was in charge of removing hidevars.

# July 2008: The above March 2008 "showvars" is a really bad idea. I've renamed "showvars" to "variableOrder" and created another option, showonlyvars. [Note also: class-setting: self.variableOrder and module default defaultVariableORder]. So the parameters

 - variableOrder (specify ordering in LaTeX of some of the first covariates, if they exist in the regression. It can also specify the order of flags/dummies listed, etc...... [latter part not done yet jul2008]),
 - showonlyvars (specify order and exact set of covariates in LaTeX; this option is risky since it's nto explicit what is being suppressed), and
 - hidevars [used to be called noshowvars] (suppress certain covariates or extrarows/stats info in the output)
- forceshowvars protects variables and properties from getting hidden due to being empty in all displayed models.


all apply to the generation of LaTeX output, *not* to what gets given to Stata. If you want to force extra lines (blank covariates) into the LaTeX output, you can use extralines (?).


        regTable now also produces a latex version with just the non-addend and non-mean  columns.

        # 2008 Feb 29: Version 2 is born: this uses a text output from Stata (without any significance info) rather than the latex output. The LaTeX-sourced version is still available outside this class.
        #
        # Feb 2008: incorporated from standalone to a member of this statalatex class. This is so that it can use the object's texfilename when outputting stuff.
        #
        suppressSE=False says to include standard errors on every second line.
        # If an element of the models array is an array rather than a string, then it is in the form ["name","dependentvars"] rather than just "dependentvars". The "name" is a column name.
        # Other possible formats: ["", "dependentvars", ["booleanAttribute"]]   or  ["", "dependentvars", [["attribute","value"],["otherattribute","anothervalue"]]] ,...
        # reg, depvar,regoptions must be scalar or have the same number of values as models:
        #
        # combineRows is a list of pairs or sets of variable names to combine into one (so both variables must not exist in the same model/column.), leaving/using the first name listed.
        For instance, when I have both real and nominal incomes, I might want the coefficients to appear on the same row, and just have the difference signified with an indicator row later.

        Columns can also be combined, which means something totally different. This takes a mean of each coefficient over several models (!). Typically, these models are identical except that they are run on different, similar surveys.
        To initiate this feature, the simplest way is to group those rows in the model list together as one entry (ie a list of normal-looking rows).
        Each row must be in full format, ie three elements (title, regressors, flags).
        ie you can give a list of rows as one element in the list. Then these will be aggregated after separate regressions are done.

        old description of this:        
        CombineColumns allows this routine to call the aggregateColumns method when it's done. This produces alternate versions with some columns averaged together. Useful for finding average results from similar regressions over multiple surveys.
        Actually, a better way than using combineColumns is to put a element column in a model line. The fourth element, if present, indicates a group name for aggregation.


September 2008:
 Values for method,depvar,regoptions can be specified for all the models at once using EITHER the individual optional parameters by the same name, or by puting those fields into defaultModel, which is a collection of default model features. The field 'flags' is an exception, in that it can be specified in both ways at once, as long as its member fields do not overlap.

        assignSaveCoefficients='b_' would mean that estimated coefficients are saved to the samples used to estimate them. These will be named b_var where "var" is the name of the RHS covariate.

Only one of "hideModels" and "showModels" can be used. Each take a list of model numbers (as shown on a simple raw only table) and only display those ones.
If future versions, one will be able to provide names (list of strings) rather than 1-based indices, or other identifying features (dict, with fields identifying the model feature names and values listing the feature values.)

"hideModelNames" can be used to avoid showing the words associated with a particular model row/column. This is mostly useful to get rid of the ones that are automatically made in the various fancy functions (sums, CRC collection) etc.


Oct 2008: renumberModels: when subset of models seclected, renumber from (1). Sept 2009: this changed to default True. from default False

Dec 2008: In LaTeX output, failed models (ie/eg with r^2 or equivalent 0 or 1) are not shown unless "showFailedRegressions" is set to True.

Aug 2009: Completed betas=True mode


Aug 2009: followupFcn=f(thisLatexClass,models,followupArgs),followupArgs={'arg1':val1, ...etc).  These are to REPLACE postplotfcn etc, which rely strangely on pairedRows etc. More generally, this can do anything it wants. It is a way to extend functionality of regTables, obviously. It is called (and some information maybe addedto followupArgs) after the estimation results have been read in. followupFcn can also be a list of function pointers if you want to do more than one, in sequence. But they all get the same followupArgs.

Aug 2009: showCompDiff= boolean (or could be "only", "aftereach" "atend") which decide whether comp diffs should be shown in the table. "only" would hide everything else. "aftereach" would intersperse comp diff cols with regressions coef cosl; "atEnd" would put them in a separate group at end of the same table. If it's not specified, but some comp diffs are asked for at the model level, then this should default to something. Say, "aftereach". Same if showCompDiff=True.

Oct 2009: returnModels= boolean : If set to True, then the models list of dicts that was passed will be updated to include all estimtes and modifications etc. This is useful if you want to use the results to make some more plots or etc (an alternative to followupFcn, I suppose).

Nov 2009: autoCreateVars=True/False: This will do a "capture gen var=0 " on all variable names to ensure that some specification incompatibility does not stop the regression from running. This makes it easier to run the same specification on multiple surveys.  See by contrast/also, the model dict element "autoExcludeVars" which will do a similar thing (but only temporarily) for variables which are 100% missing just for the regression equation sample. (see above)

skipStata can be True, False, or 'noupdate'.  The latter means only run Stata for a table if it does not already exist. Oh,wait. No. I take it back. I am killing this noupdate option now.


April 2010: captureNoObservations: allows regressions to be called which have no observations. It replaces such with a _dummyOne regression.


May 2011: I need to split this up into a display portion and a Stata portion... Or else make an option to skip reading from log files, ie to process model dicts whic may be modified for kludging, and not to regenerate results from Stata output.... hmmm.  For now I'm just making a skipReadingResults option.

Aug 2011: New field of model struct: "isManualEntry". If you want to add/insert a custom row with minimal (no!) processing, set this to True.

Aug 2012: Now deals with regressors of form "i.var" (and even i.var#var2 etc)  as follows: assume we're not interestd in the coefficients. Therefore, (1) hide it from estimate results (since estimates table doesn't use the variable names for such dummies) but also, let's not create it if it doens't exist (yet), because we want regressions to fail if not-shown variables are mistakenly absent.

Limitations:
It is only specifically savvy about regress (OLS), logit and ologit at the moment.

Should not be too hard to convert to using R, since the stata-specific parts are fairly well circumscribed or functionalised (e.g. reading Stata text output directly to get results, ugh.)

Bugs:
?
        """
        if captureNoObservations == None:
            captureNoObservations = self.captureNoObservations
        if captureNoObservations == None:  # Dec 2010: new default, since it's always an advantage.
            captureNoObservations = True

        if '_' in tablename: tablename = tablename.replace('_', '-')
        if skipStata == True and self.skipAllDerivedTables == True:
            print " REGTABLE:  !! Skipping an entire table " + str(
                (tablename, extraTexFileSuffix)
            ) + " because it is a derived table, not one that controls Stata. Set the latex.skipAllDerivedTables==False to correct this special behavoiure"
            return ('')
        assert not skipStata or not skipLaTeX  # (really?)
        if self.skipAllDerivedTables == True:
            skipLaTeX = False

        #
        #print 'depvar:',depvar
        #print 'models:' ,models
        #print 'len models: ',len(models)
        #print 'showvars:',showvars
        import os

        #from cpblUtilities import unique

        #################### MEMBER / UTILITY   FUNCTIONS FOR REGTABLE():

        def parseFlags(flags):
            """Take the 'flags' element of a model dict and turn it into a dict. Return the dict. The dict is less compact, maybe, than, e.g. a list of things that are just "turned on", ie "Yes".
            """
            if not flags:
                return ({})
            if isinstance(flags, dict):
                for kk in flags:
                    if flags[kk] in ['yes', 'true', 'True', True]:
                        flags[kk] = r'\YesMark'
                    if flags[kk] in ['no', 'false', 'False', False]:
                        flags[kk] = r'\NoMark'
                return (deepcopy(flags))
            if isinstance(flags, str):
                dictFlags = {flags: r'\YesMark'}
            elif isinstance(flags,
                            list):  # model[2] must be a list if not a str.
                dictFlags = [[atts,r'\YesMark']  for atts in flags if isinstance(atts,str)] \
                    + [atts  for atts in flags if isinstance(atts,list) and isinstance(atts[1],str)] \
                    + [[atts[0],r'\YesMark']  for atts in flags if isinstance(atts,list) and isinstance(atts[1],int) and atts[1]==1] \
                    + [[atts[0],r'\NoMark']  for atts in flags if isinstance(atts,list) and isinstance(atts[1],int) and atts[1]==0]

            return (dict(deepcopy(dictFlags)))

        assert attributes == None  # Deprecating this.

        DO_NOT_DEEPCOPY = True  # Warning!!! April 2010: I am changing things so that it's up to the caller to do a deepcopy before passing models to regTable.  This is a good idea if some of the elements of the models might point to common objects, and these ojbects may be modified per model. But I need to be able to pass things like showModels and hideModels as pointers to elements of the original models list, so doing deepcopy messes things up.   Hey, maybe I could test for redundancy by checking the memory length of oriinal and deepcopy of it? It different, there were some common pointers... [?Not done yet]
        if DO_NOT_DEEPCOPY:
            print '' + 0 * """   Warning: April 2010: I am eliminating deepcopying ... it's up to the caller now to do this in advance. Check your update() calls in making the models list for regTable."""

        if variableOrder == None and showonlyvars == None:
            if self.variableOrder is not None:
                variableOrder = self.variableOrder
            else:
                variableOrder = defaultVariableOrder  # This is a rather customised assumption okay for CPBL thesis work. Set the default, at top of this file, to an emtpy string (or disable this line) to get rid of the effect...
        assert not (variableOrder and showonlyvars
                    )  # Only one should be specified
        # Could I not just set variableorder to showonly vars here, too? Trying that, Aug 2009:
        if showonlyvars:
            variableOrder = showonlyvars

        assert extraTexFileSuffix or (
            not skipStata == True
        ) or produceOnly  # Otherwise this output .tex will overwrite the main one (though it may not be used). If you use "skipStata", provide the suffix to differentiate the LaTeX output.
        if extraTexFileSuffix == None:
            extraTexFileSuffix = ''

        if followupArgs == None:
            followupArgs = {}

        if isinstance(models, dict):
            print " CAUTION!!!!! IF you pass the models as a single dict, rather than a list of dicts, you will not receive back an updated (ie with estimates) version in the same pointer. It is better always to pass a list. OCtober 2009"
            models = [models]
        if models.__class__ in [str, unicode]:
            models = self.str2models(models)
        from copy import deepcopy
        originalModels = models
        # Well, then, given above, I don't undrstand why the following works. (oct 2009)
        # April 2010: What is the following!!? I am aam turning this off if returnModels is true:
        if not DO_NOT_DEEPCOPY and not returnModels:
            models = deepcopy([mm for mm in models if mm])  # Ignore blanks
        #produceOnly='crc'
        possibleIncomeVars = 'lnIncome lnIndivIncome lnHHincome lnAdjHHincome da_lnavHHincome ct_lnavHHincome csd_lnavHHincome cma_lnavHHincome pr_lnavHHincome lnRHHincome da_lnRavHHincome ct_lnRavHHincome csd_lnRavHHincome cma_lnRavHHincome pr_lnRavHHincome da_lnavIndivIncome ct_lnavIndivIncome csd_lnavIndivIncome cma_lnavIndivIncome pr_lnavIndivIncome lnRIndivIncome da_lnRavIndivIncome ct_lnRavIndivIncome csd_lnRavIndivIncome cma_lnRavIndivIncome pr_lnRavIndivIncome  ct_vm_lnHHincome ct_ag_lnHHincome ct_al_lnHHincome csd_vm_lnHHincome csd_ag_lnHHincome csd_al_lnHHincome cma_vm_lnHHincome cma_ag_lnHHincome cma_al_lnHHincome  '  # Agh.. AdjHHincome should really be scaled? no. the thought experiment is raising everyone's income.
        outreg2complete = True

        possibleIncomeVars = (possibleIncomeVars + possibleIncomeVars.replace(
            '_', '-')).split(' ')

        #self.append('\n'+[r'\clearpage\section',r'\subsection'][int(skipStata==True)]+'{%s (%s) ~[%s]}'%(tablename.replace('_','~'),extraTexFileSuffix.replace('_','~'),produceOnly))
        self.append(r"""
\clearpage \newpage \clearpage
""")  # Don't have figures etc mixed between sections of relevant tables.
        assert not skipLaTeX or not extraTexFileSuffix
        if self.compactPreview and not skipLaTeX:
            self.append('\n%' + [r'\section', r'\subsection'
                                 ][int(skipStata == True)] + '{%s (%s) ~[%s]}'
                        % (tablename.replace('_', '~'), extraTexFileSuffix.
                           replace('_', '~'), produceOnly) + '\n')
        elif not skipLaTeX:
            self.append('\n' + [
                r'\section', r'\subsection'
            ][int(skipStata == True)] + '{%s (%s) ~[%s]}' % (tablename.replace(
                '_', '~'), extraTexFileSuffix.replace('_', '~'), produceOnly))

        # Flatten structure of list of models:
        # Until Sept 2009, the way to denote mean-groups (groups of models to take a mean over) was by grouping them together in a sub-list. But if instead the "meanGroupName" fields are set in consecutive models, this could be used to construct the groups. I must continue to support the old method, and avoid mixing them?...
        # Algorithm at the moment is to flatten the list first (taking note of implied groups), and then look for the sumGroupNames afterwards.
        # I've enforced that meanGroupNames specified outside this function must be strings, while automatic markings herein are integers.
        #
        # Find expanded length of models: some rows can be wrapped up in to-aggregate groups:
        # Also, some "models" are actually just strings that mark a request for a separator in the table. No! The latter should not be true anymore. separators are noted within model dicts. [Oct 2009: Why?! I am reinstating this string feature.]
        def parseModelSeparators(mods):
            iSeparators = [
                ii for ii in range(len(mods))
                if isinstance(mods[ii], str) and mods[ii] == '|'
            ]
            if 0 in iSeparators:
                print '***** Bug: not sure how to deal with separator at beginning of a group!'
                iSeparators.pop[0]

            for ii in iSeparators[::-1]:
                if not isinstance(mods[ii - 1], dict):
                    foiu
                    print '***** Bug: not sure how to deal with separator right after a group!'  # Maybe ignore it? Sicne there will be one anyway..?
                else:
                    mods.pop(ii)
                    assert not 'format' in mods[ii - 1]
                    mods[ii - 1]['format'] = 'c|'
            return ()

        fullmodels = []
        combineColumns = []
        #if transposed==None:
        #    transposed=True
        sumGroup = 0  # Label for sumGroups.
        parseModelSeparators(models)
        for row in models:
            if isinstance(row, list) and isinstance(
                    row[0],
                    dict):  # If this "model" is really a group of models
                # We've found a group. Are they also labelled with group name? If so, they must all be the same:
                if any(['meanGroupName' in model for model in row]):
                    assert all([
                        'meanGroupName' and
                        model['meanGroupName'].__class__ in [str, unicode]
                        for model in row
                    ])

                # First, go through this group and look for any strings (not done yet : june 2008. maybe drop this feature.)

                parseModelSeparators(row)
                fullmodels += row  # Add them all as separate entries.
                if len(
                        row
                ) > 1:  # If there is more than one model in this group of models
                    sumGroup += 1  # Label for new group of models to sum
                    for mm in row:
                        assert isinstance(mm, dict)
                        if not 'meanGroupName' in mm:
                            mm['meanGroupName'] = str(
                                sumGroup
                            )  # Hm.. I am using meanGroupName for both numbers (auto) and string (named) format. 
                    print(
                        ' Found group "%s" of %d regressions whose coefficients I should aggregate...'
                        % (mm.get('meanGroupName', str(sumGroup)), len(row)))

            else:
                assert isinstance(row, dict)
                fullmodels += [row]
        alreadyProcessedMeans = [
            imm for imm, mm in enumerate(fullmodels) if 'isMean' in mm
        ]
        if alreadyProcessedMeans and not skipReadingResults:
            ##assert 0 # just saw this: should integrete skipreadingfile or whatever it's called, option?  skipReadingResults
            print ' It looks like you have passed an alread-processed set of models.. Dropping %d synthetic mean models out of a passed list %d long... Dropping: ' % (
                len(alreadyProcessedMeans), len(fullmodels)) + str(
                    [fullmodels[imm]['name'] for imm in alreadyProcessedMeans])
            for iimm in alreadyProcessedMeans[::-1]:
                fullmodels.pop(iimm)

        # June 2011: should I drop compdiffs here too??

        if not models:
            print('  regTable found empty models. Aborting...')
            return ('')
        assert models
        assert fullmodels
        models = fullmodels
        nModels = len(models)
        debugprint('--> combineColumns: ', combineColumns)

        # Check and warn if models include pointer duplicates:
        for im, mm in enumerate(models):
            for imm in range(im + 1, len(models)):
                # N.B. use of "is" (object identity), not "==" (value identity / equivalence, defined by whatever is .__eq__) in the following: 
                if models[im] is models[imm]:
                    print ' ** Warning!!!  Your list of models includes duplicate pointers (%dth=%dth). Is that intentional?... If so, you might want to use deepcopy. ' % (
                        im, imm)
                    1 / 0
        # Now also look to see whether "meanGroupName"s have been specified.
        #if sumGroup

        for imm in range(len(models)):
            models[imm][
                'modelNum'] = imm + 1  # An innovation Sept 2008: This ought to simplify some later stuff, no.??. Rewrite all the model/calc numbering, through this functoin. Should do same with the name.

        # Check for separator indicators: simple strings mixed in amongs the dicts. Also add format field # (Obselete...)
        for irow in range(len(models))[::-1]:
            ##if isinstance(models[irow],str) and len(models[irow])>1: #  not a separator; convert 1element to 4 element
            ##    models[irow]={'model':models[irow]} # Probably need to fill in other fields here
            if 0 and isinstance(models[irow],
                                str):  #'format' not in models[irow]:
                """ Maybe drop this feature."""
                print('Found format string? ', models[irow])
                models[irow - 1]['format'] = 'c|'
                models.pop(irow)
                nModels += -1
            elif not 'format' in models[irow]:
                models[irow]['format'] = 'c'

        if 0:  # I don't think I am using these separators yet. Add that feature later.
            # Look for vertical line indicators. These can be lines by themselves. When they are, move them to the 4th element of previous row.
            # Also, enforce (override) vertical separators around any combineColumn groups. I guess I'll need to remake the modelTeXformat for each kind of output file I make.
            # First, just modify the models array so that the 4th element contains a format code:
            for irow in range(len(models))[1:][::-1]:
                # Either the 4th element of a row, or the entirety of the following row, can both indicate a separator:
                if (isinstance(models[irow], str) and models[irow] == '|'
                    ) or irow in [cc[0] for cc in combineColumns]:
                    models[irow - 1][3] = 'c|'
                if irow in [cc[-1] for cc in combineColumns]:
                    models[irow][3] = 'c|'

        # Expand some other arguments that can be strings or lists: THESE SHOULD BE MOVED INSIDE THE DICTS.. Oct 2009: it already is, via defaultModel, below.
        if 0 and isinstance(method, str):
            for mm in models:
                assert 'method' not in mm
                mm.update({'method': method})  # This overwrites.

        # Some of the optional arguments to regTable can all be dealth with using defaultModel:
        if not defaultModel:
            defaultModel = {}
        defaultArgs = [['depvar', depvar], ['method', method],
                       ['regoptions', regoptions]]
        for defarg, argval in defaultArgs:
            assert not (argval and defarg in defaultModel
                        )  #Can't specify value through both forms
            if argval:
                defaultModel[defarg] = argval
        # The following (Sept 2008) makes redundant a whole bunch of oother flags, like the "depvar" to follow.
        if defaultModel:
            self.updateToDefaultModel(models, defaultModel)

        # Hm. What about defaults that I just want to fill in as a backstop? ie it's okay if some exist; I just won't overwrite those. ie. without the "assert" above
        for amodel in models:
            if 'name' not in amodel and not hideModelNames:
                amodel['name'] = amodel['depvar']

        ###plainSubstitutions=substitutions
        if substitutions == None:
            substitutions = self.substitutions  #standardSubstitutions

        # One must never use mutable objects (like lists) as default values in a function definition.
        # (SEe http://effbot.org/pyfaq/why-are-default-values-shared-between-objects.htm and
        #    http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/502206 )
        # So, set them to "None" in the definition, and then redefine them at runtime here:
        #if not substitutions:
        #    substitutions=[]
        if not attributes:
            attributes = []
        if not extralines:
            extralines = []
        if not hidevars:
            hidevars = []
        elif isinstance(hidevars, str):
            hidevars = [hh for hh in hidevars.split(' ') if hh]

        if not forceShowVars:
            forceShowVars = []

        # Get a non-redundant list of all the variables to be included
        # (if it is not overridden by passed value). IT would be nice
        # if the order were in order of appearance.

        # Oogh. To do this properly now, I need to ignore everything
        # after " if " in each model spec, and to look for both forms
        # (string, list) of the model specs.

        # This line was buggy when "if" not exist: kill it (july 2008): allspecs=[model['model'][0:model['model'].find(' if ')] for model in models]
        #        def getModelSpecification(am):
        #            if am['method'].startswith('ivreg'):
        #
        # 2015 June. Following seems not used
        #        allspecs=[model['model'].split(' if ')[0] for model in models if 'model' in model] # For 'isMean', there would be no 'model'
        #        allCovariates= ' '.join( uniqueInOrder(re.split(' ',' '.join(allspecs)))  )

        tablenamel = self.generateLongTableName(tablename, skipStata=skipStata)
        for ttt in models:
            ttt['tableName'] = tablenamel

        import time
        from cpblUtilities import dgetget

        # Reset output for this table by erasing the .txt file:
        #outs="""
        #*capture erase "%s%sor"
        #"""%(defaults['paths']['stata']['tex'],tablenamel)
        outs = ''

        print """regTable(): Initiated "%s"(%s) %s with %d models in %d groups. """ % (
            tablenamel, extraTexFileSuffix, skipStata * ' in skipStata mode ',
            len(models), len(
                [omm for omm in originalModels if omm not in ['|']])),

        tableLogName = defaults['paths']['stata']['tex'] + tablenamel + '.log'
        tableLogNameWithDate = defaults['paths']['stata'][
            'working'] + 'logs/' + tablenamel + time.strftime(
                '%Y_%m_%d_%H%M%S_') + '.log'

        if self.skipStataForCompletedTables and os.path.exists(tableLogName):
            if not skipStata:
                print '  Skipping Stata for %s because latex.skipStataForCompletedTables is set ON!!!! and this table is done.' % tablenamel
            outs += """
            """
            skipStata = True

        outs += """
        log using %s, text replace

        * CPBL BEGIN TABLE:%s: AT %s

        """ % (tableLogNameWithDate, tablename,
               time.strftime('%Y_%m_%d_%H%M%S'))
        """
        Need notes here: what is accomplished? What starts here?
        """
        for im in range(nModels):  #regressors in models:
            if not DO_NOT_DEEPCOPY and not returnModels:  # In case of returnModels, following security insurance is not present.
                models[im] = deepcopy(
                    models[im]
                )  # Ensure against overwriting parts of other models (is there ever a case when I want to??)
            model = models[im]
            if 'isManualEntry' in model:
                continue

            if 'code' not in model:
                model['code'] = dict(before='', after='')
            if not 'before' in model['code']:
                model['code']['before'] = ''
            if not 'after' in model['code']:
                model['code']['after'] = ''
            if ' if ' not in model['model']:
                #assert '[' not in model['model']
                model['model'] += ' if 1'

            outs += """
            * CPBL BEGIN MODEL:%s_%d:
            """ % (tablename, im + 1) + """
            * ie Start of estimate %d (for table "%s")

            """ % (im + 1, tablename)

            assert len(model['model'].split(
                ' if ')) < 3  # Did you write more than one if in your model?
            #            def multireplace(ss,adict,onlyIf=True):
            #                 if not onlyIf: return(ss)
            #                 for cfrom,cto in adict.items():
            #                     ss=ss.replace(cfrom,cto)
            #                 return(ss)
            #             def removeIVREGchars(ss,method=None):
            #                 return(  multireplace(ss,{'(':'',')':'','=':' '},onlyIf='ivreg' in method)  )
            #             def extractRHS(model)
            #             # For case of ivreg, remove =,(,).  For case of Stata's factor varialbe notation, ...
            if 0:
                RHSvarsNoWildcards = ' '.join([
                    vv
                    for vv in removeIVREGchars(
                        model['model'].split(' if ')[0]).split(' ')
                    if vv and '*' not in vv
                ])

            # At this point, all models should be multi-field'ed dicts.
            ###if isinstance(model,list):  # Use extra features....

            if model['name']:  # So first element can be empty; then it is ignored
                model['stataModelName'] = model[
                    'name']  # Used to be columnName[im]
                #rowModelNames[im]=model['name']

            # New method: just store modified flags in model:
            model['textralines'] = parseFlags(model.get('flags', None))

            modelregoptions = model.get('regoptions', ',robust' *
                                        (method not in ['rreg']))

            assert betas in [None, False, True]
            doBetaMode = False
            if 'beta' in modelregoptions or betas == True:
                assert model['method'] in [
                    'svy:reg', 'svy:regress', 'reg', 'regress', 'rreg', 'areg',
                    'xtreg'
                ]  # Can I Adding xtreg??
                doBetaMode = True
                model['textralines'][r'$\beta$ coefs'] = r'\YesMark'
                model['flags']['beta'] = True

                if ('cluster' in modelregoptions and 'beta' in modelregoptions
                    ) or model['method'] in ['rreg', 'xtreg']:
                    #print 'Replacing all "beta"s in :'+modelregoptions
                    modelregoptions = modelregoptions.replace('beta', '')

            if doBetaMode:
                assert 'compDiffBy' not in model  # You can't call comp diffs with beta mode..
                assert 'getSubSampleSums' not in model
                if '[pw=' in modelregoptions or '[pweight=' in modelregoptions:
                    debugprint(
                        """Caution! Switching to analytic weights for beta calculation. This reprodcues Stata's own "beta" coefficients when normalisation is done over the right sample, etc."""
                    )
                    modelregoptions = modelregoptions.replace(
                        '[pw=', '[w=').replace('[pweight=', '[w=')

            from cpblUtilities import flattenList
            # Following section can be rewritten, since these are mostly not used any more. Write their specific purposes here, where you creat them. [aug2012 --> [] ]
            #  make new lookups under RHS (lists) and RHSs (strings)
            RHS = {}
            # (Before 2015, we used to Remove the constant term from the actual stata call. Not sure why. Stopped doing that.)
            RHS['rawWithIf'] = model['model'].split(' if ')[0] + ' if ' + (
                ' 1' if 'if' not in model['model'] else
                model['model'].split(' if ')[1])
            RHS['ifCondition'] = RHS['rawWithIf'].split(' if ')[1]
            ###RHS['raw']=''.join([cc for cc in (model['depvar'] +' '+ re.sub('".*?"','',regressors)).replace('<',' ').replace('>',' ').replace('=',' ').replace('&',' ').split(' ') if cc and cc[0].isalpha() and not cc in ['if','samp','sample']]).split(' ') # >='A' and cc[0]<='z'
            ###RHS['rawBeforeIf']=RHS['rawWithIf'].split(' if ')[0].split(' ')
            RHS['cleanedBeforeIf'] = [
                ss
                for ss in re.sub('\(|\)|=', ' ', RHS['rawWithIf'].split(
                    ' if ')[0]).split(' ') if ss
            ]  # Deals with ivregress syntax.. This is now a list of words.
            RHS['mentionedBeforeIf'] = [
                ss
                for ss in re.sub('\(|\)|#|=', ' ', RHS['rawWithIf'].split(
                    ' if ')[0]).split(' ') if ss
            ]  # Deals with ivregress syntax, and interactions notation. Leaves i.var as is.  NOT USED?
            RHS['inConditions'] = uniqueInOrder(''.join([
                cc
                for cc in (re.sub('".*?"', '', RHS['rawWithIf'].split(
                    ' if ')[1])).replace('<', ' ').replace('>', ' ').replace(
                        '=', ' ').replace('&', ' ').split(' ')
                if cc and cc[0].isalpha() and not cc in
                ['if', 'samp', 'sample']
            ]).split(' '))
            # Assume there are no wildcards or etc after the "if"
            # What about weight var? where is that?
            RHS['inIndicators'] = flattenList([
                av[2:].split('#') for av in RHS['cleanedBeforeIf']
                if av.startswith('i.')
            ])
            RHS['inInteractions'] = flattenList([
                av.split('#') for av in RHS['cleanedBeforeIf']
                if not av.startswith('i.')
            ])
            RHS['wildcards'] = [
                av for av in RHS['cleanedBeforeIf'] if '*' in av
            ]
            RHS['inConditions'] = []
            #RHS['includingWildCardsAndInteractions']=[av[2:] if av.startswith('i.') else av for av in RHS['rawBeforeIf']]
            # Only single interactions, ie like xxx#yyy and not xxx##yyy, are recognised so far:
            RHS['simplest'] = flattenList(
                [
                    av for av in RHS['cleanedBeforeIf']
                    if '*' not in av and not av.startswith('i.') and '#' not in
                    av
                ],
                unique=True)
            # Now, compile some lists:
            RHSs = {
                'used': ' '.join(RHS['simplest'] + RHS['inConditions'] +
                                 RHS['inIndicators'] + RHS['inInteractions'])
            }
            # Do not auto-create variables in f.e. indicators, since we are not going to display the results and therefore notice that they're missing.
            if 0:
                # Check that we're not feeding a redundant list to corr (in accounting mode) later down the line:
                redundantRegressors = ' ' + deepcopy(regressors) + ' '
                for vvv in uniqueInOrder(regressors.split(' ')):
                    redundantRegressors = redundantRegressors.replace(
                        ' %s ' % vvv, ' ', 1)
                    #uniqueRegressors= ' '.join(
                if redundantRegressors.strip(
                ):  #not uniqueRegressors==regressors:
                    print 'CAUTION!!! list of regressors contains redundant term!!!  Eliminating redundancies: ', redundantRegressors.strip(
                    )
                    regressors = ' '.join(uniqueInOrder(regressors.split(' ')))

            RHSs['autoCreate'] = ' '.join(RHS['simplest'] + RHS['inConditions']
                                          + RHS['inInteractions'])
            RHSs['zScoreVars'] = ' '.join(
                [model['depvar']] + RHS['simplest'])  #+RHS['inInteractions'])
            RHSs['suppressEstimates'] = ' '.join([
                rhsv for rhsv in RHS['cleanedBeforeIf']
                if rhsv.startswith('i.') and rhsv not in forceShowVars
            ])
            assert not any(['county' in ff for ff in forceShowVars])
            assert not forceShowVars

            # Following fails if there are redundant (repeated) RHS variables here...
            regressionLine = 'capture  noisily ' * (
                captureNoObservations == True or not stopForErrors
            ) + model['method'] + ' ' + model['depvar'] + ' ' + RHS[
                'rawWithIf'] + ' ' + modelregoptions

            self.variablesUsed += ' ' + model['depvar'] + ' ' + RHSs['used']

            assert 'code' in model
            """ Nov 2009: Oh dear. I am afraid there's no single sensible ordering of where in the 'before' code to insert various things. I may need more direction from user/caller. For now, I'll let the user's "before" code go first, since it might load files, etc. And I'll append all my things (modes, below) in order... [NOT] [See documentation for regTable. 'loadData' is the very first.

Problems: for instance, when I use withCRdummies or etc, it inserts code. But the autocreatevars needs to happen BEFORE that. What I am going to do is to allow more than just "before" and "after".  Use "loadData" to come at the very beginning?
So I'll put the two auto things below at the very beginning of "before" and will likely need to fix some calls to regTable to make use of "loadData"...


"""

            if 'autoExcludeVars' in model:
                """ e.g. consider if the "if" clause identifies one country. Then this would set all values for just that country to -999. Use carefully, because if you mix subsets later, you might get some -999s mixed with real values... (or this should keep track and undo its work... Currently, it does: it uses a "restore" later to undo its work."""
                if model['autoExcludeVars'] in [
                        True, ''
                ]:  # ie its value is None or '' ...?April2010: no... caution: if ==None, this will not work.. (mod'ed april 2010)
                    preIf, postIf = regressors.split(' if ')
                    model['autoExcludeVars'] = postIf
                model['code']['autoExcludeVarsBefore'] = """
* ENSURE THAT THE "IF" CLAUSE DOES NOT TURN ANY GENERALLY NON-MISSING VARIABLES INTO ALL-MISSING:
preserve
foreach var of varlist """ + RHSs['autoCreate'] + """ {
quietly sum `var' if """ + model['autoExcludeVars'] + """
if r(N)==0 {
replace `var'=-999 if """ + model['autoExcludeVars'] + """
di " CAUTION!!!!!!!! Replaced `var' values in MODEL:%s_%d:""" % (
                    tablename, im + 1) + """, since they were all missing!"
}
}
"""

            # RHSvarsNoWildcard '
            if autoCreateVars and not model.get('special', '') == 'suestTests':
                model['code']['autoCreateVarsBefore'] = """
* ENSURE THAT ALL VARIABLES IN THE EQUATION EXIST BY SETTING MISSING ONES TO ALL ZEROs:
foreach var in  """ + RHSs['autoCreate'] + """ {
capture confirm variable `var',exact
if _rc~=0 {
di " CAUTION!!!!!!!! `var'  DID NOT EXIST in MODEL:%s_%d:""" % (tablename, im +
                                                                1) + """!"
capture gen `var'=0
}
}
"""
            # "

            if doBetaMode:  # This "if" section is continued from above.
                if RHS['wildcards']:  #'*' in thisRegRHSvars: # Can't have wildcards in this beta mode.. or else could drop them here.
                    """ Why drop them? Just leave them, ut their coefficients won't be betas. March 2013"""
                    print(
                        'regTable: CAUTION! TRYING A SAMPLE SELETION FOR A BETA REGRESSION, BUT THERE ARE WILDCARDs OR v12 INTERACTIONS OR V12 INDICTORS IN SOME VARIABLES. THESE WILL BE LEFT IN, BUT NOT NORMALIZED! ',
                        RHS['wildcards']
                    )  #[ww for ww in thisRegRHSvars.split(' ') if '*' in ww])
                #LthisRegVarsUsed_NoWildCards= [vv for vv in thisRegVarsUsed.split(' ') if vv and not '*' in vv]

                # Make sure to use proper weights in zscore!.
                zscoreVars = RHSs[
                    'zScoreVars']  #' '.join([vv for vv in (model['depvar'] +' '+ regressors +' '+ modelregoptions).split(' if ')[0].split(' ') if vv and not '*' in vv])
                zscoreLine = 'zscore ' + ' ' + zscoreVars
                #zscoreLine= 'zscore '+' '+ ' '.join(LthisRegVarsUsed_NoWildCards)+' if '+ (regressors +' '+ modelregoptions).split(' if ')[1].replace(' if ',' if z_dSample & ') #model['depvar'] +' '+ regressors 
                #if ' if ' in zscoreLine:
                #zscoreLine=zscoreLine.replace(' if ',' if z_dSample & ')
                #else:
                #    zscoreLine=zscoreLine+' if z_dSample '
                zscoreLine += ' if z_dSample & ' + RHS['ifCondition']
                #zscoreLine+='\n'+  '\n'.join(["""
                #*sum z_%s 
                #*if r(N)==0 {
                #    *replace z_%s=1
                #     *}
                #"""%(vv,vv) for vv in thisRegVarsUsed.split(' ') if vv and not '*' in vv])+'\n'

                # Oct 2009: I am removing the following for the moment. I have had to put z_dSample back in the zscore line to get the right normalisation. So it is important to call this only with variables that exist.... 
                # LAter: OCt 2009: I am putting it back. The following gets around bug in zscore which sets as missing variables that have no variation. So the following should always come along with a zscore call. So, I am now implementing a new way to ensure that only existing variables are called.
                zscoreLine += """
                foreach var of varlist %s {
                quietly sum `var'
                if r(N)==0 {
                di "Filling in values for `var', which is all missing"
                replace `var'=0
                }
                }
    """ % (' '.join([
                    'z_%s' % vv for vv in zscoreVars.split(' ')
                    if vv and not '*' in vv
                ]))
                # """ " ` "
                if combineRows == None:
                    combineRows = []
                combineRows = [[vv, 'z_' + vv] for vv in zscoreVars.split(' ')
                               if vv and not '*' in vv] + combineRows

                debugprint(
                    'regTable: USING BETA MODE FOR THIS REGRESSION: dropping all z_* variables'
                )

                # Heavily modify the regression call:

                ##########3preIf,postIf=regressors.split(' if ')

                regressionLine = 'capture noisily ' * (
                    captureNoObservations == True or not stopForErrors
                ) + model['method'] + ' z_' + model['depvar'] + ' ' + ' '.join(
                    [('*' not in vv and '#' not in vv and
                      not vv.startswith('i.')) * 'z_' + vv
                     for vv in RHS['cleanedBeforeIf'] if vv
                     ]) + ' if ' + RHS['ifCondition'] + ' ' + modelregoptions

                # Also, set up the zscore normalisation, etc.

                model['code']['before']+="""
                   capture drop z_*
                   gen z_dSample = """+ ' & '.join(['%s<.'%vv for vv in zscoreVars.split(' ') if vv and '*' not in vv])+ ' & '+RHS['ifCondition']+'\n'+zscoreLine+"""

                     """#+model['code']['before']+'\n'

                model['code']['after'] += """
                   capture drop z_*
                 """
                if 0:
                    assert 'dCountry*' not in model['code'][
                        'before']  # Why? March2013: This was not commented. So I don't understand it and I'm removing it for now.

            ###outs+='\n'+regressionLine+'\n' "

            if captureNoObservations == True and not model.get(
                    'special', '') == 'suestTests':
                model['code'][
                    'existenceConditionBefore'] = '* ALLOW FOR POSSIBILITY THAT THERE ARE NO OBSERVATIONS MEETING THIS CONDITION... REPLACE REGRESSION WITH DUMMY REGRESSION IN THIS CASE, AND KEEP GOING. (captureNoObservations==True)'
                model['code']['existenceConditionAfter']="""
                if _rc==2000 |_rc==302 |_rc==2001 {
                capture gen _dummyOne=1
                reg _dummyOne _dummyOne
                } 
                else {
                if _rc!=0 {
                di _rc
                di foodle untrapped error! (following line should stop execution if reached)
                error _rc
                }
                """+0*(regressionLine.split('capture')[1])+"""
                }
                """ # No loonger, above, need to repeat regression, since used capture NOISILY

            # New feature August 2009: Create sub-sample sums
            # I've hard-coded this to use "weight" as a weight.
            # But this needs to use "mean", not "sum"!! (done: Jan 2010)
            if returnModels and not substitutions == self.substitutions:  # Mod'd 2010 Sept; will need to update accounting code to use self.subs...?
                model[
                    'substitutions'] = substitutions  # Will be needed for formatting output of accounting analysis
            if 'getSubSampleSums' in model:  # sept 2010: leave this override in for now?
                model[
                    'substitutions'] = substitutions  # Will be needed for formatting output of accounting analysis
                # 2010 Jan: Need to use "mean", not "sum", so do both for now, and work on parsing the "mean" output
                model['code']['sumsAfter'] = """
                """ + '\n'.join([
                    """
                *BEGIN MEAN LIST MULTI
 mean """ + model['depvar'] + ' ' + RHSvarsNoWildcards + 0 *
                    thisRegVarsUsedNoWildcard +
                    ' [pw=weight] if cssaSample & (' + ifs + """),
                *END MEAN LIST MULTI

                *BEGIN SUM LIST MULTI
 sum """ + model['depvar'] + ' ' + RHSvarsNoWildcards + 0 *
                    thisRegVarsUsedNoWildcard + ' [w=weight] if cssaSample & ('
                    + ifs + """), separator(0) nowrap
                *END SUM LIST MULTI

                """ for ifs in model['getSubSampleSums']
                ])  ##+model['code']['after']

            if 'autoExcludeVars' in model:
                model['code']['autoExcludeVarsAfter'] = """
                restore
                """

            if not model.get('special', '') == 'suestTests':
                # An optional argument is this stata code to run before the regression!

                outs += '\n' + dgetget(model, 'code', 'loadData', '')
                outs += '\n' + dgetget(model, 'code', 'cellDummiesBefore', '')
                outs += '\n' + dgetget(model, 'code', 'autoCreateVarsBefore',
                                       '')
                outs += '\n' + dgetget(model, 'code', 'autoExcludeVarsBefore',
                                       '')
                outs += '\n' + dgetget(model, 'code', 'before', '')
                outs += '\n' + dgetget(model, 'code',
                                       'existenceConditionBefore', '') + '\n'

                #If stopForErrors=False has been chosen, then do the regression so that if it fails (no observations), it will be replaced by a dummy regression. This is similar to my method for cell controls, but simpler.
                outs += regressionLine + '\n'
                outs += '\n' + dgetget(
                    model, 'code', 'existenceConditionAfter', ''
                ) + '\n'  # This provides a dummy regression if some existence condition is not met. For example, it's used in national-level regressions in regressionsDunn2010.py. Note, it can also get created automatically/internally by regTable if captureNoObservations is used. 
                outs += '\n' + dgetget(model, 'code', 'cellDummiesAfter',
                                       '') + '\n'

            if 'subSumPlotParams' in model:
                model['subSumPlotParams']['comments'] = model[
                    'subSumPlotParams'].get(
                        'comments', '') + r'\ctDraftComment{' + str2latex(
                            regressionLine) + '} '

            # Now also run the after-regression code required, for instance to do some statistical tests:
            incomeVars = [
                iii for iii in possibleIncomeVars
                if iii and iii in RHS['mentionedBeforeIf']
            ]
            if incomeVars:  # Careful. It's actually possible, with semiparametric [ie rolling regression.], for an income variable to be dropped as collinear, ie everyone has same income.
                outs += '\n capture test 0=%s\n' % ('+'.join(incomeVars))

            # And save all coefficients to the dataset, if so requested: (yuck... can't I just save them using estimates store and refer to them that way!!)
            if assignSaveCoefficientsPrefix:
                assert ' if ' in regressors
                pieces = regressors.split(' if ')
                #if len(pieces)==1:
                #    pieces+=[' 1 ']
                for var in [
                        vv for vv in pieces[0].split(' ')
                        if vv and '*' not in vv
                ]:
                    outs += '\nreplace %s%s=_b[%s] if %s\n' % (
                        assignSaveCoefficientsPrefix, var, 'z_' *
                        (doBetaMode) + var, pieces[1])
                    outs += '\nreplace s%s%s=_se[%s] if %s\n' % (
                        assignSaveCoefficientsPrefix[1:], var, 'z_' *
                        (doBetaMode) + var, pieces[1]
                    )  # old jujnk:'beta' in modelregoptions
            """ Now, do immediately-after-regression stuff:
             (1) display regression results
             (2) display regression variance-covariance results
             (3) record e(sample) as cssaSample, for use with making associated stats (means) later.
             """

            if not model.get('special', '') == 'suestTests':
                dropIndicators = ' '.join([
                    ss for ss in RHSs['suppressEstimates'].split(' ')
                    if ss and 'partial(' + ss + ')' not in model['regoptions']
                ])
                outs += """
                capture drop cssaSample
                gen cssaSample=e(sample)
    estimates table , varwidth(49) style(oneline) b se p stats(F r2  r2_a r2_p N  N_clust ll r2_o """ + (
                    'ivreg2' in model['method']
                ) * 'jp idp widstat' + ') ' + 0 * (
                    'drop(' + dropIndicators + ')'
                    if dropIndicators else '') + """
    * ereturn list
    """ % ()
                if 'compDiffBy' in model or 'getSubSampleSums' in model:
                    outs += stataElicitMatrix('e(V)')

                # An optional argument is this stata code to run after the regression. I really have no idea which should come first, the externally-specified "after" or the sumsAfter. Really, I should use more specific elements than general "after" so that I can order them sensibly.
                outs += '\n' + model['code']['after'] + '\n'
                outs += '\n' + dgetget(model, 'code', 'testsAfter', '') + '\n'
                outs += '\n' + dgetget(model, 'code', 'autoExcludeVarsAfter',
                                       '')
                if dgetget(model, 'code', 'sumsAfter', ''):
                    outs += '\n' + model['code']['sumsAfter'] + '\n'

                if 0 and 'needCovariance':
                    outs += """
                    matrix list e(V),nohalf
                    * END: matrix list e(V)
    """

            if 'getSubSampleSums' in model:
                outs += """
                 * Generate a covariance matrix for regressors and display it. This is going to be used as an approximate for the cov matrix for subsets of the full sample, too. (Jan 2010: What about pweights?. Ah. Jan 2010, now incorporated pweight into following:)
                 matrix accum R = %s [pweight=weight] if cssaSample, nocons dev
                 matrix sampleIndepCorr = corr(R)
                matrix list sampleIndepCorr,nohalf
                * END: matrix list sampleIndepCorr
""" % (model['depvar'] + ' ' + thisRegRHSvars
       )  #(model['depvar']+' '+RHSvarsNoWildcards)#thisRegRHSvars#thisRegVarsUsed

            if doPcorr:  # Note: This stupidly now calls the before and after, which is no longer compatible in general (see semiparametric)...
                # So in Aug 2008 I've turned off the pcorr function by default. Not sure I ever really used it anyway. Well, actually, I've changed semiparam so it may be compatible again, but I am not using pcorr..
                outs += '\nlog using %s.pcorr_%d.txt,append text\n' % (
                    defaults['paths']['stata']['tex'] + 'pcorr/' + tablenamel,
                    im)
                # An optional argument is this stata code to run before the regression.
                if 'code' in model:
                    outs += '\n' + model['code']['before'] + '\n'
                #if len(model)>4:
                #    outs+='\n'+model[4]+'\n' 
                outs += 'capture ' * (
                    not stopForErrors
                ) + 'pcorr ' + model['depvar'] + ' ' + regressors + ' \n'
                # An optional argument is this stata code to run after the regression.
                if 'code' in model:
                    outs += '\n' + model['code']['after'] + '\n'
                #if len(model)>=6:
                #    outs+='\n'+model[5]+'\n' 
                outs += '\nlog close\n'

            # An optional argument is this stata code to run after the regression and the results export.
            if 'code' in model and 'afterExport' in model['code']:
                outs += '\n' + model['code']['afterExport'] + '\n'

            if model.get('special', '') == 'suestTests':
                outs += model['code']['after']
            outs += """
        * CPBL END MODEL:%s_%d:
        """ % (tablename, im + 1)

        outs += """
        * CPBL END TABLE:%s:

log close

* Since we've successfully finished, set the preceeding log file as the conclusive one
copy "%s" "%s", replace
        """ % (tablename, tableLogNameWithDate, tableLogName)

        # Undo the normalistion of variables, if it was done earlier:
        #if 0 and normaliseForBeta:
        #    outs+="""
        #     * UNDO NORMALISATION OF ALL VARIABLES FOR THIS TABLE
        #     use %s,clear
        #    """%betaFN

        # Rename completed output file to a more unique / complete name

        # This is useful for making different versions of output. Run Stata once; show different rows/cols in separate incantations of regTable.

        # Here is a chance to reformat some of the values in textralines. For instance, when names of surveys are included, replace them with small font shortnames:
        for mmm in models:
            if 'shortnames' in defaults:
                shortname = defaults['shortnames']
                if 'survey' in mmm['textralines'] and mmm['textralines'][
                        'survey'] in shortname:
                    mmm['textralines']['survey'] = mmm['textralines'][
                        'survey'].replace(
                            mmm['textralines']['survey'],
                            shortname[mmm['textralines']['survey']])
            if 'survey' in mmm['textralines']:
                mmm['textralines']['survey'] = r'{\smaller\smaller %s}' % mmm[
                    'textralines']['survey']

        # This marks NEARLY the end of all Stata code production. N.B. that before we decide to abort including any Stata code for this table, we must check to make sure that the number of models in the table hasn't changed since Stata was run, since this is one more basic check that we do in the processing below that can result in the advice "rerun stata", below.  So, proceed with reading Stata output (unless the log file doesn't even exist.) and then close up the Stata code soon below.

        ###################################################################################
        ###################################################################################
        ###################################################################################
        # Read in the txt version of the regression results, and do some initial processing which can be used for
        # all three output formats: old (no aggregated results), with averaged columns, and only averaged columns.
        tableFileName = tablenamel

        if skipReadingResults:
            if not all(['eststats' in mm for mm in models]):
                not os.path.exists(tableLogName)
                print ' skipReadingResults used without eststats in the models!  Assuming model not run yet...'
                print ' Missing %s... Rerun Stata' % tableLogName
                self.append(r'\newpage{ Missing %s... Rerun Stata}\newpage' %
                            str2latex(tableLogName + extraTexFileSuffix))
                return (outs)
            pass  # Should assert ALL KINDS OF THINGS HERE
            assert all(['eststats' in mm for mm in models])
        else:
            if not os.path.exists(tableLogName):
                print ' Missing %s... Rerun Stata' % tableLogName
                self.append(r'\newpage{ Missing %s... Rerun Stata}\newpage' %
                            str2latex(tableLogName + extraTexFileSuffix))
                return (outs)

            #rlf=readStataRegressionLogFile(tableLogName,output='trows',dropIfStartsWith=['dCountry'],dropVars=None)
            #import operator
            #allvarsM=uniqueInOrder(    reduce(operator.add, [mm['coefs'].keys() for mm in rlf], [])) 

            # # # # # # # # READ MAIN STATA OUTPUT . # # # # # # # # # 
            modelsOriginal = [deepcopy(mm) for mm in models]

            rsrlf = readStataRegressionLogFile(
                tableLogName,
                dropIfStartsWith=['dCountry'] * 0,
                dropVars=None,
                models=models)
            # Nov 2010: I'm going to include the entire log file in every .tex file I create, so the source result is always with the paper.

            # # # # # # # # MAKE FINAL DECISION ON SKIPPING STATA DUE TO AUTO-SKIP-COMPLETED TABLES, ETC # # # # # # # # # 
            if rsrlf in [None] or 'run Stata and try again' in rsrlf:
                skipStata = False  # I won't skip stata if the log file is outdated.
                print "  (OVERRIDE skipStata!: will run Stata for table " + tablename + " because it's outdated.)"
            if skipStata == True:
                assert self.skipStataForCompletedTables or not skipLaTeX  # Why is this necessary?? Maybe a warning should be issued... Also, May 2010: I've added an or for self.skipStataFor... The logic is not quite right. But it avoids the assert to bind in a common situation when we dont' want it to, but still lets it bind sometimes. (ugh)

                outs = """

                * regTable: Skipping reestimation of entire table %s (logged in %s) because skipStata was set True """ % (
                    tablename, tablenamel
                ) + self.skipStataForCompletedTables * ' or because self.skipStataForCompletedTables was set True ' + """

    """

            # This marks the end of all Stata code production. The rest is processing and formatting of the results.

            if isinstance(rsrlf, str):
                print(rsrlf)
                self.append(rsrlf)
                assert 'First' not in extraTexFileSuffix

                return (outs)
            if rsrlf == None:
                print 'Gone NONE from readSTataRegressionLogFile!'

                return (outs)
            models = rsrlf['models']
            assert models

            assert all(['eststats' in mm for mm in models])

            # Note the date that this regression was done.
            import time, os
            regressionDate = time.ctime(os.path.getmtime(tableLogName))
            comments += ' Regression carried out on ' + regressionDate  #ress['regressionDate']
            # Try to add some other useful comments.
            allMethods = uniqueInOrder(
                [ss for ss in [mm.get('method', '') for mm in models] if ss])
            allLHS = uniqueInOrder(
                [ss for ss in [mm.get('depvar', '') for mm in models] if ss])
            allModels = uniqueInOrder(
                [ss for ss in [mm.get('model', '') for mm in models] if ss])
            comments += ' Regression methods: %s. Dependent vars: %s ' % (
                allMethods, allLHS)
            if len(allModels) == 1 and len(allModels[0]) < 300:
                comments += ' Common model: %s' % (str2latex(allModels[0]))

    ###########################################################################################
    ###
    #def displayRegTable(self,tablename,models,method=None,depvar=None,regoptions=None,variableOrder=None,showonlyvars=None,hidevars=None,forceShowVars=None,extralines=None,comments='',substitutions=None,options='',attributes=None,landscape=False,transposed=None,combineRows=None,suppressSE=False, produceOnly=None,extraTexFileSuffix=None,doPcorr=False,stopForErrors=True,crcoefsVars=None,skipStata=False,skipLaTeX=False,hidePSumTest=False,defaultModel=None,hideModelNumbers=False,assignSaveCoefficientsPrefix=None,hideModels=None,showModels=None,hideModelNames=False,renumberModels=True,showFailedRegressions=False,multirowLabels=False,betas=False,followupFcn=None,followupArgs=None,showCompDiff=None,returnModels=False,postPlotFcn=None,postPlotArgs=None,autoCreateVars=True,captureNoObservations=None): # Do a set of regressions; output results to .tex and .txt files 
    # retired options: useOUTREG2=False,
    ###
    #######################################################################################
        """
        Alright, separating this from regTable() in May 2011. This is going to make things fragile, as lots has to be set up correctly for this function to work. So if you mess in the wrong way, things will break. [NOT. Added "skipReadingResults" option instead, above.

        """

        #trowsOld=ress['trows']

        ##############################################################################
        ############## DROP UNWANTED OR EMTPY MODELS #################################3
        #
        # If we want to drop/use a subset of the models, do that now.: hideModels / showModels
        #
        assert not hideModels or not showModels  # Can't specify both. Well, actually, the line below gives a sensible way in which they could both be allowed at once: a model would be shown if in showModels (or showModels==None) and not in hideModels.
        assert showModels or showModels == None  # don't pass [] or ''
        assert not returnModels or (showModels is None and hideModels is None)
        # Note: hideModels / showModels should be a list of pointers to actual model dicts now, and they should simply be dropped here...  No need to deepcopy here, I believe.
        #if (not hideModels or isinstance(hideModels[0],dict)) and (not showModels or isinstance(showModels[0],dict)):
        if (hideModels and isinstance(hideModels[0], dict)) and (
                showModels and isinstance(showModels[0], dict)
        ):  # Allow for strange case of both being specified... BUT this does not allow reordering!
            models = [
                mmm for mmm in models
                if (not showModels or mmm in showModels
                    ) and (not hideModels or mmm not in hideModels)
            ]  # I could instead just set a "hidden" flag for these but keep them around until exporting...
            assert models
        elif hideModels and isinstance(hideModels[0], dict):
            models = [
                mmm for mmm in models
                if (not hideModels or mmm not in hideModels)
            ]  # I could instead just set a "hidden" flag for these but keep them around until exporting...
            assert models
        elif showModels and isinstance(
                showModels[0], dict):  # This allows for reordering the models
            models = [mmm for mmm in showModels if mmm in models]
            assert models
        elif hideModels or showModels:  # These are indices (1-based..) to the model list
            if showModels:
                assert isinstance(showModels, list) and isinstance(
                    showModels[0], int)
            if hideModels:  #isinstance(hideModels,list) and hideModels and isinstance(hideModels[0],int):
                assert isinstance(hideModels, list) and isinstance(
                    hideModels[0], int)
                showModels = [
                    nn + 1 for nn in range(len(models))
                    if nn + 1 not in hideModels
                ]
            if showModels:  #isinstance(showModels,list) and showModels and  isinstance(showModels[0],int):
                # Remove from model dicts:
                if max(showModels) - 1 >= len(models):
                    print 'CAUTION!!!!!!!!!! Your list of model indices includes non-existing models!!!!!!!!!!! Ignoring  them...', [
                        iM for iM in showModels if iM - 1 >= len(models)
                    ]
                models = [
                    models[iM - 1] for iM in showModels if iM - 1 < len(models)
                ]

        if not models:
            print ' AWWWWWWWWWWWWWWWWWWWW! No models left!! Aborting this table!'
            self.append(
                ' AWWWWWWWWWWWWWWWWWWWW! No models left!! Aborting this table!')
            return ()
        assert models

        # Also, drop any models which failed (N=0? Here I used r^2=0 or 1)
        # Use existence of non-blank r^2 pr r2-p as an indicator of whether a real regression was done.
        badR2 = [fNaN, 1, 1.0,
                 'noR2']  # I think this should just be fNaN in newmode.
        for mm in models:
            if 'isManualEntry' in model:
                continue
            if mm.get('special', '') in ['suestTests']:
                continue  # These can all be empty in this case...
            if 'r2' in mm['eststats']:
                r2 = mm['eststats']['r2']
            else:
                r2 = mm['eststats'].get('r2_p', 'noR2')
            if r2 in badR2 and mm['method'] not in [
                    'glm', 'xtreg', 'xtregress'
            ] and 'ivreg' not in mm[
                    'method']:  # Huh? What about r2-p?  N.b.: I'm not detecting failed ivregress yet (2015)
                print ' Suppressing model %d (name="%s") from LaTeX table because the regression failed (OR TYPE UNKNOWN to pystata)' % (
                    mm['modelNum'], mm['name'])
                mm['eststats']['r2'] = fNaN
                mm['eststats']['r2_a'] = fNaN
                mm['eststats']['N'] = 0
        if not showFailedRegressions and 0:  # CANNOT DO HIDE BROKEN REGs UNTIL REWRITTEN COMBINEROWS FOR NEWMODE...
            woeirweoiuJUSTTESTING_CAN_DELETE_THISLINE
            models = [
                mm for mm in models if mm['eststats']['r2'] not in badR2
            ]  #('r2' in models['eststats'] and
            nModels = len(models)
        # THIS IS VERY DANGEROUS. DO NOT CALL RENUMBERMODELS IF YOU ARE CR GROUPS...... IE THIS NEEDS TO BE FIXED, SINCE I THINK IT MAY 
        if renumberModels:
            for imm in range(len(models)):
                models[imm][
                    'modelNum'] = imm + 1  # An innovation Sept 2008: This ought to simplify some later stuff, no.??. Rewrite all the model/calc numbering, through this functoin. Should do same with the name.

        assert models

        def modelCombineRows(models, combineRows):
            """ Change the names of regressors in model estimated *results* within a list of model dicts in ordre to combine (or rename) certain variables.
            Note that the estimation coefficients in these models should already be "cleaned up" ie blanks should be eliminated; if a regressor is listed, it should have an estimate.
            2013: . adict is no longer a dict, but a pandas frame.
            
            """

            def renameKey(adict, vfrom, vto):
                if vfrom in adict:
                    assert vto not in adict
                    adict[vto] = adict[vfrom]
                    del adict[vfrom]

            for vng in combineRows:
                vto = vng[0]
                for mmm in models:
                    if 'estcoefs' not in mmm:
                        continue
                    for vfrom in vng[1:]:
                        if vfrom in mmm['estcoefs']:
                            # If both a from and a to variable were estimated, this combineRows is impossible:
                            renameKey(mmm['estcoefs'], vfrom, vto)
                            if 0:  # Code before june 2010 is below:
                                assert vto not in mmm['estcoefs']
                                mmm['estcoefs'][vto] = mmm['estcoefs'][vfrom]
                                del mmm['estcoefs'][vfrom]
                    # 2010 June: added piece to also rename variables in the covariance matrix..
                    if 'estCovar' in mmm:
                        # 2013 June: modified because matrices now come as pandas DFs
                        if isinstance(mmm['estCovar'], dict):
                            for vfrom in vng[1:]:
                                renameKey(mmm['estCovar'], vfrom, vto)
                                for aa in mmm['estCovar']:
                                    renameKey(mmm['estCovar'][aa], vfrom, vto)
                        else:  # Assume it's a pandas DF
                            mmm['estCovar'].rename(
                                columns=dict(
                                    [[vfrom, vto] for vfrom in vng[1:]]),
                                inplace=True)
                            mmm['estCovar'].rename(
                                dict([[vfrom, vto] for vfrom in vng[1:]]),
                                inplace=True)

        ###################################################################################
        # Remove all ddd_* variables in case of CR-coefs models
        ###################################################################################
        for model in models:
            if 'CRgroup' in model:
                hidevars += [
                    vv for vv in model['estcoefs'] if vv.startswith('ddd_')
                ]

        ###################################################################################
        ###################################################################################
        # Deal with rows to combine. For instance, when I have both real and nominal incomes, I might want the coefficients to appear on the same row, and just have the difference signified with an indicator row later.
        # Or, if my standardzied beta mode is running, we want to rename the z_ variables to their non-z versions, allowing for the possibility that both exist in the estimates table.

        import os
        debugprint(' ------------------------')
        debugprint(tableFileName, ' combine Rows = ', combineRows)
        if combineRows:
            # Adjust format of this passed parameter:
            #combineRows=[rr for rr in   [[cell.strip().replace('_','-') for cell in row] for row in combineRows]  if rr[0]]
            modelCombineRows(models, combineRows)
            if any(['compDiffBy' in mm for mm in models]):
                print(
                    ' N.B.: combineRows is defined, so will need to revise some keys like compDiffBy...'
                )
            #if newmode: # I assume the following line is just a safety for backwards compat with what follows?
            #combineRows=None # Removed 2013 so that I can replace compdiffby.

            ###################################################################################
            ###################################################################################
            # Special modes here, to insert new "models" or new variables. e.g.: do compensating differential calculation:
        from pylab import sqrt
        # COMPENSATING DIFFERENTIALS
        for imodel in range(len(models))[::-1]:
            if 'compDiffBy' not in models[imodel] or not models[imodel][
                    'compDiffBy']:
                continue

            if 'estCovar' not in models[imodel]:
                print(
                    'There is no record of estimation covariance matrix for this model, so SKIPPING COMPENSATING DIFFERENTIALS. Rerun Stata!'
                )
                continue
            elif len(
                    set(models[imodel]['estCovar'].columns) - set(['_cons'])
            ) == 0:  #not  models[imodel]['estCovar']: # ie, it's there, but empty
                print(
                    '\n\n * * * * estCovar is empty. in model %d: "%s": There is no record of estimation covariance matrix for this model, so SKIPPING COMPENSATING DIFFERENTIALS. Rerun Stata?\n'
                    % (imodel, models[imodel]['name']))
                continue

            if showCompDiff in [
                    None, True
            ]:  # this wasn't specified, yet some model(s) had compDiff setting. So choose default ('aftereach' behaviour for showing comp diffs.
                showCompDiff = 'aftereach'

            frommodel = models[imodel]
            ##assert frommodel['model']['compDiffBy'] in frommodel['estmodel']
            ##print 'Model num unsafe in folloinwg.....' (still?? or did this refer to before deepcopy?)
            #cdModel=deepcopy(frommodel) # This is TOO MUCH... ONLY COPY A FEW, NEEDED ITEMS. explicitly listed...  [April 2011: why? does RAM matter??]
            cdModel = dict(
                deepcopy([
                    ims for ims in frommodel.items()
                    if ims[0] in [
                        'name', 'modelNum', 'model', 'substitutions', 'depvar',
                        'stataModelName', 'method', 'eststats', 'format',
                        'showCompDiffVars', 'compDiffHideVars', 'logFilename'
                    ]
                ]))
            cdModel.update({
                'baseModelCopy': deepcopy(frommodel)
            })  # Added April 2011.
            cdModel.update({
                'special': 'compDiff',
                'compDiff': True,
                'name': "comp. diff's" + 0 * frommodel['name']
            })  # ,'modelNum':max([mm['modelNum'] for mm in models])})
            cdModel['eststats']['r2'] = fNaN
            cdModel['eststats']['r2-a'] = fNaN
            cdModel['estcoefs'] = {}
            cdModel['eststats'] = deepcopy(frommodel['eststats'])
            V = frommodel[
                'estCovar']  # 2013 Feb: this changed from dict to pandas df
            incvar = frommodel['compDiffBy']
            if combineRows:
                for tofrom in combineRows:
                    if incvar in tofrom[1:]:
                        print('Using %s instead of %s as comp diff income' %
                              (tofrom[0], incvar))
                        incvar = tofrom[0]
                        continue

            if incvar not in frommodel['model'] or incvar not in frommodel[
                    'estcoefs'] or incvar not in frommodel['estCovar']:
                cwarning(frommodel['tableName'] +
                         ': YIKES! IMPORTANT THINGS ARE MISSING for "' +
                         frommodel['name'] + '"' +
                         """. CANNOT DO COMP DIFFS. TRY RERUNNING STATA?
       You asked for """ + incvar + """ as the income variable, but:
       incvar in frommodel['model'] , incvar in frommodel['estcoefs'] , incvar in frommodel['estCovar']
       """ + str((incvar in frommodel['model'], incvar in
                  frommodel['estcoefs'], incvar in frommodel['estCovar'])))

                continue

            # But do we want to show the comp diffs? Or just calculate them? All or some of them? 
            # 'showDiffCompVars' can be True, False, a string, or a list.
            cdvars = list(
                set(frommodel['estcoefs'].keys()) - (set([incvar] + [
                    '_cons',
                    'age',
                    'agesq100',
                    'age100sq',
                    'age100t3',
                    'age100t4',
                    'age100',
                ])))

            # 'compDiffVars'= list or string list of variables for which comp diffs should be calculated and/or displayed. Note that regTable has a table-level parameter "showCompDiff" which decides whether/how comp diffs should be shown.
            if 'compDiffHideVars' in cdModel:
                if isinstance(cdModel['compDiffHideVars'], str):
                    cdModel['compDiffHideVars'] = cdModel[
                        'compDiffHideVars'].split(' ')
                cdvars = [
                    cv for cv in cdvars
                    if cv not in cdModel['compDiffHideVars']
                ]

            if 'showCompDiffVars' in cdModel:
                if isinstance(cdModel['showCompDiffVars'], str):
                    cdModel['showCompDiffVars'] = cdModel[
                        'showCompDiffVars'].split(' ')
                cdvars = [
                    cv for cv in cdModel['estcoefs'].keys()
                    if cv in cdModel['showCompDiffVars'] and not cv == invar
                ]
            for vv in cdvars:  # In following, x is the variable of interest, y is income, s is sigma, b is coefficient
                bx, by = frommodel['estcoefs'][vv]['b'], frommodel['estcoefs'][
                    incvar]['b']
                sx, sy = frommodel['estcoefs'][vv]['se'], frommodel[
                    'estcoefs'][incvar]['se']
                sxy = V[vv].ix[incvar]
                compdiff = bx / by
                #secompdiff=sqrt(frommodel['estcoefs'][vv]['se'] - 2*compdiff*V[vv][incvar]  + compdiff**2*frommodel['estcoefs'][incvar]['se'] )/frommodel['estcoefs'][incvar]['b']
                secompdiff = abs(compdiff) * sqrt((sx / bx)**2 + (sy / by)**2 -
                                                  2 * sxy / bx / by)

                cdModel['estcoefs'][vv] = {'b': compdiff, 'se': secompdiff}
            # Following line looks like I still nee dto program the functionalit for showCompDiff telling me where to put them.
            # May 2011: okay.. this should really be done at the *showing* stage... but for quick kluge to add basic functionality
            assert showCompDiff in [False, 'aftereach', 'only']
            if showCompDiff in ['aftereach']:
                models.insert(imodel + 1, cdModel)
            frommodel[
                'cdModel'] = cdModel  # This should just be a pointer to the same thing: I may not want to actually insert a new model, but rather act on the existene of a cdModel element.
            #fromModel['cdModel']=cdModel # uhhh.. i can't htink how to insert models as I go in a loop over models.
            if showCompDiff in ['only']:
                models[
                    imodel] = cdModel  # Destory the from model. replace it with the comp diff model..

            ##############################################################################
            # Make pairedRows, to fit with old code, for the time being.

        r2names = [
            'e(r2-a)', 'e(r2)', 'e(r2-p)', 'r2', 'r2_a', 'r2-a', 'r2_p', 'r2-p'
        ]

        # Reproduce old behaviour of showing a summed-income-coefficients value by adding a new variable
        for model in models:
            if model.get('special', '') in ['suestTests']:
                continue
            #summedIncomecoefs=[sum([icv[iModel] for icv in incomeCoefs if icv[iModel] ])  for iModel in range(len(pairedRows[0][0])-1)]
            incsum, seincsum = seSum([
                model['estcoefs'][vv]['b'] for vv in model['estcoefs']
                if vv in possibleIncomeVars
            ], [
                model['estcoefs'][vv]['se'] for vv in model['estcoefs']
                if vv in possibleIncomeVars
            ])
            if incsum and len([
                    model['estcoefs'][vv]['b'] for vv in model['estcoefs']
                    if vv in possibleIncomeVars
            ]) > 1:
                model['estcoefs'][
                    r'$\sum\beta_{\rm{inc}}$NOTUSINGCOVMATRIX'] = {
                        'b': incsum,
                        'se': seincsum
                    }
                #assert 0 # Whoa. Should do this sum properly using covariance matrix.... Don't delete copy of my old method, below, yet.

        assert not hidePSumTest  # This is no longer implemented. And this flag could just add the r(p) etc to hideVars rather than needing special treatment.. ? [sep 2009]

        # OR... insert them  as a column juust before r(p)
        if 0 and 'r(p)' in [ss[0] for ss in sumStatsRows]:
            if incomeCoefs:
                sumStatsRows.insert(
                    [
                        ipair for ipair in range(len(sumStatsRows))
                        if sumStatsRows[ipair][0] == 'r(p)'
                    ][0], [r'$\sum I$'] + chooseSFormat(
                        summedIncomecoefs, lowCutoff=1.0e-3))
            # And format the r(p) row while I am at it:
            #if 'r(p)' in [ss[0] for ss in sumStatsRows]:
            rprow = [ss for ss in sumStatsRows if ss[0] == 'r(p)'][0]
            rprow[1:] = chooseSFormat(rprow[1:], lowCutoff=1.0e-3)

        # If there is any information about a desired order of 

        if 0:
            # Remove hidevars from LaTeX output versions:
            if hidevars:
                noshowKeys = uniqueInOrder(re.split(' ', hidevars.strip()))
                for ipair in range(len(pairedRows))[::-1]:
                    if pairedRows[ipair][0][0] in noshowKeys:
                        pairedRows.pop(ipair)

            if hidevars:  # Careful; this feature hasn't been properly commensurated with showonlyvars:
                extralines = [
                    el for el in extralines if el[0].strip() not in noshowKeys
                ]
                sumStatsRows = [
                    el for el in sumStatsRows
                    if el[0].strip() not in noshowKeys
                ]

        if betas:  # Constant term is zero for standardized beta coefficients. So if they're all beta, don't show constant.
            hidevars += ' _cons'

        # kludge sept 2009: [no, not kludge. this is a formatting decision which should be here]
        skipCounts = 0
        for mm in models:
            if 'skipNumber' in mm:
                skipCounts += 1
            if 'isManualEntry' not in mm or 'texModelNum' not in mm:
                mm['texModelNum'] = '(%d)' % (mm['modelNum'] - skipCounts)
        if skipCounts:
            print '   Equation numbering reflects some "skipNumber"s and does not correspond to actual estimate numbers'

        ###################################################################################
        ###################################################################################
        ###################################################################################
        # I can immediately create the full version of the LaTeX file except for combining rows (models):
        ####tableFileName=tablenamel
        tableTexName, bothOutfilename, justaggFilename, justpooledFilename, crcFilename, crcOnlyFilename = tablenamel + extraTexFileSuffix, tablenamel + '-withMeans' + extraTexFileSuffix, tablenamel + '-onlyMeans' + extraTexFileSuffix, tablenamel + '-onlyPooled' + extraTexFileSuffix, tablenamel + '-wCRcoefs' + extraTexFileSuffix, tablenamel + '-CRcoefs' + extraTexFileSuffix
        if not produceOnly == None:
            produceOnlyLower = produceOnly.lower()
        else:
            produceOnlyLower = None

        # May 2011: add the texfilesuffix to caption so that the mod'd versions show up more nicely in TOC in auto LaTeX doc.
        tablecaption = tablename
        if extraTexFileSuffix:
            tablecaption += extraTexFileSuffix
        if produceOnly == None or produceOnlyLower in [None, 'onlyraw']:
            if not skipLaTeX:
                self.appendRegressionTable(
                    models,
                    tableFormat={
                        'caption': tablecaption,
                        'comments': comments,
                        'hideVars': hidevars,
                        'variableOrder': variableOrder,
                        'hideModelNames': hideModelNames
                    },
                    suppressSE=suppressSE,
                    substitutions=substitutions,
                    tableFilePath=defaults['paths']['tex'] + tableTexName +
                    '.tex',
                    transposed=transposed,
                    sourceLogfile=tableLogName
                    if not skipReadingResults else None
                )  #landscape=landscape,rowModelNames=rowModelNames,hideVars=hidevars,extralines,modelTeXformat=modelTeXformat, tableCaption=tablename,tableComments=comments

            #(not hideModelNames)*[amo['depvar'] for amo in models],['(%s)'%dd for dd in range(1,len(models)+1)],pairedRows,extralines+sumStatsRows,                         suppressSE=suppressSE,substitutions=substitutions,modelTeXformat=modelTeXformat,                         landscape=landscape, tableFilePath=defaults['paths']['tex']+tableTexName+'.tex', tableCaption=tablename,                         tableComments=comments, transposed=transposed,rowModelNames=rowModelNames,hideRows=hidevars)
            # ##self,models, extrarows,greycols=None,suppressSE=False,substitutions=None,modelTeXformat=None,transposed=None, tableFilePath=None, tableCaption=None, tableComments=None):

            ###################################################################################
            ###################################################################################
            ###################################################################################
            # Now, do any preparations needed for aggregating *models*. ie calculating means of results from similar models applied to different data.
            #

            # Have I excluded failed-regressions, like I did in the oldmethod?
        lSumGroups = uniqueInOrder(
            [m['meanGroupName'] for m in models if 'meanGroupName' in m])
        sumGroups = dict([[
            crg, [mm for mm in models if mm.get('meanGroupName', None) == crg]
        ] for crg in lSumGroups])
        # 

        #lCRgroups=uniqueInOrder([m['CRgroup'].keys()[0] for m in models if 'CRgroup' in m]) 
        #CRgroups=dict([[crg,[mm for mm in models if mm.get('CRgroup',None)==crg]] for crg in lCRgroups])
        #lSumGroups=uniqueInOrder([m['meanGroupName'] for m in models if 'meanGroupName' in m])
        #sumGroups=dict([[crg,[mm for mm in models if mm.get('meanGroupName',None)==crg]] for crg in lSumGroups])

        # It would be a mistake to call this in means mode if there are no models to combine.
        # So ? huh what is means mode? What did following assert supposed to do?
        #assert( sumGroups or not produceOnly or (produceOnly.lower() not in ['withmeans','onlymeans']) )

        if 1:

            # Following needs translating to newmethod:
            # Ensure that each agg group are all members of the same CR group:
            #aggCRgroups=[[models[iag-1]['CRgroup'] for iag in aggGroup if 'CRgroup' in models[iag-1]] for aggGroup in aggColumns]

            for sg in sumGroups:
                sgbyVar, sgbyStat, sgbyTextraline = modelResultsByVar(
                    sumGroups[sg])
                meanModel = {
                    'estcoefs': {},
                    'eststats': {},
                    'texModelNum': r'$\langle$%s-%s$\rangle$' %
                    (str(sumGroups[sg][0].get('modelNum', '??!') - 0),
                     str(sumGroups[sg][-1].get('modelNum', '??!') - 0)),
                    'modelNum': 0,
                    'name': sumGroups[sg][0].get('meanGroupName',
                                                 r'\cpblMeanRowName '),
                    'tableshading': 'grey',
                    'textralines': {},
                    'isMean': True
                }

                meanModel['meanGroupName'] = meanModel[
                    'name']  # why was this needed?
                assert meanModel[
                    'name']  # May 2011.. just reading through some code and not sure whether above is safe.
                for vv in sgbyVar:
                    mu, se = seMean(sgbyVar[vv]['coefs'], sgbyVar[vv]['ses'])
                    if mu not in [None, fNaN]:
                        meanModel['estcoefs'][vv] = {
                            'b': mu,
                            'se': se,
                        }
                    meanModel['eststats']['N'] = sum(
                        sgbyStat['N'])  #'$\\geq$%d'%min(sgbyStat['N'])
                    #eNcol[insertAt]='$\\geq$%d'%(min([int(eNcol[iii+1]) for iii in igroup  ]))

                # Now copy over the flags that are in common for all addends in this group:
                for vv in sgbyTextraline:
                    if all([
                            sgbyTextraline[vv][0] == tt
                            for tt in sgbyTextraline[vv]
                    ]):  #All addends have the same value for this flag:
                        meanModel['textralines'][vv] = sgbyTextraline[vv][0]
                    elif vv == 'survey':  # Special treatment for "survey" flag
                        meanModel['textralines'][
                            'survey'] = r'{\smaller \smaller $\langle$%d$\rangle$}' % (
                                len(uniqueInOrder(sgbyTextraline['survey']))
                            )  ##nNonZeroRegs)#len([agc for agc in aggColumns[iGroup] if >0]))
                        ###bextralines[irow].insert(insertionColumns[iGroup],r'{\smaller \smaller $\langle$%d$\rangle$}'%nNonZeroRegs)#len([agc for agc in aggColumns[iGroup] if >0]))

                    # And for all other fields in the model, copy over all other elements of the summed-over models which are in common.
                for kk in sumGroups[sg][0].keys():
                    if kk not in meanModel and all([
                            sumGroups[sg][0][kk] == tt.get(kk, None)
                            for tt in sumGroups[sg]
                    ]):  #All addends have the same value for this flag:
                        meanModel[kk] = sumGroups[sg][0][kk]
                        #print '%s are in common .. copying to mean...'%kk
                """ Now do the flags:

                for irow in range(len(bextralines)):
                    " For the current group, insert a value into each of the extralines fields."

                    thisval=extralines[irow][aggColumns[iGroup][-1]] # Value for this extraline in right-most of addend columns
                    if all([extralines[irow][ic]==thisval for ic in aggColumns[iGroup]]): # All addends have the same value for this property, so copy it:
                        bextralines[irow].insert(insertionColumns[iGroup],thisval)
                        #iExtraLinesMeans+=[irow]
                    elif 'survey '==bextralines[irow][0]:
                        bextralines[irow].insert(insertionColumns[iGroup],r'{\smaller \smaller $\langle$%d$\rangle$}'%nNonZeroRegs)#len([agc for agc in aggColumns[iGroup] if >0]))

                    else:
                        bextralines[irow].insert(insertionColumns[iGroup],'')
                    """

                # Insert this new "model" in the right place?  Insert also some dividers?
                iLast = [
                    ii for ii in range(len(models))
                    if models[ii] == sumGroups[sg][-1]
                ]
                assert len(
                    iLast
                ) == 1  # Important assertion: make sure models are not repeated object pointers. (or do this more generally, earlier on?)
                # Aug 2011: Following looks bizarre. Should copy the format of the first, not the last. Why? well... if we're reusing models, does this... uh... no, maybe it's fine. problem is somewhere else.
                meanModel['format'] = deepcopy(models[iLast[0]]['format'])
                if meanModel['estcoefs']:
                    models.insert(iLast[0] + 1, meanModel)
                #print "nEED TO GO THROUGH FLAGS HERE AND PRESERVE ONES THAT ARE IN COMMON?? AND DEAL WITH SUM OVER SURVEYS IN A CUSTOM WAY"

                ###if sumGroups:
                ###    # Create a list of CRgroups; keep track of this as list of models gets changed in various ways
                ###    CRgroups=[m.get('CRgroup',{}) for m in models]

        if (not skipLaTeX) and (sumGroups or combineColumns) and (
            (produceOnly == None and self.skipAllDerivedTables == False
             ) or produceOnlyLower in [None, 'withmeans', 'means']
        ):  # or produceOnly.lower() not in ['means','crc','onlyraw']:
            self.appendRegressionTable(
                models,
                tableFormat={
                    'caption': tablecaption + '~(with~means)',
                    'comments': comments,
                    'hideVars': hidevars,
                    'variableOrder': variableOrder,
                    'hideModelNames': hideModelNames
                },
                suppressSE=suppressSE,
                substitutions=substitutions,
                tableFilePath=defaults['paths']['tex'] + bothOutfilename +
                '.tex',
                transposed=transposed,
                sourceLogfile=tableLogName)

            #self.append('%s\\begin{table}\caption{%s}\\include{%s}\n%s\n\\end{table}%s\\clearpage\n'%(lscapeb,tablename.replace(' ','~')+'~(with~means)',bothOutfilename,comments,lscapee))
            print('Wrote "both-out" tex file...')

        if (sumGroups or combineColumns) and (
            (produceOnly == None and self.skipAllDerivedTables == False) or
                produceOnlyLower in [None, 'means', 'justmeans', 'onlymeans']
        ):  # or produceOnly.lower() not in ['means','crc','onlyraw']:

            # "means-only" version:
            # Make a version with only new columns, plus any columns
            # which were not part of an aggregate.. For instance, some
            # columns may only be possible for a single survey. It
            # would be nice here to have an entry in multiple rows of
            # tiny font to show the surveys included in means.

            if 1:
                onlyMeans = deepcopy([
                    mm for mm in models
                    if not any(
                        [any([mm in sumGroups[sg]]) for sg in sumGroups])
                ])
                if 0:  #WTF does the following not work?
                    onlyMeans = [
                        mm.update({
                            'tableshading': None
                        }) for mm in deepcopy(onlyMeans)
                    ]
                for mm in onlyMeans:
                    mm['tableshading'] = None

                if any(onlyMeans):
                    if not skipLaTeX:
                        self.appendRegressionTable(
                            onlyMeans,
                            tableFormat={
                                'caption': tablecaption + '~(only~means)',
                                'comments': comments,
                                'hideVars': hidevars,
                                'variableOrder': variableOrder,
                                'hideModelNames': hideModelNames
                            },
                            suppressSE=suppressSE,
                            substitutions=substitutions,
                            tableFilePath=defaults['paths']['tex'] +
                            justaggFilename + '.tex',
                            transposed=transposed,
                            sourceLogfile=tableLogName)
                        debugprint(
                            'Wrote "just-means" tex file... [newmethod]')
                else:
                    print ' --- onlyMeans array had no real entries. Why? '

        ######################################################################################################

        # Now, do one other strange thing. When I've used byCR to isolate coefficients at different spatial scales, I want to extract those isolated coefficients one by one for each series. Use just the only-means version of the table, which collapses all models run on each survey into one line. Single-survey models are also there.

        # I think in Aug 2008, CR coeffs functionality is working on summed models but not on unsummed (ie single survey) ones. Why?

        # late Aug 2008: One bug: when CT-level controls produce no regression, the line should be ignored when picking off CR coefficients. In particular, this is failing for models with only one survey..

        # So, to fix this, I should really be working from nCRgroups, not aggCRgroups. If the former doesn't exist, I'll need to fix that  still.

        # Make lookups for the groups:
        lCRgroups = uniqueInOrder(
            [m['CRgroup']['id'] for m in models if 'CRgroup' in m])
        #It seems the following isn't working; but is it even useful?
        CRgroups = dict([[
            crg, [
                mm for mm in models
                if mm.get('CRgroup', {}).get('id', None) == crg
            ]
        ] for crg in lCRgroups])

        if 0:

            ##CRgroupModels=[m for m in models if 'CRgroup' in m.keys()]#[[k for k in m.keys() if 'CRgroup' in k] for m in models]
            if CRgroups and aggCRgroups and any(
                    aggCRgroups
            ):  ##any([any(['CRgroup' in k for k in m.keys()]) for m in models]):
                """
                Plan: loop over each group which has CRgroup tag not equal to nothing:

                find list of all unique group names
                find all models in that group.
                get list of CRs
                etc

                N.B.: I want to keep any models which are not part of a CRgroup but which appear in the npairedRows. It's just that I want to collapse any CRgroup models into one line.

                More detail needed here...
                How do I avoid copying blanks?
                Once I know my variables that I am going to fill in  and I know which models are part of the group,
                shouldn't I just copy each non-blank value down to its appropriate entry in order that the models are called? ie assume that fixed effects are called in order of  decreasing scope from one model to the next?

                """
                # Prepare versions of output for a CR-f.e. table:
                crpairedRows = deepcopy(npairedRows)
                crsumStatsRows = deepcopy(nsumStatsRows)
                crextralines = deepcopy(nextralines)
                crcolumnName = deepcopy(ncolumnName)
                crcmodelTeXformat = ['c' for ccc in crcolumnName]
                crCRgroups = deepcopy(nCRgroups)
                allGroups = uniqueInOrder(
                    [gg.keys()[0] for gg in crCRgroups
                     if gg])  # Must preserve order.
                # Initialise list of models (row pairs) to keep:
                toDelete = []  #toKeep=range(len(npairedRows[0])-1) #Fine
                clustercol = [
                    ff for ff in crextralines if 'clustering' in ff[0]
                ]
                if clustercol:
                    clustercol = clustercol[0]
                surveycol = [ff for ff in crextralines if 'survey' in ff[0]]
                if surveycol:
                    surveycol = surveycol[0]
                eNcol = [
                    ff for ff in crsumStatsRows if ff[0] in ['e(N)', 'N']
                ]  ##'e(N)' == ff[0]]
                if eNcol:
                    eNcol = eNcol[0]

        if CRgroups:
            print('About to cycle through these CR groups: %s' %
                  str(CRgroups.keys()))
        from cpblUtilities import flattenList

        for CRg in CRgroups:
            if len(CRgroups[CRg]) < 2:
                continue
            # Store location for insertion of new CR coefs model. 
            iLastModel = [
                imm for imm, mmm in enumerate(models)
                if mmm is CRgroups[CRg][-1]
            ][0]
            # Also record a copy of the original set of models in the CR group:
            originalCRmodels = [mm for mm in CRgroups[CRg]]
            # Also note (first and last) non-means, for labelling CR coefs
            firstLast = [
                mm for mm in originalCRmodels if not mm.get('isMean', False)
            ]

            # Now, May 2010: the CRgroups could include fake-models that are sums over models, and/or real (original) models. I guess it's easy to make the old behaviour work: I'll say that if any of them are means, then just take the means.
            if any([mm.get('isMean', False) for mm in CRgroups[CRg]]):
                for im, gm in enumerate(CRgroups[CRg]):
                    if not gm.get('isMean', False):
                        gm['hideInCRCview'] = True
                CRgroups[CRg] = [
                    mm for mm in CRgroups[CRg] if mm.get('isMean', False)
                ]

            # So now in this CRgroup we have either all means or no means.

            gmodels = CRgroups[CRg]
            # Assume the CRs are decreasing in scale and that they start with a model with no f.e. dummies.
            topCR = gmodels[0]['CRgroup']['takeCoef']
            # Find out the list of CRs to deal with:
            CRs = [gm['CRgroup']['takeCoef'] for gm in gmodels]
            # assert CRs[-1]=='' # This is rather dictated by the withCRcells or whatever function, right? And we surely always want it: ie Wel... do we???? hm. no. revisit this if you get this assert...
            # assert len(CRs)>1 # Why? Not necessary, but silly if not true
            # Find out which variables we are going to collect CR coefs from. Look for them in the smallest scale (HH), ie no CRs.
            if crcoefsVars == None:
                crvars = flattenList([
                    vv for vv in gmodels[-1]['estcoefs']
                    if 'ln' in vv and 'ncome' in vv
                ])
                if crvars == []:
                    print 'Oh dear.. I found no variables for CR. WHAT IS GOING ON? Maybe this regression just failed...'
                    # I don't undestand why they would be in the last one, rather than the first.
                    # Uhhhh. hm.
                    crvars = flattenList([
                        vv for vv in gmodels[0]['estcoefs']
                        if 'ln' in vv and 'ncome' in vv
                    ])

            else:
                crvars = [
                    vv for vv in crcoefsVars if vv in gmodels[-1]['estcoefs']
                ]
            print '    %s: CR coefficient collection mode: Looking for CRs %s and variables %s.' % (
                CRg, str(CRs), str(crvars))
            assert crvars
            newCRmodel = deepcopy(gmodels[-1])
            newCRmodel.update({
                'isCRcoefs': True,
                'texModelNum': r'$\langle$%s-%s$\rangle$' %
                (str(firstLast[0].get('modelNum', '??!') - 0),
                 str(firstLast[-1].get('modelNum', '??!') - 0))
            })  # ,'modelNum':0})
            # Need to fiddle here with some flags??
            for kk in ['%s~f.e.' % CR for CR in CRs
                       if CR]:  # Get rid of CR~f.e. entries. ...
                #if kk in newCRmodel['textralines']:

                newCRmodel['textralines'][kk] = r'\YesMark'
            newCRmodel['eststats']['N'] = '$\\geq$%d' % (min(
                [int(gg['eststats']['N']) for gg in CRgroups[CRg]]))
            newCRmodel['textralines']['clustering'] = r'\YesMark'

            newCRmodel['name'] += ': CRcoefs'
            anythingForNewModel = False
            for im, gm in enumerate(gmodels[:-1]):
                for crvar in crvars:
                    copyCR = gm['CRgroup']['takeCoef']
                    if copyCR.lower() + '_' + crvar in gm['estcoefs']:
                        newCRmodel['estcoefs'][copyCR.lower(
                        ) + '_' + crvar] = deepcopy(
                            gm['estcoefs'][copyCR.lower() + '_' + crvar])
                        anythingForNewModel = True

            # Now insert this new model (maybe still needs some annotation.?) right after the final one in the group?
            if anythingForNewModel:
                self.addSeparator(newCRmodel)
                self.addSeparator(models[iLastModel])
                models.insert(iLastModel + 1, newCRmodel)

        if 0:
            if 0:

                for groupName in CRgroups:  #allGroups:
                    # Find the PR f.e. extralines row because I am going to use it to note new property. [HUH?.]
                    #topCRfeLine=[nel for nel in nextralines if topCR+'~f.e.' in nel[0] and any([col.strip(' ~0') for col in nel[1:]])]

                    #startFrom='PR' # Assume all CR sequences contain the same CRs???
                    #if not TopCR: # If there was no PR row, try for CMA in stead:
                    #    TopCR=[nel for nel in nextralines if 'CMA~f.e.' in nel[0]]# and         any([col.strip(' ~') for col in nel[1:]])]
                    #    startFrom='CMA'

                    # Now, find variables corresponding to the various CR coefficients of interest, noting that PR may not exist (in May 2008 I stopped using PR as a fixed effect)
                    incomeColsI = {}
                    #for ig in igroup[1:]: # Assume first has no CR f.e.
                    #    CR=crCRgroups[ig][groupName]
                    CRs = ['DA', 'CT', 'CSD', 'CMA', 'PR']

                    # Now, to choose which columns to look at to pick out coefficients, hunt for ones that look income related. Alternatively, the caller may specify them directly [new feature aug 2008. presumably not yet implemented]:
                    # But careful: 

                    for CR in CRs:
                        #incomeColsI[CR]=([ff for ff in  range(len(crpairedRows)) if CR.lower()+'-log' in crpairedRows[ff][0][0]]+[[]])[0]#Robust to finding nothing, though if loop is over igroup that would be impossible.
                        if crcoefsVars == None:  # Should this be a string? list of vars?
                            incomeColsI[CR] = [
                                ff for ff in range(len(crpairedRows))
                                if CR.lower() + '-log' in
                                crpairedRows[ff][0][0]
                            ]
                        else:
                            incomeColsI[CR] = [
                                ff for ff in range(len(crpairedRows))
                                if any([
                                    CR.lower() + '-' + crcoefvar in
                                    crpairedRows[ff][0][0]
                                    for crcoefvar in crcoefsVars
                                ])
                            ]

                    # Now, deal with one "CR" scale specially: this is the individual level (non-CR), ie the "HH" household level.  So I am still just finding variables, not models. This is the set of all other income-related stuff that does not have any CR-level with a fixed-effect sometimes provided.: Stick those into incomeColsI['HH'].
                    if crcoefsVars == None:  # Find all other income vars (ie, the default behaviour):
                        incomeColsI['HH'] = [
                            ff for ff in range(len(crpairedRows))
                            if 'ln' in crpairedRows[ff][0][0] and 'ncome' in
                            crpairedRows[ff][0][0] and all(
                                [ff not in incomeColsI[CR] for CR in CRs])
                        ]
                    else:  # If the variable names have been specified, we want the ones which have no CR_ prefix.
                        incomeColsI['HH'] = [
                            ff for ff in range(len(crpairedRows))
                            if crpairedRows[ff][0][0] in crcoefsVars
                        ]  # and all([ff not in incomeColsI[CR] for CR in CRs ])]

                    # incomeCols is just used for debugging at the moment:
                    incomeCols = {}
                    for CR in incomeColsI.keys():
                        incomeCols[
                            CR] = [crpairedRows[ff] for ff in incomeColsI[CR]]

                    #print('CR>: ',[[LL[0] for LL in incomeCols[kk]] for kk in incomeCols])

                    ##                     print(incomeCols['PR'])
                    ##                     print(incomeCols['CMA'])
                    ##                     print(incomeCols['CSD'])
                    ##                     print(incomeCols['CT'])
                    ##                     print(incomeCols['DA'])

                    # Now, insert a new model at the end of the CR group which will receive the extracted coefficients:
                    insertAt = igroup[-1] + 1 + 1
                    print(nrowModelNames)
                    isthisreached
                    for sp in crpairedRows:
                        sp[0].insert(insertAt, '')
                        sp[1].insert(insertAt, '')
                    for el in crextralines:  # Copy all of the extralines over.
                        el.insert(
                            insertAt, deepcopy(el[insertAt - 1])
                        )  #Rewrite this in terms of igroup, not insertAt.
                    for el in crsumStatsRows:  # Leave these blank.
                        el.insert(insertAt, '')
                    if hideModelNames:
                        crcolumnName.insert(insertAt - 1, '')
                    else:
                        crcolumnName.insert(
                            insertAt - 1,
                            'CR~coefs')  # -1 because there's no label in [0]?

                    #crcolumnNumbers.pop(td-1) # This is reset below
                    nrowModelNames.insert(
                        insertAt - 1,
                        '')  # huh??? what is this again? row or col
                    crcmodelTeXformat.insert(insertAt - 1, 'c|')
                    if '|' not in crcmodelTeXformat[insertAt - 2]:
                        crcmodelTeXformat[insertAt - 2] = 'c|'
                    crCRgroups.insert(insertAt - 1,
                                      {})  #deepcopy(crCRgroups[igroup[1]]))
                    print(nrowModelNames)
                    CRs = [
                        'HH', 'DA', 'CT', 'CSD', 'CMA', 'PR', ''
                    ]  # first element, HH, gets all te non-CR coefs first.
                    stillToCopy = deepcopy(CRs)

                    print('CR>: ', [[kk, [LL[0] for LL in incomeCols[kk]]]
                                    for kk in incomeCols])

                    # Now, if there are more f.e. than one, for each f.e., copy the next smallest coefficent over.
                    # ie loop over the f.e. models and copy appropriate coefficients from each model.
                    # I say coefficientS because for the no-f.e. case, we want all CR levels larger than or equal to the biggest f.e.
                    # For the no-f.e. model, copy 

                    # Uh.. is this from an older alogirithm?: # First, start by copying over all income variables from the smallest f.e. model: this should get HH income, etc.
                    #for ipr in incomeColsI['HH']:
                    #    prow=crpairedRows[ipr]
                    #    prow[0][insertAt]=prow[0][ig+1]
                    #    prow[1][insertAt]=prow[1][ig+1]

                    # New algorithm: Cycle over all CRs from small to large. For each, copy over smaller CR coefficents remaining in a list, and then *Delete* those from the list. (Why did I do this crazy fancy thing? I could have just redundantly copied them over until each is filled... e.g. start from final model and work backwards, filling in any not already filled.)

                    # Try rewriting the algorithm below, late August 2008 frustrated and confused as to why i needed something so complex.
                    for ig in igroup[::
                                     -1]:  # Loop backwards over models within our group so we go from small to large: ie algorithm still depends on the models being called in the right order. (?) ????
                        # For each model, copy over everything of interest which is not yet filled. It seems my list of all the variables of interest is stuck in incomeColsI
                        iRelevantVariables = []
                        for ii in incomeColsI:
                            iRelevantVariables += incomeColsI[ii]
                        for iRelevantVariable in iRelevantVariables:
                            # Fill in any variable not already filled:
                            prow = crpairedRows[iRelevantVariable]
                            if not prow[0][insertAt]:
                                prow[0][insertAt] = prow[0][ig + 1]
                                prow[1][insertAt] = prow[1][ig + 1]

                        #CR=crCRgroups[ig][groupName] # This finds the CR f.e. of a particular model in our group
                        # CRs to copy is all those models with f.e. that are smaller than CR and not yet copied:
                        #iii=[ic for ic in range(len(stillToCopy)) if stillToCopy[ic]==CR]

                        # The rather simpler version above, late Aug 2008, seems to work for income CRs, at least. Is there any reason not to use it also for the general case???
                    """
                    CRstoCopy: 
                    """
                    crKeepRows = []
                    for skipThisOldMethod in []:  #ig in igroup[::-1]: # Loop backwards over models within our group so we go from small to large: ie algorithm still depends on the models being called in the right order. (?) ????
                        CR = crCRgroups[ig][
                            groupName]  # This finds the CR f.e. of a particular model in our group
                        # CRs to copy is all those models with f.e. that are smaller than CR and not yet copied:
                        iii = [
                            ic for ic in range(len(stillToCopy))
                            if stillToCopy[ic] == CR
                        ]
                        if iii:
                            CRstoCopy = stillToCopy[0:(iii[0])]
                            print(stillToCopy, CRstoCopy, CR)
                            for cc in CRstoCopy:
                                stillToCopy.remove(cc)
                            for CRtoCopy in CRstoCopy:
                                # So loop over the variable rows with those income coefficients:
                                print('<CR>: So I am looking for rows with ' +
                                      CRtoCopy + '\n')
                                for ipr in incomeColsI[CRtoCopy]:
                                    """
                                    At this point, CRtoCopy is the CR level being copied,
                                    stillToCopy lists the CRs larger than the current one;
                                    incomeColsI is a dict which tells me which variable number contains each CR coefficient.
                                    So the present loop is copying coefficients for one CR from each model large to small each available
                                    """
                                    #print('<CR>:   Row %d is one\n'%ipr)
                                    crKeepRows += [ipr]
                                    prow = crpairedRows[ipr]
                                    if prow[0][
                                            ig +
                                            1]:  # Only copy over the values if they are not blank. So, for missing regressions, the model is counted as included but actually skipped in filling in the CR coefs row.
                                        prow[0][insertAt] = prow[0][ig + 1]
                                        prow[1][insertAt] = prow[1][ig + 1]
                                    elif 'CRd' in tableFileName:
                                        pass  #                                        sdofisdf

                                    #if not prow[0][ig+1]:
                                    #    prow[0][insertAt]=groupName
                                    print(
                                        'In CRgoup %s, Copied value "%s" from indep var: %s to new indep var with position %d'
                                        % (groupName, prow[0][ig + 1],
                                           prow[0][0], insertAt))
                        else:
                            print 'uhhh..iii empty'

                    # Now, remove all coefficients in other rows that shouldn't be in this CR summary one:
                    # We want to keep all the income rows:
                    #keepCRrows=
                    # And fix up some of the other "otherlines" entries:
                    if clustercol:  # This is not quite right for the with-CRcoefs output format. It's made for the only-CRcoefs...
                        debugprint('CLUSTERCOL:', clustercol)
                        clustercol[0] = 'geo~fixed~effects'
                        clustercol[insertAt] = r'\YesMark'
                        debugprint('CLUSTERCOL:', clustercol)
                    #if surveycol:
                    #    surveycol[insertAt]=deepcopy(surveycol[igroup[-1]+1])
                    if eNcol:
                        eNcol[insertAt] = '$>$%d' % (min([
                            int(eNcol[iii + 1]) for iii in igroup
                            if int(eNcol[iii + 1]) > 0
                        ]))
                        # No... I want to mark when the CT one failed; a ">0" is as good as anything.
                        eNcol[insertAt] = '$\\geq$%d' % (min(
                            [int(eNcol[iii + 1]) for iii in igroup]))
                    ###crcmodelTeXformat[iTopCR-1]='c|'

                    # And get rid of all f.e. columns and "clustering" columns
                    # (not done...)
                for el in range(len(crextralines))[::-1]:
                    if 'f.e.' in crextralines[el][0]:
                        crextralines.pop(el)

        # Still need to fix some column titles and column numbers.
        #crcolumnNumbers=['(%d)'%dd for dd in range(1,len(crpairedRows[0][0]))]
        madeOutputCRC = False
        if (CRgroups) and not skipLaTeX and [
                mm for mm in models if mm.get('isCRcoefs', False)
        ] and ((produceOnly == None and self.skipAllDerivedTables == False) or
               produceOnlyLower in [None, 'withcrc', 'crc']):
            self.appendRegressionTable(
                [mm for mm in models if not mm.get('hideInCRCview', False)],
                tableFormat={
                    'caption': tablecaption + '~(with~crc)',
                    'comments': comments,
                    'hideVars': hidevars,
                    'variableOrder': variableOrder
                },
                suppressSE=suppressSE,
                substitutions=substitutions,
                tableFilePath=defaults['paths']['tex'] + crcFilename + '.tex',
                transposed=transposed,
                sourceLogfile=tableLogName)
            print('Wrote "with CRC coefs" tex file...')
            madeOutputCRC = True

        if (CRgroups) and (
            (produceOnly == None and self.skipAllDerivedTables == False
             ) or produceOnlyLower in [None, 'withcrc', 'onlycrc', 'crc']
        ) and [mm for mm in models
               if mm.get('isCRcoefs', False)] and not skipLaTeX:
            self.appendRegressionTable(
                [mm for mm in models if mm.get('isCRcoefs', False)],
                tableFormat={
                    'caption': tablecaption + '~(only~crc)',
                    'comments': comments,
                    'hideVars': hidevars,
                    'variableOrder': variableOrder
                },
                suppressSE=suppressSE,
                substitutions=substitutions,
                tableFilePath=defaults['paths']['tex'] + crcOnlyFilename +
                '.tex',
                transposed=transposed,
                sourceLogfile=tableLogName)
            print('Wrote "only CRC coefs" tex file...')
            madeOutputCRC = True

        if not madeOutputCRC and defaults['mode'] in [
                'RDC'
        ]:  # or 'redux' not in tablenamel or 'ontrol' not in extraTexFileSuffix
            print '   No CRC-containing tables were made for  %s (%s) because of produceOnly, no CRcoefs, or some other reason ' % (
                tablenamel, extraTexFileSuffix)

        # if 0:# and produceOnly==None or produceOnly.lower() in ['withcrc']:
        #     if not skipLaTeX:
        #         self.old_forPairedRows_appendRegressionTable((not hideModelNames)*crcolumnName,crcolumnNumbers,crpairedRows,crextralines+crsumStatsRows,substitutions=substitutions,suppressSE=False,#suppressSE,
        #             landscape=landscape, tableFilePath=defaults['paths']['tex']+crcFilename+'.tex', tableCaption=tablename+'~(with~CRC~coefs)', tableComments=comments,modelTeXformat=crcmodelTeXformat,
        #             transposed=transposed,rowModelNames=nrowModelNames,hideRows=hidevars)
        #         debugprint('Wrote "with CRC coefs" tex file...')

        #         #len(crcolumnName),len(crcolumnNumbers),len(crpairedRows),len(crextralines),len(crsumStatsRows)
        # if 0:
        #     if 0:
        #         for groupName in allGroups:
        #             igroup=[imodel for imodel in range(len(crCRgroups)) if crCRgroups[imodel] and crCRgroups[imodel].keys()[0]==groupName]
        #             print('Found %d models in CR group %s\n'%(len(igroup),groupName))

        #             # This is for a different form of output in which only CRCs are there... I want the option of both.
        #             # Now, get rid of all those models which have just been used to make CR summaries:

        #             ##toDelete=[xx+1 for xx in sorted(list(set(igroup)-set([min(igroup),max(igroup)])) )] # ie keep the first (no f.e.) and last (extracted CR coefs)
        #             # ie keep the first (no f.e.) and last (extracted CR coefs)
        #             toDelete=[xx+1 for xx in igroup[1:]]#sorted(list(set(igroup)-set([min(igroup),max(igroup)])) )] 
        #             print(' Deleting rows ', toDelete, ' for ',groupName, ' which is at ',igroup)
        #             for td in toDelete[::-1]: # This hardcodes the fact that the first entry is no f.e., and second entry receives CR summaries.
        #                 for sp in crpairedRows:
        #                     sp[0].pop(td)
        #                     sp[1].pop(td)
        #                 for el in crextralines:
        #                     el.pop(td)
        #                 for el in crsumStatsRows:
        #                     el.pop(td)
        #                 crcolumnName.pop(td-1) # -1 because there's no label in [0]?
        #                 #crcolumnNumbers.pop(td-1) # This is reset below
        #                 nrowModelNames.pop(td-1)
        #                 crcmodelTeXformat.pop(td-1)
        #                 crCRgroups.pop(td-1) # So that next igroup will be calculated correctly.

        #         # Still need to fix some column titles and column numbers.
        #         crcolumnNumbers=['(%d)'%dd for dd in range(1,len(crpairedRows[0][0]))]
        #         if produceOnly==None or produceOnly.lower() in ['means','crc']:
        #             1/0
        #             if not skipLaTeX:
        #                 self.old_forPairedRows_appendRegressionTable((not hideModelNames)*crcolumnName,crcolumnNumbers,crpairedRows,crextralines+crsumStatsRows,substitutions=substitutions,suppressSE=False,#suppressSE,
        #         landscape=landscape, tableFilePath=defaults['paths']['tex']+crcOnlyFilename+'.tex', tableCaption=tablename+'~(CRC~coefs)', tableComments=comments,modelTeXformat=crcmodelTeXformat,
        #                      transposed=transposed,rowModelNames=nrowModelNames,hideRows=hidevars)
        #                 debugprint('Wrote "CRC coefs" tex file...')

        #     print 'continuing after missing CR section...'
        #     # Finally, make a version which excludes all addends AND all means. ie just conventional, pooled columns.
        #     if 1:
        #         print 'not sure that all features are yet implemented in new method; see older code above'
        #         onlyPooled=[mm for mm in models if not any([any([mm in sumGroups[sg]]) for sg in sumGroups]) and not 'meanGroupName' in mm]
        #         if onlyPooled and not skipLaTeX:
        #             self.appendRegressionTable(onlyPooled,tableFormat={'caption':tablecaption+'~(only~pooled)','comments':comments,'hideVars':hidevars,'variableOrder':variableOrder},
        #                  suppressSE=suppressSE,substitutions=substitutions, tableFilePath=defaults['paths']['tex']+justaggFilename+'.tex', transposed=transposed)

        #
        # NOW DEAL WITH FOLLOW-UP FUNCTIONS: PASS ALL OUTPUT DATA TO ANY DESIRED PLOTTING,ETC FUNCTION(S)
        #

        # Automatically invoke subSampleAccounting whenever getSumSampleSums is invoked in any model:
        if any(['getSubSampleSums' in mm for mm in models]):
            if not followupFcn:
                followupFcn = [subSampleAccounting]
            elif not followupFcn == subSampleAccounting and not subSampleAccounting in followupFcn:
                followupFcn += [subSampleAccounting]

        if followupFcn:  # Maybe this call should come earlier, if models gets too fiddled with.
            standardArgs = {
                'tableFileName': tableFileName,
                'tablename': tablename,
                'substitutions': substitutions
            }
            for ff in standardArgs:
                followupArgs[ff] = followupArgs.get(ff, standardArgs[ff])
            if isinstance(followupFcn, list):
                for fcn in followupFcn:
                    fcn(self, models, followupArgs)
            else:
                followupFcn(self, models, followupArgs)

        if returnModels:
            # Make effort now to send the updated models out to the calling function. #:(   ie via updating the list/dict.
            # April 2010: I think this fails if a list of list of dicts is sent.........1
            lom = len(originalModels)
            # I've tried to find a way to do this which gets the model pointers into the original pointer list. I think the following strange combination works: I have to start off replacing existing elements, and then I can extend that list without losing the original address.
            for imm in range(len(models)):
                if imm < lom:
                    originalModels[imm] = models[imm]
                else:
                    originalModels += [models[imm]]
            #originalModels=originalModels[lom-1:]
            # That (above) seems successful..

        return (outs)  # Returns stata code

    def includeFig(self, figname=None, caption=None, texwidth=None,
                   title=None):  #,,onlyPNG=False,rcparams=None

        if texwidth == None:
            texwidth = r'[width=0.5\columnwidth]'
        elif not texwidth == '':
            texwidth = '[width=%s]' % texwidth

        figlocation, figfile = os.path.split(figname)
        if not figlocation:
            figlocation = r'\texdocs '
        else:
            figlocation += '/'

        if caption == None:
            caption = ' (no caption) '
        if title == None:
            title = figfile

        # % Arguments: 1=filepath, 2=height or width declaration, 3=caption for TOC, 4=caption title, 5=caption details, 6=figlabel
        figCode = r"""
        \clearpage\newpage\clearpage
%\begin{landscape}
\cpblFigureTC{""" + figlocation + figfile + '.pdf}{' + texwidth[
            1:
            -1] + r'}{ ' + title + '}{' + title + '}{' + caption + '' + '}{' + figfile + """}
%\end{landscape} 
\clearpage
"""
        # r'\ctDraftComment{'+figlocation+figfile+'}'+

        #/home/cpbl/rdcLocal/graphicsOut/corrsBynCR-A50-macroTS-GSS17-GSS22-belongCommunity}}{\linkback{corrsBynCR-A50-macroTS-GSS17-GSS22-belongCommunity}}{corrsBynCR-A50-macroTS-GSS17-GSS22-belongCommunity}
        # Old version, retired:
        r"""
\begin{figure}
\centering  \includegraphics""" + texwidth + '{' + figlocation + figfile + '.pdf' + r"""}
\caption[""" + figname + title + r'AAA]{ \ctDraftComment{' + figlocation + figfile + '}' + title + '' + caption + 0 * (
            r' \ctDraftComment{' + figlocation + figfile + '}') + r"""
\label{fig:""" + figfile + r"""} }
\end{figure} 
%\end{landscape} 
\clearpage
                """
        figtout = open(
            defaults['paths']['tex'] + 'tmpFig-' + figfile + '.tex',
            'wt',
            encoding='utf-8')
        figtout.write(figCode)
        figtout.close()

        self.append(r"""%% \input{\texdocs tmpFig-""" + figfile + """}
        """ + figCode)
        print '   Included %s in latex file...' % figname
        return ()

    def saveAndIncludeStataFig(self, figname, caption=None, texwidth=None):
        """
        You probably want to include the following in your stata plot command:
        graphregion(color(white)) bgcolor(white)
        """
        pp, ff, ee = [os.path.split(figname)[0]] + list(
            os.path.splitext(os.path.split(figname)[1]))
        if pp in ['']: pp = paths['graphics']

        stout = graphexport(pp + '/' + ff + '.pdf')
        self.includeFig(pp + '/' + ff, caption=caption, texwidth=texwidth)
        return (stout)

    def saveAndIncludeFig(
            self,
            figname=None,
            caption=None,
            texwidth=None,
            title=None,  # It seems title is not used.
            onlyPNG=False,
            rcparams=None,
            transparent=False,
            eps=False,  # EPS is useless. No transparency or gradients. Make it from png?
            # And include options from savefigall() [April 2011]
            ifany=None,
            fig=None,
            skipIfExists=False,
            pauseForMissing=True,
            bw=False,
            FitCanvasToDrawing=False,
            rv=False,
            dpi=None):
        """ Save a figure (already drawn) and include it in the latex file.

        Dec 2009: Also, create a .tex file that can be included in other drafts. ie this means caption etc can be updated automatically too.

        July 2010: hm, where to put this stuff, though? Put it all in texdocs?? Agh, it's become a mess. At the moment this works if you just don't give any path as part of figname. (duh, it's a name, not a path)..    Oh. mess because I make two kinds of output. A direct include and an \input .tex file! So look again, and decide on the paths...



    July 2010: This will now be a repository for making sure I have nice TeX fonts in here, too??? So I need to worry about the physical width of the figure and font sizes, then too.... as options... not done!!   But see my figureFontSetup in utilities!! So not yet implemented: rcparams.

Sept 2010: Moved some code out of here into includeFig(), which includes an existing graphics file

Sep t2010: Move the default location to paths['graphics'] from paths['tex']. includeFig still makes an includable .tex file that wraps the fig, and this .tex file is still in paths['tex']
    
Sept 2010: looks at self.skipStataForCompletedTables to determine whether to save the fig... This could be made more choicy with a parameter, forceUpdate...

June 2012: Added / Passing rv option through to savefigall

        """
        import pylab
        #####alreadySaved=  os.path.split(figname)[0] and (os.path.exists(figname) or os.path.exists(figname+'.pdf')) and title==None and onlyPNG==False and rcparams==None# Oh: the figure is already done..., is an absolute path. Just include it.
        classSaysSkipUpdate = self.skipStataForCompletedTables
        if self.skipSavingExistingFigures is not None:
            classSaysSkipUpdate = self.skipSavingExistingFigures

        from matplotlib import rc
        if 0:  # What?. This should be at the output stage. June 2012
            rc('font', **{'family': 'sans-serif', 'sans-serif': ['Helvetica']})
            # # for Palatino and other serif fonts use:
            # rc('font',**{'family':'serif','serif':['Palatino']})
            rc('text', usetex=True)
            if 0:
                params = {#'backend': 'ps',
               'axes.labelsize': 20,
               'text.fontsize': 14,
               'legend.fontsize': 10,
               'xtick.labelsize': 16,
               'ytick.labelsize': 16,
               'text.usetex': False,}
            #'figure.figsize': fig_size}
            if rcparams:
                plt.rcParams.update(rcparams)
        if figname == None:
            figname = self.fname + '_' + str(pylab.gcf())
        # Careful. Adding this 2012 Feb:
        from cpblUtilities import str2pathname

        # oh dear... i commented out the following april 2010. will this break anything?
        #else:
        #    title='[%s]'%title

        figlocation, figfile = os.path.split(figname)
        if not figlocation:
            figlocation = paths['graphics']
        else:
            figlocation += '/'
        # But if this is going to be included in LaTeX, it cannot contain an underscore.
        figfile = str2pathname(figfile).replace(
            '_', '-')  # really? I have other utilties for this...

        #figpath=figname
        if onlyPNG:
            if classSaysSkipUpdate and os.path.exists(
                    figlocation + figfile + '.png') and os.path.exists(
                        figlocation + figfile + '.pdf'):
                print '   Skipping  saving figure ' + figlocation + figfile + ' because it already exists and self.skipStataForCompletedTable==True'
            else:
                pylab.savefig(
                    figlocation + figfile + '.png'
                )  # Missing the bw option to make both colour and bw versions.
                assert not "oops: ifany=None,fig=None,skipIfExists=False,pauseForMissing=True): not implemented yet"
                print "      Wrote a figure: " + figname + '.[png]'
        else:
            from cpblUtilities import savefigall
            if (skipIfExists or classSaysSkipUpdate) and os.path.exists(
                    figlocation + figfile + '.png') and os.path.exists(
                        figlocation + figfile + '.pdf'):
                print '   Skipping  saving figure ' + figlocation + figfile + ' because it already exists and self.skipStataForCompletedTable==True'
                rootAndTail = True  # Huh? this is a kluge based soley on "if rootandtail" below. I dont' know what root and tail are right now.
            else:
                rootAndTail = savefigall(
                    figlocation + figfile,
                    transparent=transparent,
                    ifany=ifany,
                    fig=fig,
                    pauseForMissing=pauseForMissing,
                    bw=bw,
                    FitCanvasToDrawing=FitCanvasToDrawing,
                    eps=eps,
                    rv=rv,
                    dpi=dpi)
                print "      Wrote a figure: " + figname + '.[pdf/png]'

        if rootAndTail:
            self.includeFig(
                figlocation + figfile, caption=caption, texwidth=texwidth)

        return ()

    def compareMeansInTwoGroups(self,
                                showVars,
                                ifgroups,
                                ifnames,
                                tableName=None,
                                caption=None,
                                usetest=None,
                                skipStata=False,
                                weight=' [pw=weight] ',
                                substitutions=None,
                                datafile=None):
        """
        May 2011. I have written almost all of this into addDescriptiveStatistics() as the mode=compareMeans mode, but I'm moving it to its own function to complete it.

        So write this to work as part of latex output, only.

        Plan: generate code, which creates its own logfile. If logfile exists, process it into a table.

        Can use a t-test or a ranksum (Two-sample Wilcoxon rank-sum (Mann-Whitney) test) to compare means.

        """
        import time
        statacode = ''
        if datafile is not None:
            statacode += stataLoad(datafile)

        if substitutions is None:
            substitutions = self.substitutions
        if isinstance(showVars, basestring):
            showVars = [vv for vv in showVars.split(' ') if vv]

        tablenamel = self.generateLongTableName(tableName)  #,skipStata=False)
        print """regTable(): Initiated "%s" with %d variables. """ % (
            tablenamel, len(showVars))

        tableLogName = paths['tex'] + tablenamel + '.log'
        tableLogNameWithDate = defaults['paths']['stata'][
            'working'] + 'logs/' + tablenamel + time.strftime(
                '%Y_%m_%d_%H%M%S_') + '.log'

        if self.skipStataForCompletedTables and os.path.exists(tableLogName):
            if not skipStata:
                print '  Skipping Stata for %s because latex.skipStataForCompletedTables is set ON!!!! and this table is done.' % tablenamel
            statacode += """
            """
            skipStata = True

        assert len(ifgroups) == 2
        assert len(ifnames) == 2
        statacode += """
        log using %s, text replace

        * CPBL BEGIN TABLE:%s: AT %s

        """ % (tableLogNameWithDate, tableName,
               time.strftime('%Y_%m_%d_%H%M%S'))

        statacode += """
        capture noisily drop _cmtg
        gen _cmtg=0 if %s
        replace _cmtg=1 if %s
        """ % (ifgroups[0], ifgroups[1])

        print 'Still need to add weights and svy behaviour.'
        statacode += '\n'.join([("""

            capture confirm variable """ + vv + """,exact
            if _rc==0 {
            capture confirm numeric variable """ + vv + """,exact
            if _rc==0 {
            di "-~-~-~-~-~-~-~-~"
            mean """ + vv + ' if ' + ifgroups[0] + """
            test """ + vv + """
            mean """ + vv + ' if ' + ifgroups[1] + """
            test """ + vv + """
            *x~x~x~x~x~x~x~x~x~
            ranksum """ + vv + """, by(_cmtg)
            *--~--~--~--~--~
            }
            }
            """).replace('\n            ', '\n') for vv in showVars if vv])

        statacode += """
        * CPBL END TABLE:%s: AT %s

            * Succeeded / got to end.
            * Closing %s
            capture noisily log close
             """ % (tableName, time.strftime('%Y_%m_%d_%H%M%S'),
                    tableLogNameWithDate) + """
* Since we've successfully finished, set the preceeding log file as the conclusive one
 copy "%s" "%s", replace
 """ % (tableLogNameWithDate, tableLogName)

        if skipStata:
            statacode = ''
            oiuoiu

        if not os.path.exists(tableLogName):
            print " ****  SKIPPING THE COMPARE MEANS BY GROUP IN %s BECAUSE YOU HAVEN'T RUN Stata yet to  make it." % tableLogName
            return (statacode)

        stataLogFile_joinLines(tableLogName)

        fa = re.findall("""\* CPBL BEGIN TABLE:%s:(.*?)\* CPBL END TABLE:%s:"""
                        % (tableName, tableName), ''.join(
                            open(tableLogName, 'rt').readlines()), re.DOTALL)
        assert len(fa) == 1
        meanRE = '\s*Mean estimation\s*Number of obs\s*=\s*(\w*)\n(.*?)\n'
        meanRE = '\s*Mean estimation\s*Number of obs\s*=\s*(\w*)\n[^\|]*\|[^\|]*\|\s*([^\s]*)\s+([^\s]*)\s+([^\s]*)\s+([^\s]*)\n[\s-]*'
        meanRE = r'\s*Mean estimation\s*Number of obs\s*=\s*([^\s]*)\n[^\|]*\|[^\|]*\|\s*([^\s]*)\s+([^\s]*)\s+([^\s]*)\s+([^\s]*)\n[\s-]*'
        testRE = '.*? Prob > ([Fchi2]*) = +([^\s]*)\s*'
        WilcoxonTestRE = '.*? Prob > \|z\| = +([^\s]*)\s*'

        # Following long RE is meant to get the long list of variables in the line below (with tonumeric...) for each variable/condition 
        vps = re.findall(
            '\n-~-~-~-~-~-~-~-~\n\s*mean (\w*) if ([^\n]*)\n' + meanRE +
            '\s*test ([ \w]*)\n' + testRE + '\s*mean' + ' (\w*) if ([^\n]*)\n'
            + meanRE + '\s*test ([ \w]*)\n' + testRE +
            '\s*.x~x~x~x~x~x~x~x~x~\n\s*ranksum ([^\n]*)\n' + WilcoxonTestRE +
            '\s*\*--~--~--~--~--~', fa[0], re.DOTALL)
        if not len(vps) == len(showVars) and len(vps) > 0:
            print "    RegExp fails to match to Number of variables, but there are some.  Probably some requested variables didn't exist? INVESTIGATE, and only request extant variables."
            showVars = [vv for vv in showVars if vv in [vvv[0] for vvv in vps]]
            print('   Continuing, using only %s' % str(showVars))
        if not len(vps) == len(showVars):
            print "    RegExp fails to match to Number of variables, though maybe some didn't exist? Or the format's changed / r.e. broken. Instead, assuming code has changed. Aborting. Rerun Stata..."
            return (statacode)
        varDicts = []
        body = []
        headers = ['Variable', ifnames[0], ifnames[1], r'$p$(equal)']
        for iv, oneVar in enumerate(vps):

            v1, if1, N1, mu1, se1, low1, high1, v1t, fchi1, pmu1, v2, if2, N2, mu2, se2, low2, high2, v2t, fchi2, pmu2, Wts, pW = tonumeric(
                [kk for kk in oneVar])
            if not (showVars[iv] == v1 and showVars[iv] == v2 and
                    showVars[iv] == v1t and showVars[iv] == v2t):
                print(
                    '  Problem with variable alignment. RERUN Stata. *********** '
                )
                return (statacode)

            xs1, ses1 = latexFormatEstimateWithPvalue(
                [mu1, se1],
                pval=pmu1,
                allowZeroSE=None,
                tstat=False,
                gray=False,
                convertStrings=True,
                threeSigDigs=None)
            xs2, ses2 = latexFormatEstimateWithPvalue(
                [mu2, se2],
                pval=pmu2,
                allowZeroSE=None,
                tstat=False,
                gray=False,
                convertStrings=True,
                threeSigDigs=None)
            pWs = latexFormatEstimateWithPvalue(
                pW,
                pval=pW,
                allowZeroSE=None,
                tstat=False,
                gray=False,
                convertStrings=True,
                threeSigDigs=None)
            body += [
                [substitutedNames(v1, substitutions), xs1, xs2, pWs],
                ['', ses1, ses2, ''],
            ]

        cpblTableStyC(
            cpblTableElements(
                body='\\\\ \n'.join(['&'.join(LL) for LL in body]) +
                '\\\\ \n\\cline{1-\\ctNtabCols}\n ',
                cformat=None,
                firstPageHeader='\\hline ' + ' & '.join(headers) +
                '\\\\ \n\\hline\n',
                otherPageHeader=None,
                tableTitle='Comparing means for %s and %s (%s)' %
                (ifnames[0], ifnames[1], tableName),
                caption=None,
                label=None,
                ncols=None,
                nrows=None,
                footer=None,
                tableName=tableName,
                landscape=None),
            filepath=paths['tex'] + tablenamel + '.tex',
            masterLatexFile=self)
        #logfname+'-compareMeans-'+str2pathname('-'.join(ifNames))
        """
        \n-~-~-~-~-~-~-~-~[^~]*\|[^~]*\|\s*([^\s]*)\s+([^\s]*)\s+([^\s]*)\s+([^\s]*)\n'  +\
        r'[^~]*Prob >([\sFchi2]*)=\s*([^\s]+)\s+\}(.*?)x~x~x~x~x~x~x~x~x~'#'#(\s+.*?)~'#
"""
        return (statacode)

    def addDescriptiveStatistics(self,
                                 tablename=None,
                                 dataFile=None,
                                 codebook=None,
                                 showVars=None,
                                 weightVar=None,
                                 ifcondition=None,
                                 forceUpdate=False,
                                 mainSurvey=None,
                                 code=None,
                                 ifNames=None,
                                 caption='',
                                 mode=None,
                                 substitutions=None):
        # callStata=False,
        """ Starting over.
        This is now a member of latexRegressionFile, rather than the codebook class.

There are two modes. See old getDescriptiveStatistics in codebook class for comments (to copy here) no move here.

If DTA is specified, this will CALL STATA and make the log file (if needed). It adds a table to the self. [Oh.? This seems wrong if there is ifcondition]
IF DTA is not specified, this will produce STATA CODE to make the means log. It returns the stata code and adds a table to the self.

If codebook is specified, at the moment it still requires one of the above, but codebook can allow descriptions etc to be avaialble.


June 2010: I added the feature o being able to giv ea list of "if conditions", but it still turns these into separate tables. Need to combine the tables.

June 2010: Added "ifNames" option: give names to the ifconditions.

Nov 2010: Does not work as advertised. returning Stata code fails due to assert datafile. I got around it only by specifying a manual codebook. Maybe that's a feature. 

-->> *** Also fails to give warninga bout notFound if execStata is False. Fix this..

May 2011: adding mode=None. if mode='compareMeans', make a table which compares means for two groups. oh .. .no.. I've made that into a separate function now, so I shouldn't have meddled here.

2013 April: Added substitutions option. Works, at least, for singlesurvey means.
        """

        # Two modes: return stata code or run it standalone, ie loading a file.
        execStata = dataFile is not None

        #assert codebook==None # Not programmed yet. Dec 2009. But it should be. Then this does everything. Codebook one could just call the old function in codebook class...
        assert tablename  # Right now not sure how to generate automatic name for this table... Unless there's just one per latex file... So this must be specified.
        from cpblUtilities import str2pathname
        # Retired mar 2013: logname=str2pathname(logname)#''.join([cc for cc in logname if cc not in [' ']])
        """Old comments:

        Actually, self.codebook or codebook can be used to specify a DTA file instead of a codebook class...


This is evolving again. If callStata==False, this returns Stata code to make a log file containing means USING THE DATASET CURRENTLY IN MEMORY.

If callStata==True, then DTA should be specified (if it doesn't exist yet, we will just skip this with a warning). Also in this case, weightIf can specify the syntax for weight and a ocondition to be used in calcuating means -- ie it's in Stata syntax format. In this case, Stata will actually be called when this function executes and generate the means separately.

This function adds a table to the output LaTeX file.

So, this can be used either in a sort of automatic mode when closing a LaTeX file, e.g. based on the variables that have been used altogether, or it can be used to make an intermediate table of stats in the middle of a LaTeX file.


 I NEED EXAMPLES HERE.........  (no, see docs above (in latex class?))
        """

        # Possibly specify the relevant survey and/or datafile:
        if dataFile and self.mainDataFile and not dataFile == self.mainDataFile:
            print 'CAUTION! Overriding %s with %s for main survey for stats' % (
                self.mainDataFile, dataFile)
        if not dataFile:
            dataFile = self.mainDataFile
        if mainSurvey == None:
            mainSurvey = self.mainSurvey
        if not dataFile and mainSurvey:
            # This doesn't seem quite right -- I should be savvy enough here to load up whatever is available, ie incorporating info from the PDF codebook from Stats Can, not just what fits into a DTA file.
            dataFile = WP + 'master' + mainSurvey
        if codebook == None:
            codebook == self.codebook
        if codebook == None and mainSurvey:
            codebook = stataCodebookClass(survey=mainSurvey)

        # Choose variables to make stats of:
        """ 2010Feb. If showVars is not specified, then we try all variables in the variablesUsed list, but note that the Stata code below is robust to each variable not existing. Only those that exist are sum'ed, mean'ed, or read.
        """
        if showVars == None:
            assert self.variablesUsed
            showVars = [
                vv for vv in uniqueInOrder(self.variablesUsed.split(' ')) if vv
            ]
        if isinstance(showVars, str) or isinstance(showVars, unicode):
            showVars = uniqueInOrder([vv for vv in showVars.split(' ') if vv])
        #Require that variables are a unique list; otherwise order will be messed up? (Or could rely on auto ordering)
        assert isinstance(showVars, list)
        if not len(uniqueInOrder(showVars)) == len(showVars):
            print(
                " UHHHHH: You probably want to fix this so as not to screw up order..."
            )
            showVars = uniqueInOrder(showVars)
        vString = ' '.join(showVars)

        print '   To make stats for ' + vString

        if ifNames:
            assert isinstance(ifcondition, list)
            assert len(ifNames) == len(ifcondition)

        # Choose weight and condition:
        if isinstance(ifcondition, str):
            ifcondition = [ifcondition]
        if not ifcondition == None:
            weightsif = []
            for oneifc in ifcondition:
                assert isinstance(oneifc, str)
                weightsif += [' if ' + oneifc]
        else:
            weightsif = [' ']

        for iwif, xx in enumerate(weightsif):
            if weightVar == None:
                weightsif[iwif] += ' [w=weight] '
            elif not weightVar:  # To turn off weights, just send ''
                weightsif[iwif] += ' '
            else:
                weightsif[iwif] += ' [w=' + weightVar + '] '

            # Actually, we must have weights; don't allow unweighted results.. Why? I'm reversing this. Sometimes data are macro.
            if 0:
                assert weightsif[iwif].strip()

        # Find a codebook, if available. (self.codebook can be a filename: dec 2009)
        if codebook:  # Why the foodle does this fail?.?.
            assert isinstance(codebook, stataCodebookClass)
        elif 0 and mainSurvey:  # I've converted mainSurvey into dataFile, above, so I should not consider this option first, right??
            print " SORRY!! I still don't know how to keep track well of codebook stuff based on survey name. So ignoring mainSurvey=" % mainSurvey
            #codebook=stataCodebookClass(fromPDF)
        else:
            print "Why am I creating/using a full codebook from DTA for this file, when I may have specified particular if conditions for the statistics I want? Because I want to have the descriptions for these variables, even though my specific stats table call may contain if conditions, etc... (explanation Jan 2009)"
            assert dataFile
            codebook = stataCodebookClass(
                fromDTA=dataFile,
                recreate=self.recreateCodebook,
                showVars=showVars)  # Restrict to just the desired variables..
            #elif self.codebook and isinstance(self.codebook,str):
            #    DTA=self.codebook
            if not codebook:
                foooooo
                print('   NOOO descriptive statistics for you!!!!!!!!!!!! ')
                return ('   NOOO descriptive statistics for you!!!!!!!!!!!! ')

        # Choose logfile to use (and/or read):
        # This is a bit hacked together. Names might contain redundacies...
        if dataFile:
            pp, ff = os.path.split(dataFile)
            if ff.lower().endswith('.dta.gz'):
                ff = ff[0:-4]
            else:
                dataFile += '.dta.gz'  # So that I can check its timestamp below
            if tablename and not 'pre-2013 mode':
                logfname = self.fpathname + '-summaryStatistics-' + tablename + ''
            elif tablename:
                logfname = None  # Actually, afater 2013, logfname is simply ignored
            else:
                logfname = 'summaryStatisticsFromStata_%s' % (ff.replace(
                    '.', '_'))  #%os.path.splitext(ff)[0]
                tablename = logfname
            print 'Generating automatic descriptive statistics from %s using weight/condition "%s", and variables "%s" and condition %s into logfile %s.' % (
                dataFile, str(weightsif), vString, str(ifcondition), logfname)

        else:
            print ' PRoducing STata code to generate descriptive statistics using weight/condition "%s", and variables "%s".' % (
                str(weightsif), vString)
            if not '2013 and later mode':
                logfname = self.fpathname + '-summaryStatistics-' + tablename + ''
            else:
                logfname = tablename

        # Make the Stata code
        outPrint = '\n'
        sload = ''
        if execStata:
            sload = stataLoad(dataFile)
        """ Goal here is to ensure that each variable exists before asking for a sum, and to ensure it's numeric before asking for a mean.
N.B. As for 2010Feb, I am not yet reading/using the mean calculation.
        """

        tablenamel = self.generateLongTableName(
            tablename, skipStata=False)  #skipStata)
        tableLogNameNoSuffix = defaults['paths']['stata']['tex'] + tablenamel

        tableLogName = tableLogNameNoSuffix + '.log'
        import time
        tableLogNameWithDate = defaults['paths']['stata'][
            'working'] + 'logs/' + tablenamel + time.strftime(
                '%Y_%m_%d_%H%M%S_') + '.log'

        #logfname (obselete)
        outPrint += """
            capture noisily log close
            log using %s,replace text """ % tableLogNameWithDate + """
        """ + sload
        if code:
            outPrint += code['before']
        for iowi, oneweightsif in enumerate(weightsif):
            mweightsif = oneweightsif.replace('[w=', '[pw=')
            oneifName = oneweightsif.replace('"', "'")
            if ifNames:
                oneifName = ifNames[iowi]
            outPrint += ''.join([
                """
            capture confirm variable """ + vv + """,exact
            if _rc==0 {
            di "*-=-=-=-=-=-=-=-= """ + vv + ' ' + oneifName + """"
            sum """ + vv + ' ' + oneweightsif +
                (defaults['server']['stataVersion'] == 'linux11'
                 ) * """, nowrap""" + """
            *~=~=~=~=~=~=~=~
            return list
            capture confirm numeric variable """ + vv + """,exact
            if _rc==0 {
            di "-~-~-~-~-~-~-~-~"
            mean """ + vv + ' ' + mweightsif + """
            test """ + vv + """
            }
}
*x~x~x~x~x~x~x~x~x~
            """ for vv in showVars if vv
            ])
        outPrint += """
            capture noisily log close
            copy "%s" "%s", replace
            * Succeeded / got to end.
        """ % (tableLogNameWithDate, tableLogName)

        if not execStata:
            outPrint += """

            """

            # Following section should probably be used/integrated somehow... mar2013
        #        if self.skipStataForCompletedTables and os.path.exists(tableLogName):
        #            if not skipStata:
        #                print '  Skipping Stata for %s because latex.skipStataForCompletedTables is set ON.... and this table is done.'%tablenamel
        #            outs+="""
        #            """
        #            skipStata=True

        # Call Stata if indicated
        # Parse output logfile if indicated
        """ Now... I may or may not be calling Stata below. IF I am returning Stata code OR I don't need to recreate the log file, then I won't call Stata.
        """
        #if not dataFile or (forceUpdate==False and (not fileOlderThan(tableLogName+'.log',dataFile) and 'Succeeded' in open(tableLogName+'.log','rt').read())):

        if execStata and not forceUpdate and not fileOlderThan(
                tableLogName, dataFile) and 'Succeeded' in open(tableLogName,
                                                                'rt').read():
            print '--> Using EXISTING ' + tableLogName + ' for summary stats.\n   If you want to refresh it, simply delete the file and rerun.'
        elif execStata:
            stataSystem(outPrint, filename=WP + 'do' + tablenamel)
            if not os.path.exists(tableLogName):
                print 'Seems to have failed. 023872398723!!!!'
        assert ' ' not in tableLogName
        if not execStata and not os.path.exists(tableLogName):
            print " ****  SKIPPING THE DESCRIPTIVE STATS IN %s BECAUSE YOU HAVEN'T RUN the regressions STATA YET to make it." % (
                tableLogName)

            return (outPrint)

        sfields = [
            ['N', 'N', 'N'],
            ['sum_w', '', ''],
            ['mean', 'mean', ''],
            ['Var', '', ''],
            ['sd', 'sd', ''],
            ['min', 'min', ''],
            ['max', 'max', ''],
            ['sum', '', ''],
        ]
        mfields = [
            ['mean', 'mean', ''],
            ['se', 'se', ''],
            ['cilb', 'cilb', ''],
            ['ciub', 'ciub', ''],
            ['Fchi2', '', ''],
            ['p', 'p', ''],
        ]
        sstr=r"""
.?\s*.?-=-=-=-=-=-=-=-= (\S*) ([^\n]*)
.\s+sum (\S*) ([^\n]*)(.*?)
.\s+.~=~=~=~=~=~=~=~
.\s+return list[\n]*
scalars:
"""+ '\n'.join([r'\s+r.%s. =\s+(\S*)'%ff[0] for ff in sfields]) +r'.*?\n-~-~-~-~-~-~-~-~[^~]*\|[^~]*\|\s*([^\s]*)\s+([^\s]*)\s+([^\s]*)\s+([^\s]*)\n'  +\
        r'[^~]*Prob >([\sFchi2]*)=\s*([^\s]+)\s+\}(.*?)x~x~x~x~x~x~x~x~x~'#'#(\s+.*?)~'#
        print ' ********* Above probalby needs nowrap since I added that 2010 may (same with some other nowraps..) ... ONLY IF STATA 11.'
        #stataLogFile_joinLines(tableLogName+'.log')

        # Nov 2010: Horrid kludge..... I'M SURE THIS WILL CREATE BUGS... ?. If it looks like file not already fixed (?). well, not, not conditional: Is this somehow necessary when I make this funciton produce code rather than run stata??
        stataLogFile_joinLines(tableLogName)

        if 0:  # 2012 and earlier versoin:
            fa = re.findall(
                sstr, ''.join(open(tableLogName, 'rt').readlines()), re.DOTALL)
        # 2013 new version: for speed, split up the regexp task:
        #logtxt=''.join(open(tableLogName+'.log','rt').readlines())
        vsections = re.findall('-=-=-=-=-=-=-=-=(.*?)x~x~x~x~x~x~x~x~x~',
                               ''.join(open(tableLogName, 'rt').readlines()),
                               re.DOTALL)  # Fast
        #vsections=re.split( '-=-=-=-=-=-=-=-=',''.join(open(tableLogName+'.log','rt').readlines()))[1:]

        sstr = r""" (\S*) ([^\n]*)
.\s+sum (\S*) ([^\n]*)(.*?)
.\s+.~=~=~=~=~=~=~=~
.\s+return list[\n]*
scalars:
""" + '\n'.join(
            [r'\s+r.%s. =\s+(\S*)' % ff[0] for ff in sfields]
        ) + r'.*?\n-~-~-~-~-~-~-~-~[^~]*\|[^~]*\|\s*([^\s]*)\s+([^\s]*)\s+([^\s]*)\s+([^\s]*)\n' + r'[^~]*Prob >([\sFchi2]*)=\s*([^\s]+)\s+\}'

        sstr2 = r""" (\S*) ([^\n]*)
.\s+sum (\S*) ([^\n]*)(.*?)
.\s+.~=~=~=~=~=~=~=~
.\s+return list[\n]*
scalars:
"""
        descStats2 = []
        ifOrder = []

        for vsection in vsections:

            piecesA = re.findall(sstr2 + """(.*?)\n-~-~-~-~-~-~-~-~\n(.*)""",
                                 vsection, re.DOTALL)
            if not len(piecesA) == 1:
                print("""
                      ===============================================
                      addDescriptiveStats: len(piecesA)=={} for {}
                      ABORTING ENTIRE DESCRIPTIVE STATS TABLE.
                      Most likely this will get resolved if you rerun
                      things once or twice.
                      ===============================================

""".format(len(piecesA), vsection))
                return ('')
                #assert len(piecesA)==1
            # Following is failing April2013 on a long variable.
            # meanStr=r'[^~]*\|[^~]*\|\s*([^\s]*)\s+([^\s]*)\s+([^\s]*)\s+([^\s]*)\n'  +       r'[^~]*Prob >([\sFchi2]*)=\s*([^\s]+)\s+\}'
            # Updated re string , April 2013, which doesn't fail on long var names
            meanStr2013 = '\n\s*[^ ]+\s*\|\s*([^\s]*)\s*([^\s]*)\s*([^\s]*)\s*([^\s]*)\n-*\n .*?Prob >([\sFchi2]*)=\s*([^\s]+)\s+\}'

            mDescstats = zip([mf[1] for mf in mfields],
                             re.findall(meanStr2013, piecesA[0][-1],
                                        re.DOTALL)[0])

            sStr = '\n'.join([r'\s+r.%s. =\s+(\S*)' % ff[0] for ff in sfields])

            sDescstats = zip([mf[1] for mf in sfields],
                             re.findall(sStr, piecesA[0][5])[0])
            ##re.findall(sStr,pp,re.DOTALL)

            vv = piecesA[0]

            # July 2010: I'm worried that this is not backwards compatible.. can I make it so?
            if ' if ' in vv[3]:
                ifClause = vv[3].split(' if ')[1].split(' [')[0].strip(
                )  # This was my first try: this the if clause taken straight from the Stata sum command. A nice way to do it, but if ifNames have been provided, we should really use the names here.
            else:
                ifClause = ''

            ifClause = vv[1].strip(
            )  # New June 2010: The name of the if clause is available in the log file now. I suppose I could do an idiot check here to check for changes in the correspondence between ifs and ifnames (ie in caller vs log file). Not done.
            descStats2 += [
                dict(
                    [
                        [
                            'var',
                            vv[2],
                        ],
                        ['if', ifClause],
                    ] + sDescstats + mDescstats
                    #[ [sfields[isf][1], vv[5+isf]] for isf in range(len(sfields))]
                    #[ [mfields[isf][1], vv[5+len(sfields)+isf]] for isf in range(len(mfields)) ]
                )
            ]
            if 0:
                assert vv[5 + len(sfields) + len(mfields)] == '\n }\n\n*'
            ifOrder += [ifClause]
        ifOrder = uniqueInOrder(ifOrder)

        if not vsections:  # not fa and 
            print 'SUMMARY STATISTICS *****failed ************* regexp found nothing .... ', tableLogName
            # Maybe there was an error in the log file... ie log file shouldn't be copied over unless successful...
            fooo
        ## descStats={}
        ## for vv in fa:
        ##     if vv[0] in descStats:
        ##         continue # OBSELETE. descStats fails with multiple ifs.
        ##     descStats[vv[0]]={}
        ##     for isf in range(len(sfields)):
        ##         descStats[vv[0]][sfields[isf][1]] = vv[3+isf]

        ## # Above fails if more than on if condition. June 2010
        ## del descStats
        if 0:
            descStats2 = []
            ifOrder = []
            for vv in fa:
                # July 2010: I'm worried that this is not backwards compatible.. can I make it so?
                if ' if ' in vv[3]:
                    ifClause = vv[3].split(' if ')[1].split(' [')[0].strip(
                    )  # This was my first try: this the if clause taken straight from the Stata sum command. A nice way to do it, but if ifNames have been provided, we should really use the names here.
                else:
                    ifClause = ''

                ifClause = vv[1].strip(
                )  # New June 2010: The name of the if clause is available in the log file now. I suppose I could do an idiot check here to check for changes in the correspondence between ifs and ifnames (ie in caller vs log file). Not done.
                descStats2+=[dict([['var',vv[2],],
                             ['if',ifClause],
                             ]+[ [sfields[isf][1], vv[5+isf]] for isf in range(len(sfields))] +\
                                  [ [mfields[isf][1], vv[5+len(sfields)+isf]] for isf in range(len(mfields)) ]
                                      )]
                assert vv[5 + len(sfields) + len(mfields)] == '\n }\n\n*'
                ifOrder += [ifClause]
            ifOrder = uniqueInOrder(ifOrder)

        # Check that we found all we were looking for? If we are supposed to make the log file as a standalone right here, and we aren't forced to remake it, then we *may not* have made it freshly, in which case it may be stale. If it might be stale (is missing some vars), offer to delete it.
        notFound = [
            vv for vv in showVars
            if vv not in [dsv['var'] for dsv in descStats2]
        ]
        if notFound and execStata and not forceUpdate:
            if 'yes' == raw_input(
                    '  ---> Some variables (%s) not found in the summary statistics log file. Shall I delete so it will be recreated next time? ([no]/yes)'
                    % str(uniqueInOrder(notFound))):
                os.remove(tableLogName)
        elif notFound:
            print ' UN-FINISHED WARNING HERE!.... NEEDS DEVELOPMENT. SOME VARIABLES NOT FOUND IN LOG FILE: ', notFound

        # Now a bit of a kludge. If we have codebook info, we want it. BUT our means may not be totally general. So let's make a deep copy of the codebook, if there is one, and put the descStats into it.

        # June 2010: Further kludge. for multiple conditions, just update the codebook for each one, in turn. Order of conditions not yet fixed.
        if not codebook:
            codebook = stataCodebookClass()
        from cpblUtilities.dictTrees import dictTree
        byIf = dictTree(descStats2, ['if', 'var'])

        if ifcondition == None:
            ifcondition = []
        print "Got %d sumstats from %s for %d requested variables for %d conditions." % (
            len(descStats2[0].keys()) - 2, tableLogName, len(showVars),
            len(ifcondition))

        if ifNames and len(ifcondition) > 1:
            assert ifOrder == ifNames
            print '  -------> I am going to create a CSV which combines a bunch of ifconditions for the descriptive stats! (' + str(
                ifNames) + ') '
            allIfsCSV = ''

        for iIf, anifcond in enumerate(ifOrder):  #byIf.keys()):
            codebookT = deepcopy(codebook)
            for vv in byIf[anifcond]:
                codebookT[vv] = codebookT.get(vv, {})
                codebookT[vv]['sumstats'] = byIf[anifcond][vv][
                    0]  #ds2#escStats2[vv]

            # Now generate a table with these data.
            comments = 'If some variables have missing values, try deleting %s.' % str2latex(
                tableLogNameNoSuffix) + caption
            if os.path.exists(tableLogNameNoSuffix + '.tex'):
                import time
                statsDate = time.ctime(
                    os.path.getmtime(tableLogNameNoSuffix + '.tex'))
                comments += ' Stats carried out on ' + statsDate

            if ifcondition:
                comments += ' Samples here were taken with the following condition: "' + str2latex(
                    anifcond) + '"'  #ifcondition)+'"'
            codebookT.summaryStatisticsTable_singleSurvey(
                texFilename=tableLogNameNoSuffix + '-%d.tex' % iIf,
                latex=self,
                showVars=showVars,
                comments=comments,
                substitutions=substitutions)
            # 2010 Jun: Also create a .csv file *from* the .tex.
            ###            from cpblUtilities import cpblTableToCSV
            fout = open(tableLogNameNoSuffix + '-%d.csv' % iIf, 'wt')
            tmpCSV = tableToTSV(tableLogNameNoSuffix + '-%d.tex' % iIf)
            fout.write(tmpCSV)
            fout.close()
            if ifNames and len(ifcondition) > 1:
                allIfsCSV += '\n\n' + anifcond + '\n\n' + tmpCSV

            # So in June 2010 I used a sequence of these in csv format to concatenate a series of tables with different ifconditions.: See regressionsAknin... Actually, let's do it here..
        if ifNames and len(ifcondition) > 1:
            fout = open(tableLogNameNoSuffix + '-all.csv', 'wt')
            fout.write(allIfsCSV)
            fout.close()

        # Actually, I may want a different kind of table: May 2011. This just compares the means for the different conditions. Codebook stuff not necessary.
        if mode == 'compareMeans':
            assert ifcondition
            assert len(ifcondition) == 2
            comments = 'If some variables have missing values, try deleting %s.' % str2latex(
                tableLogName) + caption
            if os.path.exists(tableLogNameNoSuffix + '.tex'):
                import time
                statsDate = time.ctime(
                    os.path.getmtime(tableLogNameNoSuffix + '.tex'))
                comments += ' Stats carried out on ' + statsDate

            headers = ['Variable', ifNames[0], ifNames[1], r'$p$(equal)']
            body = []
            from dictTrees import dictTree
            statst = dictTree(tonumeric(descStats2),
                              ['var', 'if']).singletLeavesAsDicts()
            for vvv in showVars:
                tE = statst[vvv][ifNames[0]]
                xs1, ses1 = latexFormatEstimateWithPvalue(
                    [tE['mean'], tE['se']],
                    pval=tE['p'],
                    allowZeroSE=None,
                    tstat=False,
                    gray=False,
                    convertStrings=True,
                    threeSigDigs=None)
                tE = statst[vvv][ifNames[1]]
                xs2, ses2 = latexFormatEstimateWithPvalue(
                    [tE['mean'], tE['se']],
                    pval=tE['p'],
                    allowZeroSE=None,
                    tstat=False,
                    gray=False,
                    convertStrings=True,
                    threeSigDigs=None)
                body += [
                    [vvv, xs1, xs2, '?'],
                    ['', ses1, ses2, ''],
                ]
            cpblTableStyC(
                cpblTableElements(
                    body='\\\\ \n'.join(['&'.join(LL) for LL in body]) +
                    '\\\\ \n\\cline{1-\\ctNtabCols}\n ',
                    format=None,
                    firstPageHeader=' & '.join(headers) +
                    '\\\\ \n\\hline\\hline\n',
                    otherPageHeader=None,
                    tableTitle=None,
                    caption=None,
                    label=None,
                    ncols=None,
                    nrows=None,
                    footer=None,
                    tableName=None,
                    landscape=None),
                filepath=tableLogNameNoSuffix + '-compareMeans-' +
                str2pathname('-'.join(ifNames)) + '.tex',
                masterLatexFile=self)

            ## # 2010 Jun: Also create a .csv file *from* the .tex.
            ## from cpblUtilities import cpblTableToCSV
            ## fout=open(tableLogName+'-%d.csv'%iIf,'wt')
            ## tmpCSV=cpblTableToCSV(tableLogName+'-%d.tex'%iIf)
            ## fout.write(  tmpCSV)
            ## fout.close()
            ## if ifNames and len(ifcondition)>1:
            ##     allIfsCSV+='\n\n'+anifcond+'\n\n'+tmpCSV

        # And return the stata code if needed.
        if execStata:  # Stata was called, above, if needed, ie the stata executable code has already been used.
            return ()  #descStats)
        else:  # We will run this later, when doing regressions...
            return (outPrint)  #,descStats)

    ################################################################

    def closeAndCompile(self,
                        launch=True,
                        closeOnly=False,
                        compileOnly=False,
                        showStatsFor=None,
                        statsCondition=None,
                        noStats=False):  # ,dataFile=None
        """
        Dec 2009: New argument, DTA, allows specification of a stata file which can be used to produce means, etc. for the variables that have been used. So this is most useful when all the regressions are from the same dataset????
        Well, for now this will use addDescriptiveStatistics, a new member function that I guess will look like the one already written for my codebook class??

To make this produce a table, ust use latexfile.updateSettings ... Can no longer specify a DTA file above.


When outside RDC, use noStats=True to skip the descriptive statistics.
What is "launch"? It seems not used.
        """
        if statsCondition == None:
            statsCondition = ' 1 '

        # Add a table of descriptive statistics, if it makes any sense:
        if not compileOnly and not noStats:
            if self.codebook:  # and isinstance(self.codebook,stataCodebookClass):
                self.addDescriptiveStatistics(
                    codebook=self.codebook,
                    logname='end',
                    showVars=showStatsFor,
                    ifcondition=statsCondition)
            #elif self.codebook and isinstance(self.codebook,str):
            #    self.addDescriptiveStatistics(DTA=DTA,logname='end')
            elif self.mainDataFile:
                self.addDescriptiveStatistics(
                    dataFile=self.mainDataFile,
                    logname='end',
                    showVars=showStatsFor,
                    ifcondition=statsCondition)
            else:
                #not DTA and not compileOnly and not self.mainDataFile:
                print ' * SUGGESTION: closeAndCompile: Why have you not specified a codebook or DTA to generate a codebook, so as to get means of the variables used?'
        if self.lfileTeXbody == '':  # obselete: or   (self.lfileTeX==self.lfileTeX_original): # part following or is old /junk
            print 'There is no LaTeX code accumulated to compile'
            return (self.fpathname + '.tex')
        if not compileOnly:
            lfile = open(self.fpathname + '.tex', 'wt', encoding='utf-8')
            lfile.write(self.lfileTeXwrapper[0] + self.lfileTeXbody +
                        self.lfileTeXwrapper[
                            1])  # Write entire, accumulated contents of file.
            lfile.close()
            print 'Completing LaTeX file %s...' % (self.fpathname + '.tex')
        #  And compile the latex output:

        # Freakin' windows can't do an atomic rename when target exists... So first line is necessary for MS only
        #if os.access(defaults['paths']['tex']+'tables-allCR.tex',os.F_OK):
        #    os.remove(defaults['paths']['tex']+'tables-allCR.tex')

        # And now compile the LaTeX:
        if not closeOnly:
            from cpblUtilities import doSystemLatex
            ##doSystemLatex(self.fname,latexPath=None,launch=launch)
            doSystemLatex(
                self.fname
            )  #launch=launch,tex=None,viewLatestSuccess=True,bgCompile=True)
        return (self.fpathname + '.tex')

    ###########################################################################################
    ###
    def getTeXcode(self):
        ###
        #######################################################################################
        return (self.lfileTeXbody)

    ###########################################################################################
    ###
    def addCorrelationTable(self,
                            tablename,
                            corrvars,
                            ifClause=None,
                            threeSigDigs=False,
                            showSignificance=True,
                            variableOrder=None,
                            comments=None):
        ###
        #######################################################################################
        """
        2010 Nov. 

        Interface to mkcorr, which produces a tabular output of pairwise correlations.
        So, the output here is in a designated file, not logged to Stata stdout.
        mkcorr also logs descriptive stats! so I could use this as yet another way to make a descriptive stats table....

        Works nicely. Test case by running this module/file.

Here are other options for correlation tables: [Damn; I bet ?I could have used the matrix one and my readmatrix function]

Publication-style correlation matrix (corrtab):
findit corrtab
help corrtab
corrtab read write math science, obs sig bonf vsort(read) format(%9.2f)
corrtab read write math science, cwd obs sig bonf vsort(read) format(%9.2f)
corrtab read write math science, spearman obs sig bonf vsort(read) format(%9.2f)
Note: pairwise (the equivalent of pwcorr in Stata) is the default unless cwd
(casewise, equivalent to corr in Stata) is not specified. Spearman may also be
specified. corrtab is designed for a maximum of eight variables.

Publication-style correlation matrix (makematrix) :
findit makematrix
help makematrix
makematrix, from(r(rho)) format(%9.2f): corr read-socst
makematrix, from(r(rho)) col(socst) format(%9.2f): corr read-socst


Jan 2011: Huh? But there is no "N" recorded in the log file for each correlation...

        """
        tablenamel = self.generateLongTableName(tablename)

        tableLogName = defaults['paths']['stata']['tex'] + str2pathname(
            tablenamel) + '.log'  # Actually, a TSV file
        tableFilePath = defaults['paths']['stata']['tex'] + str2pathname(
            tablenamel)  # for .tex , below

        assert ifClause is None

        if os.path.exists(tableLogName):
            #cells=tsvToDict(tableLogName)
            cells = [
                LL.strip('\n').split('\t')
                for LL in open(tableLogName, 'rt').readlines()
            ]
            assert cells[0][
                -1] == ''  # Bug in Stata's mkcorr? extra column. arghhhh
            header = cells[0][:-1]
            varsOrder = header[5:]  # 1:5 are mean, s.d., min, max.
            np = (len(cells) - 1) / 2
            assert np == len(varsOrder)
            pcorrs = {}
            for iv, vva in enumerate(varsOrder):
                for jv, vvb in enumerate(
                        varsOrder[:1 + iv]):  # Skip upper right hand triangle 
                    pcorrs[vva] = pcorrs.get(vva, {})
                    pcorrs[vvb] = pcorrs.get(vvb, {})
                    r, p = cells[iv * 2 + 1][jv + 5], cells[iv * 2 + 2][jv + 5]
                    from cpblUtilities import NaN
                    fp = NaN
                    if p.startswith('('):
                        if p == '(0.00000)':
                            p = r'{\coefpSmall{$<$10$^{-5}$}}'
                            fp = 0.00001
                        elif p == '(1.00000)':
                            p = 1
                            fp = NaN
                        else:
                            fp = float(p[1:-1])
                            p = chooseSFormat(
                                p[1:-1],
                                convertStrings=True,
                                threeSigDigs=threeSigDigs,
                                conditionalWrapper=[r'\coefp{', '}']
                            )  #,lowCutoff=None,lowCutoffOOM=True,convertStrings=False,highCutoff=1e6,noTeX=False,threeSigDigs=False,se=None):
                    else:
                        assert p in ['']
                    # Following plan fails if I want to be able to manipulate order of variables later:
                    #if r=='1.00000': # Since using upper right triangle, rather than lower left, can hide diagonal here.
                    #    r=''
                    r = chooseSFormat(
                        r, convertStrings=True, threeSigDigs=threeSigDigs)
                    if p and showSignificance:
                        significanceString = ([' '] + [
                            tt[0] for tt in significanceTable
                            if fp <= tt[2] / 100.0
                        ])[-1]
                        r = significanceString + r + '}' * (
                            not not significanceString)

                    pcorrs[vva][vvb] = dict(b=r, p=p)
                    # Must have symmetric matrix if I am able to change order of variables...dict(b='',p='') # This hides lower left triangle. If you did these the opposite way around, it would hide diagonal AND upper right triangle. 
                    pcorrs[vvb][vva] = dict(b=r, p=p)
                    debugprint(vva, vvb, iv, jv, '---------', pcorrs[vva][vvb])

            # NOW PRODUCE OUTPUT TABLE
            # I'll have to revise this a bunch if I want to put the descriptive statistics back in.
            if variableOrder:
                varsOrder = orderListByRule(varsOrder, variableOrder)

            body = ''
            # I want values show in top left triangle, so first var in varsOrder has easiest to read corrs.
            for iv, vv in enumerate(varsOrder[:-1]):
                assert '#' not in vv
                tworows = formatPairedRow([[
                    r'\sltrheadername{%s}' % str2latex(
                        substitutedNames(vv, self.substitutions))
                ] + [
                    pcorrs[vv][vvb]['b'] * (ivvb >= iv)
                    for ivvb, vvb in enumerate(varsOrder[1:])
                ], [''] + [
                    pcorrs[vv][vvb]['p'] * (ivvb >= iv)
                    for ivvb, vvb in enumerate(varsOrder[1:])
                ]])

                body+= '\t& '.join([cc for cc in tworows[0]])+'\\\\ \n'+r'\showSEs{'+\
                                '\t& '.join([cc for cc in tworows[1]]) +' \\\\ }{}\n'
            body += r'\hline ' + '\n'  # Separate the coefs from extralines..
            headersLine = '\t&'.join([''] + [
                r'\begin{sideways}\sltcheadername{%s}\end{sideways}'
                % substitutedNames(vv, self.substitutions)
                for vv in varsOrder[1:]
            ]) + '\\\\ \n' + r'\hline'
            comments = [comments, ''][int(comments is None)]
            includeTeX, callerTeX = cpblTableStyC(
                cpblTableElements(
                    body=body,
                    cformat='c' * (len(varsOrder) + 2),
                    firstPageHeader=r'\ctSubsequentHeaders \hline ',
                    otherPageHeader=headersLine,
                    tableTitle=None,
                    caption=r'[Correlations among key variables]{Correlations among key variables. '
                    + comments + '}',
                    label='tab:Correlations',
                    ncols=None,
                    nrows=None,
                    footer=None,
                    tableName=tablename,
                    landscape=None),
                filepath=tableFilePath)

            # Should I have just written a composeLatexOtherTable() for above?

            #if transposedChoice:
            #    tableFilePath=tableFilePath+'-transposed'
            fout = open(tableFilePath + '.tex', 'wt', encoding='utf-8')
            fout.write(includeTeX)
            fout.close()
            # 2010 Jan: Also create a .csv file *from* the .tex.
            ###from cpblUtilities import cpblTableToCSV
            fout = open(tableFilePath + '-tex.csv', 'wt')
            fout.write(tableToTSV(includeTeX))
            fout.close()

            self.append(r'\newpage  ' + callerTeX.replace(
                'PUT-TABLETEX-FILEPATH-HERE',
                tableFilePath.replace(defaults['paths']['tex'], r'\texdocs '))
                        + '\n\n')

        return ("""
        * BEGIN mkcorr: produce a correlation table in output/TSV format.
        mkcorr %s,log(%s) sig cdec(5) replace means
        * END mkcorr
        """ % (corrvars, tableLogName))

    ###########################################################################################
    ###
    def writeMultiSurveyCodebookTable(self,
                                      surveys,
                                      vars=None,
                                      findAllCommonVars=False,
                                      tablename='tmpxxx',
                                      maxVars=1e6):
        ###
        #######################################################################################
        """
        May 2011. Sorry if this already exists somewhow.

        So, it's easy to add more kinds of output to this. Just make many.
         For instance, I want to make one with means in place of check marks.

        findAllCommonVars: a special mode, alternative to specifying a subset of vars  explicitly. ... not done yet.

        If all vars allowed, let's just sort them by (a) how many surveys they're in, and (b) alphabet. [(b) not done]
        """
        # Load up surveys
        cb = {}
        vvs = []
        for survey in surveys:
            cb[survey] = stataCodebookClass(survey=survey)
            for vv in cb[survey]:
                cb[survey][vv].update(dict(survey=survey, vv=vv))
                vvs += [cb[survey][vv]]
        # So, thanks to labelling each entry with survey, I can reorder:
        from dictTrees import dictTree
        byVV = dictTree(vvs, ['vv', 'survey'])
        vvk = byVV.keys()
        # Sort by number of surveys that include the variable
        vvk.sort(reverse=True, key=lambda x: len(byVV[x]))
        # Sort by whether it's derived or raw variable
        vvk.sort(
            reverse=True, key=lambda x: 'rawname' in byVV[x].values()[0][0])
        if 0 and len(vvk) > maxVars:
            vvk = vvk[:maxVars]
        from cpblUtilities import cpblTableStyC

        tablenamel = self.generateLongTableName(tablename)

        tableLogName = defaults['paths']['stata']['tex'] + str2pathname(
            tablenamel) + '.log'  # Actually, a TSV file
        tableFilePath = defaults['paths']['stata']['tex'] + str2pathname(
            tablenamel)  # for .tex , below

        cpblTableStyC(
            cpblTableElements(
                body='\n'.join([
                    str2latex(avv.replace('_', '-')) + '\t& ' + '\t& '.join([
                        r'$\checkmark$' * (asurvey in byVV[avv])
                        for asurvey in surveys
                    ]) + r'\\' for avv in vvk
                ]),
                cformat=None,
                firstPageHeader=' & '.join([''] + surveys) + r'\\',
                otherPageHeader=None,
                tableTitle=None,
                caption=None,
                label=None,
                ncols=len(surveys) + 1,
                nrows=len(vvk),
                footer=None,
                tableName=tablename,
                landscape=None),
            filepath=paths['tex'] + str2pathname(tablename) + '.tex',
            masterLatexFile=self)

        return ()

    ###########################################################################################
    ###
    def semiRollingRegression(self,
                              statamodel=None,
                              rollingCovariates=None,
                              rollingX=None,
                              ordinalRollingX=None,
                              tablename=None,
                              variableOrder=None,
                              rollCovColourLookup=None,
                              includeConstant=True,
                              showConstant=True,
                              suppressFromPlot=None,
                              nSegments=None,
                              alsoDoFullyPiecewise=True,
                              weight=None):
        ###
        #######################################################################################
        """
    Sample usage:
        stataout=stata.doHeader+stata.stataLoad(WP+'usavignettes')
        outdict=latex.semiRollingRegression(statamodel='reg Answer '+' '.join(nonrollingvars),rollingCovariates=['VLNINC'], rollingX='VLNINC',ordinalRollingX=None,tablename='rollingtest',variableOrder=None,rollCovColourLookup=None,includeConstant=True,suppressFromPlot=None,nSegments=5,alsoDoFullyPiecewise=True,weight=None)
        stataout+=outdict['statatext']

        That is, I often use the same variable as the rollingCovariate and the rollingX.

   N.B.        Return value is a dict:         return({'statatext':outStata,'models':lmodels,'figures':figs})

    statamodel: This is a Stata regression call, but with the rollingCovariates variables missing from the call.. They will be added in.

    rollingCovariates: a list of variable names:     # These are the covariates of SWBs whose coefficients we may want to estimate as a function of xrollings. You now have the option of setting these in a flag for each model (e.g. via the Stata source format), rather than globally as a parameter. I hesitate to add this feature, since it makes things more complex...

    rollingX: the rolling variable. The sample is split into sections based on an ordinal version of this. This is the variable that should appear on the abscissa in the plot.

    ordinalRollingX: 
    For now, let's assume that an ordinalRollingX exists, and the data are loaded. ie an ordinal version of the rolling variable, rollingX, exists.
    [may 2012: meaning I have to supply both rollingX and ordinalRollingX??  I've now tried to make it create one if it's not given. But not tested properly yet.]

    variableOrder: need not include the rollingCovariates, of course.

    rollCovColourLookup=a dict that gives a plotting color for each rollingCovariate

    showConstant=True: set this to False to suppress the constant in the plot that's created.

    TO DO:  There should


    Constants.:
      . do i need constants for each quantile too?
    Constants: It's now an optional argument. One basically always needs to include "nocons" as an option to your regression call, but I'm not enforcing this (.). If you don't set includeConstant=False and provide your own, this function will generate one per segment and include its constant in the rollingCovariates.

    Oct 2011: Oh. I cannot use beta with this, as it will normalize across the divisions in a very weird way. Well... actually, there should be the same number of respondents, roughly, in each. But certainly using constants with nSegments>1 and beta gives garbage / nonsense...
     So if you want to calculate betas, you should do a series of separate regressions. [oct 2011]

May 2012: Great idea is to Add in the option to also do fully-piecewise/full-rolling (not semi-rolling) regression, as a robustness test. I seem to have written this "rollingRegression" in pystata. It's not yet integrated into pystataLatex.  Do so...
    
        """
        DVNN = 'dependent var, its name'

        #assert not weight is None # Until 2015, you need to specify weight is False or give a weight, since this started out assuming a weight.

        outStata = ''
        xrollings = [
            ['lnGDPpc', 'gdprank'],  # country mean income
            [
                'lnadjHHincome', 'tgrank'
            ],  # absolute own income (log or not are same if get rid of zeros?)
            ['gwp_rankAdjHHincome', 'crank'],  # Rank within own country
            [
                'grank', 'grank'
            ],  # rank in globe.  ..BUt there's no difference between grank and tgrank.?
        ][1:2]

        # Start by processing the statamodel commands, in case we need to check it to determine rollingCovariates.
        dummyLatex = latexRegressionFile('dummyLRF')
        dummymodels = dummyLatex.str2models(statamodel)
        if suppressFromPlot is None:
            suppressFromPlot = []
        if showConstant is False:
            suppressFromPlot += ['qconstant']

        # Determine rollingCovariates:
        allRollingCovariates = [
            xx
            for xx in flattenList(
                [
                    dgetget(mm, ['flags', 'rollingCovariates'], '').split(' ')
                    for mm in dummymodels
                ],
                unique=True) if xx
        ]  # List of all covariates in flags.
        assert rollingCovariates is None or not any(allRollingCovariates)
        assert rollingCovariates is not None or all([
            dgetget(mm, ['flags', 'rollingCovariates'], '')
            for mm in dummymodels
        ])
        if rollingCovariates is not None:
            allRollingCovariates = rollingCovariates
            assert isinstance(allRollingCovariates,
                              list)  # this should be earlier..
        # Determine kernel width (well, number of segments): (uh, well, I am not allowing this to be set per model by flag, yet. So just use the function parameter):
        if nSegments is None:
            nSegments = 10
        leftlim = arange(0, 1.0 + 1.0 / nSegments, 1.0 / nSegments)

        # # rollingCovariates=['lnadjHHincome','gwp_rankAdjHHincome','dZeroishIncome','grank'] #'lnGDPpc',
        covRollingNames = {}
        outModel = includeConstant * """
        capture noisily drop qconstant
        gen qconstant=1
        """
        if rollingX is not None and ordinalRollingX is None:
            outModel += """
            * We'll need to know quantiles of the x rolling variable:
            capture noisily drop tmpOrd%(rx)s
            capture noisily drop _ord%(rx)s
egen tmpOrd%(rx)s=rank(%(rx)s)
sum tmpOrd%(rx)s
gen _ord%(rx)s=(tmpOrd%(rx)s-r(min))/(r(max)-r(min))
""" % {
                'rx': rollingX
            }
            ordinalRollingX = '_ord' + rollingX
        ifs = [
            ' %s >= %f & %s < %f ' %
            (ordinalRollingX, leftlim[iL], ordinalRollingX, leftlim[iL + 1])
            for iL in range(len(leftlim) - 1)
        ]

        print 'There are %d ifs for ns=%d' % (len(ifs), nSegments)
        for yrolling in allRollingCovariates + includeConstant * [
                'qconstant'
        ]:  # Prepare each of the rolling independent variables by making piecewise versions of them.
            covRollingNames[yrolling] = []
            # Create a series of dummies
            assert len(leftlim) < 100
            outModel += """
            * Let's recreate these
            capture noisily drop  """ + yrolling + '_q*' + """
            """
            for iL in range(len(leftlim) - 1):
                outModel += """
                gen """ + yrolling + '_q%02d%02d' % (
                    iL, len(leftlim) - 1
                ) + ' = ' + yrolling + ' * (' + ifs[iL] + """)
                """
                covRollingNames[yrolling].append(yrolling + '_q%02d%02d' % (
                    iL, len(leftlim) - 1))
                #covRollingNames.get(yrolling,'')+' '+yrolling+'_q%02d%02d'%(iL,len(leftlim)-1))+' '
            #yRollingNames.sort()
        allRollingCovNames = flattenList(
            covRollingNames.values()
        )  # So this is just a list of all the _q variables names, in order passed.
        models = []
        #  I think I should do the betas in a fully-segmented regressions, not the partial-rolling. Otherwise the normalisation is weird, no? Or just multiply all the betas by 10?
        lmodels = self.str2models(
            outModel + """
        """ + statamodel + """
        """,
            before="loadData"
        )  # CAREFUL: is there somethign othe than load data I can say here?..?

        # Add in the rolling covariates, the versions with piecewise nonzero values:
        for mmm in lmodels:
            if rollingCovariates is None:  # I will probably just make it so flags always get set, above.
                mmm['model'] = ' ' + ' '.join(
                    flattenList([
                        covRollingNames[vvv]
                        for vvv in dgetget(mmm, [
                            'flags', 'rollingCovariates'
                        ], ' ').split(' ') + includeConstant * ['qconstant']
                    ])) + ' ' + mmm['model']
            else:
                mmm['model'] = ' ' + ' '.join(
                    allRollingCovNames) + ' ' + mmm['model']
            # So the following ifs are in terms of ordinalRollingX, but the means are of rollingX:
            mmm['code']['sumsAfter'] = generate_postEstimate_sums_by_condition(
                rollingX, ifs)  #'tgrank crank'

        outStata += self.regTable(
            tablename,
            lmodels,
            returnModels=True,
            variableOrder=(variableOrder if variableOrder is not None else [])
            + allRollingCovNames,
            transposed=False,
            comments=r"""
        Rolling $x$ (quantile) variable: %s%s in %d segments.
        """ % (rollingX, (not rollingX == ordinalRollingX) *
               (' (%s)' % ordinalRollingX), nSegments))

        # What if "beta" was used in the regression call?
        combineVars = [[avvv, 'z_' + avvv] for avvv in allRollingCovNames]

        if rollCovColourLookup is None:  # Then assign it automagically? Using rainbow?
            ccc = getIndexedColormap(None, len(rollingCovariates))
            rollCovColourLookup = dict(
                [[avvv, ccc[ia]] for ia, avvv in enumerate(rollingCovariates)])

        if includeConstant and 'qconstant' not in rollCovColourLookup:
            rollCovColourLookup['qconstant'] = 'k'

        if alsoDoFullyPiecewise:
            pass

        # Now plot them?
        sef = 1.96
        plt.close('all')
        figs = []
        for ifigure, mm in enumerate(lmodels):
            if 'estcoefs' not in mm:
                continue
            # Oh, this is ugly. why is beta not a 'special' flag or etc?
            if '$\\beta$ coefs' in mm['textralines']:
                mm['flags']['beta'] = True
                print 'implement a beta flag in regtable *********** TO DO (to clean up)'
                NoWay_CANNOT_DO_BETA_WITH_ROLLING_
            # Find the x-values of the xrolling variable, corresponding to the if groups.
            ifs = sorted(mm['subSums'].keys())
            mm['x' + rollingX] = array(
                [mm['subSums'][anif][rollingX]['mean'] for anif in ifs])
            mm['xstep' + rollingX] = array([
                xx
                for xx in flatten([leftlim[0]] + [[xx, xx] for xx in leftlim[
                    1:-1]] + [leftlim[-1]])
            ])

            mm['xstep' + rollingX] = array([
                ii
                for ii in flatten([[
                    mm['subSums'][anif][rollingX]['min'],
                    mm['subSums'][anif][rollingX]['max']
                ] for anif in ifs])
            ])

            #mm['xstep'+rollingX]=array(flattenList([leftlim[0]]+ [[xx,xx] for xx in leftlim[1:-1]] , leftlim[-1]]))
            mm['sex' + rollingX] = array(
                [mm['subSums'][anif][rollingX]['seMean'] for anif in ifs])

            plt.figure(120 + ifigure)
            plt.clf()
            ax = plt.subplot(111)
            figs += [plt.gcf()]
            #  And extract the coefficients determined for this SWB measure and this xrolling variable:
            for icv, cvv in enumerate([
                    vvv
                    for vvv in allRollingCovariates + includeConstant *
                ['qconstant']
                    if vvv not in suppressFromPlot and any([
                        vv for vv in mm['estcoefs'].keys()
                        if vv.startswith(vvv)
                    ])
            ]):
                # for ixv,xv in enumerate(mm['subSums'][ifs[0]].keys()):
                cvvn = substitutedNames(cvv)
                cvvs = sorted(
                    [vvv for vvv in mm['estcoefs'] if vvv.startswith(cvv)])
                # No. Above is dangerous. It means that some might be missing. Let's force it to be what we expect. Oh, but this will cause trouble if the Stata log is out of date? too bad. Use NaNs:
                cvvs = covRollingNames[cvv]
                if not len(ifs) == len(cvvs):  # Need to re-run Stata..
                    continue
                assert len(ifs) == len(cvvs)
                if 0:
                    mm['b' + cvv] = array(
                        [mm['estcoefs'][vv]['b'] for vv in cvvs])
                    mm['bstep' + cvv] = array(
                        flattenList([[
                            mm['estcoefs'][vv]['b'], mm['estcoefs'][vv]['b']
                        ] for vv in cvvs]))
                    mm['sebstep' + cvv] = array(
                        flattenList([[
                            mm['estcoefs'][vv]['se'], mm['estcoefs'][vv]['se']
                        ] for vv in cvvs]))
                    mm['seb' + cvv] = array(
                        [mm['estcoefs'][vv]['se'] for vv in cvvs])

                mm['b' + cvv] = array(
                    [dgetget(mm, ['estcoefs', vv, 'b'], NaN) for vv in cvvs])
                mm['bstep' + cvv] = array(
                    flattenList([
                        [
                            dgetget(mm, ['estcoefs', vv, 'b'], NaN), dgetget(
                                mm, ['estcoefs', vv, 'b'], NaN)
                        ] for vv in cvvs
                    ]))  #mm['estcoefs'][vv]['b'],mm['estcoefs'][vv]['b']
                mm['se_bstep' + cvv] = array(
                    flattenList([[
                        dgetget(mm, ['estcoefs', vv, 'se'], NaN), dgetget(
                            mm, ['estcoefs', vv, 'se'], NaN)
                    ] for vv in cvvs]))
                mm['se_b' + cvv] = array(
                    [dgetget(mm, ['estcoefs', vv, 'se'], NaN) for vv in cvvs])

                df = pd.DataFrame(
                    dict([[avn, mm[avn]]
                          for avn in ['x' + rollingX, 'b' + cvv, 'se_b' + cvv]
                          ]))
                # Above should really be merged across covariates... etc

                print('Plotting %s now with envelope...?' % cvv)
                dfPlotWithEnvelope(
                    df,
                    'x' + rollingX,
                    'b' + cvv,
                    color=rollCovColourLookup[cvv],
                    label=cvvn,
                    labelson='patch',
                    ax=ax)

                #                plotWithEnvelope(mm['x'+rollingX], mm['b'+cvv],mm['b'+cvv]-sef*mm['seb'+cvv],mm['b'+cvv]+sef*mm['seb'+cvv],linestyle='-',linecolor=rollCovColourLookup[cvv],facecolor=rollCovColourLookup[cvv],lineLabel=cvvn,     laxSkipNaNsXY=True)
                if 0:  #for 
                    plotWithEnvelope(
                        mm['xstep' + rollingX],
                        mm['bstep' + cvv],
                        mm['bstep' + cvv] - sef * mm['sebstep' + cvv],
                        mm['bstep' + cvv] + sef * mm['sebstep' + cvv],
                        linestyle='--',
                        linecolor=rollCovColourLookup[cvv],
                        facecolor=rollCovColourLookup[cvv],
                        lineLabel=cvvn)

                #x,y,yLow,yHigh,linestyle='-',linecolor=None,facecolor=None,alpha=0.5,label=None,lineLabel=None,patchLabel=None,laxSkipNaNsSE=False,laxSkipNaNsXY=False,skipZeroSE=False,ax=None,laxFail=True):

                #envelopePatch=plt.fill_between(mm['x'+ordinalRollingX],mm['b'+cvv]-sef*mm['seb'+cvv],mm['b'+cvv]+sef*mm['seb'+cvv],facecolor=qColours[icv],alpha=.5)#,linewidth=0,label=patchLabel)# edgecolor=None, does not work.. So use line
                #plt.plot(mm['x'+ordinalRollingX],mm['b'+cvv],linestyle=qColours[icv]+'.-',label=cvv)#'resid'+' loess fit'+resid)
                # yerr=sef*mm['seb'+cvv],
                # If aborted above loop due to Stata needing to be re-run:
            plt.xlabel(substitutedNames(rollingX))
            plt.ylabel('Raw coefficients (for %s)' %
                       substitutedNames(mm['depvar']))
            if 'beta' in mm.get('flags', []):
                plt.ylabel(r'Standardized $\beta$ coefficients (for %s)' %
                           mm['depvar'])
                NoWay_CANNOT_DO_BETA_WITH_ROLLING_
            plt.plot(plt.xlim(), [0, 0], 'k:', zorder=-100)
            # This should be removed.. Not general. Can return figs, so no need to do this here.
            if 'lnGDPpc' in mm['estcoefs']:
                y, yse = mm['estcoefs']['lnGDPpc']['b'], mm['estcoefs'][
                    'lnGDPpc']['se']
                plotWithEnvelope(
                    plt.xlim(), [y, y], [y - sef * yse, y - sef * yse],
                    [y + sef * yse, y + sef * yse],
                    linestyle='-',
                    linecolor='k',
                    facecolor='k',
                    lineLabel=substitutedNames('lnGDPpc'))
                plt.text(plt.xlim()[1], y, r'$b_{\log(GDP/cap)}$')

            comments = r'$b_{\log(GDP/cap)}=%.02f\pm%.02f$' % (
                mm['estcoefs']['lnGDPpc']['b'], mm['estcoefs']['lnGDPpc']['se']
            ) if 'lnGDPpc' in mm['estcoefs'] else ''
            comments += {1.96: r'95\% c.i.'}[sef]
            transLegend(comments=comments)  #
            pltcomments = 'Coefficients in estimate of ' + substitutedNames(
                mm['depvar']) + ' (with ' + ';'.join(
                    mm.get('flags', {}).keys()).replace(
                        ' ',
                        '') + ')' + mm['texModelNum'] + mm['tableName'][:4]
            self.saveAndIncludeFig(
                figname=('TMP%s-%02d' % (tablename, ifigure) + '-'.join(
                    [rollingX, mm['name']] + mm.get('flags', {}).keys())
                         ).replace(' ', ''),
                caption=pltcomments)
        return ({'statatext': outStata, 'models': lmodels, 'figures': figs})

    ###########################################################################################
    ###
    def coefficientsOnIndicators(self,
                                 statamodel=None,
                                 indicators=None,
                                 rollingXvar=None,
                                 tablename=None,
                                 variableOrder=None,
                                 rollCovColourLookup=None,
                                 includeConstant=True,
                                 nSegments=None):
        ###
        #######################################################################################
        """
        see regressionsDaily.
        Not written yet.
        """

    def substitutedNames(self, names):
        """
        See pystata's substituted names!
        """
        return (substitutedNames(names, self.substitutions))

    def plotAgeCoefficients(self, models):
        """
        overlay plots of the age coefficient predicted components for all models passed.
        
        2014: Sanity check: does this make sense to keep/use? Is it really generally useful? I don't think I like quartics anymore. Just use dummies for age ranges if you really want to take into account age effects.
        """
        from pylab import arange, plot, figure, gcf, clf, show
        from cpblUtilities import transLegend
        figure(345)
        clf()
        for mm in models:
            if 'estcoefs' not in mm:
                continue
            if 'beta' in mm['regoptions'] or dgetget(
                    mm, ['textralines', '$\\beta$ coefs'],
                    '') in ['\\YesMark']:
                continue
            ageCoefs = [
                dgetget(mm, ['estcoefs', cc, 'b'], 0)
                for cc in 'age100', 'agesq100', 'agecu100', 'agefo100'
            ]
            age = arange(0, 100)
            plot(
                age,
                sum([ageCoefs[ii] * (age / 100.0)**ii for ii in range(4)]),
                hold=True,
                label=mm['texModelNum'] + ': ' + str2latex(mm['model']))
        transLegend()
        return (gcf())

    def models2df(self, models):
        # Use the function defined outside the latex class?
        return (models2df(models, latex=self))

    def oaxacaThreeWays(
            self,
            tablename,
            model,
            groupConditions,
            groupNames,
            datafile=None,
            preamble=None,  # This nearly-must include  stataLoad(datafile)
            referenceModel=None,
            referenceModelName=None,
            savedModel=None,
            oaxacaOptions=None,
            dlist=None,
            rerun=True,
            substitutions=None,
            commonOrder=True,
            skipStata=False,
            figsize=None):
        # For example usage of this function, see regressionsAboriginals2015; 
        import time
        if substitutions is None: substitutions = self.substitutions
        # Choose an output do-file and log-file name
        tablenamel = self.generateLongTableName(tablename, skipStata=skipStata)
        tableLogName = defaults['paths']['stata']['tex'] + tablenamel
        tableLogNameWithDate = defaults['paths']['stata'][
            'working'] + 'logs/' + tablenamel + time.strftime(
                '%Y_%m_%d_%H%M%S_') + '.log'
        preamble = '' if preamble is None else preamble
        if self.skipStataForCompletedTables and os.path.exists(tableLogName +
                                                               '.log'):
            if not skipStata:
                print '  Skipping Stata for %s because latex.skipStataForCompletedTables is set ON!!!! and this table is done.' % tablenamel
            outs += """
            """
            skipStata = True

        # Generate the Stata code.  As a matter of pracice, we should alwas include the file loading INSIDE the logfile (ie caller should specify datafile)
        statacode = """
            log using """ + tableLogName + """.log, text replace
            """
        statacode += '' if datafile is None else stataLoad(datafile)
        statacode += '' if preamble is None else preamble
        statacode += oaxacaThreeWays_generate(
            model=model,
            groupConditions=groupConditions,
            groupNames=groupNames,
            referenceModel=referenceModel,
            referenceModelName=referenceModelName,
            oaxacaOptions=oaxacaOptions,
            dlist=dlist, )
        statacode += '\n log close \n'
        if os.path.exists(tableLogName + '.log'):
            models = oaxacaThreeWays_parse(
                tableLogName, substitutions=substitutions)
        else:
            print(' Did not find Blinder-Oaxaca log file for %s: rerun Stata.'
                  % tableLogName)
            models = []

        # NOW MAKE A PLOT OF THE FINDINGS: SUBSAMPLE DIFFERENCE ACCOUNTING
        for imodel, model in enumerate(models):
            depvar = model['depvar']
            subsamp = model['subsamp']
            basecase = model['basecase']
            tooSmallToPlot = {subsamp: []}

            from cifarColours import colours
            import pylab as plt
            from cpblUtilities import figureFontSetup, categoryBarPlot
            import numpy as np
            plt.ioff()
            figureFontSetup()
            plt.figure(217, figsize=figsize)
            plt.clf()
            """
            What is the logic here? I want to
            - eliminate "constant".
            - order variables according to magnitude of effect, except if showvars specified.
            - include the grouped variables and not their contents
            """

            plotvars = [
                vv for vv in model['diffpredictions_se'][subsamp].keys()
                if not vv in [model['depvar'], 'constant', 'Total']
            ]
            plotvars.sort(
                key=lambda x: abs(model['diffpredictions'][subsamp][x])
            )  #abs(array([model['diffpredictions'][subsamp][vv] for vv in plotvars])))
            plotvars.reverse()

            rhsvars = plotvars

            cutoffTooSmallToPlot = .01  # If you change this, change the %.2f below, too
            tooSmallToPlot[subsamp] += [
                vv for vv in rhsvars
                if (abs(model['diffpredictions'][subsamp][vv]) + 2 * abs(
                    model['diffpredictions_se'][subsamp][vv])
                    ) / abs(model['diffLHS']) < cutoffTooSmallToPlot and vv
                not in ['constant'] and vv in plotvars
            ]
            omittedComments = ''
            if tooSmallToPlot[subsamp]:
                omittedComments = ' The following variables are not shown because their contribution was estimated with 95\\%% confidence to be less than %.2f of the predicted difference: %s. ' % (
                    cutoffTooSmallToPlot, '; '.join(tooSmallToPlot[subsamp]))
                plotvars = [
                    cv for cv in plotvars if cv not in tooSmallToPlot[subsamp]
                ]

            if commonOrder and ioaxaca > 0:
                plotvars = lastPlotVars
            else:
                lastPlotVars = plotvars

            labelLoc = 'eitherSideOfZero'
            labelLoc = None  #['left','right'][int(model['diffLHS'][subsamp]>0)]
            DV = substitutedNames(model['depvar'], substitutions)
            cbph = categoryBarPlot(
                np.array([r'$\Delta$' + DV, r'predicted $\Delta$' + DV] +
                         plotvars),
                np.array([
                    model['diffLHS'],
                    model['diffpredictions'][subsamp]['Total']
                ] + [model['diffpredictions'][subsamp][vv]
                     for vv in plotvars]),
                labelLoc=labelLoc,
                sortDecreasing=False,
                yerr=np.array([
                    model['diffLHS_se'],
                    model['diffpredictions_se'][subsamp]['Total']
                ] + [
                    model['diffpredictions_se'][subsamp][vv] for vv in plotvars
                ]),
                barColour={
                    r'$\Delta$' + DV: colours['darkgreen'],
                    r'predicted $\Delta$' + DV: colours['green']
                })
            #plt.figlegend(yerr,['SS','ww'],'lower left')
            assert DV in [
                'swl', 'SWL', 'ladder', '{\\em nation:}~ladder', 'lifeToday'
            ]  # model['depvar'] needs to be in the two lookup tables in following two lines:
            shortLHSname = {
                'SWL': 'SWL',
                'swl': 'SWL',
                'lifeToday': 'life today',
                'ladder': 'ladder',
                '{\\em nation:}~ladder': 'ladder'
            }[DV]
            longLHSname = {
                'SWL': 'satisfaction with life (SWL)',
                'swl': 'satisfaction with life (SWL)',
                'lifeToday': 'life today',
                'ladder': 'Cantril ladder',
                '{\\em nation:}~ladder': 'Cantril ladder'
            }[DV]
            # Could put here translations

            xxx = plt.legend(cbph['bars'][0:3], [
                r'$\Delta$' + shortLHSname + ' observed', r'$\Delta$' +
                shortLHSname + ' explained', 'explained contribution'
            ], {True: 'lower left',
                False: 'lower right'}[abs(plt.xlim()[0]) > abs(plt.xlim()[1])])
            xxx.get_frame().set_alpha(0.5)

            # Could you epxlain the following if??
            if 0 and plotparams.get('showTitle', False) == True:
                plt.title(model['name'] + ': ' + subsamp +
                          ': differences from ' + basecase)
                plt.title(
                    "Accounting for %s's life satisfaction difference from %s"
                    % (subsamp, basecase))
                title = ''
                caption = ''
            else:
                title = r"Accounting for %s's life satisfaction difference from %s \ctDraftComment{(%s) col (%d)}" % (
                    subsamp, basecase, model['name'], model['modelNum'])

                caption = title
            plt.xlabel(r'$\Delta$ %s' % shortLHSname)
            #plt.subtitle('Error bars show two standard error widths')

            plt.xlabel('Mean and explained difference in ' + longLHSname)
            plt.ylim(-1, len(plotvars) +
                     3)  # Give just one bar space on top and bottom.
            #plt.ylim(np.array(plt.ylim())+np.array([-1,1]))

            if commonOrder and ioaxaca > 0:
                plt.xlim(lastPlotXlim)
            else:
                lastPlotXlim = plt.xlim()

            # Save without titles:
            imageFN = paths['graphics'] + os.path.split(
                tableLogName)[1] + '-using-%s%d' % (
                    str2pathname(model['basecase']), imodel)
            needReplacePlot = fileOlderThan(imageFN + '.png',
                                            tableLogName + '.log')

            self.saveAndIncludeFig(
                imageFN,
                caption=None,
                texwidth=None,
                title=None,  # It seems title is not used!
                onlyPNG=False,
                rcparams=None,
                transparent=False,
                ifany=None,
                fig=None,
                skipIfExists=not needReplacePlot and
                self.skipSavingExistingFigures,
                pauseForMissing=True)

            # And store all this so that the caller could recreate a custom version of the plot (or else allow passing of plot parameters.. or a function for plotting...? Maybe if a function is offered, call that here...? So, if regTable returns models as well as TeX code, this can go back to caller. (pass pointer?)
            if 'accountingPlot' not in model:
                model['accountingPlot'] = {}
            model['accountingPlot'][subsamp] = {
                'labels': np.array(rhsvars + ['predicted ' + DV, DV]),
                'y': np.array([
                    model['diffpredictions'][subsamp][vv] for vv in rhsvars
                ] + [
                    model['diffpredictions'][subsamp]['Total'],
                    model['diffLHS']
                ]),
                'yerr': np.array([
                    model['diffpredictions_se'][subsamp][vv] for vv in rhsvars
                ] + [
                    model['diffpredictions_se'][subsamp]['Total'],
                    model['diffLHS_se']
                ])
            }

        return (statacode * (not skipStata))


################################################################################################
################################################################################################
################################################################################################
if __name__ == '__main__':
    ################################################################################################
    ################################################################################################
    print ' DEMO MODE!!!!!!!!! for pystata.latexRegressions ... '
    sVersion, rVersion, dVersion = 'CPBLtesting', 'XXXX', 'testing'

    from recodeGallup import gDataVersion, pathList, gVersion

    def testFunctions(latex):
        return ("""
gzuse macroNov2010,clear
""" + latex.addCorrelationTable(
            'testMkCorr', 'gwp_beta*', ifClause=None) + """

""")

    from regressionsGallup import standardSubstitutions
    runBatchSet(
        sVersion,
        rVersion, [testFunctions],
        dVersion='testingOnly-forCPBLStataLR',
        substitutions=standardSubstitutions)
