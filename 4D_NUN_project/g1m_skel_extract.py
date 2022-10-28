# Skeleton data extractor for G1M files.
# Based entirely off the work of Joschuka (fmt_g1m / Project G1M), huge thank you to Joschuka!
#
# Transforming rotation and position of bones from reltive positions to absolute posistions seems to get
# slightly different results than Noesis libraries; I don't have access to original source code but it
# makes sense to me to use quaternions exclusively rather than converting everything to matrices since
# G1M stores the skeletons using quaternions.  Hopefully this is more accurate, rather than less.  Final 
# transformation matrices are included in 4x3 format for convenience.
#
# Requires both numpy and pyquaternion
# These can be installed by:
# /path/to/python3 -m pip install numpy quaternion
#
# Steps:
# 1. Extract fmt/ib/vb from desired g1m directories with g1m_export.exe 
# 2. Run this script (in the folder with the g1m file).
#
# GitHub eArmada8/gust_stuff

import glob, os, io, sys, struct, json, numpy
from pyquaternion import Quaternion

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
            bone['q_wxyz'] = bone['rotation_q'][-1:]+bone['rotation_q'][:-1] # x,y,z,w
            quat = Quaternion(bone['q_wxyz']) # w,x,y,z
            bone['position'] = list(struct.unpack(e+"4f",f.read(16))) # x,y,z,w
            bone['pos_xyz'] = bone['position'][0:3]
            bone['boneMatrixTransform'] = quat.transformation_matrix
            bone['boneMatrixTransform'][3] = bone['position']
            bone['boneMatrixTransform'] = numpy.delete(bone['boneMatrixTransform'], -1, 1)
            bone['boneMatrixTransform'] = bone['boneMatrixTransform'].tolist()
            localBoneMatrices.append(bone['boneMatrixTransform'])
            boneList.append(bone)
        g1ms_section["localBoneMatrices"] = localBoneMatrices
        g1ms_section["boneList"] = boneList
    return(g1ms_section)

# Takes quat/pos relative to parent, and reorients / moves to be relative to the origin.
# Parent bone must already be transformed.
def calc_abs_rotation_position(bone, parent_bone):
    q1 = Quaternion(bone['q_wxyz'])
    qp = Quaternion(parent_bone['abs_q'])
    bone["abs_q"] = list(q1 * qp)
    bone["abs_p"] = rotated_p = (numpy.array(qp.rotate(bone['pos_xyz'])) + parent_bone['abs_p']).tolist()
    bone["abs_tm"] = Quaternion(bone["abs_q"]).transformation_matrix.tolist()
    bone["abs_tm"] = numpy.delete(bone["abs_tm"], -1, 1)
    bone["abs_tm"][3] = bone["abs_p"]
    bone["abs_tm"] = bone["abs_tm"].tolist()
    return(bone)

# In fmt_g1m, used only on primary skeleton; this function is performed in combine_skeleton() for 2nd layer
def calc_abs_skeleton(base_skel_data):
    for bone in range(len(base_skel_data['boneList'])):
        parentId = base_skel_data['boneList'][bone]['parentID']
        if parentId > -1:
            current_bone = base_skel_data['boneList'][bone]
            parent_bone = [x for x in base_skel_data['boneList'] if x['i'] == parentId][0]
            # Transform from relative rotation / position to absolute
            base_skel_data['boneList'][bone] = calc_abs_rotation_position(current_bone, parent_bone)
        else: #First bone (bone_0) is already absolute, no need to transform
            base_skel_data['boneList'][bone]['abs_q'] = base_skel_data['boneList'][bone]['q_wxyz']
            base_skel_data['boneList'][bone]['abs_p'] = base_skel_data['boneList'][bone]['pos_xyz']
            base_skel_data['boneList'][bone]['abs_tm'] = base_skel_data['boneList'][bone]['boneMatrixTransform']
    return(base_skel_data)

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
            bone['i'] = i + externalOffsetList
            bone['bone_id'] = 'Clothbone_' + str(i)
            if bone['parentID'] < 0:
                bone['parentID'] = bone['parentID'] & 0xFFFF
            else:
                bone['parentID'] = bone['parentID'] + externalOffsetList
            parent_bone = [x for x in combined_data['boneList'] if x['i'] == bone['parentID']][0]
            combined_data['boneList'].append(calc_abs_rotation_position(bone, parent_bone))
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
            model_skel_data = calc_abs_skeleton(parseG1M(args.g1m_filename[:-4]))
            with open(args.g1m_filename+"_skel.json", "wb") as f:
                f.write(json.dumps(model_skel_data, indent=4).encode("utf-8"))
    else:
        # When run without command line arguments, it will attempt to obtain skeleton data from exported g1m
        modeldirs = [x for x in glob.glob('*_MODEL_*') if os.path.isdir(x)]
        models = [value for value in modeldirs if value in [x[:-4] for x in glob.glob('*_MODEL_*.g1m')]]
        if len(models) > 0:
            for i in range(len(models)):
                # Need to add logic here to detect if skeleton is external
                base_skel_data = calc_abs_skeleton(parseG1M(models[i].split("_MODEL_")[0]+'_MODEL'))
                model_skel_data = parseG1M(models[i])
                skel_data = combine_skeleton(base_skel_data, model_skel_data)
                with open(models[i]+"/skel_data.json", "wb") as f:
                    f.write(json.dumps(skel_data, indent=4).encode("utf-8"))
