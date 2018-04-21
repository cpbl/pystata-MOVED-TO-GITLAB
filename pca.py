#!/usr/bin/python
# coding=utf-8

import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt
from cpblUtilities.mathgraph import  weightedPearsonCoefficient
from cpblUtilities.utilities import  shelfSave,shelfLoad

        
def _normalize(s):
    return (s-s.mean())/s.std()
def _demean(s):
    return (s-s.mean())

class pca_result(pd.DataFrame):
    """
    Stores PCA coefficients (ie, loadings) for use on other data than those on which they were estimated.
    In order to apply the coefficients, it also requires storing the standard deviations and means for each column of raw data.

    Also provides a method for applying the estimated coefficients to a new dataset.

    By default (fix_signs=True), this flips the sign on all components so that each is aligned with the variable it is most correlated with.
    """
    def __init__(self,df, data_means=None, data_stds=None, original_data = None, weight = None, explained=None, eigenvalues=None,  fix_signs=True,  filename=None,   verbose=True, other_output=None,  method_comments=None):
        if isinstance(df,basestring):
            pd.DataFrame.__init__(self)
            self.load(df)
            return
        # Columns are the data variables.  Rows (index) are PCA1, PCA2, ...
        pd.DataFrame.__init__(self, df)
        #self.columns= self.columns
        self.verbose=verbose
        if not self.columns[0] == "PCA1":
            if self.verbose: print('  Overwriting columns to PCA1, PCA2, ...')
            assert self.columns[0] in [0,1,'0','1']
            self.columns = ['PCA{}'.format(i+1) for i in range(len(self.columns))]
        if self.verbose: print(' pca_coefficients object initialized with data variables {}..{} and rows {}..{}'.format(self.index[0], self.index[-1],self.columns[0],self.columns[-1],))
        if original_data is None:
            self.data_means = pd.Series(data_means, index=self.index)
            self.data_stds = pd.Series(data_stds, index=self.index)
            self.correlations = None
        else:
            self.data_means = original_data.mean()
            self.data_stds = original_data.std()
            self.correlations = self.calculate_correlations(original_data, weight = weight)
            if fix_signs: self.fix_signs()
            
        if isinstance(explained,np.ndarray) or isinstance(explained,list):
            self.explained= pd.DataFrame(dict(fraction_explained= explained), index = self.columns)
        else:
            self.explained=explained
        if isinstance(eigenvalues,np.ndarray) or isinstance(eigenvalues,list):
            self.eigenvalues= pd.DataFrame(dict(fraction_eigenvalues= eigenvalues), index = self.columns)
        else:
            self.eigenvalues=eigenvalues
        self.other_output = other_output
        self.method_comments = method_comments
        if filename is not None:
            self.save(filename)

    def apply_coefficients_to_data(self, X, n_components=None): # I don't love this method name
        """ X should be a dataframe with row-observations and X columns which match the known PCA coefficients. However, these are not necessarily the data which generated the PCA estimate of those coefficients.
        It uses known variances and means and coefficients from a PCA estimation, and applies them to a new dataset, X.
        It returns the first n_components PCA vectors (ie new variables), called PCA1, PCA2, etc.
        """
        assert set(X.columns)==set(self.index)
        assert not pd.isnull(X).any().any()        
        cmat = self if n_components is None else self.loc[:, :n_components]
        # Use the ORIGINAL DATA normalization parameters to normalize these data:
        Xnorm = (X-self.data_means)/self.data_stds
        scores = Xnorm.dot(self)  # Nice: name-checking matrix multiplication
        assert not pd.isnull(scores).any().any()
        return scores
    def calculate_correlations(self,original_data, weight = None):
        # Calc correlations of original variables with the principal components (scores):
        scores = self.apply_coefficients_to_data(original_data)
        pccorr = self*np.nan # Just use same columns, index as the coefficients matrix
        for pcv in pccorr.columns:
            for ov in pccorr.index:
                pccorr.loc[ov,pcv] = weightedPearsonCoefficient(original_data[ov].values, scores[pcv].values, weight)
        return pccorr
    def flip_sign(self,component):
        self[component] *= -1
        self.correlations[component]     *= -1
    def fix_signs(self):
        """ Flip any PCA vector which is pointing away from its strongest correlate """
        for pc in self.columns:
            if np.sign(self.loc[self.correlations[pc].abs().idxmax(), pc]) == -1:
                self.flip_sign(pc)
        return
    def save(self,fn): # This sould be updated to use proper Python self pickling methods!
        shelfSave(fn, dict(df = self, data_means = self.data_means, data_stds = self.data_stds, correlations = self.correlations, explained = self.explained, eigenvalues = self.eigenvalues, method_comments = self.method_comments))
        if self.verbose: print('   Saved '+fn)
    def load(self,fn): # This sould be updated to use proper Python methods!
        dd = shelfLoad(fn)
        pd.DataFrame.__init__(self, dd['df'])
        self.data_means= dd['data_means']
        self.data_stds= dd['data_stds']
        self.correlations= dd['correlations']
        self.eigenvalues= dd['eigenvalues']
        self.explained= dd['explained']
        self.method_comments = dd['method_comments']
        return(self)
        """ Something like this is apparently more correct...
        @classmethod
        def loader(cls,f):
            return cPickle.load(f)
        then the caller would do something like:

        class_instance = ClassName.loader(f)
        """
    def diagnostic_plot(self,filename=None):
        # Diagnostic plot
        # Of course, mpl's figsize and 'tight' export both fail / appear to be nearly meaningless.
        fig, ax1 = plt.subplots(figsize=(4,2.5))
        xPCAticks= np.arange(len(self.explained.index))+1
        ax1.plot(xPCAticks, self.explained, 'b.-', label='Fraction explained variance')
        ax1.set_xlabel('PCA component')
        ax1.set_xticks(xPCAticks)
        plt.axis('tight')
        # Make the y-axis label, ticks and tick labels match the line color.
        ax1.set_ylabel('Explained variance', color='b')
        ax1.tick_params('y', colors='b')
        for ipca,pcaname in enumerate( self.explained[self.eigenvalues>1].index):
            ax1.text(ipca+1, self.explained[pcaname], pcaname, va='center')
        ax2 = ax1.twinx()
        ax2.plot(xPCAticks, self.eigenvalues,'b', label='Eigenvalue')
        ax2.set_ylabel('Eigenvalue', color='b')
        ax2.tick_params('y', colors='b')
        ax2.plot(  xPCAticks[[0,-1]], [1,1], 'm:')
        fig.tight_layout()
        ax1.set_xlim(xPCAticks[[0,-1]]+[-.2,.2])
        if filename is not None:
            print('  Writing '+filename)
            plt.savefig(filename, bbox_inches='tight')
    # To make a LaTeX table of coefficients, see e.g. format_LaTeX_table_of_PCA_coefficients(self) in aggregate_connectivity_metrics.py

    
def estimatePCA(df, weight=None, tmpname=None, scratch_path=None, method=None, package='stata', verbose=True, dropna=False, **argv):
    """ Pandas interface to multiple  PCA functions, including Stata's 
    df is a dataframe with desired data vectors as columns, possibly with one extra column given by weight.

    Returns dict including: coefficients, eigenvalues, cumulative fraction variance explained, the PCA vectors, correlation matrix
    """
    
    assert package in ['stata','scipy','jakevdp']
    if package in ['jakevdp'] and method is None:
        method = 'WPCA'
    if package in ['stata'] and method is None:
        method = 'cor'
    assert (method in ['cor','cov'] and package in ['stata'] ) or (package in ['jakevdp'] and method in ['WPCA','EMPCA']) or (package in ['scipy'] and weight is None)
    
    dfnn=df.dropna()
    if not len(dfnn) == len(df):
        msg=' WARNING: estimatePCA dropped {} NaN observations (out of {}).'.format(-len(dfnn)+len(df),len(df))
        if dropna:
            df=dfnn
        else:
            raise Exception(' WARNING: estimatePCA dropped {} NaN observations (out of {}).'.format(-len(dfnn)+len(df),len(df)))
        df=dfnn
    df=df.copy()
    if 0 and weight is None:
        assert 'wuns' not in df.columns
        df.loc[:,'wuns'] = 1
        weight='wuns'
    pcvars = [cc for cc in df.columns if cc not in [weight]]
    if package =='stata':
        df.to_stata(scratch_path+tmpname+'.dta')
        statado = """
        capture ssc inst pcacoefsave

        use {fn},clear
        pca {pcvars} {ww} , {method}
        predict {PCAvlist}, score
        outsheet {PCAvlist} using {SP}{fn}_score.tsv, replace  noquote        

        use {fn},clear
        pca {pcvars} {ww} , {method}
        pcacoefsave using {SP}{fn}_pca_coefs, replace
        mat eigenvalues = e(Ev)
        gen eigenvalues = eigenvalues[1,_n]
        egen varexpl=total(eigenvalues) if !mi(eigenvalues)
        replace varexpl=sum((eigenvalues/varexpl)) if !mi(eigenvalues)
        gen component=_n if !mi(eigenvalues)
        keep varexpl eigenvalues component 
        keep if ~missing(component)
        list
        outsheet using {SP}{fn}_varexpl.tsv, replace  noquote
        u {SP}{fn}_pca_coefs, clear
        outsheet using {SP}{fn}_pca_coefs.tsv, replace noquote
        """.format(PCAvlist= ' '.join(['PCA{}'.format(ii+1) for ii in range(len(pcvars))]), method = method, fn=tmpname, SP=scratch_path, pcvars = ' '.join(pcvars), ww = '' if weight is None else '[w='+weight+']')
        with open(scratch_path+tmpname+'.do','wt') as fout:
            fout.write(statado)
        os.system(' cd {SP} && stata -b {SP}{fn}.do'.format(SP=scratch_path, fn=tmpname))
        df_coefs = pd.read_table(scratch_path+tmpname+'_pca_coefs.tsv')
        df_varexpl = pd.read_table(scratch_path+tmpname+'_varexpl.tsv')
        df_varexpl['cumvarexpl'] = df_varexpl['varexpl'].values
        df_varexpl['varexpl'] = df_varexpl['cumvarexpl'].diff()
        df_varexpl.loc[0,'varexpl'] = df_varexpl['cumvarexpl'][0]
        df_score = pd.read_table(scratch_path+tmpname+'_score.tsv')

        df_cmat=df_coefs.pivot(index='PC', columns='varname', values='loading').dropna()
        df_cmat.index = df_cmat.index.map(lambda nn:'PCA'+str(nn))
        df_varexpl.index = df_cmat.index
        assert not pd.isnull(df_cmat).any().any()
        
        # Stata messes up variable order. Reinforce it here:
        pcaresult = pca_result(df_cmat[pcvars].T, original_data = df[pcvars],
                               explained = df_varexpl['varexpl'],
                               other_output = {'vectors_stata':df_score},
                               eigenvalues = df_varexpl['eigenvalues'], weight=None if weight is None else df[weight], **argv)
        #The proportion of the variance that each eigenvector represents can be calculated by dividing the eigenvalue corresponding to that eigenvector by the sum of all eigenvalues.
        
        
    elif package == 'scipy':
        assert not 'not written yet'
        #from sklearn.decomposition import PCA as spPCA    
        from statsmodels.multivariate.pca import PCA as smPCA
        ss=smPCA(df[pcvars], standardize=True) # No sample weights available; the weights argument weights variables!
        return ss
        foo
    elif package =='jakevdp':
        from wpca import PCA, WPCA, EMPCA
        #pca = PCA(n_components=10).fit(dfnorm)
        fPCA = {'PCA': PCA, 'WPCA':WPCA,'EMPCA':EMPCA}[method]
        # Compute the PCA vectors & variance
        if weight is None:
            ww=None
            dfdata = df[pcvars]
        else: # Construct weight matrix of identical shape to df ( :( ). Also, avoid singular matrix by dropping zero rows.
            iuse = df[weight]>0
            if verbose and sum(-iuse): print(' Warning: estimatePCA is dropping {} rows due to zero weight'.format(sum(-iuse)))
            dfdata = df.loc[iuse,pcvars]
            mw=df.loc[iuse,weight]/(df.loc[iuse,weight].mean())
            ww=dfdata.copy()
            for cc in ww:  ww[cc] = mw
            
        pca = fPCA().fit(dfdata.apply(_normalize, axis=0),    weights= ww)
        df_cmat = pd.DataFrame(pca.components_,columns = pcvars, index= ['PCA{}'.format(i+1) for i in range(len(pca.components_))])

        pcaresult = pca_result(df_cmat.T, original_data = df[pcvars], # Send entire data, even where weight is zero
                               other_output = {'vectors_jakevdp':pca.transform(dfdata),
                                               'vectors_jakevdp_w':pca.transform(dfdata,weights=ww)},
                               explained = pca.explained_variance_ratio_,
                               eigenvalues = pca.explained_variance_, weight=None if weight is None else df[weight], **argv)
        """
        pcaresult.save(scratch_path+tmpname+'-pcaresult.pyshelf')

        pca = PCA().fit(df[pcvars].apply(_normalize, axis=0))
        df_cmat = pd.DataFrame(pca.components_,columns = pcvars, index= ['PCA{}'.format(i+1) for i in range(len(pca.components_))])
        pcaresult = pca_result(df_cmat, original_data = df[pcvars],
                               explained = pd.DataFrame(dict(explained=pca.explained_variance_ratio_),index=pcvars))
        pcaresult.save(scratch_path+tmpname+'-pcaresult.pyshelf')

        frty
        def plot_results(ThisPCA, X, weights=None, Xtrue=None, ncomp=2):
            # Compute the standard/weighted PCA
            if weights is None:
                kwds = {}
            else:
                kwds = {'weights': weights}

            # Compute the PCA vectors & variance
            pca = ThisPCA(n_components=10).fit(X, **kwds)
        """
        
        
                   
    # Diagnostic plot
    plt.figure(456789876)
    fig, ax1 = plt.subplots()
    xPCAticks= np.arange(len(pcaresult.explained.index))+1
    xPCAticklabels = pcaresult.index.values
    ax1.plot(xPCAticks, pcaresult.explained, 'b.-', label='Fraction explained variance')
    ax1.set_xlabel('PCA component')
    ax1.set_xticks(xPCAticks)
    ax1.set_xticklabels(xPCAticklabels, rotation=45, ha='right')
    plt.axis('tight')
    # Make the y-axis label, ticks and tick labels match the line color.
    ax1.set_ylabel('Explained variance', color='b')
    ax1.tick_params('y', colors='b')
    ax1.grid()
    ax2 = ax1.twinx()
    ax2.plot(xPCAticks, pcaresult.eigenvalues,'b.-', label='Eigenvalue')
    ax2.set_ylabel('Eigenvalue', color='b')
    ax2.tick_params('y', colors='b')
    fig.tight_layout()
    plotfn=scratch_path+tmpname+'diagnostic-plot.pdf'
    plt.savefig(plotfn)
    pcaresult.fig = fig
    pcaresult.vectors = pcaresult.apply_coefficients_to_data(df[pcvars])
    return pcaresult
    
    # pcs is a df with the new vectors, along with the original index of df (so use df.join if you wish to merge)
    results= {'coefs':df_cmat, 'loadingStata':df_coefs, 'explained':df_varexpl, 'corr':pccorr, 'plot':plotfn, 'vectors':pcs,  'vectorsStata':df_score, 'fig':fig}
    #'vectorsN':pcsN,
    return results
    





