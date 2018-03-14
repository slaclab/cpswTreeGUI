import pycpsw
from cpswTreeGUICommon import InterfaceNotImplemented
from PyQt4             import QtCore

class CallbackHelper(pycpsw.AsyncIO):
  def __init__(self, real_callback):
    pycpsw.AsyncIO.__init__(self)
    self._real_callback = real_callback

  def callback(self, arg):
    try:
      if None != arg:
        self._real_callback.callback(arg)
      else:
        print("Error in callback -- Issuer:")
        print(self._real_callback.callbackIssuer())
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
  def isString( svb ):
    if not StringHeuristics._enabled:
      print("DISA")
      return False
    if svb.getNelms() > 1 and not svb.getEnum() and 8 == svb.getSizeBits():
      try:
        # there is some really slow I/O out there; limit number of chars
        sv = pycpsw.ScalVal_RO.create( svb.getPath() )
        to = svb.getNelms()
        if to > 20:
          to = 20
        bytearray(sv.getVal(fromIdx=0, toIdx=to)).decode('ascii')
        return True
      except:
        pass
    return False

class AdaptBase:
  def __init__(self, obj):
    self._obj = obj

  def obj(self):
    return self._obj

  def getDescription(self):
    return self._obj.getDescription() 

  def getConnectionName():
    return self._obj.getPath().toString()

class VarAdapt(AdaptBase):

  _ReprOther  = 0
  _ReprInt    = 1
  _ReprString = 2
  _ReprFloat  = 3

  def __init__(self, var, readOnly, reprType):
    AdaptBase.__init__(self, var)
    self._enumItems = self.obj().getEnum()
    if None != self._enumItems:
      self._enumItems = self._enumItems.getItems()
    self._readOnly  = readOnly
    self._repr      = reprType

  def setVal(self, val, fromIdx = -1, toIdx = -1):
    self.obj().setVal( val, fromIdx=fromIdx, toIdx=toIdx )

  def setWidget(self, widgt):
    self._widgt     = widgt
    self._cbHelper  = CallbackHelper( self )

  def getValAsync(self):
    self.obj().getValAsync( self._cbHelper )

  def isReadOnly(self):
    return self._readOnly

  def getEnumItems(self):
    return self._enumItems

  def getSizeBits(self):
    return self.obj().getSizeBits()

  def isSigned(self):
    return self.obj().isSigned()

  def getRepr(self):
    return self._repr

  def isFloat(self):
    return self.getRepr() == VarAdapt._ReprFloat

  def isString(self):
    return self.getRepr() == VarAdapt._ReprString

  def toString(self):
    return self.obj().getPath().toString()

  # Called by Async IO Completion
  def callback(self, value):
    self._widgt.asyncUpdateWidget( value )

  def needPoll(self):
    return True

class CmdAdapt:
  def __init__(self, cmd):
    AdaptBase.__init__(self, cmd)

  def execute(self):
    self.obj().execute()

class ChildAdapt:
  def __init__(self, entry):
    self.entry_ = entry

  def isHub(self):
    c = self.entry_.isHub()
    if c == None:
      return c
    return ChildAdapt(c)

  def findByName(self, name):
    return PathAdapt( self.entry_.findByName( name ) )

  def getChildren(self):
    cl = list()
    for c in self.entry_.getChildren():
      cl.append( ChildAdapt( c ) )
    return cl

  def getNelms(self):
    return self.entry_.getNelms()

  def getName(self):
    return self.entry_.getName()

  def getStaticDescription(self):
    return self.entry_.getDescription()

class PathAdapt:

  @staticmethod
  def loadYamlFile(yamlFile, yamlRoot, yamlIncDir = None, fixYaml = None):
    return PathAdapt( pycpsw.Path.loadYamlFile(yamlFile, yamlRoot, yamlIncDir, fixYaml) )

  def __init__(self, p):
    self._path = p

  # use heuristics to detect an ascii string
  def guessRepr(self):
    try:
      sv = pycpsw.ScalVal_Base.create( self._path )
    except pycpsw.InterfaceNotImplementedError:
      return VarAdapt._ReprOther
    # if the encoding is NONE then getEncoding returns the 'None' object
    # "NONE" is returned if there is an unknown code
    if sv.getEncoding() == "NONE":
        return VarAdapt._ReprOther
    rval = { "ASCII" : VarAdapt._ReprString, "IEEE_754" : VarAdapt._ReprFloat, "CUSTOM_0" : VarAdapt._ReprInt }.get(sv.getEncoding())
    if rval == None:
      rval = { True: VarAdapt._ReprString, False: VarAdapt._ReprInt }.get( StringHeuristics.isString( sv ) )
    return rval;

  def loadConfigFromYamlFile(self, yaml_file):
    pycpsw.Path.loadConfigFromYamlFile(self._path, yaml_file)

  def findByName(self, el):
    return PathAdapt( self._path.findByName( el ) )

  def createVar(self):
    readOnly       = False

    try:

      representation = self.guessRepr()

      if self._path.getNelms() > 1 and VarAdapt._ReprString != representation:
        raise pycpsw.InterfaceNotImplementedError("Non-String arrays (ScalVal) not supported")

      # If the representation is 'Other' then this is certainly not
      # a ScalVal - but it could still be a DoubleVal.
      # If the representation is 'Float' then it could be a ScalVal for
      # which the Float representation was chosen deliberately (in yaml)
      if representation in (VarAdapt._ReprOther, VarAdapt._ReprFloat):
        try:
          sval     = pycpsw.DoubleVal.create( self._path )
        except pycpsw.InterfaceNotImplementedError:
          sval     = pycpsw.DoubleVal_RO.create( self._path )
          readOnly = True
      else:
        try:
          val      = pycpsw.ScalVal.create( self._path )
        except pycpsw.InterfaceNotImplementedError:
          val      = pycpsw.ScalVal_RO.create( self._path )
          readOnly = True

    except pycpsw.InterfaceNotImplementedError as e:
      raise InterfaceNotImplemented(e.args)

    return VarAdapt( val, readOnly, representation )

  def createCmd(self):
    try:
      if self._path.getNelms() > 1:
        raise pycpsw.InterfaceNotImplementedError("Arrays of commands not supported")
      cmd = pycpsw.Command.create( self._path )
    except pycpsw.InterfaceNotImplementedError as e:
      raise InterfaceNotImplemented(e.args)
    return CmdAdapt( cmd )

  def createStream(self):
    try:
      if self._path.getNelms() > 1:
        raise pycpsw.InterfaceNotImplementedError("Arrays of Streams not supported")
      if self._path.tail().getName() == "Lcls1TimingStream":
        raise pycpsw.InterfaceNotImplementedError("Timing Stream Disabled")
      strm  = pycpsw.Stream.create( self._path )
    except pycpsw.InterfaceNotImplementedError as e:
      raise InterfaceNotImplemented(e.args)
    return StreamAdapt( strm )

  def toString(self):
    return self._path.toString()

  def getNelms(self):
    return self._path.getNelms()

  def origin(self):
    return self._path.origin()

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
