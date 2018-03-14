#!/usr/bin/python3

import sys
import socket
import getopt
import re
import sip
sip.setapi('QString', 2)
from   PyQt4                              import QtCore, QtGui
import yaml_cpp
import signal
import array
import numpy as np
import matplotlib
matplotlib.use("Qt4Agg")
from   matplotlib.figure                  import Figure
from   matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg    as FigureCanvas
from   matplotlib.backends.backend_qt4agg import NavigationToolbar2QT as NavigationToolbar
import fixupYaml

from   cpswTreeGUICommon import InterfaceNotImplemented

class MyModel(QtCore.QAbstractItemModel):

  def __init__(self, rootPath, useEpics):
    self._app = QtCore.QCoreApplication.instance()
    if not self._app:
      self._app = QtGui.QApplication([])

    QtCore.QAbstractItemModel.__init__(self)
    self._useEpics  = useEpics
    self._poller    = Poller(1000)
    self._col0Width = 0
    self._root      = MyNode(self, ChildAdapt(rootPath.origin()) )

    self._tree      = QtGui.QTreeView()
    QtCore.QObject.connect( self._poller, QtCore.SIGNAL("_signl()"), self.update )
    self._tree.setModel( self )
    self._tree.setRootIndex( QtCore.QAbstractItemModel.createIndex( self, 0, 0, self._root ) )
    self._tree.setRootIsDecorated( True )
    self._tree.uniformRowHeights()
    self._tree.setMinimumSize(1000, 800)
    # Context Menu for Tree View
    self._tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
    self._treeMenu = QtGui.QMenu()
    if not self._useEpics:
      loadAction = QtGui.QAction("Load from file...", self)
      loadAction.triggered.connect(self.loadFromFile)
      self._treeMenu.addAction(loadAction)
    pathAction = QtGui.QAction("Copy 'Path' to clipboard...", self)
    pathAction.triggered.connect(self.copyPathToClipboard)
    self._treeMenu.addAction(pathAction)
    self._tree.customContextMenuRequested.connect(self.openMenu)

    #QtCore.QObject.connect( self._tree.selectionModel(), QtCore.SIGNAL('selectionChanged(QItemSelection, QItemSelection)'), test)
    QtCore.QObject.connect( self._tree, QtCore.SIGNAL('clicked(QModelIndex)'), test1)
    self._tree.installEventFilter( RightPressFilter() )
    self._tree.setDragEnabled(True)
    self._tree.show()

  def openMenu(self, position):
    indexes = self._tree.selectedIndexes()
    if len(indexes) > 0:
        item = indexes[0]
        if item.isValid():
            self._treeMenu.exec_(self._tree.viewport().mapToGlobal(position))

  def loadFromFile(self):
    yaml_file = QtGui.QFileDialog.getOpenFileName(None, 'Open File...', './', 'CPSW Defaults (*.yaml)')
    yaml_file = yaml_file[0] if isinstance(yaml_file, (list, tuple)) else yaml_file
    if yaml_file:
        yaml_file = str(yaml_file)
        my_node = self._tree.selectedIndexes()[0].internalPointer()
        path = my_node.buildPath()
        try:
            msg = QtGui.QMessageBox()
            msg.setIcon(QtGui.QMessageBox.Question)
            msg.setText("Are you sure you want to load the yaml file:\n{}\nat:\n {}".format(yaml_file, path))
            msg.setStandardButtons(QtGui.QMessageBox.Yes | QtGui.QMessageBox.No)
            msg.setDefaultButton(QtGui.QMessageBox.No)
            ret = msg.exec_()
            if ret == QtGui.QMessageBox.No:
                return
            path.loadConfigFromYamlFile(yaml_file)
        except Exception as ex:
            print("Error while loading config from YAML file.")
            print("Exception: ", ex)

  def copyPathToClipboard(self):
    my_node = self._tree.selectedIndexes()[0].internalPointer()
    QtGui.QApplication.clipboard().setText( my_node.getConnectionName() )

  def setCol0Width(self, width):
    self._col0Width = width

  def getCol0Width(self):
    return self._col0Width

  def headerData(self, sect, orient, role = QtCore.Qt.DisplayRole):
    if QtCore.Qt.DisplayRole == role:
      if   0 == sect:
        return "Name"
      elif 1 == sect:
        self.getTree().setColumnWidth(1, 250 )
        return "Value"
      elif 2 == sect:
        return "Description"
    return None

  def addPoll(self, callback):
    self._poller.add(callback)

  def setUpdate(self):
    self._poller.setUpdate()

  def getPollGuard(self):
    return self._poller.getGuard()

  def setRoot(self, root):
    self._root = root

  def flags(self,index):
    flags = QtCore.Qt.ItemIsEnabled
    if index.isValid():
      flags = flags | QtCore.Qt.ItemIsSelectable
      if 0 == index.column():
        flags = flags | QtCore.Qt.ItemIsDragEnabled
    return flags

#  def mimeTypes(self):
#    return ['text/plain']

  def mimeData(self,indices):
    mimedata = QtCore.QMimeData()
    mimedata.setData('text/plain', indices[0].internalPointer().buildPath().toString())
    return mimedata


  def update(self):
    # This is probably not the 'right' way to request everything to be updated
    # but it seems to work.
    #
    # https://forum.qt.io/topic/39357/solved-qabstractitemmodel-datachanged-question
    #
    # Also: any mouse movement over the treeview widget seems to result in many
    # calls to 'data' which seems unfortunate (and which is why we cache data)
    self._tree.dataChanged(QtCore.QModelIndex(), QtCore.QModelIndex())

  def getTree(self):
    return self._tree

  def rowCount(self, mindex):
    if mindex.isValid():
      node = mindex.internalPointer()
      return node.childCount(mindex)
    return self._root.childCount(QtCore.QModelIndex())

  def columnCount(self, mindex):
    return 3

  def data(self, in_index, role):
    if not in_index.isValid():
      return None
    node = in_index.internalPointer()
    if role==QtCore.Qt.DisplayRole:
      return node.data(in_index.column())
    else:
      return None

  def index(self, in_row, in_col, in_parent):
    if None == in_parent or not in_parent.isValid():
      parent = self._root
    else:
      parent = in_parent.internalPointer()

    if not QtCore.QAbstractItemModel.hasIndex(self, in_row, in_col, in_parent):
      return QtCore.QModelIndex()

    child = parent.child(in_row, in_parent)
    if child != None:
      idx = QtCore.QAbstractItemModel.createIndex(self, in_row, in_col, child)
      return idx
    else:
      return QtCore.QModelIndex()

  def parent(self, in_index):
    if in_index.isValid():
      parent = in_index.internalPointer().parent()
      if parent:
        return QtCore.QAbstractItemModel.createIndex(self, parent.row(), 0, parent )
    return QtCore.QModelIndex()

# Action which emits itself
class ActAction(QtGui.QAction):

  _signal = QtCore.pyqtSignal(QtGui.QAction)

  def __init__(self, name, parent=None):
    QtGui.QAction.__init__(self, name, parent)
    QtCore.QObject.connect(self, QtCore.SIGNAL("triggered()"), self)

  def __call__(self):
    self._signal.emit(self)

  def connect(self, slot):
    self._signal.connect( slot )

class EnumButt(QtGui.QPushButton):
  def __init__(self, var, parent = None):
    QtGui.QPushButton.__init__(self, parent)
    self._var = var
    if not var.isReadOnly():
      menu          = QtGui.QMenu()
      for item in self._var.getEnumItems():
        a = ActAction( item[0], self )
        a.connect( self.activated )
        menu.addAction( a )
      self.setMenu( menu )

  def activated(self, act):
    self._var.setVal( str(act.text()) )

  def isModified(self):
    return False

# Validate text input for compatibility with a scalar value
class ScalValidator(QtGui.QValidator):
  def __init__(self, scalWid, parent=None):
    QtGui.QValidator.__init__(self, parent)
    nb            = scalWid.getVar().getSizeBits()
    self._scalWid = scalWid
    if scalWid.getVar().isSigned():
      self._lo = - (1<<(nb-1))
      self._hi = (1<<(nb-1)) - 1
    else:
      self._hi = (1<<nb) - 1
      self._lo = 0

  def validate(self, s, p):
    if s=='' or s=='0x' or s=='0X' or s=='0b' or s=='0B' or s=='0o' or s=='0O':
      return (QtGui.QValidator.Intermediate, s, p)
    try:
      i = int(s, 0)
    except ValueError:
      return (QtGui.QValidator.Invalid, s, p)
    if i < self._lo or i > self._hi:
      return (QtGui.QValidator.Invalid, s, p)
    return (QtGui.QValidator.Acceptable, s, p)

  # restore the original text
  def fixup(self, s):
    self._scalWid.restoreTxt()

class IfObj(QtCore.QObject):
  def __init__(self, commHdl, parent=None):
    QtCore.QObject.__init__(self, parent)
    self._widget  = None
    self._commHdl = commHdl

  def setWidget(self, widget):
    self._widget = widget

  def getWidget(self):
    return self._widget

  def commHdl(self):
    return self._commHdl;

  def getDescription(self):
    return self._commHdl.getDescription()

  def getConnectionName(self):
    return self._commHdl.getConnectionName()

class LineEditWrapper(QtGui.QLineEdit):
  def __init__(self, parent=None):
    QtGui.QLineEdit.__init__(self, parent)

  def setText(self, txt):
    QtGui.QLineEdit.setText(self, txt)
    self.home( False )

class ScalVal(IfObj):

  _sig = QtCore.pyqtSignal(object)

  def __init__(self, path, node, widget_index ):
    IfObj.__init__(self, path.createVar())

    self._node = node
    readOnly   = self.commHdl().isReadOnly()
    nelms      = path.getNelms()

    if self.commHdl().getRepr() == VarAdapt._ReprString:
      self._string = bytearray(nelms)
    else:
      self._string = None

    if None != self.commHdl().getEnumItems():
      widgt       = EnumButt( self.commHdl() )
    else:
      widgt       = LineEditWrapper()
      widgt.setReadOnly( readOnly )
      widgt.setFrame( not readOnly )
      if not readOnly:
        if not self.commHdl().isString():
          if self.commHdl().isFloat():
            validator = QtGui.QDoubleValidator()
          else:
            validator = ScalValidator( self )
          widgt.setValidator( validator )
        # returnPressed is only emitted if the string passes validation
        QtCore.QObject.connect( widgt, QtCore.SIGNAL("returnPressed()"),   self.updateVal )
        # editingFinished is emitted after returnPressed or lost focus (with valid string)
        # if we lose focus w/o return being hit then we restore the original string
        QtCore.QObject.connect( widgt, QtCore.SIGNAL("editingFinished()"), self.restoreTxt  )
    self.setWidget(widgt)
    self._cachedVal = None;
    self.updateTxt( self._cachedVal )
    self._sig.connect( self.updateTxt )
    if self.commHdl().needPoll():
      node._model.addPoll( self )
    self.commHdl().setWidget( self )

  def getVar(self):
    return self.commHdl()

  def callbackIssuer(self):
    return self.commHdl().toString()

  # read value, falling back to retrieving numerical enum entries
  # if the ScalVal cannot map back (ConversionError)
  def readValue(self):
    # We probably should not call 'isVisible()' from this thread
	# hopefully nothing really bad happens. Use because our demo
	# has a really slow network connection...
    if self.getWidget().isVisible():
      self.commHdl().getValAsync()

  # restore text to state prior to user starting edit operation
  @QtCore.pyqtSlot()
  def restoreTxt(self):
    w = self.getWidget()
    if w.isModified():
      # lost focus; restore
      self.updateTxt( self._cachedVal )
      w.setModified(False)

  # read ScalVal and update text -- unless the user is in the process of editing
  #
  # THIS IS EXECUTED IN THE EVENT LOOP BY THE MAIN THREAD
  @QtCore.pyqtSlot(int)
  def updateTxt(self, newVal):
    if newVal == None:
      strVal = "???"
    else:
      # assume they want signed numbers in decimal
      if self.commHdl().isFloat() or self.commHdl().isSigned() or self.commHdl().getEnumItems() or self.commHdl().isString():
        strVal = '{}'.format( newVal )
      else:
        w = int((self.commHdl().getSizeBits() + 3)/4) # leading 0x goes into width
        strVal = '0x{:0{}x}'.format( newVal, w )
    self.getWidget().setText( strVal )

  # write ScalVal from user text input
  @QtCore.pyqtSlot()
  def updateVal(self):
    self.getWidget().setModified(False)
    txt = str(self.getWidget().text())
    if self.commHdl().isString():
      val  = bytearray(txt, 'ascii')
      fidx = 0
      tidx = len(val)
      slen = len(self._string)
      if tidx < slen:
        val.append(0)
      else:
        tidx = slen - 1
    else:
      if self.commHdl().isFloat():
        val = float(txt)
      else:
        val  = int(txt, 0)
      fidx = -1
      tidx = -1
    self.commHdl().setVal( val, fidx, tidx )

  # update widget from changed ScalVal
  def asyncUpdateWidget(self, value):
#! Deal with conversion errors by forcing conversion
#      except pycpsw.ConversionError:
#        if None == self.commHdl().getEnumItems():
#          raise
#        v = '{}'.format( self.commHdl().getVal(forceNumeric=True) ) # force Numeric
#        return v
    if self.commHdl().isString():
      value = bytearray(value).decode('ascii')
    if self._cachedVal != value:
      # send value as a signal - this is properly sent from the
      # polling thread to the main thread's event loop
      if not self.getWidget().isModified():
        self._sig.emit(value)
      self._cachedVal = value
      self._node._model.setUpdate()


  # THIS IS EXECUTED BY THE POLLING THREAD
  def __call__(self):
    self.readValue()

# Create a push-button for nodes with a cpsw Command interface
class Cmd(IfObj):
  def __init__(self, path, node, widget_index ):
    IfObj.__init__(self, path.createCmd())
    button    = QtGui.QPushButton("Execute")
    QtCore.QObject.connect(button, QtCore.SIGNAL('clicked(bool)'), self)
    self.setWidget( button )

  def __call__(self):
    self.commHdl().execute()
    return False

# Mutex guard (QMutexLocker is not useful since lifetime of python
# object does not necessarily end when it goes out of scope)
class Guard(object):
  def __init__(self, mutex):
    object.__init__(self)
    self._mtx = mutex

  def __enter__(self):
    self._mtx.lock()

  def __exit__(self, exc_type, exc_value, traceback):
    self._mtx.unlock()
    return False

# Thread which polls all registered callables periodically
# registration (add) and polling are mutex protected
class Poller(QtCore.QThread):

  _signl  = QtCore.pyqtSignal()

  def __init__(self, pollMs):
    QtCore.QThread.__init__(self)
    self._pollMs = pollMs
    self._mtx    = QtCore.QMutex(QtCore.QMutex.Recursive)
    self._list   = []
    self.start()
    self._update = True

  def setUpdate(self):
    with Guard(self._mtx):
      self._update = True

  def run(self):
    while True:
      QtCore.QThread.msleep(self._pollMs)
      for el in self._list:
        with Guard(self._mtx):
          el()
      with Guard(self._mtx):
        if self._update:
          self._signl.emit()
        self._update = False

  def add(self, el):
    with Guard(self._mtx):
      self._list.append(el)

  def getGuard(self):
    return Guard(self._mtx)

# Adapter to the Model
class MyNode(object):
  def __init__(self, model, child, name = None, row = 0, parent = None):
    object.__init__(self)
    self._children = None
    self._model    = model
    self._child    = child
    if not name:
      name = child.getName()
    print("Making node with name ", name)
    self._name     = name
    self._desc     = None
    self._hub      = child.isHub()
    self._row      = row
    self._parent   = parent
    self._mtx      = QtCore.QMutex(QtCore.QMutex.Recursive)
    self._ifObj    = None

  def setIfObj(self, ifObj):
    if self._ifObj != None:
      raise
    self._ifObj = ifObj

  def __getChildren(self, mindex):
    return self._children

  def getNodeName(self):
    return self._name

  def getModel(self):
    return self._model

  def getChild(self):
    return self._child

  def getConnectionName(self):
    if self._ifObj:
      return self._ifObj.getConnectionName()
    else:
      return self.buildPath().toString()

  def buildPath(self):
    l = list()
    n = self
    p = n.parent()
    print("buildPath")
    while None != p:
      print("haveParent")
      l.insert(0, n.getNodeName())
      n = p
      p = p.parent()
    pnam = '/'.join(l)
    if None == pnam:
    	print("buildPath pnam NONE")
    else:
    	print("buildPath pnam", pnam)
    path = n._child.findByName( pnam )
    if None == path:
      print("buildPath path NONE")
    else:
      print("buildPath path", path.toString())
    return path

  def addChild(self, child):
    if None == self._children:
      self._children = []
    self._children.append(child)

  # build children list once, then
  # hack 'getChildren' to use __getChildren
  def getChildren(self, mindex):
    if None == self._children:
      self._children   = []
    tree             = self._model.getTree()
    fm               = tree.fontMetrics()
    self.getChildren = self.__getChildren
    maxWidth         = 0
    if None != self._hub:
      row  = 0
      # for all children
      path = self.buildPath()
      for child in self._hub.getChildren():
        childHub = child.isHub()
        nelms    = child.getNelms()
        leafmax  = 16 # max. to expand leaf children
        nexpand  = nelms
        if nelms > 1:
          # could be a string -- in this case we wouldn't want to expand
          if not childHub:
            if VarAdapt._ReprString == path.findByName( child.getName() ).guessRepr():
              leafmax = 0
          childNames = list()
          if childHub or nelms <= leafmax:
            # Hub- and small leaf- arrays will be expanded
            for i in range(0,nexpand):
              childNames.append( "{}[{}]".format(child.getName(),i) )
          else:
            # big leaf arrays receive name with full index range (so the user can see)
            childNames = [ '{}[0-{}]'.format( child.getName(), nelms - 1 ) ]
        else:
          # non-array name is just the child's name (w/o indices)
          childNames = [ child.getName() ]
        for childName in childNames:
          # create the model Node
          childNode  = MyNode( self._model, child, childName, row, self )
          # calculate the displayed size
          childWidth = fm.width( childName )
          if childWidth > maxWidth:
            maxWidth = childWidth
          self.addChild( childNode )
          row += 1
          if None == childHub:
            widget_index = self._model.index(row - 1, 1, mindex)
            childPath    = path.findByName( childName )
            # Check
            IFs = [ ScalVal, Cmd, Stream ]
            for IF in IFs:
              try:
                ifObj = IF( childPath, childNode, widget_index )
                widgt = ifObj.getWidget()
                childNode.setIfObj( ifObj )
                break
              except InterfaceNotImplemented:
                pass
            else:
              if nelms > 1:
                widgt = QtGui.QLabel("<Arrays or Interface not supported>")
              else:
                widgt = QtGui.QLabel("<No known Interface supported>")
            tree.setIndexWidget( widget_index, widgt )
      # calculate necessary space for indentation
      depth = 0
      p     = self
      while p:
        depth += 1
        p = p.parent()
      maxWidth += depth*tree.indentation()+10 # don't know where this extra offset comes from...
      if maxWidth > self._model.getCol0Width():
        self._model.setCol0Width( maxWidth )
        tree.setColumnWidth(0, maxWidth )
    return self._children

  def childCount(self, mindex):
    return len(self.getChildren(mindex))

  def data(self, col):
    if col == 0:
      return self.getNodeName()
    elif col == 1:
        #  use index widgets to display
        return None
    elif col == 2:
        if None == self._desc:
          if None == self._ifObj:
            self._desc = self.getChild().getStaticDescription()
          else:
            self._desc = self._ifObj.getDescription()
        if None == self._desc:
          return "" #Not yet known
        return self._desc
    else:
        return None

  def child(self, idx, mindex):
    children = self.getChildren(mindex)
    if idx >= 0 and idx < len( children ):
      return children[idx]
    else:
      return None

  def row(self):
    return self._row

  def parent(self):
    return self._parent

# test code
@QtCore.pyqtSlot("QItemSelection, QItemSelection")
def test(selected, deselected):
  print("XXX")
  print(selected)

@QtCore.pyqtSlot("QModelIndex")
def test1(index):
  print("ACTIVETED")
  print("ROW {}, COL {}".format(index.row(), index.column()))
  if index.column() == 0:
    print(index.internalPointer().getNodeName())
    for c in index.internalPointer().getChildren(None):
      print("has child ", c.getNodeName())

class Stream(IfObj):

  _bufs    = []
  _strms   = []

  def __init__(self, path, node, widget_index):
    IfObj.__init__(self, path.createStream())
    #self._buf   = array.array('h',range(0,16384))
    self._buf    = np.empty(16384,'int16')
    self._buf.fill(0)
    self._fig    = Figure([2,2])
    self._canvas = FigureCanvas( self._fig )
    toolbar      = NavigationToolbar( self._canvas, None )
    box          = QtGui.QWidget()
    layout       = QtGui.QVBoxLayout()
    layout.addWidget(self._canvas )
    layout.addWidget( toolbar )
    box.setLayout( layout )
    self._axes   = self._fig.add_subplot(111)
    # create a child node so that we can collapse this widget...
    model        = node.getModel()
    widgetNode   = MyNode( model, node.getChild(), None, 0, node )
    node.addChild( widgetNode )
    plot_index = model.index(0, 1, widget_index)
    model.getTree().setIndexWidget( plot_index, box )
    # our regular widget is just empty
    self.setWidget( QtGui.QLabel("") )
    Stream._bufs.append( self._buf )
    Stream._strms.append( self )
    self.plot( 100 )
    self.commHdl().setWidget( self )

  def getCanvas(self):
    return self._canvas

  def getBuf(self):
    return self._buf

  def plot(self, bufsz):
    self._axes.cla()
    self._axes.plot( range(0,bufsz), self._buf[0:bufsz] )
    self._canvas.draw()

  def gb(self):
    return self._buf

class RightPressFilter(QtCore.QObject):
  def __init__(self):
    QtCore.QObject.__init__(self)

  def eventFilter(self, obj, event):
    print("EVENTFILTER")
    if event.type() in (QtCore.QEvent.MouseButtonPress):
      if event.button() == QtCore.Qt.RightButton:
        print("RIGHT BUTTON")
        return True
    return super(RighPressFilter, self).eventFilter(obj, event)

def main1(oargs):

  useTcp        = False
  srpV2         = False
  noStreams     = False
  ipAddr        = None
  disableDepack = False
  portMaps      = []
  backDoor      = False
  strHeuristic  = True
  useEpics      = False

  ( opts, args ) = getopt.getopt(
                      oargs[1:],
                      "ha:TBs",
                      ["backdoor",
                       "no-streams",
                       "no-string-heuristics",
                       "tcp",
                       "mapPort=",
                       "ipAddress=",
                       "useEpics",
                       "help"] )

  for opt in opts:
    if opt[0] in ('--useEpics'):
      useEpics = True

  for opt in opts:
    if   opt[0] in ('-a', '--ipAddress'):
      ipAddr        = socket.gethostbyname( opt[1] )
    elif opt[0] in ('-T', '--tcp'):
      useTcp        = True
    elif opt[0] in ('-B', '--backdoor'):
      backDoor      = True
    elif opt[0] in ('-s', '--no-streams'):
      noStreams     = True
    elif opt[0] in ('--no-string-heuristics'):
      strHeuristic  = False
    elif opt[0] in ('--mapPort'):
      opta = opt[1].split(':')
      if len(opta) != 2:
        raise RuntimeError('--mapPort option requires <fromPort>:<toPort> argument')
      portMaps.append( [ int(num) for num in opta ] )
    elif opt[0] in ('-h', '--help'):
      if not useEpics:
        print("Usage: {} [-a <ip_addr>] [-TsBh] [--<long-opt>] yaml_file [root_node [inc_dir_path]]".format(oargs[0]))
        print()
        print("          -a <ip_addr>         : patch IP address in YAML")
        print("          -B                   : see '--backdoor' -- EXPERT USE ONLY")
        print("          -T                   : use TCP transport (requires rssi bridge connection)")
        print("          -s                   : disable all streams")
        print("          -h                   : this message")
        print()
        print("          yaml_file            : top-level YAML file to load (required)")
        print("          root_node            : YAML root node (default: \"root\")")
        print("          inc_dir_path         : directory where to look for included YAML files")
        print("                                 default: directory where 'yaml_file' is located")
        print()
        print("  Long Options                 :")
        print("      --ipAddress <addr>       : same as -a")
        print("      --tcp                    : same as -T")
        print("      --help                   : same as -h")
        print("      --no-streams             : same as -s")
        print("      --mapPort <f>:<t>        : patch UDP/TCP port '<f>' to port '<t>' in YAML")
        print("                                 i.e., if a port is 'f' in YAML then change it")
        print("                                 to 't'")
        print("      --no-string-heuristics   : disable some tests which guess if a value is a")
        print("                                 string. Some slow devices may take a long time")
        print("                                 to respond. If this annoys you try this option.")
        print("      --backdoor               : patch YAML for \"backdoor\" access; implies '-s' and")
        print("                                 many features are altered: no RSSI/depacketizer/TDESTMux,")
        print("                                 SRP protocol is altered to V2 and only one port is enabled.")
        print("                                 By default this is port 8193 if --tcp is given and 8192")
        print("                                 otherwise. You still need to specify --tcp when using")
        print("                                 the rssi_bridge. If you need a non-standard port then")
        print("                                 use '--mapPort'")
        print("      --useEpics               : Use EPICS CA to connect; more info with --help --useEpics")
      else:
        print("Usage: {} --useEpics [--help] yaml_file [root_node]".format(oargs[0]))
        print()
        print("                               : Use EPICS CA to connect instead of CPSW. A proper IOC must")
        print("                                 be running; most-likely it is an IOC running YCPSWASYN.")
        print("                                 Such an IOC produces a dump of the device hierarchy from")
        print("                                 which hashed PV names can be computed. This hierarchy is")
        print("                                 in YAML format (but different from the CPSW YAML file).")
        print("                                 Use this YAML file to build the GUI.")

      return

  if not strHeuristic:
    StringHeuristics.disable()

  if backDoor:
    srpV2         = True
    noStreams     = True
    disableDepack = True
    if len(portMaps) > 1:
      portMaps = [ portMaps[0] ]
    if len(portMaps) == 1:
      if portMaps[0][1] != 0:
        portMaps.append( [ portMaps[0][1], 0 ] )
    else:
      portMaps = [ [ { True: 8193, False: 8192 }.get( useTcp ), 0 ] ]

  if len(args) > 0:
    yamlFile = args[0]
  else:
    if useEpics:
      print("usage: {} [options] <yaml_file> [yaml_root_node_name='root' ]".format(oargs[0]))
    else:
      print("usage: {} [options] <yaml_file> [yaml_root_node_name='root' [yaml_inc_dir=''] ]".format(oargs[0]))
    sys.exit(1)
  if len(args) > 1:
    yamlRoot = args[1]
  else:
    yamlRoot = "root"
  if len(args) > 2:
    yamlIncDir = args[2]
  else:
    yamlIncDir = None

  if not useEpics:
    fixYaml       = fixupYaml.Fixup(
                      useTcp        = useTcp,
                      srpV2         = srpV2,
                      noStreams     = noStreams,
                      ipAddr        = ipAddr,
                      disableDepack = disableDepack,
                      portMaps      = portMaps
                    )
  else:
    fixYaml    = None
    yamlIncDir = None
  app      = QtGui.QApplication(args)
  modl, rp = startGUI(yamlFile, yamlRoot, fixYaml, yamlIncDir, useEpics)
  return (modl, app, rp)

def startGUI(yamlFile, yamlRoot, fixYaml=None, yamlIncDir=None, useEpics=False):
  if useEpics:
    from   caAdapt   import VarAdapt, CmdAdapt, StreamAdapt, PathAdapt, ChildAdapt
  else:
    from   cpswAdapt import VarAdapt, CmdAdapt, StreamAdapt, PathAdapt, ChildAdapt
  global VarAdapt
  global CmdAdapt
  global StreamAdapt
  global PathAdapt
  global ChildAdapt
  rp = PathAdapt.loadYamlFile(
              yamlFile,
              yamlRoot,
              yamlIncDir,
              fixYaml)
  signal.signal( signal.SIGINT, signal.SIG_DFL )
  modl  = MyModel( rp, useEpics )
  return (modl, rp)

def main():
  return main2(sys.argv)

def main2(args):
  got = main1(args)
  if got != None:
    (m,app,root) = got
    sys.exit( app.exec_() )

if __name__ == '__main__':
  main()
