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

import glob, os, io, sys, struct, json, numpy
from pyquaternion import Quaternion
from lib_fmtibvb import *

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
    ib = [x for x in model_mesh_metadata['sections'] if x['type'] == "INDEX_BUFFER"][0]
    subvbs = [x for x in model_mesh_metadata['sections'] if x['type'] == "SUBMESH"][0]
    vbsubs = find_submeshes(model_mesh_metadata)
    # Generate fmt structures from metadata
    fmts = []
    for i in range(len(vb['data'])):
        fmt_elements = []
        for j in range(len(vb_attr['data'][i]['attributes_list'])):
            fmt_element = {"id": str(j),
                "SemanticName": vb_attr['data'][i]['attributes_list'][j]["semantic"],\
                "SemanticIndex": str(vb_attr['data'][i]['attributes_list'][j]["layer"]),\
                "Format": vb_attr['data'][i]['attributes_list'][j]["dataType"],\
                "InputSlot": str(vb_attr['data'][i]['attributes_list'][j]["bufferID"]), # Not sure if correct\
                "AlignedByteOffset": str(vb_attr['data'][i]['attributes_list'][j]["offset"]),\
                "InputSlotClass": "per-vertex",\
                "InstanceDataStepRate": "0"}
            fmt_elements.append(fmt_element)
        fmt_struct = {}
        fmt_struct["stride"] = str(vb['data'][i]['stride'])
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

def generate_vb(index, g1mg_stream, model_mesh_metadata, fmts, e = '<'):
    vb = [x for x in model_mesh_metadata['sections'] if x['type'] == "VERTEX_BUFFERS"][0]
    if index in range(len(fmts)):
        with io.BytesIO(g1mg_stream) as f:
            f.seek(vb['data'][index]['offset'])
            return(read_vb_stream(f.read(int(vb['data'][index]['stride']*vb['data'][index]['count'])), fmts[index], e))

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

def generate_submesh(subindex, g1mg_stream, model_mesh_metadata, skel_data, fmts, e = '<', cull_vertices = True):
    subvbs = [x for x in model_mesh_metadata['sections'] if x['type'] == "SUBMESH"][0]
    ibindex = subvbs['data'][subindex]['indexBufferIndex']
    vbindex = subvbs['data'][subindex]['vertexBufferIndex']
    boneindex = subvbs['data'][subindex]['bonePaletteIndex']
    submesh = {}
    submesh["fmt"] = fmts[vbindex]
    # When inputting index buffer offsets, divide by 3 as library returns triplets and g1m uses single index counts
    submesh["ib"] = generate_ib(ibindex, g1mg_stream, model_mesh_metadata, fmts, e = '<')\
        [int(subvbs['data'][subindex]['indexBufferOffset']/3):\
        int((subvbs['data'][subindex]['indexBufferOffset']+subvbs['data'][subindex]['indexCount'])/3)]
    submesh["vb"] = generate_vb(vbindex, g1mg_stream, model_mesh_metadata, fmts, e = '<')
    if cull_vertices == True: # Call with False to produce submeshes identical to G1M Tools
        submesh = cull_vb(submesh)
    # Trying to detect if the external skeleton is missing
    if skel_data['jointCount'] > 1 and not skel_data['boneList'][0]['parentID'] == -2147483648:
        submesh["vgmap"] = generate_vgmap(boneindex, model_mesh_metadata, skel_data)
    else:
        submesh["vgmap"] = False # G1M uses external skeleton that isn't available
    return(submesh)

def write_submeshes(g1mg_stream, model_mesh_metadata, skel_data, path = '', e = '<', cull_vertices = True):
    fmts = generate_fmts(model_mesh_metadata)
    subvbs = [x for x in model_mesh_metadata['sections'] if x['type'] == "SUBMESH"][0]
    for subindex in range(len(subvbs['data'])):
        submesh = generate_submesh(subindex, g1mg_stream, model_mesh_metadata,\
            skel_data, fmts, e=e, cull_vertices = cull_vertices)
        write_fmt(submesh['fmt'],'{0}{1}.fmt'.format(path, subindex))
        write_ib(submesh['ib'],'{0}{1}.ib'.format(path, subindex), submesh['fmt'])
        write_vb(submesh['vb'],'{0}{1}.vb'.format(path, subindex), submesh['fmt'])
        if not submesh["vgmap"] == False:
            with open('{0}{1}.vgmap'.format(path, subindex), 'wb') as f:
                f.write(json.dumps(submesh['vgmap'], indent=4).encode("utf-8"))

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
def parseG1M(g1m_name, overwrite = False, write_buffers = True, cull_vertices = True):
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
                model_skel_data = parseG1MS(f.read(chunk["size"]),e)
                if os.path.exists(g1m_name+'Oid.bin'):
                    model_skel_oid = binary_oid_to_dict(g1m_name+'Oid.bin')
                    model_skel_data = name_bones(model_skel_data, model_skel_oid)
                ext_skel = get_ext_skeleton(g1m_name)
                if not ext_skel == False:
                    model_skel_data = combine_skeleton(ext_skel, model_skel_data)
                have_skeleton == True # I guess some games duplicate this section?
            elif chunk["magic"] in ['G1MG', 'GM1G']:
                f.seek(chunk["start_offset"],0)
                g1mg_stream = f.read(chunk["size"])
                model_mesh_metadata = parseG1MG(g1mg_stream,e)
            else:
                f.seek(chunk["start_offset"] + chunk["size"],0) # Move to next chunk
            file["chunks"] = chunks
        if os.path.exists(g1m_name) and (os.path.isdir(g1m_name)) and (overwrite == False):
            if str(input(g1m_name + " folder exists! Overwrite? (y/N) ")).lower()[0:1] == 'y':
                overwrite = True
        if (overwrite == True) or not os.path.exists(g1m_name):
            if not os.path.exists(g1m_name):
                os.mkdir(g1m_name)
            if write_buffers == True:
                write_submeshes(g1mg_stream, model_mesh_metadata, model_skel_data,\
                    path = g1m_name+'/', e=e, cull_vertices = cull_vertices)
            with open(g1m_name+"/mesh_metadata.json", "wb") as f:
                f.write(json.dumps(model_mesh_metadata, indent=4).encode("utf-8"))
            with open(g1m_name+"/skel_data.json", "wb") as f:
                f.write(json.dumps(model_skel_data, indent=4).encode("utf-8"))
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
        parser.add_argument('g1m_filename', help="Name of g1m file to extract G1MG metadata (required).")
        args = parser.parse_args()
        if os.path.exists(args.g1m_filename) and args.g1m_filename[-4:].lower() == '.g1m':
            parseG1M(args.g1m_filename[:-4], overwrite = args.overwrite,\
                write_buffers = args.no_buffers, cull_vertices = args.full_vertices)
    else:
        # When run without command line arguments, it will attempt to obtain data from all models
        models = glob.glob('*_MODEL_*.g1m')
        if len(models) > 0:
            for i in range(len(models)):
                parseG1M(models[i][:-4])

