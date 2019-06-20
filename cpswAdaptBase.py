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
import cpswTreeGUI
from   PyQt4             import QtCore

class AdaptBase:
  def __init__(self, obj):
    self._obj = obj

  def obj(self):
    return self._obj

  def getDescription(self):
    return self._obj.getDescription() 

  def getConnectionName(self):
    return self._obj.getPath().toString()

class VarAdaptBase(AdaptBase):

  def __init__(self, val, readOnly, reprType):
    AdaptBase.__init__(self, val)
    if cpswTreeGUI._ReprFloat == reprType:
      self._enumItems = None
      print("FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF")
    else:
      if self.obj().getName() == "State":
        print("@@@@@@@@@@@@@@@@@@@@ State", self.obj())
      self._enumItems = self.obj().getEnum()
    if None != self._enumItems:
      self._enumItems = self._enumItems.getItems()
    self._readOnly  = readOnly
    self._repr      = reprType

  def setWidget(self, widgt):
    self._widgt     = widgt

  def isReadOnly(self):
    return self._readOnly

  def getEnumItems(self):
    return self._enumItems

  def hasEnums(self):
    return None != self.getEnumItems()

  def getSizeBits(self):
    return self.obj().getSizeBits()

  def isSigned(self):
    if self.isFloat():
      return True
    return self.obj().isSigned()

  def getRepr(self):
    return self._repr

  def isFloat(self):
    return self.getRepr() == cpswTreeGUI._ReprFloat

  def isString(self):
    return self.getRepr() == cpswTreeGUI._ReprString

  def toString(self):
    return self.obj().getPath().toString()

  def needPoll(self):
    return False

class ChildAdaptBase:
  def __init__(self, entry):
    self.entry_ = entry

  def isHub(self):
    c = self.entry_.isHub()
    if c == None:
      return c
    return self.mkChildAdapt(c)

  def findByName(self, name):
    return self.entry_.findByName( name )

  def getChildren(self):
    cl = list()
    for c in self.entry_.getChildren():
      cl.append( self.mkChildAdapt(c) )
    return cl

  def getNelms(self):
    return self.entry_.getNelms()

  def getName(self):
    return self.entry_.getName()

  def getStaticDescription(self):
    return self.entry_.getDescription()

class PathAdaptBase:

  @staticmethod
  def loadYamlFile(yamlFile, yamlRoot, yamlIncDir = None, fixYaml = None):
    try:
      return pycpsw.Path.loadYamlFile(yamlFile, yamlRoot, yamlIncDir, fixYaml)
    except pycpsw.CPSWError as e:
      print(e.what())
      raise

  def __init__(self,p):
    self._path = p

  def getp(self):
    return self._path

  # use heuristics to detect an ascii string
  def guessRepr(self, svb = None):
    if None == svb:
      try:
        svb = pycpsw.ScalVal_Base.create( self._path )
      except pycpsw.InterfaceNotImplementedError:
        return cpswTreeGUI._ReprOther
    # if the encoding is NONE then getEncoding returns the 'None' object
    # "NONE" is returned if there is an unknown code
    if svb.getEncoding() == "NONE":
        return cpswTreeGUI._ReprOther
    rval = { "ASCII" : cpswTreeGUI._ReprString, "IEEE_754" : cpswTreeGUI._ReprFloat, "CUSTOM_0" : cpswTreeGUI._ReprInt }.get(svb.getEncoding())
    if rval == None:
      if svb.getNelms() > 1 and not svb.getEnum() and 8 == svb.getSizeBits():
         # caller may try something else
         return None
      else:
         return cpswTreeGUI._ReprInt
    return rval;

  def toString(self):
    return self._path.toString()

  def getNelms(self):
    return self._path.getNelms()

  def origin(self):
    return self._path.origin()

  def createVar(self):
    readOnly = False
    try:
      representation = self.guessRepr()

      if self._path.getNelms() > 1 and cpswTreeGUI._ReprString != representation:
        raise pycpsw.InterfaceNotImplementedError("Non-String arrays (ScalVal) not supported")

      # If the representation is 'Other' then this is certainly not
      # a ScalVal - but it could still be a DoubleVal.
      # If the representation is 'Float' then it could be a ScalVal for
      # which the Float representation was chosen deliberately (in yaml)
      if representation in (cpswTreeGUI._ReprOther, cpswTreeGUI._ReprFloat):
        try:
          val     = pycpsw.DoubleVal.create( self._path )
        except pycpsw.InterfaceNotImplementedError:
          val     = pycpsw.DoubleVal_RO.create( self._path )
          readOnly = True
        representation = cpswTreeGUI._ReprFloat
      else:
        try:
          val      = pycpsw.ScalVal.create( self._path )
        except pycpsw.InterfaceNotImplementedError:
          val      = pycpsw.ScalVal_RO.create( self._path )
          readOnly = True

    except pycpsw.InterfaceNotImplementedError as e:
      raise cpswTreeGUI.InterfaceNotImplemented(e.args)

    return ( val, readOnly, representation )

  def createCmd(self):
    try:
      if self._path.getNelms() > 1:
        raise pycpsw.InterfaceNotImplementedError("Arrays of commands not supported")
      cmd = pycpsw.Command.create( self._path )
    except pycpsw.InterfaceNotImplementedError as e:
      raise cpswTreeGUI.InterfaceNotImplemented(e.args)
    return cmd

  def createStream(self):
    try:
      if self._path.getNelms() > 1:
        raise pycpsw.InterfaceNotImplementedError("Arrays of Streams not supported")
      if self._path.tail().getName() == "Lcls1TimingStream":
        raise pycpsw.InterfaceNotImplementedError("Timing Stream Disabled")
      strm  = pycpsw.Stream.create( self._path )
    except pycpsw.InterfaceNotImplementedError as e:
      raise cpswTreeGUI.InterfaceNotImplemented(e.args)
    return strm
