#!/usr/bin/python
# -*- coding: utf-8 -*-
import os, re, sys, copy
from cpblUtilities.configtools import readConfigFile, read_hierarchy_of_config_files

"""
This module provides dicts paths and defaults, which contain any parameters needed by multiple other modules.
These parameters are generally unchanging over time, but may vary from one installation/environment to another.


 - Specify structure of file.
 - Load cascaded values from config files.
 - Then rearrange as we need to put them into the dict arrays paths and defaults.
"""
config_file_structure={
    'paths': [
        'working',
        'input',
        'graphics',
        'outputdata',
        'output',
        'tex',
        'scratch',
        'bin',
        ],
    'defaults': [
        ('rdc',bool),
        'mode',
        ],
    'server': [
        ('parallel',bool),
        ('manycoreCPU',bool),
        ('islinux',bool),
        'stataVersion', # e.g. 'linux12'
    ],
    }


# The file config-template.cfg contains an example of a file which should be renamed config.cfg

def main():
    """
    """
    VERBOSE=True
    localConfigFile=os.getcwd()+'/config.cfg'
    localConfigTemplateFile=os.getcwd()+'/config-template.cfg'
    repoPath=os.path.abspath(os.path.dirname(__file__ if __file__ is not None else '.'))
    incomingPath=os.getcwd()
    
    # Change directory to the repo bin folder, ie location of this module. That way, we always have the osm config.cfg file as local, which means other utlilities using config.cfg will find the right one.
    path = os.path.abspath(__file__)
    dir_path = os.path.dirname(path)
    if 'bin/pystata' not in os.getcwd():
        print(' Caution: new code October 2016: chdir in pystata_config. Not sure why this was not done before. Complaints to CPBL. chdir(%s)'%dir_path)
        os.chdir(dir_path)

    repoFile=(repoPath if repoPath else '.')+'/config.cfg'
    repoTemplateFile=(repoPath if repoPath else '.')+'/config-template.cfg'

    print('pystata setting defaults:')
    merged_dictionary=read_hierarchy_of_config_files([
        repoTemplateFile,
        repoFile,
        localConfigTemplateFile,
        localConfigFile,
    ], config_file_structure,
                                                     verbose=VERBOSE)
    #print localConfigFile
    # Now impose our structure
    defaults={}
    if 'defaults' in merged_dictionary:
        defaults.update(merged_dictionary['defaults'])
    #defaults.upda=dict([[kk,vv] for kk,vv in merged_dictionary['defaults'].items() if kk in ['rdc','mode',]])
    defaults.update(dict(paths=merged_dictionary['paths'],
                        server=merged_dictionary['server'],
                  ))
    defaults['stata'] =  {'paths':copy.deepcopy(defaults['paths'])}
    defaults['native'] = {'paths':copy.deepcopy(defaults['paths'])}

    os.chdir(incomingPath)
    return(defaults)
defaults=main()
paths=defaults['paths']
if 'python_utils_path' in paths:
    sys.path.append(paths['python_utils_path'])



