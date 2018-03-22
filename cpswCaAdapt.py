import yaml_cpp as yaml
import cpswTreeGUI
from   cpswAdaptBase     import *
from   hashlib           import sha1
from   epics             import ca
import epics

class CAConnector:
  def __init__(self, caAdapter):
    self.caAdapter_ = caAdapter

  def __call__(self, **kwargs):
    if kwargs["conn"]:
      self.caAdapter_.subscribe()

class CAAdaptBase:
  def __init__(self, path, suff, isSubscriber=False):
    self._path         = path
    self._hnam         = path.hash()
    self._cnam         = self._hnam + suff
    if isSubscriber:
      self._chid = None
    else:
      self._chid = ca.create_channel(self._cnam)

  def createChannel(self):
    self._chid = ca.create_channel(self._cnam, callback = CAConnector(self))

  def hnam(self):
    return self._hnam

  def chid(self):
    return self._chid

  def getConnectionName(self):
    if self._chid:
      return ca.name( self._chid )
    return "<Not Connected>"

class CmdAdapt(AdaptBase, CAAdaptBase):
  def __init__(self, cmd):
    AdaptBase.__init__(self, cmd)
    CAAdaptBase.__init__(self, PathAdapt( cmd.getPath() ), ":Ex")

  def execute(self):
    ca.put( self._chid, 1 )

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
    CAAdaptBase.__init__(self, PathAdapt( svb.getPath() ), ":Rd", True)
    self.signoff_ = 0
    self.monitor_ = None
    if None == self.getEnumItems() and not svb.isSigned():
        self.signoff_ = 1 << svb.getSizeBits()

    # if we don't have to fight with the subscription stuff
    # then 'pv' is easier
    if not readOnly:
      self._pvw   = epics.get_pv( self.hnam() + ":St", connection_timeout=0.0 )

  def setVal(self, val, fromIdx = -1, toIdx = -1):
    self._pvw.put( val )

  def setWidget(self, widgt):
    VarAdaptBase.setWidget(self, widgt)
    self.createChannel()
    print("Made PV: '{}' -- type '{}'".format(self.hnam()+":Rd", ca.field_type( self.chid() )))

  def subscribe(self):
    # MUST keep reference to monitor around! (see pyepics docs)
    if None != self.monitor_:
      # re-connect event
      return
    withCtrl      = None != self.getEnumItems()
    self.monitor_ = ca.create_subscription( self.chid(), callback=self, use_ctrl=withCtrl )
    if None != self.getEnumItems():
      val = ca.get( self.chid(), ftype=0, wait=False )
    else:
      val = ca.get( self.chid(), wait=False )
    if None != val:
      # if connection was fast we must update
      self.callback( val )

  def getValAsync(self):
    raise NotImplemented("getValAsync not implemented for CA")

  # Called by Async IO Completion
  def callback(self, value):
    self._widgt.asyncUpdateWidget( value )

  def __call__(self, **kwargs):
    val = kwargs["value"]
    if None != self.getEnumItems():
      val = kwargs["enum_strs"][val].decode("ascii")
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
