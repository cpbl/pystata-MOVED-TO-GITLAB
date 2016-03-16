#!/usr/bin/python

# You need to have pystata installed in your python path
# You need to have cpblUtilities installed in your python path
# You need to have cpbl-tables installed, both the python files and the LaTeX .sty files, in your python and texmf paths.
#
# Then copy this demo.py  and sample_data_BES.dta.gz OUTSIDE of the pystata folders to some working folder of your choosing.
# Copy the config-template.cfg from pystata to the same working folder, and edit it to specify existing paths for outputs.
#
# Then run this script, three times.

import pystata as pst
import pystata.latexRegressions as ltx


print(""" This demo  will write in the following paths:
Working: """+pst.paths['working']+"""
LaTeX:   """+pst.paths['tex']+"""
""")
WP=pst.paths['working']


# Run this python file at least two-three times, to generate PDF with results.

latex=ltx.latexRegressionFile('pystata.demo',modelVersion='2014',regressionVersion='A',
                              substitutions=[[ 'aq5a','conservatives handle crime']]+pst.standardSubstitutions)
latex.variableOrder=('aq1 aq5a aq6a aq7a ').split(' ')+pst.defaultVariableOrder
latex.skipStataForCompletedTables=False# If we've already run it, assume it hasn't changed. (figures too!!)
latex.skipSavingExistingFigures=False

import os
stataout=pst.doHeader+pst.stataLoad(os.getcwd()+'/sample_data_BES')
dmodels=latex.str2models("""
* Note: this string is working Stata code. However, it will get heavily preprocessed by pystata.
*flag:clustering=wards
reg aq1 aq5a aq6a aq7a [pw=aweightt], cluster(awardid)
reg aq1 aq5a aq6a aq7a [pw=aweightt], beta
*|
*name:Special
reg aq1 aq5a aq6a aq7a [pw=aweightt],
""")
stataout+=latex.regTable('simple demo',dmodels,returnModels=True,transposed='both')

latex.regTable('simple demo',dmodels,showModels=[mm for mm in dmodels if mm['name'] in ['Special'] or mm.get('flags',{}).get('clustering','') in ['wards']],transposed='both', extraTexFileSuffix='-subset', skipStata=True)

latex.closeAndCompile()
pst.stataSystem(stataout,filename=WP+'demos')
if 0:
    print '\n\n The following is the list of model dicts: \n'
    print dmodels

# If the above results in a PDF with coloured regression tables, then you've the basics working together.
# There are many more features to be demo'd, which could be added in here

