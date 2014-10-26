#!/usr/bin/python

import re
import os
from cpblUtilities import unique
import cpblDefaults
defaults=cpblDefaults.defaults()
import cpblStata
reload(cpblStata)
from cpblStata import *

"""
Just run this several times in a row and then view the resulting PDF. If you're on Linux, it will create a do file, run stata, create and compile LaTeX, all automatically.  Under cygwin, probably the same. Under Windows, most of those things. 
"""

################################################################################################
################################################################################################
def regressions_demo(statatex,reloadString='Reloading_not_activated'):
################################################################################################
################################################################################################

    outPrint='\n'+"""
	sysuse auto, clear
"""

##### Example one: the older formats for regTable#############################################
    outPrint+='\n'+ statatex.regTableOldForm('A demo using old format', "regress", ' ,robust', 'price', [statatex.toDict(aline) for aline in [
                'mpg rep78 headroom',
                ['baseline','mpg rep78 headroom trunk      length turn  displacement gear_ratio foreign',],
                ['','mpg rep78 headroom trunk weight length turn  displacement gear_ratio foreign if weight>3000 ',['heavy']],
                ['','mpg rep78 headroom trunk weight length turn  displacement gear_ratio foreign if weight<3000 ',[['heavy',0]]],
                ['','mpg rep78 headroom trunk weight length turn  displacement gear_ratio foreign if weight<3500 & weight>2500 ',[['heavy','mid']]],
                ]],
comments='All cars in sample have wheels',transposed='both')

##### Example two: the newer, dict-based format. Maybe not an advantage for simple tables like this  ############################

    defaultDict={'name':'','method':'regress','depvar':'price','regoptions':',robust'}
    models=[statatex.toDict(ff,defaultValues=defaultDict) for ff in [
                    'mpg rep78 headroom',
                    'mpg rep78 headroom trunk      length turn  displacement gear_ratio foreign',
                    'mpg rep78 headroom trunk weight length turn  displacement gear_ratio foreign if weight>3000 ',
                    'mpg rep78 headroom trunk weight length turn  displacement gear_ratio foreign if weight<3000 ',
                    'mpg rep78 headroom trunk weight length turn  displacement gear_ratio foreign if weight<3500 & weight>2500 ']]
    models[2]['flags']=[['heavy',1]]
    models[3]['flags']=[['heavy',0]]
    models[4]['flags']=[['heavy','mid']]

    outPrint+='\n'+ statatex.regTable('A demo using new format', models,    comments='All cars in sample have wheels',
    transposed='both',substitutions=standardSubstitutions+[['gear-ratio',r'$1/\frac{bg}{tg}$'],['rep78',r'C$^{\rm rep}_{78}$']])


##### Example three: failsafe group controls (fixed effects). See "withCellDummies" description.  ############################

    mmm=statatex.withCellDummies(models,'rep78',cellName='r78',minSampleSize=10)

    outPrint+='\n'+ statatex.regTable('Cell dummies demo', mmm, regoptions=',robust',    comments='All cars in sample have wheels',
    transposed=False,substitutions=standardSubstitutions+[['gear-ratio',r'$1/\frac{bg}{tg}$'],['rep78',r'C$^{\rm rep}_{78}$']])


##### Some other features  ############################

    """ The "bysurvey" function uses knowledge about what variables are available for a given dataset (this won't exist for your data) to remove any variables that will not be present (thus avoiding Stata errors, etc). It can also be used to display appropriately weighted averages of regression coefficients over those different surveys/datasets for when similar models are applied to different datasets.
    """
    
##### Example 2.1: use of the LaTeX formatting, independent of Stata .  ############################
    """ So this might be useful if you already have some text-format statistical output and want to manipulate  it in LaTeX. The code that this produces is customisable not just through the options in the function calls; the LaTeX code itself is also written in a very scripted way so that it's easy to change properties of the compiled table without changing the included .tex file."""
    colnames=['numberChoices','prevCons','var3']
    colnums=['' for cc in colnames]
    coefrows=[[['alpha',.3,.4,.5],
               ['',.01,.02,.44]],
    [['beta',.1,.15,.2] ,
     ['',.01,.02,.44]],
    [['gamma',.3,.4,.5],
     ['',.01,.02,.44]],
    ]
    extrarows=[]
    
    statatex.appendTable(colnames,colnums,coefrows,extrarows)#greycols=None,suppressSE=False,substitutions=None,colFormat=None,transposed=None,                       tableFilePath=None, tableCaption=None, tableComments=None,                       landscape=False,rowModelNames=None)
    statatex.appendTable(colnames,colnums,coefrows,extrarows,suppressSE=True,transposed=True,tableCaption="formatTable demo")#greycols=None,suppressSE=False,substitutions=None,colFormat=None,transposed=None,                       tableFilePath=None, tableCaption=None, tableComments=None,                       landscape=False,rowModelNames=None)
    #Oh, actually: see note: "April 2008: the "suppressSE" argument throughout this class and etc just became obselete: LaTeX now uses a facultative \useSEs{}{} to choose between showing standard errors or not.

    return(outPrint)


################################################################################################
################################################################################################
################################################################################################
################################################################################################
################################################################################################
################################################################################################
################################################################################################
################################################################################################
################################################################################################
################################################################################################
################################################################################################
################################################################################################
if __name__ == '__main__':
################################################################################################
################################################################################################
################################################################################################
################################################################################################
################################################################################################
################################################################################################
################################################################################################
################################################################################################
################################################################################################

    doFile=defaults['workingPath']+'regressions-demo.do'
    previewFile='tablesPreviewDemo'
    import cpblStata
    from cpblStata import *
    # Initialise a LaTeX file that includes all the tables....  Include lscape package for landscape
    stata=latexRegressionFile(previewFile)

    # Convert any completed Stata output to LaTeX. Also, prepare Stata code for making the output.
    outPrint=cpblStata.doHeader +\
              regressions_demo(stata,reloadString='Reloading_not_activated')

    if 1:#not defaults['islinux'] or 'yes'==raw_input('Write '+doFile+'? (say "yes")'):
        try:
            ESCm=open(doFile,'wt')
            ESCm.write(outPrint+'\n')
            ESCm.close()
            print 'Finished writing '+doFile+' file'
        except IOError:
            print 'FAILED TO WRITE REGRESSIONS do!!!!!!!!!!  Probably you are using MS Windows and another Stata has locked it. (Try using a better operating system)'

    stata.closeAndCompile()
    #stataSystem( doFile.replace('.do',''))

    if defaults['islinux'] and 'yes'==raw_input('Run stata as batch?  (say "yes")'):
        stataSystem(doFile[0:-3],mem=100)


