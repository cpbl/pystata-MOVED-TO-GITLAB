#!/usr/bin/python

#Unfinished! See #2


# Test use of "d." and "l." operators in regression models

# You need to have pystata installed in your python path
# You need to have cpblUtilities installed in your python path, and the latex .sty files in your texmf paths.
#
# See the README file for the extensive but easy setup to be able to run this demo.
#
# Then run this script, three times.

import pystata as pst
import pystata.latexRegressions as ltx
import pandas as pd
from pystata.pystata_config import defaults,paths

print(""" This demo  will write in the following paths:
Working: """+pst.paths['working']+"""
LaTeX:   """+pst.paths['tex']+"""
""")
WP=pst.paths['working']

# Run this python file at least two-three times, to generate PDF with results.

latex=ltx.latexRegressionFile('pystata.xtreg.demo',modelVersion='2018',regressionVersion='A',
                              substitutions= pst.standardSubstitutions)
latex.variableOrder=('').split(' ')+pst.defaultVariableOrder
latex.skipStataForCompletedTables=False# If we've already run it, assume it hasn't changed. (figures too!!)
latex.skipSavingExistingFigures=False

import os
if not os.path.exists(paths['scratch']):    os.makedirs(paths['scratch'])
fn='GWP-means-from-WHR2017'
pst.df2dta( pd.read_table(fn+'.tsv'), paths['scratch']+'GWP-means-from-WHR2017' ) # Create gzipped Stata data file from tabular text data
stataout=pst.doHeader+pst.stataLoad(paths['scratch']+fn)+"""
encode country,gen(icountry)
xtset icountry year
"""
dmodels=latex.str2models("""
* Note: this string is working Stata code. However, it will get heavily preprocessed by pystata.
*flag:clustering=wards
reg d.Life_Ladder d.Social_support i.year
***reg d.Life_Ladder d.Social_support i.year, beta
xtreg Life_Ladder Social_support i.year
""")

stataout+=latex.regTable('xreg demo',dmodels,returnModels=True,transposed='both')

#latex.regTable('simple demo',dmodels,showModels=[mm for mm in dmodels if mm['name'] in ['Special'] or mm.get('flags',{}).get('clustering','') in ['wards']],transposed='both', extraTexFileSuffix='-subset', skipStata=True)

latex.closeAndCompile()
pst.stataSystem(stataout,filename=WP+'demos-xtreg')
if 0:
    print '\n\n The following is the list of model dicts: \n'
    print dmodels

# If the above results in a PDF with coloured regression tables, then you've the basics working together.
# There are many more features to be demo'd, which could be added in here

