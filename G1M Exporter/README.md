# Gust (Atelier) mesh export and import
A pair of scripts to get the mesh data out of G1M files and back into G1M files.  The output is in .fmt/.ib/.vb/.vgmap files that are compatible with DarkStarSword Blender import plugin for 3DMigoto, and metadata is in JSON format.

## Credits:
99.9% of my understanding of the G1M format comes from the reverse engineering work of Joschuka (github/Joschuka), and specifically his deprecated fmt_g1m.py plugin for Noesis: https://github.com/Joschuka/fmt_g1m

I also definitely need to thank the Three Houses Research Group (github/three-houses-research-team), and the author of G1M Tools (github/eterniti).  And while I did not use any code from Gust Tools (github/VitaSmith/gust_tools), none of my work would be possible without their amazing work since I would not have access to the G1M files in the first place.

None of this would be possible without the work of DarkStarSword and his amazing 3DMigoto-Blender plugin, of course.

I am very thankful for Joschuka, eterniti, DarkStarSword, the THRG team and VitaSmith for their brilliant work and for sharing that work so freely.

## Requirements:
1. Python 3.10 and newer is required for use of these scripts.  It is free from the Microsoft Store, for Windows users.  For Linux users, please consult your distro.
2. The numpy and pyquaternion modules for python are needed.  Install by typing "python3 -m pip install pyquaternion" in the command line / shell.  (The io, re, struct, sys, os, shutil, glob, copy, json, argparse modules are also required, but these are all already included in most basic python installations.)
3. The output can be imported into Blender using DarkStarSword's amazing plugin: https://github.com/DarkStarSword/3d-fixes/blob/master/blender_3dmigoto.py
4. g1m_export_meshes.py is dependent on lib_fmtibvb.py, which must be in the same folder.  
g1m_import_meshes.py is dependent on both g1m_export_meshes.py and lib_fmtibvb.py.

## Usage:
### g1m_export_meshes.py
Double click the python script and it will search the current folder for elixir.json (from Gust Tools) and export the meshes into a folder with the same name as the g1m file; it will assume the first g1m file is the external skeleton.  If it does not find (or cannot read) the elixir.json file, it will look for Atelier-style naming (e.g. PCxxA_MODEL_default.g1m etc) and attempt to process those files by guessing which file is the external skeleton.  Finally, if it cannot find models that way, it will display a list of all g1m files and ask which one you want it to unpack.

Additionally, it will output a JSON file with metadata from the geometry (G1MG) section, that will be sourced during repacking.

**Command line arguments:**
`g1m_export_meshes.py [-h] [-o] [-n] [-f] g1m_filename`

`-h, --help`
Shows help message.

`-o, --overwrite`
Overwrite existing files without prompting.

`-n, --no_buffers`
Using this option will cause the script to write only the metadata JSON, without writing the buffers.

`-f, --full_vertices`
The default behavior of the exporter is to fully separate each submesh from its parent mesh by culling all unused vertices.  Using this option will direct the script to export the entire vertex buffer with each submesh, in a manner identical to G1M tools.

### g1m_import_meshes.py
Double click the python script and it will search the current folder for all .g1m files with exported folders, and import the meshes in the folder back into g1mmdl file.  Additionally, it will parse the metadata JSON file (G1MG section) if available and use that information to rebuild the entire geometry (G1MG) section of the G1M file.  This script requires a working g1m file already be present as it does not reconstruct the entire file; only the G1MG section.  The remaining parts of the file are copied unaltered from the intact g1m file.

It will make a backup of the original, then overwrite the original.  It will not overwrite backups; for example if "model.g1m.bak" already exists, then it will write the backup to "model.g1m.bak1", then to "model.g1m.bak2", and so on.

**Command line arguments:**
`g1m_import_meshes.py [-h] mdl_filename`

`-h, --help`
Shows help message.
