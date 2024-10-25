''' topLevelMod.py '''
  
  # The purpose of this Python script is to modify the top level YAML file of a YAML hierarchy,
  # in order for a user to be able to run cpswTreeGUI in parallel with an IOC accessing the same FPGA

import os
import re
import sys
import time
import math
import logging
import argparse
import subprocess
import numpy as np

# Global vars
remove_stream_blocks   = ['strm','stream','Stream','Bsa','bsa','BSA']
remove_mmio_blocks     = ['rssi','RSSI:','depack:','Depack:','TDEST:','TDESTMux:']
replace_srp_protocol   = ['SRP_UDP_V3']
typical_udp_ports      = ['8193','8194','8197','8198']

def modify_top_level( toplevel_path ):
  # Read the original top level YAML file
  f = open( toplevel_path, 'r' )                                                                                                
  toplevel_lines = f.readlines()
  f.close()
  # Now scan through each one and replace / remove as needed
  modified_lines = []
  netiodev  = False 
  stream    = False
  mmio      = False
  netiodev_indentation = line_indentation = 0
  # Main loop starts here
  for line in toplevel_lines:
    if 'NetIODev:' in line:
      # Parse the NetIODev block of lines
      netiodev = True
      modified_lines.append(line)
      netiodev_indentation = len( line ) - len( line.lstrip() )
    elif netiodev == True:
      # Check if this is the end of the NetIODev block
      line_indentation = len( line ) - len( line.lstrip() )
      # If we are done with NetIODev, add current line to new top level YAML
      if line_indentation <= netiodev_indentation:
        netiodev = False
        modified_lines.append( line )
      else:
        # Check if we should keep, modify or remove this line
        if 'mmio:' in line:
          # Beginning of mmio block
          mmio = True; mmio_remove = False; stream = False
          modified_lines.append( line )
        elif any([x in line for x in remove_stream_blocks]):
          # Beginning of stream block
          stream = True; mmio = False; mmio_remove = False
          stream_indentation = len( line ) - len( line.lstrip() )
        elif mmio:
          # Check if we need to replace the SRP protocol version
          if any([x in line for x in replace_srp_protocol]):
            nline = line.replace('SRP_UDP_V3','SRP_UDP_V2')
            modified_lines.append( nline )
          elif 'port: ' in line:
            # Replace port with a different port number to avoid conflict with the IOC
            sline = line.split()
            if len(sline) > 1:
              if len([x for x in typical_udp_ports if x in sline[1]]):
                port = [x for x in typical_udp_ports if x in sline[1]][0]
                nline = line.replace(port,'8192')
              elif not sline[1].isnumeric():
                nline = line.replace(sline[1],'8192')
              else:
                nline = line
            modified_lines.append( nline )
          # Remove mmio properties that pertain to RSSI, depack and TDESTMux
          elif any([x in line for x in remove_mmio_blocks]):
            mmio_remove = True 
          elif mmio_remove:
            pass
          else:
            mmio_remove = False
            modified_lines.append( line )
        # Remove all lines in a stream block
        elif stream:
          pass
        else:
          modified_lines.append( line )
    else:
      modified_lines.append( line )
  
  modified_lines.append( '\n' )
  return modified_lines

############################################
#         __main__ block goes here         #
############################################
if __name__ == "__main__":


  parser = argparse.ArgumentParser(description='Modify top level YAML file to allow for a parallel IOC operation.')
  parser.add_argument('--toplevel', dest='toplevel', default='000TopLevel', help='Path to top level YAML (default: 000TopLevel)')
  parser.add_argument('--modified', dest='modified', default='000TopLevel.modified', help='Path to modified top level YAML (default: 000TopLevel.modified)')

  # Parse out arguments
  args = parser.parse_args()
  
  lines = modify_top_level( args.toplevel )

  f = open( args.modified, 'w' )
  f.writelines( lines )
  f.close()

