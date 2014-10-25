#!/usr/bin/python

from cpblDefaults import defaults, paths, WP
import pystata as pst

print(" The following folders must exist: ")
print paths['tex']
print WP
print WP+'logs/'

# Run this python file at least two-three times, to generate PDF with results.
# You need to have cpblDefaults.py in the path (still as of Oct 2014)
# You need to have cpblUtilities installed in your python path
# You need to have cpbl-tables installed, both the python files and the LaTeX .sty files, in your python and texmf paths.

latex=pst.latexRegressionFile('pystata-demo',modelVersion='2014',regressionVersion='A',
                              substitutions=[[ 'aq5a','conservatives handle crime']]+pst.standardSubstitutions)
latex.variableOrder=('aq1 aq5a aq6a aq7a ').split(' ')+pst.defaultVariableOrder
latex.skipStataForCompletedTables=False# If we've already run it, assume it hasn't changed. (figures too!!)
latex.skipSavingExistingFigures=False

import os
stataout=pst.doHeader+pst.stataLoad(os.getcwd()+'/sample_data_BES')
dmodels=latex.str2models("""
*flag:clustering=wards
reg aq1 aq5a aq6a aq7a [pw=aweightt], cluster(awardid)
*|
reg aq1 aq5a aq6a aq7a [pw=aweightt], beta
*name:Special
reg aq1 aq5a aq6a aq7a [pw=aweightt],
""")
stataout+=latex.regTable('simple demo',dmodels,returnModels=True,transposed='both')
latex.closeAndCompile()
pst.stataSystem(stataout,filename=WP+'demos')

# If the above results in a PDF with coloured regression tables, then you've the basics working together.
# There are many more features to be demo'd, which could be added in here

