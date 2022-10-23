# Small tool to convert the binary OID files in Atelier Ryza (and probably other
# Gust / KT games) into text format that is recognized by g1m2fbx.
# GitHub eArmada8/gust_stuff
import io, os, glob

# From Julian Uy's ED9 MDL parser, thank you
def read_pascal_string(f):
    sz = int.from_bytes(f.read(1), byteorder="little")
    return f.read(sz)

def binary_oid_to_dict(oid_file):
    with open(oid_file, 'rb') as f:
        f_length = f.seek(0,io.SEEK_END)
        f.seek(0)
        headers = []
        bones = {}
        while f.tell() < f_length:
            bone_string = read_pascal_string(f).decode("ASCII")
            if len(bone_string.split(',')) > 1:
                bones[int(bone_string.split(',')[0])] = bone_string.split(',')[1]
            elif len(bone_string.split('ObjectID:')) > 1:
                oid_file = bone_string.split('ObjectID:')[1]
            else:
                headers.append(bone_string)
    return({'oid_file': oid_file, 'headers': headers, 'bones': bones})

def write_oid_textfile(oid_dict):
    overwrite = False
    oid_output = ';\r\n; object id,name\r\n;\r\n'
    for key in oid_dict['bones']:
        oid_output += str(key) + ',' + oid_dict['bones'][key] + '\r\n'
    if os.path.exists(oid_dict['oid_file'] + '.oid'):
        if str(input(oid_dict['oid_file'] + '.oid' + " exists! Overwrite? (y/N) ")).lower()[0:1] == 'y':
            overwrite = True
    if (overwrite == True) or not os.path.exists(oid_dict['oid_file'] + '.oid'):
        with open(oid_dict['oid_file'] + '.oid', 'wb') as f:
            f.write(oid_output.encode())

if __name__ == "__main__":
    os.chdir(os.path.abspath(os.path.dirname(__file__)))
    oid_files = glob.glob('*Oid.bin')
    for i in range(len(oid_files)):
        oid_dict = binary_oid_to_dict(oid_files[i])
        write_oid_textfile(oid_dict)