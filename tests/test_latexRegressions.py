import os
import pystata as pst
pst.paths['tex'] = './tex/'
pst.paths['output'] = './scratch/'
os.system('mkdir -p tex')
os.system('mkdir -p output')
os.system('mkdir -p output/tex')


def test_duplicate_regressors(latex):
    import os
    stataout=pst.doHeader+pst.stataLoad(#os.getcwd()+
        '../demo/sample_data_BES')
    dmodels=latex.str2models("""
    *name:Regressor listed twice
    reg aq1 aq5a aq6a aq5a aq7a [pw=aweightt],

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
    






#from regressionsGallup import standardSubstitutions
pst.runBatchSet(
    'sVersion',
    'rVersion', [
        test_duplicate_regressors,
        #test_addCorrelationTable
    ],
    dVersion='testingOnly-forCPBLStataLR',
    substitutions=pst.standardSubstitutions)
