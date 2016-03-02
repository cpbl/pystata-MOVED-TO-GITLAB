"""
Configuration:
 A config.ini file should be used to set up folders to be used by pystata. The configuration procedure is as follows:
  (1) pystata.configure() can be called to explicity set config values.
  (2) Otherwise, pystata will look for a config.ini file in the operating system's local path at run time. Typically, this would be a file in the package of some caller module and would be in .gitignore so that it can be locally customized
  (3) Otherwise, pystata will look for a config.ini file in its own (the pystata repository) folder.  

"""
import os
import re


def configure(newdefaults=None):
    assert isinstance(newdefaults,dict)
    global defaults,paths,WP,IP,RDC
    defaults=newdefaults
    paths=defaults['paths']
    defaults['native']={'paths':paths.copy()} # A relic from running posix os under MS (cygwin)
    WP=paths['working']
    IP=paths['input']
    RDC=defaults.get('RDC',False)
    return(defaults)


def createDefaultConfigFile(outpath='./config.cfg'):
    """
    Write a config file which provides the path info that this module requires.  (Or should it ADD the info that this module requires?)
    N.B. Even this default one requires the "pwd" be defined as a default. This is the local operating system directory at run-time.
    """
    import ConfigParser
    config = ConfigParser.RawConfigParser()
    # When adding sections or items, add them in the reverse order of
    # how you want them to be displayed in the actual file.
    # In addition, please note that using RawConfigParser's and the raw
    # mode of ConfigParser's respective set functions, you can assign
    # non-string values to keys internally, but will receive an error
    # when attempting to write to a file or when you get it in non-raw
    # mode. SafeConfigParser does not allow such assignments to take place.
    config.add_section('paths')
    config.set('paths', 'working', '%(pwd)s/')
    config.set('paths', 'input', '%(pwd)s/')
    config.set('paths', 'tex', '%(pwd)s/')
    config.set('paths', 'scratch', '%(pwd)s/')
    config.add_section('defaults') # For as-yet unsectioned settings
    config.set('defaults', 'RDC', 'False')

    # Writing our configuration file to 'example.cfg'
    with open(outpath, 'wt') as configfile:
        config.write(configfile)

def readConfigFile(inpath):
    import ConfigParser
    # New instance with 'bar' and 'baz' defaulting to 'Life' and 'hard' each
    config = ConfigParser.SafeConfigParser({'pwd': os.getcwd(),'cwd': os.getcwd()})
    config.read(inpath)
    defaultsDict=dict(
        paths=dict(
            working=config.get('paths', 'working'),
            input=config.get('paths', 'input'),
            tex=config.get('paths', 'tex'),
            scratch=config.get('paths', 'scratch'),
            ),
        RDC=config.getboolean('defaults', 'RDC'),
        )
    return(defaultsDict)
    

# Is there a config file in the local directory?
localConfigFile=os.getcwd()+'/config.cfg'
if os.path.exists(localConfigFile):
    configDict=readConfigFile(localConfigFile)
# Is there a config file in cpblUtilities directory?  
# If it doesn't exist, create one. This is really just a way to record a defaults; but it also provides a template.
else:
    print('Information: Cannot find your custom config.cfg. You may want to look in the '+__file__+' repo for a template to customize folders.')
    repoPath=os.path.dirname(__file__ if __file__ is not None else '.')
    repoFile=(repoPath if repoPath else '.')+'/config.cfg'
    if not os.path.exists(repoFile):
        createDefaultConfigFile(repoFile)
    configDict=readConfigFile(repoFile)
configure(configDict)
