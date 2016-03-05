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
    global defaults,paths
    defaults=newdefaults.copy()
    paths=defaults['paths']
    defaults['native']={'paths':paths.copy()} # A relic from running posix os under MS (cygwin)
    #WP=paths['working']
    #IP=paths['input']
    #RDC=defaults.get('RDC',False)
    return(defaults)


def createDefaultConfigFile(outpath='./config.cfg'):
    """
    Write a config file which provides the path info that this module requires.  (Or should it ADD the info that this module requires?)
     
    In  fact, instead of a function, this could be a template file that is included in the git repository but allowed to be modified, by including in .gitignore
    """
    import os
    import ConfigParser
    config = ConfigParser.RawConfigParser()
    defaultRoot="%(pwd)s"
    defaultRoot=os.path.dirname(__file__)    
    # When adding sections or items, add them in the reverse order of
    # how you want them to be displayed in the actual file.
    config.add_section('paths')
    config.set('paths', 'working', defaultRoot+'/workingData/')
    config.set('paths', 'download', defaultRoot+'/input/download/')
    config.set('paths', 'input', defaultRoot+'/input/')
    #config.set('paths', 'output/data', defaultRoot+'/')
    config.set('paths', 'graphics', defaultRoot+'/output/graphics/')
    config.set('paths', 'outputData', defaultRoot+'/output/data/')
    config.set('paths', 'output', defaultRoot+'/output/')
    config.set('paths', 'tex', defaultRoot+'/output/tex/')
    config.set('paths', 'scratch', defaultRoot+'/scratch/')
    config.set('paths', 'bin', defaultRoot+'/')

    config.add_section('defaults') # For as-yet unsectioned settings
    config.set('defaults', 'RDC', 'False')
    config.set('defaults', 'mode', 'none')

    # Writing our configuration file to 'example.cfg'
    with open(outpath, 'wt') as configfile:
        config.write(configfile)

def readConfigFile(inpath):
    import ConfigParser
    print(__file__+': Parsing '+inpath)
    # New instance with 'bar' and 'baz' defaulting to 'Life' and 'hard' each
    config = ConfigParser.SafeConfigParser({'pwd': os.getcwd(),'cwd': os.getcwd()})
    config.read(inpath)
    defaultsDict=dict(
        paths=dict([
            [ppp, config.get('paths', ppp)] for ppp in [
                'working',
                'input',
                'output',
                'tex',
                'scratch',
                'bin',
                'download',
                'graphics',
                'outputData',
             ] ]             ),
        RDC=config.getboolean('defaults', 'RDC'),
        mode=config.get('defaults', 'mode'),
        )
    return(defaultsDict)
    

# Is there a config file in the local directory?
localConfigFile=os.getcwd()+'/config.cfg'
if os.path.exists(localConfigFile):
    configDict=readConfigFile(localConfigFile)
# Is there a config file in cpblUtilities directory?  
# If it doesn't exist, create one. This is really just a way to record a defaults; but it also provides a template.
else:
    print('Information: Cannot find your custom '+localConfigFile+'. You may want to look in the '+__file__+' repo for a template to customize folders.')
    repoPath=os.path.dirname(__file__ if __file__ is not None else '.')
    repoFile=(repoPath if repoPath else '.')+'/config.cfg'
    if not os.path.exists(repoFile):
        createDefaultConfigFile(repoFile)
    configDict=readConfigFile(repoFile)
configure(configDict)


# Also fill in some other things, through testing?
defaults['stataVersion']='linux14' # Deprecated; need to remove
