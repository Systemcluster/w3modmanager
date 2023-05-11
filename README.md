# w3modmanager

<p align="center">
  <img width="250" height="250" src="resources/icons/w3b.ico" alt="logo">
</p>

Mod manager and installer for The Witcher 3.

## Description

w3modmanager is a tool that simplifies installation and management of mods for The Witcher 3.

It was inspired by [The Witcher 3 Mod Manager](https://github.com/Systemcluster/The-Witcher-3-Mod-manager), but was created from the ground up to enable additional features and more resilient mod management by separating mods into their separate components.
It focuses on usability and reliably correct handling of the various mod formats found in the wild.

__w3modmanager is currently under development and not yet usable.__

## Planned Features

This list is preliminary and may change before release.

### Mod Management

- Displays information about directories, size, settings additions, menu files, installation dates and more
- Allows configuration of load order priorities
- Allows renaming mods and directories
- Allows enabling and disabling individual mods with proper handling of xml and ini additions
- Downloads and checks for updates from Nexus Mods
- Detects mod conflicts and notifies when script merging is required
- Allows management of manually installed mods

### Mod Installation

- Installs mods from archives, folders or directly from Nexus Mods
- Detects xml and ini files and copies them to the correct place inside `bin`
- Merges changed xml and ini files with preexisting ones
- Detects and installs `user.settings` and `input.settings` additions
- Creates separate mod directories for loose settings, xml and ini files
- Detects and allows installation of patches and other binary files

### Mod Removal

- Deletes mod and dlc directories
- Unmerges changes made to xml and ini files
- Removes xml and ini files from `bin`
- Removes additions to `user.settings` and `input.settings`

### General

- Watches for changes made to mods and settings outside the manager
- Automatically detects the game installation path
- Extracts and installs multiple mods in parallel
- Requests mod information from Nexus Mods for manually installed mods
- Imports the configuration from previous mod manager versions

## Source and Development

Download the source and install the requirements with `pdm install`. Python 3.11+ and `pdm` have to be installed.

Afterwards run with `pdm run invoke start`. To show the available build and test tasks run `pdm run invoke --list`.
