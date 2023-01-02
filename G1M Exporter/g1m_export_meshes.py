# Mesh extractor for G1M files, now includes skeleton extraction code as well.
#
# Based primarily off the work of GitHub/Joschuka and GitHub/three-houses-research-team,
# huge thank you!  Also many thanks to eterniti for sharing code with me to reference.
#
# This code includes functions to convert bones from local space to model space in bind pose, which will
# be needed for modifying 4D meshes.  As such, it requires both numpy and pyquaternion.
#
# These can be installed by:
# /path/to/python3 -m pip install pyquaternion
#
# Steps:
# 1. Use Gust Tools to extract G1M from the .elixir.gz file.
# 2. Run this script (in the folder with the g1m file).
#
# For command line options:
# /path/to/python3 g1m_export_meshes.py --help
#
# GitHub eArmada8/gust_stuff

import glob, os, io, sys, struct, copy, json, numpy
from pyquaternion import Quaternion
from lib_fmtibvb import *

# This script transforms cloth meshes (aka 4D meshes) by default, change the following line to False to disable
transform_cloth_mesh_default = True

# From GitHub/uyjulian's ED9 MDL parser, thank you
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

def parseG1MS(g1ms_chunk,e):
    g1ms_section = {}
    with io.BytesIO(g1ms_chunk) as f:
        g1ms_section["magic"] = f.read(4).decode("utf-8")
        g1ms_section["version"], g1ms_section["size"], = struct.unpack(e+"II", f.read(8))
        jointDataOffset, unknown = struct.unpack(e+"II", f.read(8))
        g1ms_section["jointCount"], g1ms_section["jointIndicesCount"], g1ms_section["layer"] = struct.unpack(e+"HHH", f.read(6))
        g1ms_section["externalOffset"], g1ms_section["externalOffsetList"], g1ms_section["externalOffsetMax"] = 0, 0, 0
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
            bone['q_wxyz'] = bone['rotation_q'][-1:]+bone['rotation_q'][:-1] # w,x,y,z
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
    bone["abs_q"] = list((qp * q1).unit)
    bone["abs_p"] = (numpy.array(qp.rotate(bone['pos_xyz'])) + parent_bone['abs_p']).tolist()
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

def name_bones(skel_data, oid):
    for bone in range(len(skel_data['boneList'])):
        # Not sure if the auto-generated id is needed, but will preserve it before overwriting it
        skel_data['boneList'][bone]['bone_id_auto'] = skel_data['boneList'][bone]['bone_id']
        if skel_data['boneToBoneID'][skel_data['boneList'][bone]['i']] in oid['bones'].keys():
            skel_data['boneList'][bone]['bone_id_auto'] = skel_data['boneList'][bone]['bone_id']
            skel_data['boneList'][bone]['bone_id'] = oid['bones'][skel_data['boneToBoneID'][skel_data['boneList'][bone]['i']]]
    return(skel_data)

def combine_skeleton(base_skel_data, model_skel_data):
    if model_skel_data['jointIndicesCount'] == len(base_skel_data['boneIDList']):
        return(base_skel_data)
    else:
        combined_data = base_skel_data
        combined_data['externalOffset'] = len(combined_data['boneIDList'])
        combined_data['externalOffsetList'] = len(combined_data['boneList'])
        for i in range(model_skel_data['jointIndicesCount']):
            id = model_skel_data['boneIDList'][i]
            if i >= combined_data['externalOffset'] or i == 0:
                combined_data['boneIDList'].append(id + combined_data['externalOffsetList'] + 1)
            if (id != 0xFFFF and i != 0):
                combined_data['boneToBoneID'][id + combined_data['externalOffsetList']] = i
        for i in range(model_skel_data["jointCount"]):
            combined_data['externalOffsetMax'] += 1
            bone = model_skel_data['boneList'][i]
            bone['i'] = i + combined_data['externalOffsetList']
            bone['bone_id'] = 'Clothbone_' + str(i)
            if bone['parentID'] < 0:
                bone['parentID'] = bone['parentID'] & 0xFFFF
            else:
                bone['parentID'] = bone['parentID'] + combined_data['externalOffsetList']
            parent_bone = [x for x in combined_data['boneList'] if x['i'] == bone['parentID']][0]
            combined_data['boneList'].append(calc_abs_rotation_position(bone, parent_bone))
        return(combined_data)

def parseNUNO1(chunkVersion, f, e):
    nuno1_block = {}
    nuno1_block['name'] = "nuno1"
    nuno1_block['parentBoneID'] = None
    # Not sure if it should just be nuno1_block['parentBoneID'], = struct.unpack(e+"I",f.read(4))
    # instead of the next 2 lines
    a,b = struct.unpack(e+"HH", f.read(4))
    nuno1_block['parentBoneID'] = a if e == '<' else b
    controlPointCount, = struct.unpack(e+"I", f.read(4))
    unknownSectionCount, = struct.unpack(e+"I", f.read(4))
    skip1, = struct.unpack(e+"I", f.read(4))
    skip2, = struct.unpack(e+"I", f.read(4))
    skip3, = struct.unpack(e+"I", f.read(4))
    f.read(0x3C)
    if chunkVersion > 0x30303233:
        f.read(0x10)
    if chunkVersion >= 0x30303235:
        f.read(0x10)
    nuno1_block['controlPoints'] = []
    for i in range(controlPointCount):
        nuno1_block['controlPoints'].append(struct.unpack("ffff", f.read(16)))
    nuno1_block['influences'] = []
    for i in range(controlPointCount):
        influence = {}
        influence['P1'], influence['P2'], influence['P3'], influence['P4'], influence['P5'],\
            influence['P6'] = struct.unpack("iiiiff", f.read(24))
        nuno1_block['influences'].append(influence)
    # reading the unknown sections data
    f.seek(48 * unknownSectionCount,1)
    f.seek(4 * skip1,1)
    f.seek(4 * skip2,1)
    f.seek(4 * skip3,1)
    return(nuno1_block)

def parseNUNO2(chunkVersion, f, e):
    nuno2_block = {}
    nuno2_block['name'] = "nuno2"
    nuno2_block['parentBoneID'] = None
    # Not sure if it should just be nuno2_block['parentBoneID'], = struct.unpack(e+"I",f.read(4))
    # instead of the next 2 lines
    a,b = struct.unpack("<HH", f.read(4))
    nuno2_block['parentBoneID'] = a if e == '<' else b
    f.read(0x68)
    nuno2_block['controlPoint'] = struct.unpack("fff", f.read(12))
    f.read(0x08)
    return(nuno2_block)

def parseNUNO3(chunkVersion, f, e):
    nuno3_block = {}
    nuno3_block['name'] = "nuno3"
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
        influence['P1'], influence['P2'], influence['P3'], influence['P4'], influence['P5'],\
            influence['P6'] = struct.unpack(e+"iiiiff", f.read(24))
        nuno3_block['influences'].append(influence)
    # reading the unknown sections data
    f.seek(48 * unknownSectionCount,1)
    f.seek(4 * skip1,1)
    f.seek(8 * skip2,1)
    f.seek(12 * skip3,1)
    f.seek(8 * skip4,1)
    return(nuno3_block)

def parseNUNO5(chunkVersion, f, e, entryIDtoNunoID):
    nuno5_block = {}
    nuno5_block['name'] = "nuno5"
    nuno5_block['parentBoneID'] = None
    nuno5_block['parentSetID'] = -1
    # Not sure if it should just be nuno5_block['parentBoneID'], = struct.unpack(e+"I",f.read(4))
    # instead of the next 2 lines
    a,b = struct.unpack("<HH", f.read(4))
    nuno5_block['parentBoneID'] = a if e == '<' else b
    f.seek(4,1)
    lodCount, = struct.unpack(e+"I", f.read(4))
    f.seek(8,1)
    nuno5_block['entryID'], nuno5_block['entryIDflag'] = struct.unpack(e+"2H", f.read(4))
    if nuno5_block['entryIDflag'] & 0x7FF:
        nuno5_block['parentSetID'] = entryIDtoNunoID[nuno5_block['entryID']]
    f.seek(12,1)
    for i in range(lodCount):
        controlPointCount, = struct.unpack(e+"I", f.read(4))
        cpSectionRelatedCount, = struct.unpack(e+"I", f.read(4))
        skip = struct.unpack(e+"9I", f.read(36))
        f.seek(4,1)
        current_offset = f.tell()
        cpOffset, = struct.unpack(e+"I", f.read(4))
        f.seek(current_offset+cpOffset,0)
        if i == 0: # We only want the first LOD, apparently?
            nuno5_block['controlPoints'] = []
            nuno5_block['influences'] = []
            for i in range(controlPointCount):
                controlpoint = list(struct.unpack(e+"3f", f.read(12)))
                controlpoint.append(1.0)
                nuno5_block['controlPoints'].append(controlpoint)
                f.seek(12,1)
                influence = {}
                # Per Project G1M, P5 and P6 are incorrect, but we do not use them.
                influence['P1'], influence['P2'], influence['P3'], influence['P4'], influence['P5'] = \
                    struct.unpack(e+"iiiif", f.read(20))
                influence['P6'] = 0.0
                nuno5_block['influences'].append(influence)
        else:
            f.seek(44 * controlPointCount,1)
        #Skip physics section
        f.seek(32 * controlPointCount,1)
        if (cpSectionRelatedCount == 3):
            f.seek(24 * controlPointCount,1)
        f.seek(skip[0] * 4 + skip[1] * 12 + skip[2] * 16 + skip[3] * 12 +\
            skip[4] * 8 + skip[5] * 48 + skip[6] * 72 + skip[7] * 32, 1)
        if skip[8] > 0:
            for j in range(skip[8]):
                current_offset = f.tell()
                tempCount, = struct.unpack(e+"I", f.read(4))
                f.seek(current_offset + (4 * tempCount) + 16)
    return(nuno5_block)

def parseNUNV1(chunkVersion, f, e):
    nunv1_block = {}
    nunv1_block['name'] = "nunv1"
    nunv1_block['parentBoneID'] = None
    # Not sure if it should just be nunv1_block['parentBoneID'], = struct.unpack(e+"I",f.read(4))
    # instead of the next 2 lines
    a,b = struct.unpack("<HH", f.read(4))
    nunv1_block['parentBoneID'] = a if e == '<' else b
    controlPointCount, = struct.unpack(e+"I", f.read(4))
    unknownSectionCount, = struct.unpack(e+"I", f.read(4))
    skip1, = struct.unpack(e+"i", f.read(4))
    f.read(0x54)
    if chunkVersion >= 0x30303131:
        f.read(0x10)
    nunv1_block['controlPoints'] = []
    for i in range(controlPointCount):
        nunv1_block['controlPoints'].append(struct.unpack("ffff", f.read(16)))
    nunv1_block['influences'] = []
    for i in range(controlPointCount):
        influence = {}
        influence['P1'], influence['P2'], influence['P3'], influence['P4'], influence['P5'],\
            influence['P6'] = struct.unpack(e+"iiiiff", f.read(24))
        nunv1_block['influences'].append(influence)
    # reading the unknown sections data
    f.seek(48 * unknownSectionCount,1)
    f.seek(4 * skip1,1)
    return(nunv1_block)

def parseNUNS1(chunkVersion, f, e):
    nuns1_block = {}
    nuns1_block['name'] = "nuns1"
    nuns1_block['parentBoneID'] = None
    # Not sure if it should just be nuns1_block['parentBoneID'], = struct.unpack(e+"I",f.read(4))
    # instead of the next 2 lines
    a,b = struct.unpack("<HH", f.read(4))
    nuns1_block['parentBoneID'] = a if e == '<' else b
    controlPointCount, = struct.unpack(e+"I", f.read(4))
    f.read(0xB8)
    for i in range(controlPointCount):
        nuns1_block['controlPoints'].append(struct.unpack("ffff", f.read(16)))
    nuns1_block['influences'] = []
    for i in range(controlPointCount):
        influence = {}
        influence['P1'], influence['P2'], influence['P3'], influence['P4'], influence['P5'], influence['P6'],\
            influence['P7'], influence['P8'] = struct.unpack(e+"iiiiffii", f.read(24))
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

def parseNUNO(nuno_chunk, e):
    nuno_section = {}
    with io.BytesIO(nuno_chunk) as f:
        nuno_section["magic"] = f.read(4).decode("utf-8")
        nuno_section["version"], nuno_section["size"], nuno_section["chunk_count"], = struct.unpack(e+"III", f.read(12))
        nuno_section["chunks"] = []
        for i in range(nuno_section["chunk_count"]):
            chunk = {}
            chunk["Type"],chunk["size"],chunk["subchunk_count"] = struct.unpack(e+"III", f.read(12))
            chunk["subchunks"] = []
            entryIDtoNunoID = {}
            if chunk["Type"] in [0x00030001, 0x00030002, 0x00030003, 0x00030005]: # Skip NUNO4, unknown
                for j in range(chunk["subchunk_count"]):
                    if chunk["Type"] == 0x00030001:
                        chunk["subchunks"].append(parseNUNO1(nuno_section["version"],f,e))
                    elif chunk["Type"] == 0x00030002:
                        chunk["subchunks"].append(parseNUNO2(nuno_section["version"],f,e))
                    elif chunk["Type"] == 0x00030003:
                        chunk["subchunks"].append(parseNUNO3(nuno_section["version"],f,e))
                    elif chunk["Type"] == 0x00030005:
                        chunk["subchunks"].append(parseNUNO5(nuno_section["version"],f,e, entryIDtoNunoID))
                        if not chunk["subchunks"][-1]["entryID"] in entryIDtoNunoID.keys():
                            entryIDtoNunoID[chunk["subchunks"][-1]["entryID"]] = j
            else:
                f.seek(chunk["size"],1)
            if chunk["Type"] == 0x00030005:
                # Untested, the model I have access to does not have subsets
                nunoIDToSubsetMap = {}
                for j in range(len(chunk["subchunks"])):
                    if chunk["subchunks"][j]["parentSetID"] >= 0:
                        if not (chunk["subchunks"][j]["parentSetID"] in nunoIDToSubsetMap.keys()):
                        # New Map
                            tempMap = {}
                            parentchunk = chunk["subchunks"][chunk["subchunks"][j]["parentSetID"]]
                            for k in range(len(parentchunk["controlPoints"])):
                                tempMap[sum(parentchunk["controlPoints"][i])] = k
                            nunoIDToSubsetMap[chunk["subchunks"][j]["parentSetID"]] = tempMap
                        else:
                        #Existing Map
                            tempMap = nunoIDToSubsetMap[chunk["subchunks"][j]["parentSetID"]]
                            for k in range(len(chunk["subchunks"][j]["controlPoints"])):
                                if sum(chunk["subchunks"][j]["controlPoints"][k]) in tempMap.keys(): #should always be true?
                                    chunk["subchunks"][j]["influences"][k]['P1'] = \
                                        tempMap[sum(chunk["subchunks"][j]["controlPoints"][k])]
            nuno_section["chunks"].append(chunk)
    return(nuno_section)

def parseNUNV(nuno_chunk, e):
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

# This combines NUNO/NUNV/NUNS struct into a single stack
def stack_nun(nun_data):
    nun_stack = []
    for key in nun_data:
        for i in range(len(nun_data[key]['chunks'])):
            for j in range(len(nun_data[key]['chunks'][i]['subchunks'])):
                nun_stack.append(nun_data[key]['chunks'][i]['subchunks'][j])
    return nun_stack

def make_drivermesh_fmt():
    return({'stride': '36', 'topology': 'trianglelist', 'format': 'DXGI_FORMAT_R16_UINT',\
    'elements': [{'id': '0', 'SemanticName': 'POSITION', 'SemanticIndex': '0', 'Format': 'R32G32B32_FLOAT',\
    'InputSlot': '0', 'AlignedByteOffset': '0', 'InputSlotClass': 'per-vertex', 'InstanceDataStepRate': '0'},\
    {'id': '1', 'SemanticName': 'BLENDWEIGHT', 'SemanticIndex': '0', 'Format': 'R32G32B32A32_FLOAT',\
    'InputSlot': '0', 'AlignedByteOffset': '12', 'InputSlotClass': 'per-vertex', 'InstanceDataStepRate': '0'},\
    {'id': '2', 'SemanticName': 'BLENDINDICES', 'SemanticIndex': '0', 'Format': 'R16G16B16A16_UINT',\
    'InputSlot': '0', 'AlignedByteOffset': '28', 'InputSlotClass': 'per-vertex', 'InstanceDataStepRate': '0'}]})

def computeCenterOfMass(position, weights, bones, nunoMap, nun_transform_info):
    temp = [0,0,0]
    for bone_num in range(len(bones)):
        bone = [x for x in nun_transform_info if x['bone_name'].split('_')[-1] == str(nunoMap[bones[bone_num]])][0]
        temp += Quaternion(bone['abs_q']).rotate(position) + numpy.array(bone['abs_p']) * weights[bone_num]
    return(temp)

def calc_nun_maps(nun_data, skel_data):
    nunvOffset = 0
    nunsOffset = 0
    clothMap = []
    clothParentIDMap = []
    driverMeshList = []
    for i in range(len(nun_data)):
        try:
            boneStart = len(skel_data['boneList'])
            parentBone = skel_data['boneIDList'][nun_data[i]['parentBoneID']]
            nunoMap = {}
            vertices = []
            skinWeightList = []
            skinIndiceList = []
            triangles = []
            vertCount = 0
            transform_info = []
            is_nuno5 = (nun_data[i]['name'] == 'nuno5')
            for pointIndex in range(len(nun_data[i]['controlPoints'])):
                transform_point_info = {}
                p = nun_data[i]['controlPoints'][pointIndex][0:3]
                transform_point_info['p'] = list(p)
                link = nun_data[i]['influences'][pointIndex]
                nunoMap[pointIndex] = len(skel_data['boneList'])
                q = Quaternion()
                parentID = link['P3']
                transform_point_info['parentID'] = parentID
                transform_point_info['parentBone'] = parentBone
                if (parentID == -1):
                    parentID = parentBone
                    parentID_bone = [x for x in skel_data['boneList'] if x['i'] == parentID][0]
                    q_wxyz = q
                    pos_xyz = p
                else:
                    parentID += boneStart
                    parent_bone = [x for x in skel_data['boneList'] if x['i'] == parentBone][0]
                    parentID_bone = [x for x in skel_data['boneList'] if x['i'] == parentID][0]
                    # Trying to reproduce Noesis 4x3 inversion of parentID_bone here;
                    # 4x3 inversion appears to be 4x4 inversion with xyzw in the column, not row
                    #if not is_nuno5:
                    if True:
                        q_wxyz = Quaternion(parent_bone['abs_q']) * Quaternion(parentID_bone['abs_q']).inverse
                        tm_temp = Quaternion(parentID_bone['abs_q']).transformation_matrix
                        tm_temp[0:3,3] = parentID_bone['abs_p'] # Insert into 4th column of matrix
                        pIDinv_pos_xyz = numpy.linalg.inv(tm_temp)[0:3,3] # Read 4th column after inversion
                        temp_p = (numpy.array(Quaternion(parentID_bone['abs_q']).inverse.rotate(parent_bone['abs_p'])) + pIDinv_pos_xyz).tolist()
                    #else:
                        #q_wxyz = Quaternion(parent_bone['abs_q'])
                        #temp_p = parent_bone['abs_p']
                    pos_xyz = (numpy.array(q_wxyz.rotate(p)) + temp_p).tolist()
                bone = {}
                bone['i'] = len(skel_data['boneList'])
                bone['bone_id'] = nun_data[0]['name'] + 'bone_p' + str(parentBone) + "_" + str(len(skel_data['boneList']))
                bone['parentBone'] = parentBone
                bone['parentID'] = parentID
                bone['q_wxyz'] = list(q_wxyz)
                bone['pos_xyz'] = pos_xyz
                parent_bone = [x for x in skel_data['boneList'] if x['i'] == parentID][0]
                #if is_nuno5 and link['P5'] == 0:
                if False:
                    bone["abs_q"] = bone['q_wxyz']
                    bone["abs_p"] = bone['pos_xyz']
                else:
                    # Convert relative to absolute
                    qp = Quaternion(parent_bone['abs_q'])
                    bone["abs_q"] = list((qp * q_wxyz).unit)
                    bone["abs_p"] = (numpy.array(qp.rotate(bone['pos_xyz'])) + parent_bone['abs_p']).tolist()
                transform_point_info['bone_name'] = bone["bone_id"]
                transform_point_info['abs_q'] = bone["abs_q"]
                transform_point_info['abs_p'] = bone["abs_p"]
                bone["abs_tm"] = Quaternion(bone["abs_q"]).transformation_matrix.tolist()
                bone["abs_tm"] = numpy.delete(bone["abs_tm"], -1, 1)
                bone["abs_tm"][3] = bone["abs_p"]
                bone["abs_tm"] = bone["abs_tm"].tolist()
                skel_data['boneList'].append(bone)
                boneMatrixUpdateQ = Quaternion(skel_data['boneList'][-1]['abs_q'])
                updatedPosition = (numpy.array(boneMatrixUpdateQ.rotate([0.0, 0.0, 0.0])) + skel_data['boneList'][-1]['abs_p']).tolist()
                transform_point_info['NewparentID'] = parentID
                transform_point_info['updatedPosition'] = updatedPosition
                transform_info.append(transform_point_info)
                vertices.append(updatedPosition)
                vertCount += 1
                skinWeightList.append([1.0, 0.0, 0.0, 0.0])
                skinIndiceList.append([len(skel_data['boneList']) - 1, 0, 0, 0])
                if (link['P1'] > 0 and link['P3'] > 0):
                    triangles.append([int(pointIndex), link['P1'], link['P3']])
                if (link['P2'] > 0 and link['P4'] > 0):
                    triangles.append([int(pointIndex), link['P2'], link['P4']])
            driverMesh = {}
            driverMesh["vertCount"] = vertCount
            driverMesh["vertices"] = [{"SemanticName": 'POSITION', "SemanticIndex": 0, "Buffer": vertices},\
                {"SemanticName": 'BLENDWEIGHT', "SemanticIndex": 0, "Buffer": skinWeightList},
                {"SemanticName": 'BLENDINDICES', "SemanticIndex": 0, "Buffer": skinIndiceList}]
            driverMesh["indices"] = triangles
            driverMesh["transform_info"] = transform_info
            clothMap.append(nunoMap)
            clothParentIDMap.append(parentBone)
            driverMeshList.append(driverMesh)
        except:
            pass
    return({'clothMap': clothMap, 'clothParentIDMap': clothParentIDMap, 'driverMeshList': driverMeshList})

def parseG1MG(g1mg_chunk,e):
    g1mg_section = {}
    with io.BytesIO(g1mg_chunk) as f:
        g1mg_section["magic"] = f.read(4).decode("utf-8")
        g1mg_section["version"], g1mg_section["size"], = struct.unpack(e+"II", f.read(8))
        g1mg_section["platform"] = f.read(4).decode("utf-8")
        g1mg_section["reserved"], min_x, min_y, min_z, max_x, max_y, max_z = struct.unpack(e+"I6f", f.read(28))
        g1mg_section["bounding_box"] = {'min_x': min_x, 'min_y': min_y, 'min_z': min_z,\
            'max_x': max_x, 'max_y': max_y, 'max_z': max_z}
        g1mg_section["sectionCount"], = struct.unpack(e+"I", f.read(4))

        sections = []
        for i in range(g1mg_section["sectionCount"]):
            section = {}
            section['offset'] = f.tell()
            section['type'] = ''
            section['magic'], section['size'], section['count'] = struct.unpack(e+"3I", f.read(12))
            match section['magic']:
                case 0x00010001:
                    section['type'] = 'GEOMETRY_SOCKETS'
                    sockets_groups = []
                    for j in range(section['count']):
                        sockets_group = {'start': {}, 'end': {}}
                        sockets_group['start']['bone_id'], sockets_group['start']['unknown'],\
                            sockets_group['start']['weight'] = struct.unpack(e+"2hf", f.read(8))
                        sockets_group['start']['scale'] = struct.unpack(e+"3f", f.read(12))
                        sockets_group['start']['position'] = struct.unpack(e+"3f", f.read(12))
                        sockets_group['end']['bone_id'], sockets_group['end']['unknown'],\
                            sockets_group['end']['weight'] = struct.unpack(e+"2hf", f.read(8))
                        sockets_group['end']['scale'] = struct.unpack(e+"3f", f.read(12))
                        sockets_group['end']['position'] = struct.unpack(e+"3f", f.read(12))
                        sockets_groups.append(sockets_group)
                    tail_length = (section['size'] - (f.tell() - section['offset']))
                    section['tail'] = list(struct.unpack(e+"{0}I".format(int(tail_length/4)), f.read(tail_length)))
                    section['data'] = sockets_groups
                case 0x00010002:
                    section['type'] = 'MATERIALS'
                    texture_block = []
                    for j in range(section['count']):
                        texture_section = {}
                        texture_section['unknown1'], texture_section['textureCount'], texture_section['unknown2'],\
                            texture_section['unknown3'] = struct.unpack(e+"4I", f.read(16))
                        textures = []
                        for k in range(texture_section['textureCount']):
                            texture = {}
                            texture["id"], texture["layer"], texture["type"], \
                            texture["subtype"], texture["tilemodex"], texture["tilemodey"] = \
                                struct.unpack(e+"6H", f.read(12))
                            textures.append(texture)
                        texture_section['textures'] = textures
                        texture_block.append(texture_section)
                    section['data'] = texture_block
                case 0x00010003:
                    section['type'] = 'SHADER_PARAMS'
                    shader_blocks = []
                    for j in range(section['count']):
                        shader_info = {}
                        shader_info['shader_count'], = struct.unpack(e+"I", f.read(4))
                        shader_block = []
                        for j in range(shader_info['shader_count']):
                            shader = {}
                            shader["size"], name_size, shader["unk1"], shader["buffer_type"], shader["buffer_count"] = struct.unpack(e+"3I2H",f.read(16))
                            shader["name"] = f.read(name_size).replace(b'\x00',b'').decode()
                            shader["buffer"] = []
                            for k in range(shader["buffer_count"]):
                                match shader["buffer_type"]:
                                    case 1:
                                        shader["buffer"].append(struct.unpack(e+"f", f.read(4))[0])
                                    case 2:
                                        shader["buffer"].append(struct.unpack(e+"2f", f.read(8)))
                                    case 3:
                                        shader["buffer"].append(struct.unpack(e+"3f", f.read(12)))
                                    case 4:
                                        shader["buffer"].append(struct.unpack(e+"4f", f.read(16)))
                                    case 5:
                                        shader["buffer"].append(struct.unpack(e+"i", f.read(4))[0])
                            shader_block.append(shader)
                        shader_blocks.append(shader_block)
                    section['data'] = shader_blocks
                case 0x00010004:
                    section['type'] = 'VERTEX_BUFFERS'
                    vertex_block = []
                    for j in range(section['count']):
                        buffer = {}
                        buffer["unknown1"], buffer["stride"], buffer["count"] = struct.unpack(e+"3I", f.read(12))
                        if g1mg_section["version"] > 0x30303430:
                            buffer["unknown2"], = struct.unpack(e+"I", f.read(4))
                        buffer["offset"] = f.tell()
                        # Skipping over the actual buffer data here, switch to f.read to actually get the buffer
                        f.seek(buffer["stride"] * buffer["count"],1)
                        vertex_block.append(buffer)
                    section['data'] = vertex_block
                case 0x00010005:
                    section['type'] = 'VERTEX_ATTRIBUTES'
                    # I think this is correct?
                    #semantic_list = ['Position', 'JointWeight', 'JointIndex', 'Normal', 'PSize', 'UV',\
                    #'Tangent', 'Binormal', 'TessalationFactor', 'PosTransform', 'Color', 'Fog', 'Depth', 'Sample']
                    semantic_list = ['POSITION', 'BLENDWEIGHT', 'BLENDINDICES', 'NORMAL', 'PSIZE', 'TEXCOORD',\
                    'TANGENT', 'BINORMAL', 'TESSFACTOR', 'POSITIONT', 'COLOR', 'FOG', 'DEPTH', 'SAMPLE'] #What is Sample??
                    vertex_attr_block = []
                    for j in range(section['count']):
                        attributes = {}
                        list_count, = struct.unpack(e+"I", f.read(4))
                        attributes['buffer_list'] = struct.unpack(e+str(list_count)+"I", f.read(4*list_count))
                        attributes['attr_count'], = struct.unpack(e+"I", f.read(4))
                        attributes_list = []
                        for k in range(attributes['attr_count']):
                            attr = {}
                            attr['bufferID'], attr['offset'] = struct.unpack(e+"2H", f.read(4))
                            data_type, attr['dummy_var'], semantic, attr['layer'] = struct.unpack(e+"4B", f.read(4))
                            match data_type:
                                case 0x00:
                                    attr['dataType'] = 'R32_FLOAT' # Float_x1
                                case 0x01:
                                    attr['dataType'] = 'R32G32_FLOAT' # Float_x2
                                case 0x02:
                                    attr['dataType'] = 'R32G32B32_FLOAT' # Float_x3
                                case 0x03:
                                    attr['dataType'] = 'R32G32B32A32_FLOAT' # Float_x4
                                case 0x05:
                                    attr['dataType'] = 'R8G8B8A8_UINT' # UByte_x4
                                case 0x07:
                                    attr['dataType'] = 'R16G16B16A16_UINT' # UShort_x4
                                case 0x09:
                                    attr['dataType'] = 'R32G32B32A32_UINT' # UInt_x4, need confirmation per Project G1M
                                case 0x0A:
                                    attr['dataType'] = 'R16G16_FLOAT' # HalfFloat_x2
                                case 0x0B:
                                    attr['dataType'] = 'R16G16B16A16_FLOAT' # HalfFloat_x4
                                case 0x0D:
                                    attr['dataType'] = 'R8G8B8A8_UNORM' # NormUByte_x4
                                case 0xFF:
                                    attr['dataType'] = 'UNKNOWN' # Dummy
                                case _:
                                    attr['dataType'] = 'UNKNOWN' # Unknown
                            attr['semantic'] = semantic_list[semantic]
                            attributes_list.append(attr)
                        attributes['attributes_list'] = attributes_list
                        vertex_attr_block.append(attributes)
                    section['data'] = vertex_attr_block
                case 0x00010006:
                    section['type'] = 'JOINT_PALETTES'
                    joint_block = []
                    for j in range(section['count']):
                        joint_info = {}
                        joint_info['joint_count'], = struct.unpack(e+"I", f.read(4))
                        joints = []
                        for k in range(joint_info['joint_count']):
                            joint = {}
                            joint['G1MMIndex'], joint['physicsIndex'], joint['jointIndex'] = struct.unpack(e+"3I", f.read(12))
                            if joint['jointIndex'] > 0x80000000: #External Skeleton Bone
                                joint['physicsIndex'] = joint['physicsIndex'] ^ 0x80000000
                                joint['jointIndex'] = joint['jointIndex'] ^ 0x80000000
                                joint['0x80000000_flag'] = 'True'
                            else:
                                joint['0x80000000_flag'] = 'False'
                            joints.append(joint)
                        joint_info['joints'] = joints
                        joint_block.append(joint_info)
                    section['data'] = joint_block
                case 0x00010007:
                    section['type'] = 'INDEX_BUFFER'
                    index_block = []
                    for j in range(section['count']):
                        buffer = {}
                        buffer["count"], data_type = struct.unpack(e+"II", f.read(8))
                        if g1mg_section["version"] > 0x30303430:
                            buffer["unknown1"], = struct.unpack(e+"I", f.read(4))
                        buffer["dataType"] = "R{0}_UINT".format(data_type)
                        buffer["stride"] = int(data_type / 8)
                        buffer["offset"] = f.tell()
                        # Skipping over the actual buffer data here, switch to f.read to actually get the buffer
                        f.seek(buffer["stride"] * buffer["count"],1)
                        if (f.tell() % 4):
                            f.seek(4 - f.tell() % 4,1) # Align offset if needed
                        index_block.append(buffer)
                    section['data'] = index_block
                case 0x00010008:
                    section['type'] = 'SUBMESH'
                    submesh_blocks = []
                    for j in range(section['count']):
                        submesh_info = {}
                        submesh_info["submeshFlags"], submesh_info["vertexBufferIndex"], submesh_info["bonePaletteIndex"],\
                        submesh_info["boneIndex"], submesh_info["unknown"], submesh_info["shaderParamIndex"],\
                        submesh_info["materialIndex"], submesh_info["indexBufferIndex"], submesh_info["unknown2"],\
                        submesh_info["indexBufferPrimType"], submesh_info["vertexBufferOffset"], submesh_info["vertexCount"],\
                        submesh_info["indexBufferOffset"], submesh_info["indexCount"] = struct.unpack(e+"14I", f.read(56))
                        submesh_blocks.append(submesh_info)
                    section['data'] = submesh_blocks
                case 0x00010009:
                    #LOD
                    section['type'] = 'MESH_LOD'
                    lod_blocks = []
                    for j in range(section['count']):
                        lod_block = {}
                        lod_block["LOD"], = struct.unpack(e+"I", f.read(4))
                        if g1mg_section["version"] > 0x30303330:
                            lod_block["Group"], lod_block["GroupEntryIndex"] = struct.unpack(e+"2I", f.read(8))
                        else:
                            lod_block["Group"] = 0
                            lod_block["GroupEntryIndex"] = 0
                        lod_block["submeshCount1"], lod_block["submeshCount2"] = struct.unpack(e+"2I", f.read(8))
                        if g1mg_section["version"] > 0x30303340:
                            lod_block["lodRangeStart"], lod_block["lodRangeLength"], \
                            lod_block["unknown1"], lod_block["unknown2"] = struct.unpack(e+"4I", f.read(16))
                        else:
                            lod_block["lodRangeStart"] = 0
                            lod_block["lodRangeLength"] = 0
                        lods = []
                        for k in range(lod_block["submeshCount1"] + lod_block["submeshCount2"]):
                            lod = {}
                            lod["name"] = f.read(16).replace(b'\x00',b'').decode("ASCII")
                            # In Project G1M, clothID is meshType, and NUNID is externalID
                            lod["clothID"], lod["unknown"], lod["NUNID"], lod["indexCount"] = struct.unpack(e+"2H2I", f.read(12))
                            if (lod["indexCount"] > 0):
                                lod["indices"] = struct.unpack(e+"{0}I".format(lod["indexCount"]), f.read(4*lod["indexCount"]))
                            else:
                                f.seek(4,1)
                            lods.append(lod)
                        lod_block["lod"] = lods
                        lod_blocks.append(lod_block)
                    section['data'] = lod_blocks
                case _:
                    section['type'] = 'UNKNOWN'
            sections.append(section)
            f.seek(section['offset']+section['size'])
        g1mg_section["sections"] = sections
    return(g1mg_section)

def find_submeshes(model_mesh_metadata):
    # Grab the SUBMESH section
    subvbs = [x for x in model_mesh_metadata['sections'] if x['type'] == "SUBMESH"][0]
    # Build a quick list of the meshes, each with a list of submeshes
    vbs = []
    for i in range(len(subvbs['data'])):
        vbs.append(subvbs['data'][i]['vertexBufferIndex'])
    vbsubs = {}
    for vb in list(set(vbs)):
        vbsubs[vb] = []
    for i in range(len(subvbs['data'])):
        vbsubs[subvbs['data'][i]['vertexBufferIndex']].append(i)
    return(vbsubs)

def generate_fmts(model_mesh_metadata):
    # Grab metadata
    vb = [x for x in model_mesh_metadata['sections'] if x['type'] == "VERTEX_BUFFERS"][0]
    vb_attr = [x for x in model_mesh_metadata['sections'] if x['type'] == "VERTEX_ATTRIBUTES"][0]
    attr_list = [x['buffer_list'] for x in vb_attr['data']]
    ib = [x for x in model_mesh_metadata['sections'] if x['type'] == "INDEX_BUFFER"][0]
    subvbs = [x for x in model_mesh_metadata['sections'] if x['type'] == "SUBMESH"][0]
    vbsubs = find_submeshes(model_mesh_metadata)
    # Generate fmt structures from metadata
    fmts = []
    for i in range(len(vb_attr['data'])):
        vb_strides = [0] # Add in a dummy first value of 0, so AlignedByteOffset is calculated correctly
        for j in range(len(vb_attr['data'][i]['buffer_list'])):
            vb_strides.append(vb['data'][vb_attr['data'][i]['buffer_list'][j]]['stride'])
        fmt_elements = []
        for j in range(len(vb_attr['data'][i]['attributes_list'])):
            # Input Slot is set to zero, and AlignedByteOffset is set to offset + vb_strides[input slot]
            # because blender plugin does not support multiple input slots.
            fmt_element = {"id": str(j),
                "SemanticName": vb_attr['data'][i]['attributes_list'][j]["semantic"],\
                "SemanticIndex": str(vb_attr['data'][i]['attributes_list'][j]["layer"]),\
                "Format": vb_attr['data'][i]['attributes_list'][j]["dataType"],\
                "InputSlot": '0',
                "AlignedByteOffset": str(vb_attr['data'][i]['attributes_list'][j]["offset"]\
                    + vb_strides[vb_attr['data'][i]['attributes_list'][j]["bufferID"]]),\
                "InputSlotClass": "per-vertex",\
                "InstanceDataStepRate": "0"}
            fmt_elements.append(fmt_element)
        fmt_struct = {}
        fmt_struct["stride"] = str(sum(vb_strides))
        #For some reason, topology is stored in submesh instead of vertex attributes
        if subvbs['data'][vbsubs[i][0]]["indexBufferPrimType"] == 1:
            fmt_struct["topology"] = "pointlist" #THRG says this is Quad, dunno what that is, it's not in DX11?
        elif subvbs['data'][vbsubs[i][0]]["indexBufferPrimType"] == 3:
            fmt_struct["topology"] = "trianglelist"
        elif subvbs['data'][vbsubs[i][0]]["indexBufferPrimType"] == 4:
            fmt_struct["topology"] = "trianglestrip"
        else:
            fmt_struct["topology"] = "undefined"
        fmt_struct["format"] = 'DXGI_FORMAT_' + ib['data'][i]['dataType']
        fmt_struct["elements"] = fmt_elements
        fmts.append(fmt_struct)
    return(fmts)

def generate_ib(index, g1mg_stream, model_mesh_metadata, fmts, e = '<'):
    ib = [x for x in model_mesh_metadata['sections'] if x['type'] == "INDEX_BUFFER"][0]
    if index in range(len(fmts)):
        with io.BytesIO(g1mg_stream) as f:
            f.seek(ib['data'][index]['offset'])
            return(read_ib_stream(f.read(int(ib['data'][index]['stride']*ib['data'][index]['count'])), fmts[index], e))

def trianglestrip_to_list(ib_list):
    triangles = []
    for i in range(len(ib_list)-2):
        if i % 2 == 0:
            triangles.append([ib_list[i], ib_list[i+1], ib_list[i+2]])
        else:
            triangles.append([ib_list[i], ib_list[i+2], ib_list[i+1]]) #DirectX implementation
            #triangles.append([ib_list[i+1], ib_list[i], ib_list[i+2]]) #OpenGL implementation
    return(triangles)

def generate_vb(index, g1mg_stream, model_mesh_metadata, fmts, e = '<'):
    vb = [x for x in model_mesh_metadata['sections'] if x['type'] == "VERTEX_BUFFERS"][0]
    vb_attr = [x for x in model_mesh_metadata['sections'] if x['type'] == "VERTEX_ATTRIBUTES"][0]
    if index in range(len(fmts)):
        with io.BytesIO(g1mg_stream) as f:
            if vb['data'][vb_attr['data'][index]['buffer_list'][0]]['count'] > 1:
                vb_stream = bytes()
                for i in range(vb['data'][vb_attr['data'][index]['buffer_list'][0]]['count']):
                    for j in range(len(vb_attr['data'][index]['buffer_list'])):
                        f.seek(vb['data'][vb_attr['data'][index]['buffer_list'][j]]['offset']\
                            + (vb['data'][vb_attr['data'][index]['buffer_list'][j]]['stride'] * i))
                        vb_stream += f.read(vb['data'][vb_attr['data'][index]['buffer_list'][j]]['stride'])
                vb_struct = read_vb_stream(vb_stream, fmts[index], e)
            else: # 
                f.seek(vb['data'][vb_attr['data'][index]['buffer_list'][0]]['offset'])
                vb_struct = read_vb_stream(f.read(int(vb['data'][vb_attr['data'][index]['buffer_list'][0]]['stride']\
                    * vb['data'][vb_attr['data'][index]['buffer_list'][0]]['count'])), fmts[index], e)
            return(vb_struct)

def cull_vb(submesh):
    active_indices = list({x for l in submesh['ib'] for x in l})
    new_vb = []
    for i in range(len(submesh['vb'])):
        new_vb.append({'SemanticName': submesh['vb'][i]['SemanticName'],\
            'SemanticIndex': submesh['vb'][i]['SemanticIndex'], 'Buffer': []})
    new_indices = {}
    num_buffers = len(submesh['vb'])
    current_vertex = 0
    for i in range(len(submesh['vb'][0]['Buffer'])):
        if i in active_indices:
            for j in range(len(submesh['vb'])):
                new_vb[j]['Buffer'].append(submesh['vb'][j]['Buffer'][i])
            new_indices[i] = current_vertex
            current_vertex += 1
    submesh['vb'] = new_vb
    for i in range(len(submesh['ib'])):
        for j in range(len(submesh['ib'][i])):
            submesh['ib'][i][j] = new_indices[submesh['ib'][i][j]]
    return(submesh)

def generate_vgmap(boneindex, model_mesh_metadata, skel_data):
    bonepalettes = [x for x in model_mesh_metadata['sections'] if x['type'] == "JOINT_PALETTES"][0]
    vgmap_json = {}
    for i in range(len(bonepalettes['data'][boneindex]['joints'])):
        vgmap_json[skel_data['boneList'][bonepalettes['data'][boneindex]['joints'][i]['jointIndex']]['bone_id']] = i * 3
    return(vgmap_json)

def generate_submesh(subindex, g1mg_stream, model_mesh_metadata, skel_data, fmts, e = '<', cull_vertices = True,\
        preserve_trianglestrip = False):
    subvbs = [x for x in model_mesh_metadata['sections'] if x['type'] == "SUBMESH"][0]
    ibindex = subvbs['data'][subindex]['indexBufferIndex']
    vbindex = subvbs['data'][subindex]['vertexBufferIndex']
    boneindex = subvbs['data'][subindex]['bonePaletteIndex']
    submesh = {}
    submesh["fmt"] = fmts[vbindex]
    ib_data = generate_ib(ibindex, g1mg_stream, model_mesh_metadata, fmts, e = '<')
    # Flatten from 2D to 1D before sectioning.
    submesh["ib"] = [x for y in ib_data for x in y][int(subvbs['data'][subindex]['indexBufferOffset']):\
        int(subvbs['data'][subindex]['indexBufferOffset']+subvbs['data'][subindex]['indexCount'])]
    if submesh["fmt"]["topology"] == "trianglestrip" and preserve_trianglestrip == False:
        submesh["ib"] = trianglestrip_to_list(submesh["ib"])
        submesh["fmt"]["topology"] = "trianglelist"
    else:
        submesh["ib"] = [[x] for x in submesh["ib"]] # Turn back into 2D list so cull_vertices() works
    submesh["vb"] = generate_vb(vbindex, g1mg_stream, model_mesh_metadata, fmts, e = '<')
    if cull_vertices == True: # Call with False to produce submeshes identical to G1M Tools
        submesh = cull_vb(submesh)
    # Trying to detect if the external skeleton is missing
    if skel_data['jointCount'] > 1 and not skel_data['boneList'][0]['parentID'] < -200000000:
        submesh["vgmap"] = generate_vgmap(boneindex, model_mesh_metadata, skel_data)
    else:
        submesh["vgmap"] = False # G1M uses external skeleton that isn't available
    return(submesh)

def render_cloth_submesh(submesh, NUNID, model_skel_data, nun_maps, e = '<', remove_physics = False):
    is_nuno5 = (nun_maps['nun_data'][NUNID]['name'] == 'nuno5')
    # NUNO5 subset code will go here eventually
    new_fmt = copy.deepcopy(submesh['fmt'])
    new_vb = copy.deepcopy(submesh['vb'])
    position_data = [x for x in submesh['vb'] if x['SemanticName'] == 'POSITION'][0]['Buffer']
    normal_data = [x for x in submesh['vb'] if x['SemanticName'] == 'NORMAL'][0]['Buffer']
    BlendIndicesList = [x for x in submesh['vb'] if x['SemanticName'] == 'BLENDINDICES'][0]['Buffer']
    skinWeightList = [x for x in submesh['vb'] if x['SemanticName'] == 'BLENDWEIGHT'][0]['Buffer']
    nunoMap = nun_maps['clothMap'][NUNID]
    clothParentBone = [x for x in model_skel_data['boneList'] if x['i'] == nun_maps['clothParentIDMap'][NUNID]][0]
    clothStuff1Buffer = [x for x in submesh['vb'] if x['SemanticName'] == 'PSIZE'][0]['Buffer']
    clothStuff2Buffer = [x for x in submesh['vb'] if x['SemanticName'] == 'TEXCOORD' and int(x['SemanticIndex']) > 2][0]['Buffer'] #Not really sure about this one
    #clothStuff3Buffer = [x[3] for x in position_data]
    clothStuff4Buffer = [x[3] for x in normal_data]
    clothStuff5Buffer = [x for x in submesh['vb'] if x['SemanticName'] == 'COLOR' and int(x['SemanticIndex']) != 0][0]['Buffer']
    #colorBuffer = [x for x in submesh['vb'] if x['SemanticName'] == 'COLOR' and int(x['SemanticIndex']) == 0][0]['Buffer']
    tangent_data = [x for x in submesh['vb'] if x['SemanticName'] == 'TANGENT'][0]['Buffer']
    binormalBuffer = [x for x in submesh['vb'] if x['SemanticName'] == 'BINORMAL'][0]['Buffer']
    fogBuffer = [x for x in submesh['vb'] if x['SemanticName'] == 'FOG'][0]['Buffer']
    vertPosBuff = []
    vertNormBuff = []
    tangentBuffer = []
    nun_transform_info = nun_maps['driverMeshList'][NUNID]['transform_info'] # NUN Bones
    for i in range(len(position_data)):
        if binormalBuffer[i] == [0,0,0,0]:
            vertPosBuff.append((Quaternion(clothParentBone['abs_q']).rotate(position_data[i][0:3]) + numpy.array(clothParentBone['abs_p'])).tolist())
            vertNormBuff.append(normal_data[i])
            tangentBuffer.append(tangent_data[i])
        else:
            clothPosition = position_data[i]
            position = [0,0,0]
            a = [0,0,0]
            a += computeCenterOfMass(position, clothPosition, BlendIndicesList[i], nunoMap, nun_transform_info) * skinWeightList[i][0]
            a += computeCenterOfMass(position, clothPosition, clothStuff1Buffer[i], nunoMap, nun_transform_info) * skinWeightList[i][1]
            a += computeCenterOfMass(position, clothPosition, fogBuffer[i], nunoMap, nun_transform_info) * skinWeightList[i][2]
            a += computeCenterOfMass(position, clothPosition, clothStuff2Buffer[i], nunoMap, nun_transform_info) * skinWeightList[i][3]
            b = [0,0,0]
            b += computeCenterOfMass(position, clothPosition, BlendIndicesList[i], nunoMap, nun_transform_info) * clothStuff5Buffer[i][0]
            b += computeCenterOfMass(position, clothPosition, clothStuff1Buffer[i], nunoMap, nun_transform_info) * clothStuff5Buffer[i][1]
            b += computeCenterOfMass(position, clothPosition, fogBuffer[i], nunoMap, nun_transform_info) * clothStuff5Buffer[i][2]
            b += computeCenterOfMass(position, clothPosition, clothStuff2Buffer[i], nunoMap, nun_transform_info) * clothStuff5Buffer[i][3]
            c = [0,0,0]
            c += computeCenterOfMass(position, binormalBuffer[i], BlendIndicesList[i], nunoMap, nun_transform_info) * skinWeightList[i][0]
            c += computeCenterOfMass(position, binormalBuffer[i], clothStuff1Buffer[i], nunoMap, nun_transform_info) * skinWeightList[i][1]
            c += computeCenterOfMass(position, binormalBuffer[i], fogBuffer[i], nunoMap, nun_transform_info) * skinWeightList[i][2]
            c += computeCenterOfMass(position, binormalBuffer[i], clothStuff2Buffer[i], nunoMap, nun_transform_info) * skinWeightList[i][3]
            d = numpy.cross(b,c)
            vertNormBuff.append(b * normal_data[i][1] + c * normal_data[i][0] + d * normal_data[i][2])
            vertNormBuff[-1] = (vertNormBuff[-1] / numpy.linalg.norm(vertNormBuff[-1])).tolist()
            tangentBuffer.append(b * tangent_data[i][1] + c * tangent_data[i][0] + d * tangent_data[i][2])
            tangentBuffer[-1] = (tangentBuffer[-1] / numpy.linalg.norm(tangentBuffer[-1])).tolist() + [tangent_data[i][3]]
            if is_nuno5:
                d = (d / numpy.linalg.norm(d))
            vertPosBuff.append((d * clothStuff4Buffer[i] + a).tolist())
    #Position
    original_pos_fmt = int([x for x in new_fmt['elements'] if x['SemanticName'] == 'POSITION'][0]['id'])
    new_pos_fmt = len(new_fmt['elements'])
    new_fmt['elements'].append(copy.deepcopy(new_fmt['elements'][original_pos_fmt]))
    new_fmt['elements'][original_pos_fmt]['SemanticName'] = '4D_POSITION'
    new_fmt['elements'][new_pos_fmt]['id'] = str(new_pos_fmt)
    new_fmt['elements'][new_pos_fmt]['Format'] = "R32G32B32_FLOAT"
    new_fmt['elements'][new_pos_fmt]['AlignedByteOffset'] = copy.deepcopy(new_fmt['stride'])
    new_fmt['stride'] = str(int(new_fmt['stride']) + 12)
    new_vb.append({'SemanticName': 'POSITION', 'SemanticIndex': '0', 'Buffer': vertPosBuff})
    #Normal
    original_nml_fmt = int([x for x in new_fmt['elements'] if x['SemanticName'] == 'NORMAL'][0]['id'])
    new_nml_fmt = len(new_fmt['elements'])
    new_fmt['elements'].append(copy.deepcopy(new_fmt['elements'][original_nml_fmt]))
    new_fmt['elements'][original_nml_fmt]['SemanticName'] = '4D_NORMAL'
    new_fmt['elements'][new_nml_fmt]['id'] = str(new_nml_fmt)
    new_fmt['elements'][new_nml_fmt]['Format'] = "R32G32B32_FLOAT"
    new_fmt['elements'][new_nml_fmt]['AlignedByteOffset'] = copy.deepcopy(new_fmt['stride'])
    new_fmt['stride'] = str(int(new_fmt['stride']) + 12)
    new_vb.append({'SemanticName': 'NORMAL', 'SemanticIndex': '0', 'Buffer': vertNormBuff})
    #Tangent
    original_tng_fmt = int([x for x in new_fmt['elements'] if x['SemanticName'] == 'TANGENT'][0]['id'])
    new_tng_fmt = len(new_fmt['elements'])
    new_fmt['elements'].append(copy.deepcopy(new_fmt['elements'][original_tng_fmt]))
    new_fmt['elements'][original_tng_fmt]['SemanticName'] = '4D_TANGENT'
    new_fmt['elements'][new_tng_fmt]['id'] = str(new_tng_fmt)
    new_fmt['elements'][new_tng_fmt]['Format'] = "R32G32B32A32_FLOAT"
    new_fmt['elements'][new_tng_fmt]['AlignedByteOffset'] = copy.deepcopy(new_fmt['stride'])
    new_fmt['stride'] = str(int(new_fmt['stride']) + 16)
    new_vb.append({'SemanticName': 'TANGENT', 'SemanticIndex': '0', 'Buffer': tangentBuffer})
    if remove_physics == True:
        semantics_to_keep = ['POSITION', 'BLENDWEIGHT', 'BLENDINDICES', 'NORMAL', 'COLOR', 'TEXCOORD', 'TANGENT']
        simple_fmt = {'stride': '0', 'topology': new_fmt['topology'], 'format': new_fmt['format'], 'elements': []}
        simple_vb = []
        offset = 0
        for i in range(len(new_fmt['elements'])):
            if (new_fmt['elements'][i]['SemanticName'] in semantics_to_keep) and (new_fmt['elements'][i]['SemanticIndex'] == '0'):
                simple_fmt['elements'].append(copy.deepcopy(new_fmt['elements'][i]))
                simple_vb.append(copy.deepcopy(new_vb[i]))
                simple_fmt['elements'][-1]['id'] = str(len(simple_fmt['elements']) - 1)
                simple_fmt['elements'][-1]['AlignedByteOffset'] = str(offset)
                offset += get_stride_from_dxgi_format(simple_fmt['elements'][-1]['Format'])
        simple_fmt['stride'] = str(offset)
        return({'fmt': simple_fmt, 'ib': submesh['ib'], 'vb': simple_vb, 'vgmap': submesh['vgmap']})
    else:
        return({'fmt': new_fmt, 'ib': submesh['ib'], 'vb': new_vb, 'vgmap': submesh['vgmap']})

def render_cloth_submesh_2(submesh, subindex, model_mesh_metadata, model_skel_data, remove_physics = False):
    new_fmt = copy.deepcopy(submesh['fmt'])
    new_vb = copy.deepcopy(submesh['vb'])
    submeshinfo = [x for x in model_mesh_metadata['sections'] if x['type'] == "SUBMESH"][0]["data"][subindex]
    palette = [x["joints"] for x in [x for x in model_mesh_metadata['sections'] if x['type']\
        == "JOINT_PALETTES"][0]["data"]][submeshinfo['bonePaletteIndex']]
    physicsBoneList = [x["physicsIndex"] & 0xFFFF for x in palette]
    position_data = [x for x in submesh['vb'] if x['SemanticName'] == 'POSITION'][0]['Buffer']
    oldSkinIndiceList = [x for x in submesh['vb'] if x['SemanticName'] == 'BLENDINDICES'][0]['Buffer']
    vertPosBuff = []
    jointIndexBuff = []
    for i in range(len(position_data)):
        if oldSkinIndiceList[i][0] // 3 < len(physicsBoneList):
            index = physicsBoneList[oldSkinIndiceList[i][0] // 3]
            if index < len(model_skel_data["boneList"]):
                quat1 = Quaternion(model_skel_data["boneList"][index]["abs_q"])
                quat2 = Quaternion([quat1[0], 0-quat1[1], 0-quat1[2], 0-quat1[3]]) \
                    * Quaternion(0, position_data[i][0], position_data[i][1], position_data[i][2]) \
                    * quat1
                vertPosBuff.append((numpy.array(model_skel_data["boneList"][index]["abs_p"]) \
                    + numpy.array([quat2[1], quat2[2], quat2[3]])).tolist())
    original_pos_fmt = int([x for x in new_fmt['elements'] if x['SemanticName'] == 'POSITION'][0]['id'])
    new_pos_fmt = len(new_fmt['elements'])
    new_fmt['elements'].append(copy.deepcopy(new_fmt['elements'][original_pos_fmt]))
    new_fmt['elements'][original_pos_fmt]['SemanticName'] = '4D_POSITION'
    new_fmt['elements'][new_pos_fmt]['id'] = str(new_pos_fmt)
    new_fmt['elements'][new_pos_fmt]['Format'] = "R32G32B32_FLOAT"
    new_fmt['elements'][new_pos_fmt]['AlignedByteOffset'] = copy.deepcopy(new_fmt['stride'])
    new_fmt['stride'] = str(int(new_fmt['stride']) + 12)
    new_vb.append({'SemanticName': 'POSITION', 'SemanticIndex': '0', 'Buffer': vertPosBuff})
    if remove_physics == True:
        semantics_to_keep = ['POSITION', 'BLENDWEIGHT', 'BLENDINDICES', 'NORMAL', 'COLOR', 'TEXCOORD', 'TANGENT']
        simple_fmt = {'stride': '0', 'topology': new_fmt['topology'], 'format': new_fmt['format'], 'elements': []}
        simple_vb = []
        offset = 0
        for i in range(len(new_fmt['elements'])):
            if (new_fmt['elements'][i]['SemanticName'] in semantics_to_keep) and (new_fmt['elements'][i]['SemanticIndex'] == '0'):
                simple_fmt['elements'].append(copy.deepcopy(new_fmt['elements'][i]))
                simple_vb.append(copy.deepcopy(new_vb[i]))
                simple_fmt['elements'][-1]['id'] = str(len(simple_fmt['elements']) - 1)
                simple_fmt['elements'][-1]['AlignedByteOffset'] = str(offset)
                offset += get_stride_from_dxgi_format(simple_fmt['elements'][-1]['Format'])
        simple_fmt['stride'] = str(offset)
        return({'fmt': simple_fmt, 'ib': submesh['ib'], 'vb': simple_vb, 'vgmap': submesh['vgmap']})
    else:
        return({'fmt': new_fmt, 'ib': submesh['ib'], 'vb': new_vb, 'vgmap': submesh['vgmap']})

def write_submeshes(g1mg_stream, model_mesh_metadata, skel_data, nun_maps, path = '', e = '<', cull_vertices = True,\
        transform_cloth = True, write_empty_buffers = False, preserve_trianglestrip = False):
    if not nun_maps == False:
        nun_indices = [x['name'][0:4] for x in nun_maps['nun_data']]
        if 'nunv' in nun_indices:
            nunv_offset = [x['name'][0:4] for x in nun_maps['nun_data']].index('nunv')
        if 'nuns' in nun_indices:
            nuns_offset = [x['name'][0:4] for x in nun_maps['nun_data']].index('nuns')
    driverMesh_fmt = make_drivermesh_fmt()
    subvbs = [x for x in model_mesh_metadata['sections'] if x['type'] == "SUBMESH"][0]
    lod_data = [x for x in model_mesh_metadata["sections"] if x['type'] == 'MESH_LOD'][0]
    for subindex in range(len(subvbs['data'])):
        print("Processing submesh {0}...".format(subindex))
        submesh = generate_submesh(subindex, g1mg_stream, model_mesh_metadata,\
            skel_data, fmts = generate_fmts(model_mesh_metadata), e=e, cull_vertices = cull_vertices,\
            preserve_trianglestrip = preserve_trianglestrip)
        write_fmt(submesh['fmt'],'{0}{1}.fmt'.format(path, subindex))
        if len(submesh['ib']) > 0 or write_empty_buffers == True:
            write_ib(submesh['ib'],'{0}{1}.ib'.format(path, subindex), submesh['fmt'])
            write_vb(submesh['vb'],'{0}{1}.vb'.format(path, subindex), submesh['fmt'])
        if not submesh["vgmap"] == False:
            with open('{0}{1}.vgmap'.format(path, subindex), 'wb') as f:
                f.write(json.dumps(submesh['vgmap'], indent=4).encode("utf-8"))
        submesh_lod = [x for x in lod_data['data'][0]['lod'] if subindex in x['indices']][0]
        if submesh_lod['clothID'] == 1 and not nun_maps == False and transform_cloth == True:
            print("Performing cloth mesh (4D) transformation...".format(subindex))
            if (submesh_lod['NUNID']) >= 10000 and (submesh_lod['NUNID'] < 20000):
                NUNID = (submesh_lod['NUNID'] % 10000) + nunv_offset
            else:
                NUNID = submesh_lod['NUNID'] % 10000
            transformed_submesh = render_cloth_submesh(submesh, NUNID, skel_data, nun_maps, e=e)
            write_fmt(transformed_submesh['fmt'],'{0}{1}_transformed.fmt'.format(path, subindex))
            if len(transformed_submesh['ib']) > 0 or write_empty_buffers == True:
                write_ib(transformed_submesh['ib'],'{0}{1}_transformed.ib'.format(path, subindex), transformed_submesh['fmt'])
                write_vb(transformed_submesh['vb'],'{0}{1}_transformed.vb'.format(path, subindex), transformed_submesh['fmt'])
            if not transformed_submesh["vgmap"] == False:
                with open('{0}{1}_transformed.vgmap'.format(path, subindex), 'wb') as f:
                    f.write(json.dumps(transformed_submesh['vgmap'], indent=4).encode("utf-8"))
            drivermesh = nun_maps['driverMeshList'][NUNID]
            write_fmt(driverMesh_fmt,'{0}{1}_drivermesh.fmt'.format(path, subindex))
            if len(transformed_submesh['ib']) > 0 or write_empty_buffers == True:
                write_ib(drivermesh['indices'],'{0}{1}_drivermesh.ib'.format(path, subindex), driverMesh_fmt)
                write_vb(drivermesh['vertices'],'{0}{1}_drivermesh.vb'.format(path, subindex), driverMesh_fmt)
        if submesh_lod['clothID'] == 2 and transform_cloth == True:
            print("Performing cloth mesh (4D) transformation...".format(subindex))
            transformed_submesh = render_cloth_submesh_2(submesh, subindex, model_mesh_metadata, skel_data)
            write_fmt(transformed_submesh['fmt'],'{0}{1}_transformed.fmt'.format(path, subindex))
            if len(transformed_submesh['ib']) > 0 or write_empty_buffers == True:
                write_ib(transformed_submesh['ib'],'{0}{1}_transformed.ib'.format(path, subindex), transformed_submesh['fmt'])
                write_vb(transformed_submesh['vb'],'{0}{1}_transformed.vb'.format(path, subindex), transformed_submesh['fmt'])

# The argument passed (g1m_name) is actually the folder name
def parseSkelG1M(g1m_name):
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
                ext_skel_data = calc_abs_skeleton(g1ms_data)
                if os.path.exists(g1m_name+'Oid.bin'):
                    ext_skel_oid = binary_oid_to_dict(g1m_name+'Oid.bin')
                    ext_skel_data = name_bones(ext_skel_data, ext_skel_oid)
                have_skeleton == True # I guess some games duplicate this section?
            else:
                f.seek(chunk["start_offset"] + chunk["size"],0) # Move to next chunk
            file["chunks"] = chunks
    return(ext_skel_data)

def get_ext_skeleton(g1m_name):
    if os.path.exists('elixir.json'): # Assuming first g1m is the skeleton
        with open('elixir.json','r') as f:
            elixir = json.loads(re.sub('0x[0-9a-zA-Z+],','0,',f.read()))
        ext_skel_model = [x for x in elixir['files'] if x[-4:] == '.g1m'][0][:-4]
    else:
        ext_skel_model = g1m_name.split("_MODEL_")[0]+'_MODEL' # Assuming single external skeleton
    if os.path.exists(ext_skel_model+'.g1m'):
        return(parseSkelG1M(ext_skel_model))
    else:
        g1m_files = glob.glob('*.g1m')
        g1m = {}
        if len(g1m_files) < 1:
            return False
        elif len(g1m_files) == 1 and g1m_files[0] == g1m_name+'.g1m':
            return False
        else:
            print('For processing g1m ' + g1m_name + '.g1m, which g1m file has your skeleton?\n')
            for i in range(len(g1m_files)):
                print(str(i+1) + '. ' + g1m_files[i])
            print(str(i+2) + '. No external skeleton available')
            g1m_file_choice = -1
            while (g1m_file_choice < 0) or (g1m_file_choice >= len(g1m_files) + 1):
                try:
                    g1m_file_choice = int(input("\nPlease enter which g1m file to use:  ")) - 1
                except ValueError:
                    pass
            if g1m_file_choice in range(len(g1m_files)):
                return(parseSkelG1M(g1m_files[g1m_file_choice][:-4]))
            else:
                return False

# The argument passed (g1m_name) is actually the folder name
def parseG1M(g1m_name, overwrite = False, write_buffers = True, cull_vertices = True, transform_cloth = transform_cloth_mesh_default, write_empty_buffers = False, preserve_trianglestrip = False):
    with open(g1m_name + '.g1m', "rb") as f:
        print("Processing {0}...".format(g1m_name + '.g1m'))
        file = {}
        nun_struct = {}
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
                model_skel_data = parseG1MS(f.read(chunk["size"]),e)
                if os.path.exists(g1m_name+'Oid.bin'):
                    model_skel_oid = binary_oid_to_dict(g1m_name+'Oid.bin')
                    model_skel_data = name_bones(model_skel_data, model_skel_oid)
                if model_skel_data['jointCount'] > 1 and not model_skel_data['boneList'][0]['parentID'] < -200000000:
                    #Internal Skeleton
                    model_skel_data = calc_abs_skeleton(model_skel_data)
                else:
                    ext_skel = get_ext_skeleton(g1m_name)
                    if not ext_skel == False:
                        model_skel_data = combine_skeleton(ext_skel, model_skel_data)
                have_skeleton == True # I guess some games duplicate this section?
            elif chunk["magic"] in ['NUNO', 'ONUN']: # NUNO
                f.seek(chunk["start_offset"],0)
                nun_struct["nuno"] = parseNUNO(f.read(chunk["size"]),e)
            elif chunk["magic"] in ['NUNV', 'VNUN']: # NUNV
                f.seek(chunk["start_offset"],0)
                nun_struct["nunv"] = parseNUNV(f.read(chunk["size"]),e)
            elif chunk["magic"] in ['NUNS', 'SNUN']: # NUNS
                f.seek(chunk["start_offset"],0)
                nun_struct["nuns"] = parseNUNV(f.read(chunk["size"]),e)
            elif chunk["magic"] in ['G1MG', 'GM1G']:
                f.seek(chunk["start_offset"],0)
                g1mg_stream = f.read(chunk["size"])
                model_mesh_metadata = parseG1MG(g1mg_stream,e)
            else:
                f.seek(chunk["start_offset"] + chunk["size"],0) # Move to next chunk
            file["chunks"] = chunks
        nun_maps = False
        if len(nun_struct) > 0 and model_skel_data['jointCount'] > 1:
            nun_data = stack_nun(nun_struct)
            nun_maps = calc_nun_maps(nun_data, model_skel_data)
            if not nun_maps == False:
                nun_maps['nun_data'] = nun_data
        if os.path.exists(g1m_name) and (os.path.isdir(g1m_name)) and (overwrite == False):
            if str(input(g1m_name + " folder exists! Overwrite? (y/N) ")).lower()[0:1] == 'y':
                overwrite = True
        if (overwrite == True) or not os.path.exists(g1m_name):
            if not os.path.exists(g1m_name):
                os.mkdir(g1m_name)
            with open(g1m_name+"/mesh_metadata.json", "wb") as f:
                f.write(json.dumps(model_mesh_metadata, indent=4).encode("utf-8"))
            #with open(g1m_name+"/skel_data.json", "wb") as f:
                #f.write(json.dumps(model_skel_data, indent=4).encode("utf-8"))
            if write_buffers == True:
                write_submeshes(g1mg_stream, model_mesh_metadata, model_skel_data,\
                    nun_maps, path = g1m_name+'/', e=e, cull_vertices = cull_vertices,\
                    transform_cloth = transform_cloth, write_empty_buffers = write_empty_buffers,\
                    preserve_trianglestrip = preserve_trianglestrip)
    return(True)

if __name__ == "__main__":
    # Set current directory
    os.chdir(os.path.abspath(os.path.dirname(__file__)))
    if len(sys.argv) > 1:
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument('-o', '--overwrite', help="Overwrite existing files", action="store_true")
        parser.add_argument('-n', '--no_buffers', help="Do not write fmt/ib/vb/vgmap files", action="store_false")
        parser.add_argument('-f', '--full_vertices',\
            help="Output full meshes instead of submeshs (identical to G1M tools)", action="store_false")
        if transform_cloth_mesh_default == True:
            parser.add_argument('-s', '--skip_transform', help="Do not transform cloth meshes (4D->3D)", action="store_false")
        else:
            parser.add_argument('-t', '--transform', help="Transform cloth meshes (4D->3D)", action="store_true")
        parser.add_argument('-e', '--write_empty_buffers', help="Write ib/vb files even if 0 bytes", action="store_true")
        parser.add_argument('-p', '--preserve_trianglestrip',\
            help="Output original trianglestrip index buffers instead of converting to trianglelist", action="store_true")
        parser.add_argument('g1m_filename', help="Name of g1m file to extract meshes / G1MG metadata (required).")
        args = parser.parse_args()
        if transform_cloth_mesh_default == True:
            transform_cloth = args.skip_transform
        else:
            transform_cloth = args.transform
        if os.path.exists(args.g1m_filename) and args.g1m_filename[-4:].lower() == '.g1m':
            parseG1M(args.g1m_filename[:-4], overwrite = args.overwrite,\
                write_buffers = args.no_buffers, cull_vertices = args.full_vertices,\
                transform_cloth = transform_cloth, write_empty_buffers = args.write_empty_buffers,\
                preserve_trianglestrip = args.preserve_trianglestrip)
    else:
        # When run without command line arguments, it will attempt to obtain data from all models
        models = []
        if os.path.exists('elixir.json'):
            try:
                with open('elixir.json','r') as f:
                    elixir = json.loads(re.sub('0x[0-9a-zA-Z+],','0,',f.read()))
                models = [x for x in elixir['files'] if x[-4:] == '.g1m'][1:]
            except:
                pass
        if len(models) > 0:
            for i in range(len(models)):
                parseG1M(models[i][:-4])
        else:
            models = glob.glob('*_MODEL_*.g1m')
            if len(models) > 0:
                for i in range(len(models)):
                    parseG1M(models[i][:-4])
            else:
                g1m_files = glob.glob('*.g1m')
                if len(g1m_files) == 1:
                    parseG1M(g1m_files[0][:-4])
                elif len(g1m_files) > 1:
                    print('Which g1m file do you want to unpack?\n')
                    for i in range(len(g1m_files)):
                        print(str(i+1) + '. ' + g1m_files[i])
                    g1m_file_choice = -1
                    while (g1m_file_choice < 0) or (g1m_file_choice >= len(g1m_files)):
                        try:
                            g1m_file_choice = int(input("\nPlease enter which g1m file to use:  ")) - 1
                        except ValueError:
                            pass
                    if g1m_file_choice in range(len(g1m_files)):
                        parseG1M(g1m_files[g1m_file_choice][:-4])
