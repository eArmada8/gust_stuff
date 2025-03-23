# Atelier Yumia (and some other KT games) have more BLENDINDICES than BLENDWEIGHTS.
# This script will rename the excess BLENDINDICES, hiding them from Blender.  Use
# yumia_g1m_restore_original_fmts.py to restore the BLENDINDICES prior to import
# back to G1M.  NOTE: Do NOT delete the .fmt.original files, the restore script needs
# them to restore the proper semantics!
#
# This code depends on lib_fmtibvb.py being in the same folder.
#
# For command line options:
# /path/to/python3 yumia_g1m_remove_excess_blendindices.py --help
#
# GitHub eArmada8/gust_stuff

try:
    import glob, shutil, os, sys
    from lib_fmtibvb import *
except ModuleNotFoundError as e:
    print("Python module missing! {}".format(e.msg))
    input("Press Enter to abort.")
    raise

def process_fmts (mesh_folder):
    fmts = glob.glob('{}/*.fmt'.format(mesh_folder))
    for fmt_file in fmts:
        if not os.path.exists(fmt_file + '.original'):
            shutil.copy2(fmt_file, fmt_file + '.original')
        fmt = read_fmt(fmt_file)
        unknowns = [i for i in range(len(fmt['elements'])) if fmt['elements'][i]['SemanticName'] == 'UNKNOWN']
        blendweights = [i for i in range(len(fmt['elements'])) if fmt['elements'][i]['SemanticName'] == 'BLENDWEIGHT']
        blendindices = [i for i in range(len(fmt['elements'])) if fmt['elements'][i]['SemanticName'] == 'BLENDINDICES']
        if len(blendindices) > len(blendweights):
            blidx_layers = dict(sorted({int(fmt['elements'][i]['SemanticIndex']):i for i in blendindices}.items()))
            j = len(unknowns)
            for i in blidx_layers:
                if i >= len(blendweights):
                    fmt['elements'][blidx_layers[i]]['SemanticName'] = 'UNKNOWN'
                    fmt['elements'][blidx_layers[i]]['SemanticIndex'] = str(j)
                    j += 1
            write_fmt(fmt, fmt_file)
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
        parser.add_argument('mesh_folder', help="Name of folder to fix fmt files (required).")
        args = parser.parse_args()
        if os.path.exists(args.mesh_folder) and os.path.isdir(args.mesh_folder):
            process_fmts(args.mesh_folder)
    else:
        g1m_files = glob.glob('*.g1m')
        g1m_files = [x for x in g1m_files if os.path.isdir(x[:-4])]
        for i in range(len(g1m_files)):
            process_fmts(g1m_files[i][:-4])
