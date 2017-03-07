#!/usr/bin/python3 -i

import sys
from PyQt4 import QtCore, QtGui
import pycpsw
import signal
import array

class MyModel(QtCore.QAbstractItemModel):

  def __init__(self):
    QtCore.QAbstractItemModel.__init__(self)
    self._poller    = Poller(1000)
    self._col0Width = 0

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

  def getPollGuard(self):
    return self._poller.getGuard()

  def setRoot(self, root):
    self._root = root

  def setTree(self, treeview):
    self._tree = treeview
    QtCore.QObject.connect( self._poller, QtCore.SIGNAL("_signl()"), self.update )

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
      return mindex.internalPointer().childCount(mindex)
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
    if not in_parent or not in_parent.isValid():
      parent = self._root
    else:
      parent = in_parent.internalPointer()

    if not QtCore.QAbstractItemModel.hasIndex(self, in_row, in_col, in_parent):
      return QtCore.QModelIndex()

    child = parent.child(in_row, in_parent)
    if child:
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
  def __init__(self, scalVal, readOnly, parent = None):
    QtGui.QPushButton.__init__(self, parent)
    self._scalVal = scalVal
    if not readOnly:
      menu          = QtGui.QMenu()
      for item in self._scalVal.getEnum().getItems():
        a = ActAction( item[0], self )
        a.connect( self.activated )
        menu.addAction( a )
      self.setMenu( menu )

  def activated(self, act):
    self._scalVal.setVal( act.text() )

  def isModified(self):
    return False

# Validate text input for compatibility with a scalar value
class ScalValidator(QtGui.QValidator):
  def __init__(self, scalVal, parent=None):
    QtGui.QValidator.__init__(self, parent)
    nb            = scalVal._val.getSizeBits()
    self._scalVal = scalVal
    if scalVal._val.isSigned():
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
    self._scalVal.restoreTxt()

class IfObj(QtCore.QObject):
  def __init__(self, parent=None):
    QtCore.QObject.__init__(self, parent)
    
  def setWidget(self, widget):
    self._widget = widget
  
  def getWidget(self):
    return self._widget

class ScalVal(IfObj):

  _sig = QtCore.pyqtSignal(object)

  def __init__(self, path, node, widget_index ):
    IfObj.__init__(self)
    self._node        = node
    readOnly = False
    print('creating ' + path.toString())
    try:
      self._val    = pycpsw.ScalVal.create( path )
    except pycpsw.InterfaceNotImplementedError:
      self._val    = pycpsw.ScalVal_RO.create( path )
      readOnly     = True

    self._enum     = self._val.getEnum()
    nelms          = path.getNelms()

    # use heuristics to detect an ascii string
    if self._val.getEncoding() == 'ASCII' or (nelms > 1 and not self._enum and 8 == self._val.getSizeBits()):
      self._string = bytearray(nelms) 
    else:
      self._string = 0

    if nelms > 1 and not self._string:
      raise pycpsw.InterfaceNotImplementedError("Non-String arrays (ScalVal) not supported")
    
    if self._enum:
      widgt       = EnumButt( self._val, readOnly )
    else:
      widgt       = QtGui.QLineEdit()
      widgt.setReadOnly( readOnly )
      widgt.setFrame( not readOnly )
      if not readOnly:
        if not self._string:
          validator = ScalValidator( self )
          widgt.setValidator( validator )
        # returnPressed is only emitted if the string passes validation
        QtCore.QObject.connect( widgt, QtCore.SIGNAL("returnPressed()"),   self.updateVal )
        # editingFinished is emitted after returnPressed or lost focus (with valid string)
        # if we lose focus w/o return being hit then we restore the original string
        QtCore.QObject.connect( widgt, QtCore.SIGNAL("editingFinished()"), self.restoreTxt  )
    self.setWidget(widgt)
    self._cachedVal = self.readValue()
    self.updateTxt( self._cachedVal )
    node._model.addPoll( self )
    self._sig.connect( self.updateTxt )
    # Access is slow because it's synchronous. For speedup CPSW would have to
    # implement asynchronous I/O (but that would not really be its job; better
    # to use tools which already do that such as EPICS).

  # write ScalVal from user text input
  @QtCore.pyqtSlot()
  def updateVal(self):
    self.getWidget().setModified(False)
    txt = self.getWidget().text()
    if self._string:
      val  = bytearray(txt, 'ascii')
      fidx = 0
      tidx = len(val)
      slen = len(self._string)
      if tidx < slen:
        val.append(0)
      else:
        tidx = slen - 1
    else:
      val  = int(txt, 0)
      fidx = -1
      tidx = -1
    self._val.setVal( val, fidx, tidx )

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
    # don't update while someone is editing
    if self.getWidget().isModified():
      return
    # assume they want signed numbers in decimal
    if self._val.isSigned() or self._enum or self._string:
      strVal = '{}'.format( newVal )
    else:
      w = int((self._val.getSizeBits() + 3)/4) # leading 0x goes into width
      strVal = '0x{:0{}x}'.format( newVal, w )
    self.getWidget().setText( strVal )

  # read value, falling back to retrieving numerical enum entries
  # if the ScalVal cannot map back (ConversionError)
  def readValue(self):
    if self._string:
      self._val.getVal(self._string)
      try:
        return self._string[0:self._string.find(0)].decode('ascii')
      except UnicodeDecodeError:
        return "<unable to decode utf-8>"
    else:
      try:
        v = self._val.getVal()
        return v
      except pycpsw.ConversionError:
        if not self._enum:
          raise
        v = '{}'.format( self._val.getVal(forceNumeric=True) ) # force Numeric
        return v 
      except pycpsw.BadStatusError:
        print( self._val.getPath() )
        raise

  # THIS IS EXECUTED BY THE POLLING THREAD
  def __call__(self):
    # We probably should not call 'isVisible()' from this thread
	# hopefully nothing really bad happens. Use because our demo
	# has a really slow network connection...
    if not self.getWidget().isVisible():
      return False
    value = self.readValue()
    if self._cachedVal != value:
      # send value as a signal - this is properly sent from the 
      # polling thread to the main thread's event loop
      self._sig.emit(value)
      self._cachedVal = value
      return True
    return False

# Create a push-button for nodes with a cpsw Command interface
class Cmd(IfObj):
  def __init__(self, path, node, widget_index ):
    IfObj.__init__(self)
    if path.getNelms() > 1:
      raise pycpsw.InterfaceNotImplementedError("Arrays of commands not supported")
    self._cmd = pycpsw.Command.create( path )
    button    = QtGui.QPushButton("Execute")
    QtCore.QObject.connect(button, QtCore.SIGNAL('clicked(bool)'), self)
    self.setWidget( button )
  
  def __call__(self):
    self._cmd.execute()
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
    
# Thread which increments a ScalVal periodically
class Counter(QtCore.QThread):
  def __init__(self, model, path, sleepMs):
    QtCore.QThread.__init__(self)
    self._val     = pycpsw.ScalVal.create(path)
    self._model   = model
    self._sleepMs = sleepMs
    self.start()

  def run(self):
    while True:
      QtCore.QThread.msleep(self._sleepMs)
      with self._model.getPollGuard():
        self._val.setVal( self._val.getVal() + 1 )

# Thread which polls all registered callables periodically
# registration (add) and polling are mutex protected
class Poller(QtCore.QThread):

  _signl  = QtCore.pyqtSignal()

  def __init__(self, pollMs):
    QtCore.QThread.__init__(self)
    self._pollMs = pollMs
    self._mtx    = QtCore.QMutex()
    self._list   = []
    self.start()

  def run(self):
    while True:
      QtCore.QThread.msleep(self._pollMs)
      update = False
      for el in self._list:
        with Guard(self._mtx):
          if el():
            update = True
      if update:
        self._signl.emit()

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
    self._name     = name
    self._desc     = child.getDescription()
    self._hub      = child.isHub()
    self._row      = row
    self._parent   = parent
    self._mtx      = QtCore.QMutex()

  def __getChildren(self, mindex):
    return self._children

  def __buildPath(self, node, p):
    parent = node.parent()
    if parent:
      self.__buildPath(parent, p)
    else:
      # must be the root
      p = pycpsw.Path.create(self._child)
    p.findByName(self.getNodeName())

  def getNodeName(self):
    return self._name

  def buildPath(self):
    l = list()
    n = self
    p = n.parent()
    while None != p:
      l.insert(0, n.getNodeName())
      n = p
      p = p.parent()
    pnam = '/'.join(l)
    path = n._child.findByName( pnam )
    return path

  # build children list once, then
  # hack 'getChildren' to use __getChildren
  def getChildren(self, mindex):
    self._children   = []
    tree             = self._model.getTree()
    fm               = tree.fontMetrics()
    self.getChildren = self.__getChildren
    maxWidth         = 0
    if None != self._hub:
      row = 0
      # for all children
      for child in self._hub.getChildren():
        childHub = child.isHub()
        nelms    = child.getNelms()
        if nelms > 1:
          if childHub:
            # Hub arrays will be expanded
            childName = child.getName() + "[0]"
          else:
            # leaf arrays receive name with full index range (so the user can see)
            childName = '{}[0-{}]'.format( child.getName(), nelms - 1 )
        else:
          # non-array name is just the child's name (w/o indices)
          childName = child.getName()
        # create the model Node
        childNode  = MyNode( self._model, child, childName, row, self )
        # calculate the displayed size
        childWidth = fm.width( childName )
        if childWidth > maxWidth:
          maxWidth = childWidth
        self._children.append( childNode )
        row += 1
        if None == childHub:
          widget_index = self._model.index(row - 1, 1, mindex)
          # build a Path that leads here
          path = childNode.buildPath()
          # Check 
          for IF in [ Cmd, ScalVal ]:
            try:
              widgt = IF(path, childNode, widget_index).getWidget()
              break
            except pycpsw.InterfaceNotImplementedError:
              pass
          else:
            if nelms > 1:
            	widgt = QtGui.QLabel("<Arrays or Interface not supported>")
            else:
            	widgt = QtGui.QLabel("<No known Interface supported>")
          tree.setIndexWidget( widget_index, widgt )
        else:
          # flatten out array of hubs
          for i in range(1, child.getNelms()):
            childName = '{}[{}]'.format(child.getName(), i)
            childNode = MyNode( self._model, child, childName, row, self )
            self._children.append( childNode )
            row += 1
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

class Stream(QtCore.QThread):
  def __init__(self, path):
    QtCore.QThread.__init__(self)
    self._strm = pycpsw.Stream.create(path)
    self._buf  = array.array('h',range(0,16384))
    self.start()

  def run(self):
    got = self._strm.read(self._buf)
    print('Got {} items', got)
    print(self._buf[0:20])

def main():
  signal.signal( signal.SIGINT, signal.SIG_DFL )
  app = QtGui.QApplication(sys.argv)

  model = MyModel()

  if len(sys.argv) > 1:
    yamlFile = sys.argv[1]
  else:
    print("usage: {} <yaml_file> [yaml_root_node_name='root' [yaml_inc_dir=''] ]".format(sys.argv[0])) 
    sys.exit(1)
  if len(sys.argv) > 2:
    yamlRoot = sys.argv[2]
  else:
    yamlRoot = "root"
  if len(sys.argv) > 3:
    yamlIncDir = sys.argv[3]
  else:
    yamlIncDir = ""
  h    = pycpsw.Path.loadYamlFile(yamlFile, yamlRoot, yamlIncDir).origin()
  print(h)
  root = MyNode(model, h)

  #try:
  #strm = Stream(h.findByName("Stream0"))
  #except:
  #  print("Stream NOT created")

  model.setRoot(root)
  v = QtGui.QTreeView()
  model.setTree(v)
  v.setModel( model )
  v.setRootIndex( QtCore.QAbstractItemModel.createIndex(model, 0, 0, root) )
  v.setRootIsDecorated( True )

  try:
    counter = Counter( model, pycpsw.Path.create( h ).findByName("mmio/val"), 3000 )
  except pycpsw.NotFoundError:
    print("mmio/val not found -- not creating a counter")
  v.uniformRowHeights()
  v.setMinimumSize(700, 250)

  #QtCore.QObject.connect(v.selectionModel(), QtCore.SIGNAL('selectionChanged(QItemSelection, QItemSelection)'), test)
  v.show()
  sys.exit(app.exec_())

if __name__ == '__main__':
  main()
