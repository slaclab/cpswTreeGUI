class InterfaceNotImplemented(Exception):
  def __init__(self, args):
    Exception.__init__(self,args)

class NotFound(Exception):
  def __init__(self, args):
    Exception.__init__(self, args)

