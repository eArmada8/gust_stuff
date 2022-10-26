# Skeleton data extractor for G1M files.
# Based entirely off the work of Joschuka (fmt_g1m / Project G1M), huge thank you to Joschuka!
#
# Steps:
# 1. Extract fmt/ib/vb from desired g1m directories with g1m_export.exe 
# 2. Run this script (in the folder with the g1m file).
#
# GitHub eArmada8/gust_stuff

import glob, os, io, sys, struct, json, numpy

def quaternionto3x3matrix(q): #[x,y,z,w]
    return(numpy.array([\
        [2*(q[3]*q[3]+q[0]*q[0])-1, 2*(q[0]*q[1]-q[3]*q[2]), 2*(q[0]*q[2]+q[3]*q[1])], \
        [2*(q[0]*q[1]+q[3]*q[2]), 2*(q[3]*q[3]+q[1]*q[1])-1, 2*(q[1]*q[2]-q[3]*q[0])], \
        [2*(q[0]*q[2]-q[3]*q[1]), 2*(q[1]*q[2]+q[3]*q[0]), 2*(q[3]*q[3]+q[2]*q[2])-1] \
        ]))

def parseG1MS(g1ms_chunk,e):
    g1ms_section = {}
    with io.BytesIO(g1ms_chunk) as f:
        g1ms_section["magic"] = f.read(4).decode("utf-8")
        g1ms_section["version"], g1ms_section["size"], = struct.unpack(e+"II", f.read(8))
        jointDataOffset, unknown = struct.unpack(e+"II", f.read(8))
        g1ms_section["jointCount"], g1ms_section["jointIndicesCount"], g1ms_section["layer"] = struct.unpack(e+"HHH", f.read(6))
        f.seek(2,1)
        boneIDList = []
        boneToBoneID = {}
        for i in range(g1ms_section["jointIndicesCount"]):
            id, = struct.unpack(e+"H", f.read(2))
            boneIDList.append(id)
            if (id != 0xFFFF):
                boneToBoneID[id] = i
        g1ms_section["boneIDList"] = boneIDList
        g1ms_section["boneToBoneID"] = boneToBoneID
        f.seek(jointDataOffset,0)
        localBoneMatrices = []
        boneList = []
        for i in range(g1ms_section["jointCount"]):
            bone = {}
            bone['i'] = i
            bone['bone_id'] = 'bone_' + str(boneToBoneID[i])
            bone['scale'] = struct.unpack(e+"3f",f.read(12))
            bone['parentID'], = struct.unpack(e+"i", f.read(4))
            bone['rotation_q'] = list(struct.unpack(e+"4f",f.read(16))) # x,y,z,w
            bone['position'] = list(struct.unpack(e+"4f",f.read(16))) # x,y,z,w
            bone['boneMatrixTransform'] = numpy.r_[numpy.linalg.inv(quaternionto3x3matrix(bone['rotation_q'])), \
            [bone['position'][0:3]]].tolist()
            localBoneMatrices.append(bone['boneMatrixTransform'])
            boneList.append(bone)
        g1ms_section["localBoneMatrices"] = localBoneMatrices
        g1ms_section["boneList"] = boneList
    return(g1ms_section)

def combine_skeleton(base_skel_data, model_skel_data):
    if model_skel_data['jointIndicesCount'] == len(base_skel_data['boneIDList']):
        return(base_skel_data)
    else: # Everything below here is untested! (The model I have access to does not have extra bones)
        combined_data = base_skel_data
        externalOffset = len(combined_data['boneIDList'])
        externalOffsetList = len(combined_data['boneList'])
        for i in range(model_skel_data['jointIndicesCount']):
            id = model_skel_data['boneIDList'][i]['id']
            if i >= externalOffset or i ==0:
                combined_data['boneIDList'].append(id + externalOffsetList +1)
            if (id != 0xFFFF and i != 0):
                combined_data['boneToBoneID'][id + externalOffsetList] = i
        for i in range(model_skel_data["jointCount"]):
            bone = model_skel_data['boneList'][i]
            if bone['parentID'] < 0:
                bone['i'] = i + externalOffsetList
                bone['bone_id'] = 'Clothbone_' + str(i)
                bone['parentID'] = bone['parentID'] & 0xFFFF
                parent_bone = [x for x in combined_data['boneList'] if x['i'] == bone['parentID']][0]
                bone['boneMatrixTransform'] = (numpy.array(bone['boneMatrixTransform']) * numpy.array(parent_bone['boneMatrixTransform'])).tolist()
                combined_data['boneList'].append(bone)
            else:
                bone['i'] = i + externalOffsetList
                bone['bone_id'] = 'Clothbone_' + str(i)
                bone['parentID'] = bone['parentID'] + externalOffsetList
                parent_bone = [x for x in combined_data['boneList'] if x['i'] == bone['parentID']][0]
                bone['boneMatrixTransform'] = (numpy.array(bone['boneMatrixTransform']) * numpy.array(parent_bone['boneMatrixTransform'])).tolist()
                combined_data['boneList'].append(bone)
        return(combined_data)

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
        have_skeleton = False
        for i in range(chunks["count"]):
            chunk = {}
            chunk["start_offset"] = f.tell()
            chunk["magic"] = f.read(4).decode("utf-8")
            chunk["version"] = f.read(4).hex()
            chunk["size"], = struct.unpack(e+"I", f.read(4))
            chunks["chunks"].append(chunk)
            if chunk["magic"] in ['G1MS', 'SM1G'] and have_skeleton == False:
                f.seek(chunk["start_offset"],0)
                g1ms_data = parseG1MS(f.read(chunk["size"]),e)
                have_skeleton == True # I guess some games duplicate this section?
            else:
                f.seek(chunk["start_offset"] + chunk["size"],0) # Move to next chunk
            file["chunks"] = chunks
    return(g1ms_data)

if __name__ == "__main__":
    # Set current directory
    os.chdir(os.path.abspath(os.path.dirname(__file__)))
    if len(sys.argv) > 1:
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument('-o', '--overwrite', help="Overwrite existing files", action="store_true")
        parser.add_argument('g1m_filename', help="Name of g1m file to extract G1MS data (required).")
        args = parser.parse_args()
        if os.path.exists(args.g1m_filename) and args.g1m_filename[-4:].lower() == '.g1m':
            model_skel_data = parseG1M(args.g1m_filename[:-4])
            with open(args.g1m_filename+"_skel.json", "wb") as f:
                f.write(json.dumps(model_skel_data, indent=4).encode("utf-8"))
    else:
        # When run without command line arguments, it will attempt to obtain skeleton data from exported g1m
        modeldirs = [x for x in glob.glob('*_MODEL_*') if os.path.isdir(x)]
        models = [value for value in modeldirs if value in [x[:-4] for x in glob.glob('*_MODEL_*.g1m')]]
        if len(models) > 0:
            for i in range(len(models)):
                # Need to add logic here to detect if skeleton is external
                base_skel_data = parseG1M("_".join(models[i].split("_")[:-1]))
                model_skel_data = parseG1M(models[i])
                skel_data = combine_skeleton(base_skel_data, model_skel_data)
                with open(models[i]+"/skel_data.json", "wb") as f:
                    f.write(json.dumps(skel_data, indent=4).encode("utf-8"))
