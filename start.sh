#!/usr/bin/env bash

###############
# Definitions #
###############

# TOP directory
top_dir=$(dirname -- "$(readlink -f $0)")

# Environment setup script
env_setup=${top_dir}/env.slac.sh

# CPSW framework version. Extract it from the environment setup script so
# we don't have to write it twice.
cpsw_framework_version=$(grep cpsw/framework ${env_setup} | head -n 1 | sed -r 's|.+/framework/([^/]+)/.*|\1|')

# Remote CPU user
cpu_user=laci

# Shell PID
top_pid=$$

# This script name
script_name=$(basename $0)

########################
# Function definitions #
########################

# Trap ctrl-c signal
trap "echo 'Crtl-C was detected.'; clean_up 1" INT

# Trap TERM signal
trap "echo 'An error was generated on the last function called.'; clean_up 1" TERM

# Clean up system, and exit with the passed value
clean_up()
{
    echo "Cleaning up..."

    # Kill the rssi bridge session
    if [ ${rssibridge_session_started+x} ]; then
        echo "Killing rssi bridge session on remote CPU..."
	      if [[ ${rssibridge_session_binary} == screen ]];then
            ssh ${cpu_user}@${cpu} screen -X -S ${rssibridge_session_name}  quit
	      elif [[ ${rssibridge_session_binary} == tmux ]];then
            ssh ${cpu_user}@${cpu} tmux kill-session -t ${rssibridge_session_name}
        else
	          printf "Unknown session binary... ${rssibridge_session_binary}"
	      fi
        echo "Done"
        echo
    fi

    # Clean temp file, if it was used
    if [ ${temp_dir+x} ]; then
      echo "Removing temporal directory '${temp_dir}'..."
      rm -rf ${temp_dir}
      echo "Done!"
      echo
    fi

    echo "Done"
    exit $1
}

# Usage message
usage()
{
    echo "Start the cpswTreeGUI with an rssi_bridge on a remote CPU."
    echo
    echo "usage: ${script_name}  [-S|--shelfmanager <shelfmanager_name> -N|--slot <slot_number>]"
    echo "                 [-a|--addr <FPGA_IP>] -c|--cpu <cpu_name> [-y|--yaml <YAML_file>]"
    echo "                 [-t|--tar <tarball_file>] [-r|--record-prefix <prefix>] [-p|--socks-proxy <addr>]"
    echo "                 [-L|--max-expanded-leaves <max>] [-u|--user <username>] [-e|--epics] [-E|--epics-only]"
    echo "                 [-C|--disable-comm] [-Y|--just-load-yaml] [-s|--enable-streams] [-H|--disable-string-heuristics]"
    echo  
    echo "    -S|--shelfmanager         <shelfmanager_name> : ATCA shelfmanager node name or IP address. Must be used with -N."
    echo "    -N|--slot                 <slot_number>       : ATCA crate slot number. Must be used with -S."
    echo "    -a|--addr                 <FPGA_IP>           : FPGA IP address. If defined, -S and -N are ignored."
    echo "    -c|--cpu                  <cpu_name>          : The remote CPU node name."
    echo "    -y|--yaml                 <YAML_file>         : Path to the top level YAML file. If defined, -t will be ignored."
    echo "    -t|--tar                  <tarball_file>      : Path to the YAML tarball file. Must be defined if -y is not defined."
    echo "    -r|--record-prefix        <prefix>            : EPICS Record name prefix; must match IOC prefix."
    echo "    -p|--socks-proxy          <addr>              : connect to any EPICS IOC via a SOCKS proxy on the machine at <addr>."
    echo "    -L|--max-expanded-leaves  <max>               : If leaves in the tree are arrays, show elements only if no more than <max>."
    echo "    -u|--user                 <username>          : User account."
    echo "    -h|--help                                     : Show this message."
    echo "    -e|--epics                                    : Use EPICS CA to connect."
    echo "    -E|--epics-only                               : Disable CPSW entirely but use a simplified YAML file."
    echo "    -C|--disable-comm                             : Disable CPSW communication. This option can be used to test."
    echo "    -Y|--just-load-yaml                           : just load the YAML file and exit; used to test the yaml fixup."
    echo "    -s|--enable-streams                           : Enable all streams."
    echo "    -H|--disable-string-heuristics                : disable some tests which guess if a value is a string."
    echo  
    echo "If -a is not defined, then both -S and -N must be defined. The FPGA IP address will be automatically calculated from the crate ID and slot number."
    echo "If -a is defined, -S and -N are ignored."
    echo
    echo "All streams are disabled by default. They can be enabled by using the '-s|--enable-streams' option."
    echo
    echo "The YAML file must be specified either pointing to a top level file (usually called 000TopLevel.yaml) using -y|--yaml, or a tarball file containing"
    echo "all the YAML files, using -t|--tar. If -y is used, -t is ignored."
    echo
    echo "The script will start the rssi_bridge on the remote CPU inside a screen or tmux session called 'rssi_bridge_<FPGA_IP>'. Then it will start the cpswTreeGUI here."
    echo 
    echo "When the GUI is closed, the remote screen or tmux session will be automatically killed."
    echo 
    echo "The script will check if an rssi_bridge is already running on the remote CPU connected to the specified FGPA_IP. Also, it will check if the CPU and the FPGA are online."
    echo
    echo "Currently, the remote CPU supported can be linuxRT (i.e. CPUs running 'buildroot-2016.11.1-x86_64' or 'buildroot-2019.08-x86_64'), Ubuntu or a RedHat distribution."
    echo
}

# Read the crateID from the shelfmanager
getCrateId()
{
    local crate_id_str

    crate_id_str=$(ipmitool -I lan -H $shelfmanager -t $ipmb -b 0 -A NONE raw 0x34 0x04 0xFD 0x02 2> /dev/null)

    if [ "$?" -ne 0 ]; then
        echo "Error while trying to read the crate ID via IPMI"
        kill -s TERM ${top_pid}
    fi

    local crate_id=`printf %04X  $((0x$(echo $crate_id_str | awk '{ print $2$1 }')))`

    if [ -z ${crate_id} ]; then
        echo "Create ID read was empty."
        kill -s TERM ${top_pid}
    fi

    echo ${crate_id}
}

# Calculate the FPGA IP address from the crateID and slot number
getFpgaIp()
{

    # Calculate FPGA IP subnet from the crate ID
    local subnet="10.$((0x${crate_id:0:2})).$((0x${crate_id:2:2}))"

    # Calculate FPGA IP last octet from the slot number
    local fpga_ip="${subnet}.$(expr 100 + $slot)"

    echo ${fpga_ip}
}

#############
# Main body #
#############

# Verify inputs arguments
while [[ $# -gt 0 ]]
do
key="$1"

case ${key} in
    -S|--shelfmanager)
    shelfmanager="$2"
    shift
    ;;
    -N|--slot)
    slot="$2"
    shift
    ;;
    -a|--addr)
    fpga_ip="$2"
    shift
    ;;
    -c|--cpu)
    cpu="$2"
    shift
    ;;
    -y|--yaml)
    yaml="$2"
    shift
    ;;
    -t|--tar)
    tar="$2"
    shift
    ;;
    -L|--maxExpandedLeaves)
    maxleaves="--maxExpandedLeaves=$2"
    shift
    ;;
    -s|--enable-streams)
    enable_streams=1
    ;;
    -u|--user)
    cpu_user="$2"
    shift
    ;;
    -e|--epics)
    use_epics=1
    ;;
    -E|--epics-only)
    use_epics_only=1
    ;;
    -R|--rssi-bridge)
    rssi_bridge_addr="--rssiBridge=$2"
    shift
    ;;
    -r|--record-prefix)
    record_prefix="--recordPrefix=$2"
    shift
    ;;
    -p|--socks-proxy)
    socks_proxy="--socksProxy=$2"
    shift
    ;;
    -Y|--just-load-yaml)
    just_load_yaml=1
    ;;
    -C|--disable-comm)
    dis_comm=1
    ;;
    -H|--disable-string-heuristics)
    dis_string_heuristics=1
    ;;
    -h|--help)
    usage
    exit 0
    ;;
    *)
    args="${args} $key"
    ;;
esac
shift
done
      
echo
                     
# Verify mandatory parameters

# Check if the top level YAML file was defined, and if it exist
printf "Checking YAML file...                             "
if [ -z ${yaml+x} ]; then
    printf "Top level YAML file not defined!\n"
    printf "Checking tarball file...                          "
                          
    # Check if the tarball file was defined, and if it exist
    if [ -z ${tar+x} ]; then
        printf "Tarball YAML file not defined!\n"
        echo "You must specified a either a top level YAML file, or a tarball file."
        clean_up 1
    else
        if [ ! -f ${tar} ]; then
            printf "Tarball file '${tar}' not found!\n"
            clean_up 1
        else
            temp_dir=/tmp/${USER}/cpswTreeGUI_yaml
            printf "Tarball file found. Extracting it to '${temp_dir}'\n"
            rm -rf ${temp_dir}
            mkdir -p ${temp_dir}
            tar -zxf ${tar} --strip 1 -C ${temp_dir}
            yaml=${temp_dir}/000TopLevel.yaml
            if [ ! -f ${yaml} ]; then
                echo "Not top level YAML file was found in the extracted tarball file: ${yaml}"
                clean_up 1
            fi
        fi
    fi
else
    if [ ! -f ${yaml} ]; then
        printf "Top level yaml file '${yaml}' not found!\n"
        clean_up 1
    fi
fi
printf "Top level YAML file found: ${yaml}"
echo

# Check if the CPU was defined, and if it is online
printf "Verifying if CPU is online...                     "
if [ -z ${cpu+x} ]; then
    printf "CPU not defined!\n"
    clean_up 1
else
    if ! ping -c 2 ${cpu} &> /dev/null ; then
        printf "CPU unreachable!\n"
        clean_up 1
    fi
fi
printf "CPU is online.\n"

# Check kernel version on CPU
printf "Looking for CPU kernel type...                    "
kernel_version=$(ssh ${cpu_user}@${cpu} /bin/uname -r)

# Check if the target CPU is running a linuxRT kernel
rt=$(echo ${kernel_version} | grep rt)
if [ -z ${rt} ]; then
    printf "Non-RT kernel detected.\n"
else
    printf "RT kernel detected.\n"
fi

# Check buildroot version
printf "Looking for distribution version...               "
br2016=$(echo ${kernel_version} | grep 4.8.11)
if [ ${br2016} ]; then
    printf "buildroot-2016.11.1\n"
    cpu_arch=buildroot-2016.11.1-x86_64
else
    br2019=$(echo ${kernel_version} | grep 4.14.139)
    if [ $br2019 ]; then
        printf "buildroot-2019.08\n"
        cpu_arch=buildroot-2019.08-x86_64
    else
        OS_DESC=$(ssh ${cpu_user}@${cpu} lsb_release -d)
        OS_REL=$(ssh ${cpu_user}@${cpu} lsb_release -r)
        if [[ $OS_DESC = *'Red Hat'* ]]; then
            printf "Running on Red Hat ${OS_REL}.\n"
            cpu_arch=rhel7-x86_64
        elif [[ $OS_DESC = *'Ubuntu'* ]]; then
            printf "Running on Ubuntu ${OS_REL}.\n"
            cpu_arch=ubuntu20046-x86_64
        fi
    fi
fi

# rssi_bridge binary
rssi_bridge_bin=$PACKAGE_TOP/cpsw/framework/${cpsw_framework_version}/${cpu_arch}/bin/rssi_bridge

# Check if the rssi_binary exist
if [ ! -f ${rssi_bridge_bin} ]; then
    echo "rssi_binary '${rssi_bridge_bin}' not found!"
    clean_up 1
fi

# Check IP address or shelfmanager/slot number
printf "Checking FPGA IP address...                       "
if [ -z ${fpga_ip+x} ]; then

    printf "IP address was not defined. Calculating automatically from crate ID and slot number.\n"

    # If the IP address is not defined, shelfmanager and slot number must be defined
    if [ -z ${shelfmanager+x} ]; then
        echo "Shelfmanager not defined!"
        clean_up 1
    fi

    if [ -z ${slot+x} ]; then
        echo "Slot number not defined!"
        clean_up 1
    fi

    # Verify that the slot number is in the range [2,7]
    if [ ${slot} -lt 2 -o ${slot} -gt 7 ]; then
        echo "Invalid slot number! Must be a number between 2 and 7."
        clean_up 1
    fi

    # Check if the shelfmanager is online
    printf "Verifying if the shelfmanager is online...        "
    if ! ping -c 2 ${shelfmanager} &> /dev/null ; then
        printf "shelfmanager unreachable!\n"
        clean_up 1
    else
        printf "shelfmanager is online.\n"
    fi

    # Calculate the FPGA IP address
    ipmb=$(expr 0128 + 2 \* $slot)

    printf "Reading Crate ID via IPMI...                      "
    crate_id=$(getCrateId)
    printf "${crate_id}\n"

    fpga_ip=$(getFpgaIp)
else
    printf "IP address was defined. Ignoring shelfmanager and slot number.\n"
fi
printf "FPGA IP:                                          ${fpga_ip}\n"

# Unless streams were enabled by the user, they are disabled by default
if [ -z ${enable_streams+x} ]; then
    disable_streams="--disableStreams"
fi

# Check if we are just testing the yaml fixup 
if [[ -v ${just_load_yaml} ]]; then
    only_load_yaml="--justLoadYaml"
fi

# This option disables string heuristics
if [[ -v ${dis_string_heuristics} ]]; then
    disable_string_heuristics="--disableStringHeuristics"
fi

# This option disables CPSW 
if [[ -v ${dis_comm} ]]; then
    disable_comm="--disableComm"
fi

# Check if EPICS is used instead of reading from hardware 
if [[ -v ${use_epics} ]]; then
    enable_epics="--useEpics"
fi

# Check if EPICS ONLY is used (i.e. cpsw is entirely disabled) 
if [[ -v ${use_epics_only} ]]; then
    enable_epics_only="--useEpicsOnly"
fi

# Check connection between CPU and FPGA
printf "Checking connection between CPU and FPGA...       "
if ! ssh ${cpu_user}@${cpu} ping -c 2 ${fpga_ip} &> /dev/null ; then
    printf "FPGA can not be reached from the remote CPU.\n"
    clean_up 1
fi
printf "Connection OK.\n"

# Check which terminal multiplexer we should be using
printf "Identify terminal multiplexer to use...     "
if [ $(ssh ${cpu_user}@${cpu} which screen | wc -l) == 0 ]; then
  if [ $(ssh ${cpu_user}@${cpu} which tmux | wc -l) == 0 ]; then
    printf "Could not find neither screen nor tmux on the remote host...\n"
    printf "Exiting...\n"
    exit 0
  else
    printf "      Use tmux.\n"
    rssibridge_session_binary=tmux
  fi
else
  printf "      Use screen.\n"
  rssibridge_session_binary=screen 
fi

# Check if an rssi_bridge is already running on the remote cpu
rssibridge_session_name=rssi_bridge_${fpga_ip}
rssibridge_session_name=${rssibridge_session_name//[.]/_}

printf "Verifying if rssi_bridge is already running...    "
if [[ ${rssibridge_session_binary} == screen ]];then
  if [ $(ssh ${cpu_user}@${cpu} screen -ls | grep ${rssibridge_session_name} | wc -l) != 0 ]; then
    printf "Yes, it is already running. Aborting...\n"
    clean_up 1
  else
    printf "No rssi_bridge was found.\n"
  fi
elif [[ ${rssibridge_session_binary} == tmux ]];then
  if [ $(ssh ${cpu_user}@${cpu} tmux ls | grep ${rssibridge_session_name} | wc -l) != 0 ]; then
    printf "Yes, it is already running. Aborting...\n"
    clean_up 1
  else
    printf "No rssi_bridge was found.\n"
  fi
fi

# Start the rssi_bridge on the remote CPU
printf "Starting an rssi_bridge...                        "
if [[ ${rssibridge_session_binary} == screen ]];then
  ssh ${cpu_user}@${cpu} screen -dmS ${rssibridge_session_name} -h 8192 ${rssi_bridge_bin} -a ${fpga_ip} -u 8192 -p 8193 -p 8194 -u 8197 -p 8198 -v -d
  rssibridge_session_started=yes
elif [[ ${rssibridge_session_binary} == tmux ]];then
  printf "\n\nIN THE FOLLOWING TMUX SCREEN, DETACH MANUALLY WITH CTRL+B THEN D TO BRING UP cpswTreeGUI\n";sleep 8
  ssh -t ${cpu_user}@${cpu} tmux new -s ${rssibridge_session_name} ${rssi_bridge_bin} -a ${fpga_ip} -u 8192 -p 8193 -p 8194 -u 8197 -p 8198 -v -d 
  rssibridge_session_started=yes
fi

# Verifying if a screen or tmux session is running
if [[ ${rssibridge_session_binary} == screen ]];then
    if [ $(ssh ${cpu_user}@${cpu} screen -ls | grep ${rssibridge_session_name} | wc -l) == 0 ]; then
        printf "Failed to start the rssi_bridge.\n"
        clean_up 1
    else
        printf "Done! It is now running in the screen session '${rssibridge_session_name}' on '${cpu}'.\n"
    fi
elif [[ ${rssibridge_session_binary} == tmux ]];then
    if [ $(ssh ${cpu_user}@${cpu} tmux ls | grep ${rssibridge_session_name} | wc -l) == 0 ]; then
        printf "Failed to start the rssi_bridge.\n"
        clean_up 1
    else
        printf "Done! It is now running in the tmux session '${rssibridge_session_name}' on '${cpu}'.\n"
    fi
fi

# Start the cpswTreeGui
echo "Starting the GUI..."
echo
. ${env_setup} && python3 ${top_dir}/cpswTreeGUI.py --ipAddr ${fpga_ip} --rssiBridge=${cpu} ${enable_epics} ${maxleaves} ${socks_proxy} ${record_prefix} ${disable_streams} ${only_load_yaml} ${disable_string_heuristics} ${disable_comm} ${yaml} NetIODev

# Clean up system and exit
clean_up 0 
