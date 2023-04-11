# Release notes

Release notes for the CPSW Tree GUI

## Releases:
* __R1.2.2__: 2023-04-11 J. Bellister
  * Update cpsw/framework to version R4.5.1 to use our python 3.8 conda environment during the
    build process. This fixes an issue where the tree would not run on RHEL 7 machines.
  * Update the tree gui code to use the sip module from the PyQt5 package.

* __R1.2.1__: 2022-07-13 J. Bellister
  * Update cpsw/framework to version R4.5.0 which will support displaying unicode characters

* __R1.2.0__: 2020-03-10 J. Vasquez
  * Add support for buildroot 2019.08.
  * Update to cpsw/framework version 4.4.2.
  * Add the option `-d` to the `rssi_bridge` to get debug information.
  * The script `start.sh` can now be called from any location. It is not longer
    necessary to be be in the cpswTreeGUI top directory.
  * Disable all streams by defaults. The user can enable them explicitly by
    passing the option `-s|--enable-streams` to the `start.sh` script.

* __R1.1.0__: 2020-02-03 J. Vasquez
  * Return the number of entries loaded by loadConfigFromYamlFile().
  * Print info message before and after loading a config file.
  * Add `start.sh` script to start the cpswTreeGui with an rssi_bridge.
  * Fetch poll interval and do not pollp eriodically is 0.0.
  * Bug fixes.

* __R1.0.0__: 2019-07-02 T. Straumann
  * First tagged release.
