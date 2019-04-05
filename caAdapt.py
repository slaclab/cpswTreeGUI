#@C Copyright Notice
#@C ================
#@C This file is part of cpswTreeGUI. It is subject to the license terms in the
#@C LICENSE.txt file found in the top-level directory of this distribution and at
#@C
#@C https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
#@C
#@C No part of cpswTreeGUI, including this file, may be copied, modified, propagated, or
#@C distributed except according to the terms contained in the LICENSE.txt file.
import yaml_cpp as yaml
import cpswTreeGUI
from   hashlib           import sha1
import epics

class AdaptBase:
  def __init__(self, path, suff):
    self._path = path
    self._hnam = path.hash()
    self._pv   = epics.get_pv(self._hnam + suff)

  def hnam(self):
    return self._hnam

  def pv(self):
    return self._pv

  def getDescription(self):
    return epics.caget( self._pv.pvname + ".DESC", timeout=0.0, use_monitor = True )

  def getConnectionName(self):
    return self._pv.pvname

class CmdAdapt(AdaptBase):
  def __init__(self, path):
    AdaptBase.__init__(self, path, ":Ex")

  def execute(self):
    self._pv.put("Run")

class StreamAdapt(AdaptBase):
  def __init__(self):
    raise NotImplemented("STREAM not implemented for CA")

class VarAdapt(AdaptBase):

  def __init__(self, path, readOnly, reprType, hasEnum):
    AdaptBase.__init__(self, path, ":Rd") 

    if not readOnly:
      self._pvw     = epics.get_pv(self.hnam()+":St")

    self._enumItems = None
    if hasEnum:
      self.pv().wait_for_connection()
      if None != self.pv().enum_strs:
        self._enumItems = [ (it,) for it in self.pv().enum_strs ]
    print("Made PV: '{}' -- type '{}'".format(self.hnam()+":Rd", self.pv().type))
    self._readOnly  = readOnly
    self._repr      = reprType

  def setVal(self, val, fromIdx = -1, toIdx = -1):
    self._pvw.put( val )

  def setWidget(self, widgt):
    self._widgt     = widgt
    self.pv().add_callback( self, with_ctrlvars=False )
    asStr           = (None != self.getEnumItems())
    val             = self.pv().get( as_string=asStr, timeout=0.0 )
    if None != val:
      # if connection was fast we must update
      self.callback( val )

  def getValAsync(self):
    raise NotImplemented("getValAsync not implemented for CA")

  def isReadOnly(self):
    return self._readOnly

  def getEnumItems(self):
    return self._enumItems

  def getSizeBits(self):
    return 32 #FIXME

  def isSigned(self):
    return False #FIXME

  def getRepr(self):
    return self._repr

  def isFloat(self):
    return self.getRepr() == cpswTreeGUI._ReprFloat

  def isString(self):
    return self.getRepr() == cpswTreeGUI._ReprString

  def toString(self):
    return self._var.getPath().toString()

  # Called by Async IO Completion
  def callback(self, value):
    self._widgt.asyncUpdateWidget( value )

  def __call__(self, **kwargs):
    if None != self.getEnumItems():
       val = kwargs["char_value"]
    else:
       val = kwargs["value"]
    self.callback( val )

  def needPoll(self):
    return False

class PathAdapt:

  @staticmethod
  def loadYamlFile(yamlFile, yamlRoot, yamlIncDir = None, fixYaml = None):
    rn = yaml.Node.LoadFile(yamlFile)
    n  = rn[yamlRoot]
    if not n.IsMap():
      raise cpswTreeGUI.NotFound("Root node '" + yamlRoot + "' not found in: " + yamlFile)
    hashPrefixNode = rn["hashPrefix"]
    if hashPrefixNode.IsDefined() and hashPrefixNode.IsScalar():
      hashPrefix=hashPrefixNode.getAs()
      print("Using hash prefix: {}",format(hashPrefix))
    else:
      hashPrefix=""
      print("Warning: No hash prefix")
    return PathAdapt( [ (yamlRoot, n, hashPrefix) ] )

  def __init__(self, p):
    self._p = p

  def getTypeInfo(self):
    return self._p[-1][1].getAs()

  def guessRepr(self):
    info = self.getTypeInfo().split(",")
    if info[0] == "FLT" and info[2] == "SCL":
      return cpswTreeGUI._ReprFloat
    if info[0] == "INT":
      if info[2] == "STR":
        return cpswTreeGUI._ReprString
      if info[2] == "SCL" or info[2] == "ENM" :
        return cpswTreeGUI._ReprInt
    return cpswTreeGUI._ReprOther

  def loadConfigFromYamlFile(self, yaml_file):
    raise NotImplemented("loadConfigFromYamlFile not implemented")

  def toString(self):
    s = ""
    for i in self._p[1:]:
      s = s + "/" + i[0] 
    return s

  def findByName(self, ell):
    nl = list(self._p)
    for el in ell.split('/'):
      if 0 != len(el):
        n = nl[-1][1][el]
        if not n.IsDefined() or n.IsNull():
          print("EL {}".format(el))
          print("XXXX lookup in {}".format(self.toString()))
          raise cpswTreeGUI.NotFound(el + " -- not found in " + self.toString())
        nl.append( (el,n) )
    return PathAdapt( nl );

  def createVar(self):
    info  = self.getTypeInfo().split(",")
    ro    = info[1] != "RW"
    reprs = self.guessRepr()
    if cpswTreeGUI._ReprOther == reprs:
      raise cpswTreeGUI.InterfaceNotImplemented("Unkown representation")
    return VarAdapt( self, ro, reprs, info[2]=="ENM"  )

  def createCmd(self):
    info = self.getTypeInfo().split(",")
    if info[0] == "CMD" and info[2] == "SCL":
      return CmdAdapt( self )
    raise cpswTreeGUI.InterfaceNotImplemented("Streams not implemented")

  def createStream(self):
    raise cpswTreeGUI.InterfaceNotImplemented("Streams not implemented")

  def getNelms(self):
    return 1 # FIXME

  def origin(self):
    return [ self._p[0] ]

  def hash(self):
    hashPrefix = self._p[0][2]
    hnam = cpswTreeGUI._RecordNamePrefix+sha1( bytearray( (hashPrefix + self.toString()), "ascii" ) ).hexdigest().upper()
    hnam = hnam[0:cpswTreeGUI._HashedNameLenMax]
    return hnam
 
class ChildAdapt:
  def __init__(self, chldp):
    self._chldp = chldp

  def getStaticDescription(self):
    return None

  def isHub(self):
    if not self._chldp[-1][1].IsMap():
      return None
    return self

  def findByName(self, name):
    return PathAdapt(self._chldp).findByName( name )

  def getChildren(self):
    cl = list()
    for c in self._chldp[-1][1]:
      p = list( self._chldp )
      p.append( (c.first.getAs(), c.second) )
      cl.append( ChildAdapt( p ) )
    return cl

  def getNelms(self):
    return 1 #FIXME

  def getName(self):
    return self._chldp[-1][0]
