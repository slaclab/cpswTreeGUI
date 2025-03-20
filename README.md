Quick instructions
==================

[DOE Code](https://www.osti.gov/doecode/biblio/75957)

T. Straumann, 4/2019

Licensing Information
---------------------

Consult LICENSE.txt for details.

cpswTreeGUI
-----------

1. Source proper settings for environment variable:

     source env.slac.sh

2. Launch with python

     python cpswTreeGUI.py --help

3. Normal invocation requires path to YAML description and name
   of root node:

     python cpswTreeGUI.py <myLocation>/000TopLevel.yaml NetIODev

4. Some definitions in YAML can be tweaked from the command line
   (most notably IP address of AMC carrier)

     python cpswTreeGUI.py --ipAddress <myLocation>/000TopLevel.yaml NetIODev

5. In most cases the GUI should run on a Desktop without
   direct connectivity to the AMC Carrier. Read on for
   the RSSI Bridge...

RSSI Bridge
-----------

The RSSI bridge is software to be executed on the embedded
CPU that is connected directly to an AMC Carrier. The
bridge translates the UDP/RSSI protocol that is used by
the firmware into TCP which is better at handling longer
distances:

    Desktop                 CPU Blade                  AMC Carrier
   python/GUI <-- TCP -->  RSSI Bridge <-- RSSI/UDP --> Firmware

IMPORTANT NOTE: The RSSI/UDP protocol supports only !!ONE!!
                peer to be connected - but is not very good at
                detecting violations of this rule!

                YOU MUST MAKE SURE no other rssiBridge, EPICS IOC
                or other software is connected to the target IP/UDP
                prior to starting the bridge.

                The same applies to starting EPICS IOCs or any
                other software.

On the embedded CPU (login as laci):

    <laci@cpu-b084-hp01>$ <path>/rssi_bridge -a <ip_of_amcc> -p 8183 -p 8194

The latest version is in <path> (you may need to modify buildroot
version and/or target architecture):

    /afs/slac/g/lcls/package/cpsw/framework/master/buildroot-2016.11.1-x86_64/bin/

Note that the RSSI bridge has no knowledge of YAML or anything about
your firmware. In particular, it has no way of knowing how many ports
are open and what kind (bare UDP vs. RSSI) they are. Thus, you must
explicitly list all ports to be bridged -- otherwise the upstream client
(python/GUI) will fail to connect.

In the above example the bridge is established on UDP/RSSI ports 8193
and 8194 (multiple '-p' may be given). A bare UDP port (e.g., for the
backdoor service) can be bridged with '-u' (e.g., -u 8192).

cpswTreeGUI in combination with rssi_bridge
-------------------------------------------

So to use the GUI on a desktop you have learned how to start a bridge
on the embedded CPU. The bridge must be established before starting
the GUI. Once you have the bridge e.g., on 'cpu-b084-hp01' running:

    <cpu-b084-hp01>$ rssi_bridge -a 10.0.1.102 -p 8193 -p 8194

you start the GUI on your desktop:

    <desktop>$ python cpswTreeGUI.py --ipAddress=10.0.1.102 --rssiBridge=cpu-b084-hp01 <path>/000TopLevel.yaml NetIODev

and you should be in business...

SSH Tunneling
-------------

In some cases it is desirable to run the python/GUI client on a remote
desktop which only has SSH access. The GUI supports tunneling via SOCKS:

1. start the rssi bridge in the exactly same way as described above
2. on your remote desktop, start an ssh connection to a machine which
   has connectivity to the rssi_bridge and *enable the SOCKS proxy*
   built into openssh:

    ssh -D 1080 firewall

3. on your remote desktop start the cpswTreeGUI as described above
   (same options for --ipAddress, --rssiBridge) but add

    --socksProxy=localhost

   Of course, you have to download the YAML description to your
   desktop since CPSW (which runs on your desktop) needs direct
   access to this file.

Background Info
- - - - - - - -
You can skip this section if you are not interested in details.

In order to allow for running multiple instances of rssi_bridge to
execute on a CPU blade (serving multiple AMC carriers from a single
CPU) the bridges use ephemeral TCP ports in combination with a
RPC portmap service. When establishing a TCP connection to the
embedded CPU (as directed by the --rssiBridge option) CPSW first
contacts the RPC service in order to find the TCP port which bridges
to the requested IP/RSSI-port on the UDP side.

Automated script to start cpswTreeGUI with rssi_bridge at SLAC
--------------------------------------------------------------

The provided 'start.sh' script can be used to start cpswTreeGUI on a
desktop and the rssi_bridge on a remote CPU with a single command.

```
usage: start.sh [-S|--shelfmanager <shelfmanager_name> -N|--slot <slot_number>]
                [-a|--addr <FPGA_IP>] -c|--cpu <cpu_name> [-y|--yaml <YAML_file>]
                [-t|--tar <tarball_file>]

    -S|--shelfmanager <shelfmanager_name> : ATCA shelfmanager node name or IP address. Must be used with -N.
    -N|--slot         <slot_number>       : ATCA crate slot number. Must be used with -S.
    -a|--addr         <FPGA_IP>           : FPGA IP address. If defined, -S and -N are ignored.
    -c|--cpu          <cpu_name>          : The remote CPU node name.
    -y|--yaml         <YAML_file>         : Path to the top level YAML file.If defined, -t will be ignored.
    -t|--tar          <tarball_file>      : Path to the YAML tarball file. Must be defined is -y is not defined.
    -h|--help                             : Show this message.
```

If -a if not defined, then -S and -N must both be defined, and the
FPGA IP address will be automatically  calculated from the crate ID
and slot number. If -a if defined, -S and -N are ignored.

The YAML file must be specified either pointing to a top level file
(usually called 000TopLevel.yaml) using -y|--yaml, or a tarball file
containing all the YAML files, using -t|--tar. If -y is used, -t is
ignored.

The scrip will start the rssi_bridge in the remote CPU inside a
screen  session called 'rssi_bridge_<FPGA_IP>'. Then it will start
the cpswTreeGUI here When the GUI is closed, the remote screen
session will be automatically killed. The script will check if an
rssi_bridge is already running in the remote CPU connected to the
specified FGPA_IP. Also, it will check if the CPU and FPGA are online.

Currently, the remote CPU supported are only linuxRT CPUs running
buildroot-2016.11.1-x86_64, and using the user 'laci'.
