# Gust Stuff
This is my repository for tools for modding Atelier games.  Everything here is currently for working with G1M files, and is written in Python 3.10.

## G1M Exporter
https://github.com/eArmada8/gust_stuff/tree/main/G1M%20Exporter

This is a working tool, similar to G1M Tools although written in python.  I wrote this specifically so that I could start deconstructing the so-called 4D meshes, but it works well enough now that others may find it useful as well.  It can unpack G1M files from Atelier (and Blue Reflection) games and properly incorporate the external skeleton for named vertex groups.

## Blender scripts
https://github.com/eArmada8/gust_stuff/tree/main/blender%20scripts

Mostly deprecated, these scripts are meant to be used with G1M Tool to facilitate skeletal rigging in Blender.  The majority of its functions are already in my G1M Exporter.

## 4D NUN project
https://github.com/eArmada8/gust_stuff/tree/main/4D_NUN_project

My work folder for developing G1M Exporter.  As tools mature, I move them to the G1M Exporter code and remove them from here.

### find_matching_files.py
A utility that I wrote to find 3DMigoto files with a specific hash.
