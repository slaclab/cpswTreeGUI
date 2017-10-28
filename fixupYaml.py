import yaml_cpp
import pycpsw

class Fixup(pycpsw.YamlFixup):
  def __init__(self, ipAddr=None, noStreams=False, srpV2=False, useTcp=False, disableDepack=False):
    pycpsw.YamlFixup.__init__(self)
    self._noStreams     = noStreams
    self._srpV2         = srpV2
    self._useTcp        = useTcp
    self._ipAddr        = ipAddr
    self._disableDepack = disableDepack

  def ok(self,node):
    return node != None and node.IsDefined()

  def edit(self, node, l):
    cl = node["class"]
    if self.ok(cl) and cl.Scalar() == "NetIODev":
      if None != self._ipAddr:
        ip = self.find(node, "ipAddr")
        if not self.ok(ip):
          raise RuntimeError("No ipAddr node found")
        print("Fixing IP address; setting to {}\n".format(self._ipAddr))
        ip.set( self._ipAddr )

      if not self._useTcp and not self._noStreams and not self._srpV2 and not self._disableDepack:
        return
  
      children = node["children"]
      if not self.ok(children):
        raise RuntimeError("No NetIODev children found")

      for childit in children:
        #print("Checking {}\n".format(childit.first.Scalar()))
        child = childit.second
        at  = self.find(child,"at")
        if self._noStreams or self._srpV2 or self._disableDepack:
          got = self.findWithPath(at,   "SRP/protocolVersion")
          if None != got:
            (srp, path, parent) = got
            path.insert(0, childit.first.Scalar())
            if self._noStreams and srp.Scalar() == "SRP_UDP_NONE":
              child["instantiate"].set("False")
              print("SRP Node found: {} {} -- disabling\n".format( "/".join(path), srp.Scalar()))
            else:
              if self._srpV2 and srp.Scalar() == "SRP_UDP_V3":
                print("SRP Node found: {} {} -- changing to SRP_UDP_V2\n".format( "/".join(path), srp.Scalar()))
                srp.set("SRP_UDP_V2")
              if self._disableDepack:
                got = self.findWithPath(at, "depack")
                if None != got:
                  (node, path, parent) = got
                  path.insert(0, childit.first.Scalar())
                  print("depack found: {} -- disabling\n".format( "/".join(path)))
                  parent.remove("depack")
                got = self.findWithPath(at, "TDESTMux")
                if None != got:
                  (node, path, parent) = got
                  path.insert(0, childit.first.Scalar())
                  print("TDESTMux found: {} -- disabling\n".format( "/".join(path)))
                  parent.remove("TDESTMux")
          else:
            #print("Non-SRP Node found: {}\n".format( "/".join(l) ))
            pass
        if self._useTcp:
          got = self.findWithPath(at, "UDP")
          if None != got:
            (udp, path, parent) = got
            path.insert(0, childit.first.Scalar())
            prt = self.find(udp, "port")
          else:
            prt = None
          if self.ok(prt):
            for x in parent:
              if x.first.Scalar() == "UDP":
                print("UDP Node found: {} -- changing to TCP\n".format( "/".join(path) ))
                x.first.set("TCP")
                break
          else:
            #print("Non-UDP Node found: {}\n".format( "/".join(l) ))
            pass

  def trav(self, node, l=[]):
    if node.IsMap():
      self.edit(node, l)
      for it in node:
        l.append(it.first.Scalar())
        self.trav(it.second)
        l.pop()

  def find(self, node, name):
    res = self.findWithPath(node, name)
    if None == res:
      return None
    node = res[0]
    return node
    
  def findWithPath(self, node, name):
    l   = []
    for part in name.split("/"):
      res = []
      self.findNod(node, part, [], res)
      if len(res) == 0:
        return None
      lvl = 0
      while len(res) > 1:
        for it in res:
          (n, l, par) = it
          eln = l[lvl]
          if eln != "<<":
            break
        if eln == part:
          return (n, l, par)
        if eln == "<<":
          # only merge keys; drop one level
          pass
        else:
          # filter merge nodes
          for i in range(len(res)-1,-1,-1):
            if res[i][1][lvl] == "<<":
              res.pop(i)
            elif res[i][1][lvl] != eln:
              raise RuntimeError("find: name mismatch -- scope probably too wide")
        # drop one level
        lvl = lvl + 1
      node = res[0][0]
      l.extend(res[0][1])
    return (node, l, res[0][2])
  
  def findNod(self, node, name, l, res):
    if node.IsMap():
      fnd = node[name]
      if self.ok(fnd):
        nl = l.copy()
        nl.append( name )
        res.append( (fnd, nl, node) )
      for it in node:
        l.append( it.first.Scalar() )
        self.findNod(it.second, name, l, res)
        l.pop()

  def fixup(self, node):
    if self._ipAddr != None or self._useTcp or self._noStreams or self._srpV2 or self._disableDepack:
      self.trav(node)
