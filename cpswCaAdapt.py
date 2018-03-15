import yaml_cpp as yaml
import cpswTreeGUI
from   cpswAdaptBase     import *
from   hashlib           import sha1
import epics

class CAAdaptBase:
  def __init__(self, path, suff):
    self._path = path
    self._hnam = path.hash()
    self._pv   = epics.get_pv(self._hnam + suff, connection_timeout=0.0)

  def hnam(self):
    return self._hnam

  def pv(self):
    return self._pv

  def getConnectionName(self):
    return self._pv.pvname

class CmdAdapt(AdaptBase, CAAdaptBase):
  def __init__(self, cmd):
    AdaptBase.__init__(self, cmd)
    CAAdaptBase.__init__(self, PathAdapt( cmd.getPath() ), ":Ex")

  def execute(self):
    self._pv.put("Run")

  def getConnectionName(self):
    return CAAdaptBase.getConnectionName( self )

class StreamAdapt(AdaptBase, CAAdaptBase):
  def __init__(self, strm):
    #AdaptBase.__init__(self, strm)
    raise NotImplemented("STREAM not implemented for CA")

  def getConnectionName(self):
    return CAAdaptBase.getConnectionName( self )

class VarAdapt(VarAdaptBase, CAAdaptBase):

  def __init__(self, svb, readOnly, reprType):
    VarAdaptBase.__init__(self, svb, readOnly, reprType)
    CAAdaptBase.__init__(self, PathAdapt( svb.getPath() ), ":Rd")
    self.signoff_ = 0
    enums         = self.getEnumItems()
    if None != enums:
      self.enumReverseMap_ = { entry[1]: entry[0] for entry in enums }
    else:
      self.enumReverseMap_ = None
      if not svb.isSigned():
        self.signoff_ = 1 << svb.getSizeBits()
    
    if not readOnly:
      self._pvw     = epics.get_pv(self.hnam()+":St", connection_timeout=0.0)
    print("Made PV: '{}' -- type '{}'".format(self.hnam()+":Rd", self.pv().type))

  def setVal(self, val, fromIdx = -1, toIdx = -1):
    self._pvw.put( val )

  def setWidget(self, widgt):
    VarAdaptBase.setWidget(self, widgt)
    self.pv().add_callback(self, with_ctrlvars=False)
    asStr           = (None != self.getEnumItems())
    val             = self.pv().get( timeout=0.0 )
    if None != val:
      if None != self.enumReverseMap_:
        val = self.enumReverseMap_.get( val, "???" )
      # if connection was fast we must update
      self.callback( val )

  def getValAsync(self):
    raise NotImplemented("getValAsync not implemented for CA")

  # Called by Async IO Completion
  def callback(self, value):
    self._widgt.asyncUpdateWidget( value )

  def __call__(self, **kwargs):
    val = kwargs["value"]
    if None != self.enumReverseMap_:
      val = self.enumReverseMap_.get( val, "???" )
    else:
      if not self.isString() and val < 0:
        val = val + self.signoff_
    self.callback( val )

  def getConnectionName(self):
    return CAAdaptBase.getConnectionName( self )

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

  def guessRepr(self):
    rval = PathAdaptBase.guessRepr(self)
    if None == rval:
      rval = cpswTreeGUI._ReprInt
    return rval

  def findByName(self, el):
    return PathAdapt( self.getp().findByName( el ) )

  def loadConfigFromYamlFile(self, yaml_file):
    raise NotImplemented("loadConfigFromYamlFile not implemented")

  def createVar(self):
    scalVal, ro, representation = PathAdaptBase.createVar( self )
    return VarAdapt( scalVal, ro, representation )

  def createCmd(self):
    raise cpswTreeGUI.InterfaceNotImplemented("Streams not implemented")

  def createStream(self):
    raise cpswTreeGUI.InterfaceNotImplemented("Streams not implemented")

  def hash(self):
    hashPrefix = cpswTreeGUI._HashPrefix
    namLim     = cpswTreeGUI._HashedNameLenMax
    recPrefix  = cpswTreeGUI._RecordNamePrefix
    hnam = recPrefix + sha1( bytearray( (hashPrefix + self.toString()), "ascii" ) ).hexdigest().upper()
    hnam = hnam[0:namLim]
    return hnam
