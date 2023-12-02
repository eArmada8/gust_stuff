# Short script to repair g1t files with the "File size mismatch" Error with Gust Tools.
# This only fixes the offsets and does not repair truly corrupt files.  Not all texture types supported.
#
# Steps:
# 1. Run this script (in the folder with the broken g1t file).
# 2. Use Gust Tools to extract textures from the repaired .g1t file.
#
# For command line options:
# /path/to/python3 g1t_filesize_repair.py --help
#
# GitHub eArmada8/gust_stuff

import struct, shutil, sys, os, glob

def repair_g1t_offsets (g1t_filename):
    with open(g1t_filename,'r+b') as f:
        header = {}
        header['magic'] = f.read(4).decode()
        if header['magic'] == 'GT1G':
            e = '<'
        elif header['magic'] == 'G1TG':
            e = '>'
        else:
            input("Not G1T, aborting!  Press Enter to continue.")
            return False
        header['version'], header['filesize'], header['tableOffset'], header['entryCount'] = struct.unpack(e+"4I",f.read(16))
        header['remainder'] = list(struct.unpack(e+"{}I".format((header['tableOffset']-20)//4), f.read(header['tableOffset']-20)))
        offset_list = list(struct.unpack(e+"{}I".format(header['entryCount']), f.read(header['entryCount']*4)))
        true_offset_list = [offset_list[0]]
        for i in range(len(offset_list)):
            f.seek(header['tableOffset']+true_offset_list[i])
            mipSys, textureFormat, dxdy, unk0, unk1, unk2, unk3, extra_header_version = struct.unpack(e+"8B",f.read(8))
            mipMapNumber = mipSys >> 4
            texSys = mipSys & 0xF
            height = pow(2, int(dxdy>> 4))
            width = pow(2, dxdy & 0x0F)
            headerSize = 0x8
            if extra_header_version > 0:
                extraDataSize, = struct.unpack(e+"B",f.read(1))
                if extraDataSize < 0xC or extraDataSize > 0x14:
                    input("Unsupported texture header size, aborting!  Press Enter to continue.")
                    return False
                headerSize += extraDataSize
                unk4, unk5 = struct.unpack(e+"2B",f.read(2))
                if extraDataSize >= 0x10:
                    width, = struct.unpack(e+"B",f.read(1))
                if extraDataSize >= 0x14:
                    height, = struct.unpack(e+"B",f.read(1))
            if textureFormat in [0,1,2,3,4,9,0xA]:
                size = width * height * 4
            elif textureFormat in [0xB, 0xD, 0xF]:
                size = width * height
            elif textureFormat in [0x34, 0x36]:
                size = width * height * 2
            elif textureFormat in [6, 0x10, 0x3C, 0x3D, 0x56, 0x59, 0x5C, 0x60, 0x63]: #BC1, BC4, ETC1
                size = width * height // 2
            elif textureFormat in [7, 8, 0x12, 0x5B, 0x5D, 0x5E, 0x5F, 0x62, 0x64, 0x65, 0x66, 0x6F]: #BC2, BC3, BC5, BC6, BC7, ETC2
                size = width * height
            else:
                input("Unsupported texture type, aborting!  Press Enter to continue.")
                return False
            true_size = sum([size // (4**i) for i in range(mipMapNumber)])
            if i+1 < len(offset_list): # This adds the true offset of the NEXT file, so skip if processing the final file
                true_offset_list.append(true_offset_list[-1] + headerSize + true_size)
        f.seek(0,2)
        true_filesize = f.tell()
        # Fix fizesize and offsets
        f.seek(8,0)
        f.write(struct.pack(e+"I",true_filesize))
        f.seek(header['tableOffset'],0)
        f.write(struct.pack(e+"{}I".format(len(true_offset_list)), *true_offset_list))
        return True

def process_g1t (g1t_filename, overwrite_backup = False):
    if os.path.exists(g1t_filename) and not os.path.isdir(g1t_filename):
        print("Processing {}...".format(g1t_filename))
        backup_success = False
        if os.path.exists(g1t_filename+'.bak') and (overwrite_backup == False):
            if str(input("Backup file " + g1t_filename+'.bak' + " exists! Overwrite? (y/N) ")).lower()[0:1] == 'y':
                overwrite_backup = True
        if (overwrite_backup == True) or not os.path.exists(g1t_filename+'.bak'):
            shutil.copy2(g1t_filename,g1t_filename+'.bak')
            backup_success = True
        if not backup_success:
            if str(input("Process " + g1t_filename + " without making a backup? (y/N) ")).lower()[0:1] == 'y':
                backup_success = True            
        if backup_success:
            return(repair_g1t_offsets(g1t_filename))
        else:
            return False

if __name__ == "__main__":
    # Set current directory
    if getattr(sys, 'frozen', False):
        os.chdir(os.path.dirname(sys.executable))
    else:
        os.chdir(os.path.abspath(os.path.dirname(__file__)))
    if len(sys.argv) > 1:
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument('-o', '--overwrite_backup', help="Overwrite existing backup", action="store_true")
        parser.add_argument('g1t_filename', help="Name of g1t file to repair offsets (required).")
        args = parser.parse_args()
        if os.path.exists(args.g1t_filename) and args.g1t_filename[-4:].lower() == '.g1t':
            process_g1t(args.g1t_filename, overwrite_backup = args.overwrite_backup)
    else:
        # When run without command line arguments, it will attempt to obtain data from all models
        g1t_files = [os.path.basename(x) for x in glob.glob('*.g1t')]
        for g1t_filename in g1t_files:
            process_g1t(g1t_filename)