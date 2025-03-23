# This scripts restores original fmt files after they have been hidden for the sake of Blender,
# as the hidden semantics required for Blender renders the meshes incompatible with re-import
# into G1M.
#
# NOTE: Do NOT delete the .fmt.original files created by yumia_g1m_remove_excess_blendindices.py,
# as this script needs them to restore the proper semantics!
#
# For command line options:
# /path/to/python3 yumia_g1m_restore_original_fmts.py --help
#
# GitHub eArmada8/gust_stuff

try:
    import glob, shutil, os, sys
    from lib_fmtibvb import *
except ModuleNotFoundError as e:
    print("Python module missing! {}".format(e.msg))
    input("Press Enter to abort.")
    raise

def restore_fmts (mesh_folder):
    fmts = glob.glob('{}/*.fmt.original'.format(mesh_folder))
    for fmt_file in fmts:
        shutil.copy2(fmt_file, fmt_file[:-8])
    return

if __name__ == "__main__":
    # Set current directory
    if getattr(sys, 'frozen', False):
        os.chdir(os.path.dirname(sys.executable))
    else:
        os.chdir(os.path.abspath(os.path.dirname(__file__)))

    # If argument given, attempt to import into file in argument
    if len(sys.argv) > 1:
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument('mesh_folder', help="Name of folder to restore fmt files (required).")
        args = parser.parse_args()
        if os.path.exists(args.mesh_folder) and os.path.isdir(args.mesh_folder):
            restore_fmts(args.mesh_folder)
    else:
        g1m_files = glob.glob('*.g1m')
        g1m_files = [x for x in g1m_files if os.path.isdir(x[:-4])]
        for i in range(len(g1m_files)):
            restore_fmts(g1m_files[i][:-4])
