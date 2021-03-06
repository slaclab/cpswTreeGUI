#@C Copyright Notice
#@C ================
#@C This file is part of cpswTreeGUI. It is subject to the license terms in the
#@C LICENSE.txt file found in the top-level directory of this distribution and at
#@C
#@C https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
#@C
#@C No part of cpswTreeGUI, including this file, may be copied, modified, propagated, or
#@C distributed except according to the terms contained in the LICENSE.txt file.
import pycpsw
from   cpswAdaptBase     import *
import cpswTreeGUI
from   PyQt5             import QtCore
import threading

class CallbackHelper(pycpsw.AsyncIO):
  def __init__(self, real_callback):
    pycpsw.AsyncIO.__init__(self)
    self._real_callback = real_callback

  def callback(self, *args):
    try:
      if None != args[0]:
        self._real_callback.callback(args[0])
      else:
        if len(args) > 1:
          err = args[1]
        else:
          err = ""
        print("Error in callback {}-- Issuer:".format(err))
        print(self._real_callback.callbackIssuer())
  # FIXME: should reflect the timeout status in the GUI...
  #      sys.exit(1)
    except:
      print("Exception in callback -- Issuer:{}".format( self._real_callback.callbackIssuer() ) )
      print("Exception Info {}".format(sys.exc_info()[0]))
      print("Callback arg: {}".format(arg))
      sys.exit(1)

class StringHeuristics:
  def __init__(self):
    raise RuntimeError("This class cannot instantiate objects")

  _enabled = True

  @staticmethod
  def enable():
    StringHeuristics._enabled = True

  def disable():
    StringHeuristics._enabled = False

  @staticmethod
  def isString( path ):
    if not StringHeuristics._enabled:
      return False
    try:
      # there is some really slow I/O out there; limit number of chars
      sv = pycpsw.ScalVal_RO.create( path )
      to = svb.getNelms()
      if to > 20:
        to = 20
      bytearray(sv.getVal(fromIdx=0, toIdx=to)).decode('ascii')
      return True
    except:
      pass
    return False

class VarAdapt(VarAdaptBase):

  def __init__(self, var, readOnly, reprType):
    VarAdaptBase.__init__(self, var, readOnly, reprType)
    self._busy = False
    self._lock = threading.Lock()

  def setVal(self, val, fromIdx = -1, toIdx = -1):
    self.obj().setVal( val, fromIdx=fromIdx, toIdx=toIdx )

  def setWidget(self, widgt):
    VarAdaptBase.setWidget(self, widgt)
    self._cbHelper  = CallbackHelper( self )

  def getValAsync(self):
    # must not re-use '_cbHelper' (the AsyncIO) object
    # whild still in flight!
    with self._lock:
      if not self._busy:
        self._busy = True
        self.obj().getValAsync( self._cbHelper )

  # Called by Async IO Completion
  def callback(self, value):
    self._widgt.asyncUpdateWidget( value )
    # no need for lock here
    self._busy = False

  def needPoll(self):
    return True, self.obj().getPollSecs()

  def callbackIssuer(self):
    return self.getConnectionName()

class CmdAdapt(AdaptBase):
  def __init__(self, cmd):
    AdaptBase.__init__(self, cmd)

  def execute(self):
    self.obj().execute()

class ChildAdapt(ChildAdaptBase):

  @staticmethod
  def mkChildAdapt(chld):
    return ChildAdapt(chld)

  def __init__(self, chld):
    ChildAdaptBase.__init__(self, chld)

  def findByName(self, el):
    return PathAdapt( ChildAdaptBase.findByName( self, el ) )

class PathAdapt(PathAdaptBase):

  @staticmethod
  def loadYamlFile(yamlFile, yamlRoot, yamlIncDir = None, fixYaml = None):
    return PathAdapt( PathAdaptBase.loadYamlFile( yamlFile, yamlRoot, yamlIncDir, fixYaml ) )

  def __init__(self, p):
    PathAdaptBase.__init__(self, p)

  def loadConfigFromYamlFile(self, yaml_file):
    return pycpsw.Path.loadConfigFromYamlFile(self._path, yaml_file)

  def guessRepr(self, svb=None):
    rval = PathAdaptBase.guessRepr(self, svb)
    if rval == None:
      rval = { True: cpswTreeGUI._ReprString, False: cpswTreeGUI._ReprInt }.get( StringHeuristics.isString( self.getp() ) )
    return rval;

  def findByName(self, el):
    return PathAdapt( self.getp().findByName( el ) )

  def createVar(self):
    scalVal, ro, representation = PathAdaptBase.createVar( self )
    return VarAdapt( scalVal, ro, representation )

  def createCmd(self):
    return CmdAdapt( PathAdaptBase.createCmd( self ) )

  def createStream(self):
    return StreamAdapt( PathAdaptBase.createStream( self ) )

class StreamAdapt(AdaptBase, QtCore.QThread):

  def __init__(self, strm):
    AdaptBase.__init__(self, strm)
    QtCore.QThread.__init__(self)

  def setWidget(self, widgt):
    self._widgt = widgt
    self.start()

  def read(self):
    # divide bytes by sample-size
    bufsz = int( self.obj().read(self._widgt.getBuf()) / 2 )
    #print('Got {} items'.format(bufsz))
    #print(self._widgt.getBuf()[0:20])
    self._widgt.plot( bufsz )

  def run(self):
    with self.obj():
      while True:
        self.read()
