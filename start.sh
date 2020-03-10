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

    # Kill the screen session
    if [ ${screen_session_started+x} ]; then
        echo "Killing screen session in remote CPU..."
        ssh ${cpu_user}@${cpu} screen -X -S ${screen_session_name}  quit
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
    echo ""
    echo "usage: ${script_name} [-S|--shelfmanager <shelfmanager_name> -N|--slot <slot_number>]"
    echo "                      [-a|--addr <FPGA_IP>] -c|--cpu <cpu_name> [-y|--yaml <YAML_file>]"
    echo "                      [-t|--tar <tarball_file>]"
    echo "    -S|--shelfmanager <shelfmanager_name> : ATCA shelfmanager node name or IP address. Must be used with -N."
    echo "    -N|--slot         <slot_number>       : ATCA crate slot number. Must be used with -S."
    echo "    -a|--addr         <FPGA_IP>           : FPGA IP address. If defined, -S and -N are ignored."
    echo "    -c|--cpu          <cpu_name>          : The remote CPU node name."
    echo "    -y|--yaml         <YAML_file>         : Path to the top level YAML file.If defined, -t will be ignored."
    echo "    -t|--tar          <tarball_file>      : Path to the YAML tarball file. Must be defined is -y is not defined."
    echo "    -s|--enable-streams                   : Enable all streams"
    echo "    -h|--help                             : Show this message."
    echo ""
    echo "If -a if not defined, then -S and -N must both be defined, and the FPGA IP address will be automatically calculated from the crate ID and slot number."
    echo "If -a if defined, -S and -N are ignored."
    echo
    echo "All streams are disabled by default. They can be enabled by using the '-s|--enable-streams' option."
    echo
    echo "The YAML file must be specified either pointing to a top level file (usually called 000TopLevel.yaml) using -y|--yaml, or a tarball file containing"
    echo "all the YAML files, using -t|--tar. If -y is used, -t is ignored."
    echo
    echo "The script will start the rssi_bridge in the remote CPU inside a screen session called 'rssi_bridge_<FPGA_IP>'. Then it will start the cpswTreeGUI here"
    echo "When the GUI is closed, the remote screen session will be automatically killed."
    echo "The script will check if an rssi_bridge is already running in the remote CPU connected to the specified FGPA_IP. Also, it will check if the CPU and FPGA"
    echo "are online."
    echo
    echo "Currently, the remote CPU supported are only linuxRT CPUs running 'buildroot-2016.11.1-x86_64' or 'buildroot-2019.08-x86_64', and using the user '${cpu_user}'."
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
echo "Checking YAML file..."
if [ -z ${yaml+x} ]; then
    echo "Top level YAML file not defined!"
    echo "Checking tarball file..."

    # Check if the tarball file was defined, and if it exist
    if [ -z ${tar+x} ]; then
        echo "Tarball YAML file not defined!"
        echo "You must specified a either a top level YAML file, or a tarball file."
        clean_up 1
    else
        if [ ! -f ${tar} ]; then
            echo "Tarball file '${tar}' not found!"
            clean_up 1
        else
            temp_dir=/tmp/${USER}/cpswTreeGUI_yaml
            echo "Tarball file found. Extracting it to '${temp_dir}'..."
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
        echo "Top level yaml file '${yaml}' not found!"
        clean_up 1
    fi
fi
echo "Top level YAML file found: ${yaml}"
echo

# Check if the CPU was defined, and if it is online
echo "Checking CPU..."
if [ -z ${cpu+x} ]; then
    echo "CPU not defined!"
    clean_up 1
else
    echo "Verifying if CPU is online..."
    if ! ping -c 2 ${cpu} &> /dev/null ; then
        echo "CPU unreachable!"
        clean_up 1
    fi
fi
echo "CPU is online."
echo

# Check kernel version on CPU
printf "Looking for CPU kernel type...                    "
kernel_version=$(ssh ${cpu_user}@${cpu} /bin/uname -r)

# Check if the target CPU is running a linuxRT kernel
rt=$(echo ${kernel_version} | grep rt)
if [ -z ${rt} ]; then
    printf "Error: non-RT kernel detected. Only linuxRT target are supported.\n"
    exit 1
fi

printf "RT kernel detected.\n"

# Check buildroot version
printf "Looking for Buildroot version...                  "
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
        prtinf "Buildroot version not supported!"
        exit 1
    fi
fi

# rssi_bridge binary
rssi_bridge_bin=$PACKAGE_TOP/cpsw/framework/${cpsw_framework_version}/${cpu_arch}/bin/rssi_bridge

# Check if the rssi_binary exist
if [ ! -f ${rssi_bridge_bin} ]; then
    echo "rssi_binary '${rssi_bridge_bin}' not found!"
    exit 1
fi

# Check IP address or shelfmanager/slot number
echo "Checking FPGA IP address..."
if [ -z ${fpga_ip+x} ]; then

    echo "IP address was not defined. It will be calculated automatically from the crate ID and slot number..."

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
    echo "Verifying if the shelfmanager is online..."
    if ! ping -c 2 ${shelfmanager} &> /dev/null ; then
        echo "shelfmanager unreachable!"
        clean_up 1
    else
        echo "shelfmanager is online."
    fi
    echo


    # Calculate the FPGA IP address
    ipmb=$(expr 0128 + 2 \* $slot)

    echo "Reading Crate ID via IPMI..."
    crate_id=$(getCrateId)
    echo "Create ID: ${crate_id}"

    echo "Calculating FPGA IP address..."
    fpga_ip=$(getFpgaIp)
else
    echo "IP address was defined. Ignoring shelfmanager and slot number."
fi
echo "FPGA IP: ${fpga_ip}"
echo

# Unless streams were enabled by the user, they are disabled by default
if [ -z ${enable_streams+x} ]; then
    disable_streams="--disableStreams"
fi

# Check connection between CPU and FPGA
echo "Checking connection between CPU and FPGA..."
if ! ssh ${cpu_user}@${cpu} ping -c 2 ${fpga_ip} &> /dev/null ; then
    echo "FPGA can not be reached from the remote CPU."
    clean_up 1
fi
echo "Connection OK."
echo

# Check if a rssi_bridge is already running in the remote cpu
screen_session_name=rssi_bridge_${fpga_ip}
echo "Verifying is a screen session '${screen_session_name}' is already running in '${cpu}'..."
if [ $(ssh ${cpu_user}@${cpu} screen -ls | grep ${screen_session_name} | wc -l) != 0 ]; then
  echo "Yes, a screen session '${screen_session_name}' is already running in '${cpu}'. Aborting..."
else
  # Start the rssi_bridge in a screen session in the remote CPU
  echo "No screen session was found. Starting a new screen session..."
  ssh ${cpu_user}@${cpu} screen -dmS ${screen_session_name} -h 8192 ${rssi_bridge_bin} -a ${fpga_ip} -u 8192 -p 8193 -p 8194 -u 8197 -p 8198 -v
  screen_session_started=yes

  # Verifying if the screen session is running
  if [ $(ssh ${cpu_user}@${cpu} screen -ls | grep ${screen_session_name} | wc -l) == 0 ]; then
    echo "Failed to start the rssi_bridge. Is there already a rssi_bidge running in '${cpu}'?"
  else
    echo "Done!. The rssi_bridge is now running in '${cpu}' in the screen session '${screen_session_name}'"
    echo

    # Start the cpswTreeGui
    echo "Starting the GUI..."
    . ${env_setup} && python3 ${top_dir}/cpswTreeGUI.py --ipAddr ${fpga_ip} --rssiBridge=${cpu} ${maxleaves} ${disable_streams} ${yaml} NetIODev
  fi
fi

# Clean up system and exit
clean_up 0
