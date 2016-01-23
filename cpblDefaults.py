#!/usr/bin/python
# -*- coding: utf-8 -*-
"""

This is a git / open / public version of cpblDefaults.py, rather than cpbl's version which includes all kinds of information about Canadian statistics, etc etc, as well as local paths.

So, you may need to define extra elements of the dict defaults, here, to make some of my other modules work.

"""

from copy import deepcopy
import os


def fDefaults(mode=None):
    Defaults=dict()


    boxName=os.uname()[1]
    curdir=os.getcwd()
    if mode is not None:
        DefaultsMode = mode
    else:
        if curdir  in  ['/home/myhome/bin','/home/myhome/Dropbox/bin']:
            DefaultsMode='bin'
        else:
            print(' cpblDefaults: Alert! Cannot discern mode from cwd')
            import imp
            try:
                imp.find_module('filepaths')
                found = True
            except ImportError:
                found = False

            DefaultsMode='sprawl' if found else 'unknown' #return(Defaults)#DefaultsMode=None
    print('cpblDefaults mode: '+DefaultsMode)
    assert DefaultsMode in ['sprawl','bin','canada','gallup','klips','lab','osm','papers', 'unknown']

    Defaults={}##'unix':unixDefaults,'cygwin':cygwinDefaults,'windows':ntDefaults}

    Defaults['islaptop']= boxName in ['cpbl-thinkpad','cpbl-eee','cpbl-tablet']
    Defaults['manycoreCPU']='apollo' in boxName
    Defaults['islinux']=os.uname()[0].lower()=='linux' or os.uname()[1].lower()=='linux'

    dirchar='/'  # This used to be used to accomodate the non-POSIX OS, but that was long ago.

    # phome is some kind of top level folder, which may contain most other relevant folders, or symlinks to them.
    # However, it is updated or overwritten for the major modes, which have their own customized definitions.
    phomes={
        'unknown':curdir+dirchar,
            }
    if DefaultsMode in phomes:
        phome=phomes.get(DefaultsMode,curdir+'/')

    paths={'local':phome,
           'bin':phome+'bin/',
           'working':phome+'workingData/',
           'scratch':phome+'scratch/',
           'input':phome+'inputData/',
           'graphics':phome+'graphicsOut/',
           'tex':phome+'texdocs/',
           }


    for nn,pp in paths.items()+[['tmptex',paths['tex']+'tmpTEX/'],['logs',paths['working']+'logs/']]:
        try:
            os.makedirs(pp)
        except OSError:
                if not os.path.isdir(pp):
                            raise
            
    Defaults['stataVersion']='linux12'
    Defaults['mode']=DefaultsMode
    Defaults['paths']=paths
    Defaults['native']={'paths':paths}
    return(Defaults)


# The goal here is to allow the first invocator of cpblDefaults to modify it. Then, it will not be updated here by any other modules which call this.
# This allows users to modify the data in defaults.
# Really? Doesn't python do all this automatically? Ie isn't this module global?
global _privateMode # Make this accesible to all instances of cpblDefaults, ie every time it gets called/imported...
try:
    _privateMode
except NameError:
    ###if not privateMode:
    _privateMode=''
    defaults= fDefaults(mode=None)
RDC=False
PUMF=False
assert defaults
if defaults:
    paths=defaults['paths']
    WP=defaults['paths']['working']
    if 'scratch' in paths:
        SP=defaults['paths']['scratch']
    IP=defaults['paths']['input']

if __name__ == '__main__':
    print( defaults)




