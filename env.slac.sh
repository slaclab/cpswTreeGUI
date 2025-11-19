CPSW_VERSION=R4.6.1

if [ -z $PACKAGE_SITE_TOP ] ; then
  PACKAGE_SITE_TOP=/sdf/sw/epics/package
fi

if [ -z "$ARCH" ] ; then
  MACH=`uname -m`
  REL=`uname -r`
  if echo $REL | grep -q el6 ; then
    ARCH=rhel6-
  elif echo $REL | grep -q el7 ; then
    ARCH=rhel7-
  elif echo $REL | grep -q el8 ; then
    ARCH=rhel8-
  elif echo $REL | grep -q el9 ; then
    ARCH=rhel9-
  elif echo $REL | grep -q 60-generic ; then
    ARCH=ubuntu2204-
  else
    ARCH="linux-"
  fi
  ARCH=$ARCH$MACH
fi

if [ -z $ARCH ] ; then
  echo "ARCH not set; not modifying environment"
else
  echo "Setting environment for $ARCH"
  . $PACKAGE_SITE_TOP/cpsw/framework/$CPSW_VERSION/$ARCH/bin/env-cpsw.sh
  . $PACKAGE_SITE_TOP/anaconda/envs/python3.8envs/v2.5/bin/activate
fi

export PYTHONPATH=${PYTHONPATH}:$(dirname -- "$(readlink -f -- $0)")
