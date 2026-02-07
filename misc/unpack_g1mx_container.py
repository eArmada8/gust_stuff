# GitHub eArmada8/gust_stuff

import struct, glob, os, sys

def unpack_g1mx_container (g1mx_file):
    base_name = g1mx_file.split('.g1mx')[0]
    with open(g1mx_file, 'rb') as f:
        i = 0
        f.seek(0,2)
        eof = f.tell()
        f.seek(0,0)
        magic = f.read(4)
        if magic == b'M1GK':
            header = struct.unpack("<3I", f.read(12))
            name = os.path.basename(f.read(header[2]).decode()).split('.g1mx')[0]
            while f.tell() % 0x10 > 0:
                f.seek(1,1)
            base_name += '_' + name
            if not os.path.exists(base_name):
                os.mkdir(base_name)
            g1mx_start = f.tell()
            magic = f.read(4)
            assert magic == b'XM1G'
            header = struct.unpack("<3I", f.read(12))
            magic = f.read(4)
            assert magic == b'FXMG'
            f.seek(20,1)
            magic = f.read(4)
            assert magic == b'MXMG'
            header = struct.unpack("<4I", f.read(16))
            f.seek(header[3] - 20,1)
            g1mx_end = f.tell()
            f.seek(g1mx_start)
            data = f.read(g1mx_end - g1mx_start)
            ext = 'g1mx'
            open("{0}/{0}_{1:02d}.{2}".format(base_name, i, ext), 'wb').write(data)
            i += 1
            while f.tell() < eof:
                start = f.tell()
                magic = f.read(4)
                if magic == b'\x00\x00\x00\x00':
                    continue # Skip padding
                if magic == b'_M1G':
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
        parser.add_argument('g1mx_container', help="Name of g1m container to unpack (required).")
        args = parser.parse_args()
        if os.path.exists(args.g1mx_container):
            unpack_g1mx_container(args.g1mx_container)
    else:
        g1mx_files = glob.glob('*.g1mx')
        for i in range(len(g1mx_files)):
            unpack_g1mx_container(g1mx_files[i])