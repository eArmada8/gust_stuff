# GitHub eArmada8/gust_stuff

import struct, glob, os, sys

def unpack_g1m_container (g1m_file):
    base_name = g1m_file.split('.g1m')[0]
    if not os.path.exists(base_name):
        os.mkdir(base_name)
    with open(g1m_file, 'rb') as f:
        i = 0
        f.seek(0,2)
        eof = f.tell()
        f.seek(0,0)
        while f.tell() < eof:
            start = f.tell()
            magic = f.read(4)
            if magic == b'\x00\x00\x00\x00':
                continue # Skip padding
            if magic in [b'_H1G', b'PH1G']:
                header = struct.unpack("<5I", f.read(20))
                f.seek(start)
                data = f.read(header[4])
                ext = 'g1h'
            elif magic == b'_M1G':
                header = struct.unpack("<2I", f.read(8))
                f.seek(start)
                data = f.read(header[1])
                ext = 'g1m'
            else:
                input("Unknown header at {0}, i={1}!  Press Enter to quit.".format(hex(start), i))
                return
            open("{0}/{0}_{1:02d}.{2}".format(base_name, i, ext), 'wb').write(data)
            i += 1
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
        parser.add_argument('g1m_container', help="Name of g1m container to unpack (required).")
        args = parser.parse_args()
        if os.path.exists(args.g1m_container):
            unpack_g1m_container(args.g1m_container)
    else:
        g1m_files = glob.glob('*.g1m')
        for i in range(len(g1m_files)):
            unpack_g1m_container(g1m_files[i])