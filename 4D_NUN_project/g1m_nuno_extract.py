# NUN data extractor, based entirely off the work of Joschuka (fmt_g1m / Project G1M), huge thank you to Joschuka!
#
# Steps:
# 1. Extract fmt/ib/vb from desired g1m directories with g1m_export.exe 
# 2. Run this script (in the folder with the g1m file).
#
# GitHub eArmada8/gust_stuff

import glob, os, io, sys, struct, json

def parseNUNO1(chunkVersion, f,e):
    nuno1_block = {}
    nuno1_block['name'] = "nuno"
    nuno1_block['parentBoneID'] = None
    # Not sure if it should just be nuno1_block['parentBoneID'], = struct.unpack("<I",f.read(4))
    # instead of the next 2 lines
    a,b = struct.unpack("<HH", f.read(4))
    nuno1_block['parentBoneID'] = a if e == '<' else b
    controlPointCount, = struct.unpack(e+"I", f.read(4))
    unknownSectionCount, = struct.unpack(e+"I", f.read(4))
    skip1, = struct.unpack(e+"i", f.read(4))
    skip2, = struct.unpack(e+"i", f.read(4))
    skip3, = struct.unpack(e+"i", f.read(4))
    f.read(0x3C)
    if chunkVersion < 0x30303233:       
        f.read(0x10)
    if chunkVersion >= 0x30303235:
        f.read(0x10)
    nuno1_block['controlPoints'] = []
    for i in range(controlPointCount):
        nuno1_block['controlPoints'].append(struct.unpack("ffff", f.read(16)))
    nuno1_block['influences'] = []
    for i in range(controlPointCount):
        influence = {}
        influence['P1'], influence['P2'], influence['P3'], influence['P4'], influence['P5'], influence['P6'] = struct.unpack("iiiiff", f.read(24))
        nuno1_block['influences'].append(influence)
    # reading the unknown sections data
    f.seek(48 * unknownSectionCount,1)
    f.seek(4 * skip1,1)
    f.seek(4 * skip2,1)
    f.seek(4 * skip4,1)
    return(nuno1_block)

def parseNUNO2(chunkVersion, f,e):
    nuno2_block = {}
    nuno2_block['name'] = "nuno"
    nuno2_block['parentBoneID'] = None
    # Not sure if it should just be nuno2_block['parentBoneID'], = struct.unpack("<I",f.read(4))
    # instead of the next 2 lines
    a,b = struct.unpack("<HH", f.read(4))
    nuno2_block['parentBoneID'] = a if e == '<' else b
    f.read(0x68)
    nuno2_block['controlPoint'] = struct.unpack("fff", f.read(12))
    f.read(0x08)
    return(nuno2_block)

def parseNUNO3(chunkVersion, f,e):
    nuno3_block = {}
    nuno3_block['name'] = "nuno"
    nuno3_block['parentBoneID'] = None
    # Not sure if it should just be nuno3_block['parentBoneID'], = struct.unpack(e+"I",f.read(4))
    # instead of the next 2 lines
    a,b = struct.unpack("<HH", f.read(4))
    nuno3_block['parentBoneID'] = a if e == '<' else b
    controlPointCount, = struct.unpack(e+"I", f.read(4))
    unknownSectionCount, = struct.unpack(e+"I", f.read(4))
    skip1, = struct.unpack(e+"i", f.read(4))
    f.read(4)
    skip2, = struct.unpack(e+"i", f.read(4))
    skip3, = struct.unpack(e+"i", f.read(4))
    skip4, = struct.unpack(e+"i", f.read(4))
    if chunkVersion < 0x30303332:       
        f.read(0xA8)
        if chunkVersion >= 0x30303235:
            f.read(0x10)
    else:
        f.read(0x8)
        current_offset = f.tell()
        temp, = struct.unpack(e+"I", f.read(4))
        f.seek(current_offset+temp,0)
    nuno3_block['controlPoints'] = []
    for i in range(controlPointCount):
        nuno3_block['controlPoints'].append(struct.unpack("ffff", f.read(16)))
    nuno3_block['influences'] = []
    for i in range(controlPointCount):
        influence = {}
        influence['P1'], influence['P2'], influence['P3'], influence['P4'], influence['P5'], influence['P6'] = struct.unpack(e+"iiiiff", f.read(24))
        nuno3_block['influences'].append(influence)
    # reading the unknown sections data
    f.seek(48 * unknownSectionCount,1)
    f.seek(4 * skip1,1)
    f.seek(8 * skip2,1)
    f.seek(12 * skip3,1)
    f.seek(8 * skip4,1)
    return(nuno3_block)

def parseNUNV1(chunkVersion, f,e):
    nunv1_block = {}
    nunv1_block['name'] = "nunv"
    nunv1_block['parentBoneID'] = None
    # Not sure if it should just be nunv1_block['parentBoneID'], = struct.unpack(e+"I",f.read(4))
    # instead of the next 2 lines
    a,b = struct.unpack("<HH", f.read(4))
    nunv1_block['parentBoneID'] = a if e == '<' else b
    controlPointCount, = struct.unpack(e+"I", f.read(4))
    unknownSectionCount, = struct.unpack(e+"I", f.read(4))
    skip1, = struct.unpack(e+"i", f.read(4))
    f.read(54)
    if chunkVersion >= 0x30303131:       
        f.read(0x10)
    nunv1_block['controlPoints'] = []
    for i in range(controlPointCount):
        nunv1_block['controlPoints'].append(struct.unpack("ffff", f.read(16)))
    nunv1_block['influences'] = []
    for i in range(controlPointCount):
        influence = {}
        influence['P1'], influence['P2'], influence['P3'], influence['P4'], influence['P5'], influence['P6'] = struct.unpack(e+"iiiiff", f.read(24))
        nunv1_block['influences'].append(influence)
    # reading the unknown sections data
    f.seek(48 * unknownSectionCount,1)
    f.seek(4 * skip1,1)
    return(nunv1_block)

def parseNUNS1(chunkVersion, f,e):
    nuns1_block = {}
    nuns1_block['name'] = "nuns"
    nuns1_block['parentBoneID'] = None
    # Not sure if it should just be nuns1_block['parentBoneID'], = struct.unpack(e+"I",f.read(4))
    # instead of the next 2 lines
    a,b = struct.unpack("<HH", f.read(4))
    nuns1_block['parentBoneID'] = a if e == '<' else b
    controlPointCount, = struct.unpack(e+"I", f.read(4))
    unk1, = struct.unpack(e+"I", f.read(4))
    unk2, = struct.unpack(e+"I", f.read(4))
    unk3, = struct.unpack(e+"I", f.read(4))
    unk4, = struct.unpack(e+"I", f.read(4))
    skip1, = struct.unpack(e+"I", f.read(4))
    f.read(0xA4)
    for i in range(controlPointCount):
        nuns1_block['controlPoints'].append(struct.unpack("ffff", f.read(16)))
    nuns1_block['influences'] = []
    for i in range(controlPointCount):
        influence = {}
        influence['P1'], influence['P2'], influence['P3'], influence['P4'], influence['P5'], influence['P6'], influence['P7'], influence['P8'] = struct.unpack(e+"iiiiffii", f.read(24))
        nuns1_block['influences'].append(influence)
    # reading the unknown sections data
    temp = -1
    while(temp != 0x424C5730):
        temp, = struct.unpack(e+"I", f.read(4))
    #BLWO
    f.read(4)
    blwoSize, = struct.unpack(e+"I", f.read(4))
    f.read(blwoSize)
    f.read(0xC)
    return(nuns1_block)

def parseNUNO(nuno_chunk,e):
    nuno_section = {}
    with io.BytesIO(nuno_chunk) as f:
        nuno_section["magic"] = f.read(4).decode("utf-8")
        nuno_section["version"], nuno_section["size"], nuno_section["chunk_count"], = struct.unpack(e+"III", f.read(12))
        nuno_section["chunks"] = []
        for i in range(nuno_section["chunk_count"]):
            chunk = {}
            chunk["Type"],chunk["size"],chunk["subchunk_count"] = struct.unpack(e+"III", f.read(12))
            chunk["subchunks"] = []
            for j in range(chunk["subchunk_count"]):
                if chunk["Type"] == 0x00030001:
                    chunk["subchunks"].append(parseNUNO1(nuno_section["version"],f,e))
                elif chunk["Type"] == 0x00030002:
                    chunk["subchunks"].append(parseNUNO2(nuno_section["version"],f,e))
                elif chunk["Type"] == 0x00030003:
                    chunk["subchunks"].append(parseNUNO3(nuno_section["version"],f,e))
                else:
                    chunk["subchunks"].append({'Error': 'unsupported NUNO'})
                    f.seek(chunk["size"],1)
            nuno_section["chunks"].append(chunk)
    return(nuno_section)

def parseNUNV(nuno_chunk,e):
    nunv_section = {}
    with io.BytesIO(nuno_chunk) as f:
        nunv_section["magic"] = f.read(4).decode("utf-8")
        nunv_section["version"], nunv_section["size"], nunv_section["chunk_count"], = struct.unpack(e+"III", f.read(12))
        nunv_section["chunks"] = []
        for i in range(nunv_section["chunk_count"]):
            chunk = {}
            chunk["Type"],chunk["size"],chunk["subchunk_count"] = struct.unpack(e+"III", f.read(12))
            chunk["subchunks"] = []
            for j in range(chunk["subchunk_count"]):
                if chunk["Type"] == 0x00050001:
                    chunk["subchunks"].append(parseNUNV1(nunv_section["version"],f,e))
                else:
                    chunk["subchunks"].append({'Error': 'unsupported NUNV'})
                    f.seek(chunk["size"],1)
            nunv_section["chunks"].append(chunk)
    return(nunv_section)

def parseNUNS(nuno_chunk, e):
    nuns_section = {}
    with io.BytesIO(nuno_chunk) as f:
        nuns_section["magic"] = f.read(4).decode("utf-8")
        nuns_section["version"], nuns_section["size"], nuns_section["chunk_count"], = struct.unpack(e+"III", f.read(12))
        nuns_section["chunks"] = []
        for i in range(nuns_section["chunk_count"]):
            chunk = {}
            chunk["Type"],chunk["size"],chunk["subchunk_count"] = struct.unpack(e+"III", f.read(12))
            chunk["subchunks"] = []
            for j in range(chunk["subchunk_count"]):
                if chunk["Type"] == 0x00050001:
                    chunk["subchunks"].append(parseNUNS1(nuns_section["version"],f,e))
                else:
                    chunk["subchunks"].append({'Error': 'unsupported NUNS'})
                    f.seek(chunk["size"],1)
            nuns_section["chunks"].append(chunk)
    return(nuns_section)

# The argument passed (g1m_name) is actually the folder name
def parseG1M(g1m_name):
    with open(g1m_name + '.g1m', "rb") as f:
        file = {}
        file["file_magic"], = struct.unpack(">I", f.read(4))
        if file["file_magic"] == 0x5F4D3147:
            e = '<' # Little Endian
        elif file["file_magic"] == 0x47314D5F:
            e = '>' # Big Endian
        else:
            print("not G1M!") # Figure this out later
            sys.exit()
        file["file_version"] = f.read(4).hex()
        file["file_size"], = struct.unpack(e+"I", f.read(4))
        chunks = {}
        chunks["starting_offset"], chunks["reserved"], chunks["count"] = struct.unpack(e+"III", f.read(12))
        chunks["chunks"] = []
        f.seek(chunks["starting_offset"])
        nun_data = {}
        for i in range(chunks["count"]):
            chunk = {}
            chunk["start_offset"] = f.tell()
            chunk["magic"] = f.read(4).decode("utf-8")
            chunk["version"] = f.read(4).hex()
            chunk["size"], = struct.unpack(e+"I", f.read(4))
            chunks["chunks"].append(chunk)
            if chunk["magic"] in ['NUNO', 'ONUN']: # NUNO
                f.seek(chunk["start_offset"],0)
                nun_data["nuno"] = parseNUNO(f.read(chunk["size"]),e)
            if chunk["magic"] in ['NUNV', 'VNUN']: # NUNV
                f.seek(chunk["start_offset"],0)
                nun_data["nunv"] = parseNUNV(f.read(chunk["size"]),e)
            if chunk["magic"] in ['NUNS', 'SNUN']: # NUNS
                f.seek(chunk["start_offset"],0)
                nun_data["nuns"] = parseNUNV(f.read(chunk["size"]),e)
            else:
                f.seek(chunk["start_offset"] + chunk["size"],0) # Move to next chunk
        file["chunks"] = chunks

        with open(g1m_name+"_contents.json", "wb") as f:
            f.write(json.dumps(file, indent=4).encode("utf-8"))

        if not os.path.exists(g1m_name): 
            os.mkdir(g1m_name)

        with open(g1m_name+"/nun_data.json", "wb") as f:
            f.write(json.dumps(nun_data, indent=4).encode("utf-8"))

if __name__ == "__main__":
    # Set current directory
    os.chdir(os.path.abspath(os.path.dirname(__file__)))
    if len(sys.argv) > 1:
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument('-o', '--overwrite', help="Overwrite existing files", action="store_true")
        parser.add_argument('g1m_filename', help="Name of g1m file to extract NUN data (required).")
        args = parser.parse_args()
        if os.path.exists(args.g1m_filename) and args.g1m_filename[-4:].lower() == '.g1m':
            parseG1M(args.g1m_filename[:-4])
    else:
        # When run without command line arguments, it will attempt to obtain NUN data from exported g1m
        modeldirs = [x for x in glob.glob('*_MODEL_*') if os.path.isdir(x)]
        models = [value for value in modeldirs if value in [x[:-4] for x in glob.glob('*_MODEL_*.g1m')]]
        if len(models) > 0:
            for i in range(len(models)):
                parseG1M(models[i])