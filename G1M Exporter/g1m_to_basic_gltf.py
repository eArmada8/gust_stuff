# Very basic glTF builder for G1M files, mostly working now for its intended purpose (skeletal rigging
# of extracted meshes from g1m_export_meshes.py).
#
# Based primarily off the work of GitHub/Joschuka and GitHub/three-houses-research-team,
# huge thank you!  Also many thanks to eterniti for sharing code with me to reference.
# Credit also to the Khronos group tutorial.
#
# This code depends on g1m_export_meshes.py, g1m_import_meshes.py and lib_fmtibvb.py being in the same folder.
#
# This code requires both numpy and pyquaternion for skeletal manipulation.
#
# For materials, it will read g1t.json if present in the same directory.
#
# These can be installed by:
# /path/to/python3 -m pip install pyquaternion
#
# Steps:
# 1. Use Gust Tools to extract G1M from the .elixir.gz file (and to extract textures from the .g1t file).
# 2. Run this script (in the folder with the g1m file).
#
# For command line options:
# /path/to/python3 g1m_to_basic_gltf.py --help
#
# GitHub eArmada8/gust_stuff

import glob, os, io, sys, copy, json, numpy
from pyquaternion import Quaternion
from g1m_export_meshes import *

# This only handles formats compatible with G1M
def convert_format_for_gltf(dxgi_format):
    dxgi_format = dxgi_format.split('DXGI_FORMAT_')[-1]
    dxgi_format_split = dxgi_format.split('_')
    if len(dxgi_format_split) == 2:
        numtype = dxgi_format_split[1]
        vec_format = re.findall("[0-9]+",dxgi_format_split[0])
        vec_bits = int(vec_format[0])
        vec_elements = len(vec_format)
        if (numtype in ['FLOAT', 'UNORM']):
            componentType = 5126
            dxgi_format = re.sub('[0-9]+', '32', dxgi_format) # Half-floats are not supported
            dxgi_format = re.sub('UNORM', 'FLOAT', dxgi_format) # UNORMs are not supported
            componentStride = len(re.findall('[0-9]+', dxgi_format)) * 4
        elif numtype == 'UINT':
            if vec_bits == 32:
                componentType = 5125
                componentStride = len(re.findall('[0-9]+', dxgi_format)) * 4
            elif vec_bits == 16:
                componentType = 5123
                componentStride = len(re.findall('[0-9]+', dxgi_format)) * 2
            elif vec_bits == 8:
                componentType = 5121
                componentStride = len(re.findall('[0-9]+', dxgi_format))
        accessor_types = ["SCALAR", "VEC2", "VEC3", "VEC4"]
        accessor_type = accessor_types[len(re.findall('[0-9]+', dxgi_format))-1]
        return({'format': dxgi_format, 'componentType': componentType,\
            'componentStride': componentStride, 'accessor_type': accessor_type})
    else:
        return(False)

def convert_fmt_for_gltf(fmt):
    new_fmt = copy.deepcopy(fmt)
    stride = 0
    new_semantics = {'BLENDWEIGHT': 'WEIGHTS', 'BLENDINDICES': 'JOINTS'}
    need_index = ['WEIGHTS', 'JOINTS', 'COLOR', 'TEXCOORD']
    for i in range(len(fmt['elements'])):
        if new_fmt['elements'][i]['SemanticName'] in new_semantics.keys():
            new_fmt['elements'][i]['SemanticName'] = new_semantics[new_fmt['elements'][i]['SemanticName']]
        new_info = convert_format_for_gltf(fmt['elements'][i]['Format'])
        new_fmt['elements'][i]['Format'] = new_info['format']
        if new_fmt['elements'][i]['SemanticName'] in need_index:
            new_fmt['elements'][i]['SemanticName'] = new_fmt['elements'][i]['SemanticName'] + '_' +\
                new_fmt['elements'][i]['SemanticIndex']
        new_fmt['elements'][i]['AlignedByteOffset'] = stride
        new_fmt['elements'][i]['componentType'] = new_info['componentType']
        new_fmt['elements'][i]['componentStride'] = new_info['componentStride']
        new_fmt['elements'][i]['accessor_type'] = new_info['accessor_type']
        stride += new_info['componentStride']
    index_fmt = convert_format_for_gltf(fmt['format'])
    new_fmt['format'] = index_fmt['format']
    new_fmt['componentType'] = index_fmt['componentType']
    new_fmt['componentStride'] = index_fmt['componentStride']
    new_fmt['accessor_type'] = index_fmt['accessor_type']
    new_fmt['stride'] = stride
    return(new_fmt)

def convert_bones_to_single_file(submesh):
    bone_element_index = int([x for x in submesh['fmt']['elements'] if x['SemanticName'] == 'BLENDINDICES'][0]['id'])
    for i in range(len(submesh['vb'][bone_element_index]['Buffer'])):
        for j in range(len(submesh['vb'][bone_element_index]['Buffer'][i])):
            submesh['vb'][bone_element_index]['Buffer'][i][j] = \
                int(submesh['vb'][bone_element_index]['Buffer'][i][j] // 3) # Dunno why G1M indices count by 3, I think it's for NUN?
    return(submesh)

def list_of_utilized_bones(submesh, model_skel_data):
    true_bone_map = {}
    if model_skel_data['jointCount'] > 1:
        for i in range(len(model_skel_data['boneList'])):
            true_bone_map[model_skel_data['boneList'][i]['bone_id']] = model_skel_data['boneList'][i]['i']
    return([true_bone_map[x] for x in submesh['vgmap'].keys()])

def fix_weight_groups(submesh):
    # Avoid some strange behavior from variable assignment, will copy instead
    new_submesh = copy.deepcopy(submesh)
    bone_element_index = int([x for x in new_submesh['fmt']['elements'] if x['SemanticName'] == 'BLENDINDICES'][0]['id'])
    weight_element_index = int([x for x in new_submesh['fmt']['elements'] if x['SemanticName'] == 'BLENDWEIGHT'][0]['id'])
    # If the final weight group is missing, re-insert it
    if len(new_submesh['vb'][bone_element_index]['Buffer'][0]) - len(new_submesh['vb'][weight_element_index]['Buffer'][0]) > 0:
        for i in range(len(new_submesh['vb'][bone_element_index]['Buffer'][0]) - len(new_submesh['vb'][weight_element_index]['Buffer'][0])):
            for j in range(len(new_submesh['vb'][weight_element_index]['Buffer'])):
                new_submesh['vb'][weight_element_index]['Buffer'][j].append(1-sum(new_submesh['vb'][weight_element_index]['Buffer'][j]))
            prefices = ['R','G','B','A','D']
            weightformat = new_submesh['fmt']['elements'][weight_element_index]['Format']
            dxgi_format_split = weightformat.split('_')
            if len(dxgi_format_split) == 2:
                numtype = dxgi_format_split[1]
                vec_format = re.findall("[0-9]+",dxgi_format_split[0])
                vec_bits = int(vec_format[0])
                vec_elements = len(vec_format)
                vec_elements += 1 #Expand by one
            new_submesh['fmt']['elements'][weight_element_index]['Format'] =\
                "".join(["{0}{1}".format(prefices[j], vec_bits) for j in range(vec_elements)]) + '_' + numtype
            #Expand stride and adjust offsets
            new_submesh['fmt']['stride'] = str(int(int(new_submesh['fmt']['stride']) + vec_bits / 8))
            for j in range(weight_element_index+1, len(new_submesh['fmt']['elements'])):
                new_submesh['fmt']['elements'][j]['AlignedByteOffset'] =\
                    str(int(int(new_submesh['fmt']['elements'][j]['AlignedByteOffset']) + vec_bits / 8))
    # Remove invalid weight numbers (<0.00001 and negative numbers)
    for i in range(len(new_submesh['vb'][weight_element_index]['Buffer'])):
        for j in range(len(new_submesh['vb'][weight_element_index]['Buffer'][i])):
            if (new_submesh['vb'][weight_element_index]['Buffer'][i][j] < 0.00001):
                new_submesh['vb'][weight_element_index]['Buffer'][i][j] = 0
    # Remove cloth weights from 4D meshes
    for i in range(len(new_submesh['vb'][weight_element_index]['Buffer'])):
        # Hopefully this correctly detects 4D weight groups
        if not new_submesh['vb'][weight_element_index]['Buffer'][i][0] == max(new_submesh['vb'][weight_element_index]['Buffer'][i]):
            new_submesh['vb'][weight_element_index]['Buffer'][i] = [1]+[0 for x in new_submesh['vb'][weight_element_index]['Buffer'][i][1:]]
            new_submesh['vb'][bone_element_index]['Buffer'][i] = [0 for x in new_submesh['vb'][bone_element_index]['Buffer'][i]]
    return(new_submesh)

def fix_tangent_length(submesh):
    tangent_element_index = int([x for x in submesh['fmt']['elements'] if x['SemanticName'] == 'TANGENT'][0]['id'])
    for i in range(len(submesh['vb'][tangent_element_index]['Buffer'])):
        submesh['vb'][tangent_element_index]['Buffer'][i][0:3] =\
            (submesh['vb'][tangent_element_index]['Buffer'][i][0:3] / numpy.linalg.norm(submesh['vb'][tangent_element_index]['Buffer'][i][0:3])).tolist()
    return(submesh)

def generate_materials(gltf_data, model_mesh_metadata, metadata_sections):
    materials = model_mesh_metadata['sections'][metadata_sections['MATERIALS']]['data']
    if os.path.exists('g1t.json'):
        with open('g1t.json','rb') as jf:
            g1t_data = json.loads(re.sub('0x[0-9a-fA-F]+', (lambda x: str(int(x.group()[2:],16))), jf.read().decode('utf-8')))
        images = [x['name'] for x in g1t_data['textures']]
    else:
        # Making an assumption here that all images are the number and .dds, since g1t.json is not available
        images = ['{0}.dds'.format(str(i).zfill(3)) for i in range(max([x['id'] for y in materials for x in y['textures']])+1)]
    gltf_data['images'] = [{'uri':x} for x in images]
    for i in range(len(materials)):
        material = {}
        for j in range(len(materials[i]['textures'])):
            sampler = { 'wrapS': 10497, 'wrapT': 10497 } # It seems like wrap is the only type used, according to THRG?
            texture = { 'source': materials[i]['textures'][j]['id'], 'sampler': len(gltf_data['samplers']) }
            if materials[i]['textures'][j]['type'] == 1:
                material['pbrMetallicRoughness']= { 'baseColorTexture' : { 'index' : len(gltf_data['textures']) },\
                    'metallicFactor' : 0.0, 'roughnessFactor' : 1.0 }
            elif materials[i]['textures'][j]['type'] == 3:
                material['normalTexture'] =  { 'index' : len(gltf_data['textures']), 'texCoord': materials[i]['textures'][j]['layer'] }
            elif materials[i]['textures'][j]['type'] == 5:
                material['occlusionTexture'] =  { 'index' : len(gltf_data['textures']), 'texCoord': materials[i]['textures'][j]['layer'] }
            elif materials[i]['textures'][j]['type'] == 2:
                material['emissiveTexture'] =  { 'index' : len(gltf_data['textures']), 'texCoord': materials[i]['textures'][j]['layer'] }
            gltf_data['samplers'].append(sampler)
            gltf_data['textures'].append(texture)
        gltf_data['materials'].append(material)
    return(gltf_data)

def write_glTF(g1m_name, g1mg_stream, model_mesh_metadata, model_skel_data, nun_maps, e = '<', keep_color = False):
    # Trying to detect if the external skeleton is missing
    metadata_sections = {model_mesh_metadata['sections'][i]['type']:i for i in range(len(model_mesh_metadata['sections']))}
    skel_present = model_skel_data['jointCount'] > 1 and not model_skel_data['boneList'][0]['parentID'] == -2147483648
    subvbs = model_mesh_metadata['sections'][metadata_sections['SUBMESH']]
    if not nun_maps == False:
        nun_indices = [x['name'][0:4] for x in nun_maps['nun_data']]
        if 'nunv' in nun_indices:
            nunv_offset = [x['name'][0:4] for x in nun_maps['nun_data']].index('nunv')
        if 'nuns' in nun_indices:
            nuns_offset = [x['name'][0:4] for x in nun_maps['nun_data']].index('nuns')
    lod_data = [x for x in model_mesh_metadata["sections"] if x['type'] == 'MESH_LOD'][0]
    fmts = generate_fmts(model_mesh_metadata)
    gltf_data = {}
    gltf_data['asset'] = { 'version': '2.0' }
    gltf_data['accessors'] = []
    gltf_data['bufferViews'] = []
    gltf_data['buffers'] = []
    gltf_data['images'] = []
    gltf_data['materials'] = []
    gltf_data['meshes'] = []
    gltf_data['nodes'] = []
    gltf_data['samplers'] = []
    gltf_data['scenes'] = [{}]
    gltf_data['scenes'][0]['nodes'] = [0]
    gltf_data['scene'] = 0
    gltf_data['skins'] = []
    gltf_data['textures'] = []
    giant_buffer = bytes()
    mesh_nodes = []
    buffer_view = 0
    if 'MATERIALS' in metadata_sections:
        gltf_data = generate_materials(gltf_data, model_mesh_metadata, metadata_sections)
    for i in range(len(model_skel_data['boneList'])):
        try: # NUN bones should be skipped
            node = {'children': [], 'name': model_skel_data['boneList'][i]['bone_id']}
            if not list(model_skel_data['boneList'][i]['rotation_q']) == [0,0,0,1]:
                node['rotation'] = model_skel_data['boneList'][i]['rotation_q']
            if not list(model_skel_data['boneList'][i]['scale']) == [1,1,1]:
                node['scale'] = model_skel_data['boneList'][i]['scale']
            if not list(model_skel_data['boneList'][i]['pos_xyz']) == [0,0,0]:
                node['translation'] = model_skel_data['boneList'][i]['pos_xyz']
            if i > 0:
                gltf_data['nodes'][model_skel_data['boneList'][i]['parentID']]['children'].append(len(gltf_data['nodes']))
            gltf_data['nodes'].append(node)
        except:
            pass
    for i in range(len(gltf_data['nodes'])):
        if len(gltf_data['nodes'][i]['children']) == 0:
            del(gltf_data['nodes'][i]['children'])
    for subindex in range(len(subvbs['data'])):
        print("Processing submesh {0}...".format(subindex))
        # Skip submesh if 4D, unless NUN data is available
        if (len(re.findall('[0-9]+', [x for x in fmts[subvbs['data'][subindex]['vertexBufferIndex']]['elements'] if x['SemanticName'] == 'POSITION'][0]['Format'])) == 3) \
            or not nun_maps == False:
            submesh_lod = [x for x in lod_data['data'][0]['lod'] if subindex in x['indices']][0]
            primitive = {"attributes":{}}
            fmts = generate_fmts(model_mesh_metadata) # Refresh FMT every time, to dereference
            submesh = generate_submesh(subindex, g1mg_stream, model_mesh_metadata, model_skel_data, fmts, e=e, cull_vertices = True, preserve_trianglestrip = True)
            if submesh_lod['clothID'] == 1 and not nun_maps == False:
                print("Performing cloth mesh (4D) transformation...".format(subindex))
                if (submesh_lod['NUNID']) >= 10000 and (submesh_lod['NUNID'] < 20000):
                    NUNID = (submesh_lod['NUNID'] % 10000) + nunv_offset
                else:
                    NUNID = submesh_lod['NUNID'] % 10000
                submesh = render_cloth_submesh(submesh, NUNID, model_skel_data, nun_maps, e=e, remove_physics = True)
            if submesh_lod['clothID'] == 2:
                print("Performing cloth mesh (4D) transformation...".format(subindex))
                submesh = render_cloth_submesh_2(submesh, subindex, model_mesh_metadata, model_skel_data, remove_physics = True)
            # Skip empty submeshes
            if len(submesh['ib']) > 0:
                skip_weights = False
                try:
                    submesh = convert_bones_to_single_file(submesh)
                    submesh = fix_weight_groups(submesh)
                except:
                    skip_weights = True # Certain models do not have weights at all
                if not submesh_lod['clothID'] == 0 and 'TANGENT' in [x['SemanticName'] for x in submesh['vb']]:
                    submesh = fix_tangent_length(submesh) # Needed for cloth meshes, I have no idea why
                gltf_fmt = convert_fmt_for_gltf(submesh['fmt'])
                vb_stream = io.BytesIO()
                write_vb_stream(submesh['vb'], vb_stream, gltf_fmt, e=e, interleave = False)
                block_offset = len(giant_buffer)
                for element in range(len(gltf_fmt['elements'])):
                    primitive["attributes"][gltf_fmt['elements'][element]['SemanticName']]\
                        = len(gltf_data['accessors'])
                    gltf_data['accessors'].append({"bufferView" : buffer_view,\
                        "componentType": gltf_fmt['elements'][element]['componentType'],\
                        "count": len(submesh['vb'][element]['Buffer']),\
                        "type": gltf_fmt['elements'][element]['accessor_type']})
                    if gltf_fmt['elements'][element]['SemanticName'] == 'POSITION':
                        gltf_data['accessors'][-1]['max'] =\
                            [max([x[0] for x in submesh['vb'][element]['Buffer']]),\
                             max([x[1] for x in submesh['vb'][element]['Buffer']]),\
                             max([x[2] for x in submesh['vb'][element]['Buffer']])]
                        gltf_data['accessors'][-1]['min'] =\
                            [min([x[0] for x in submesh['vb'][element]['Buffer']]),\
                             min([x[1] for x in submesh['vb'][element]['Buffer']]),\
                             min([x[2] for x in submesh['vb'][element]['Buffer']])]
                    gltf_data['bufferViews'].append({"buffer": 0,\
                        "byteOffset": block_offset,\
                        "byteLength": len(submesh['vb'][element]['Buffer']) *\
                        gltf_fmt['elements'][element]['componentStride'],\
                        "target" : 34962})
                    block_offset += len(submesh['vb'][element]['Buffer']) *\
                        gltf_fmt['elements'][element]['componentStride']
                    buffer_view += 1
                vb_stream.seek(0)
                giant_buffer += vb_stream.read()
                vb_stream.close()
                del(vb_stream)
                ib_stream = io.BytesIO()
                write_ib_stream(submesh['ib'], ib_stream, gltf_fmt, e=e)
                # IB is 16-bit so can be misaligned, unlike VB (which only has 32-, 64- and 128-bit types in G1M)
                while (ib_stream.tell() % 4) > 0:
                    ib_stream.write(b'\x00')
                primitive["indices"] = len(gltf_data['accessors'])
                gltf_data['accessors'].append({"bufferView" : buffer_view,\
                    "componentType": gltf_fmt['componentType'],\
                    "count": len([index for triangle in submesh['ib'] for index in triangle]),\
                    "type": gltf_fmt['accessor_type']})
                gltf_data['bufferViews'].append({"buffer": 0,\
                    "byteOffset": len(giant_buffer),\
                    "byteLength": ib_stream.tell(),\
                    "target" : 34963})
                buffer_view += 1
                ib_stream.seek(0)
                giant_buffer += ib_stream.read()
                ib_stream.close()
                del(ib_stream)
                if subvbs['data'][subindex]["indexBufferPrimType"] == 3:
                    primitive["mode"] = 4 #TRIANGLES
                elif subvbs['data'][subindex]["indexBufferPrimType"] == 4:
                    primitive["mode"] = 5 #TRIANGLE_STRIP
                else:
                    primitive["mode"] = 0 #POINTS
                if subvbs['data'][subindex]['materialIndex'] < len(gltf_data['materials']):
                    primitive["material"] = subvbs['data'][subindex]['materialIndex']
                    if not keep_color:
                        # Remove vertex colors, as g1m does not actually use this semantic for vertex colors (it is for cloth transform)
                        primitive["attributes"] = {k:v for (k,v) in primitive["attributes"].items() if not 'COLOR' in k}
                mesh_nodes.append(len(gltf_data['nodes']))
                gltf_data['nodes'].append({'mesh': len(gltf_data['meshes']), 'name': "Mesh_{0}".format(subindex)})
                gltf_data['meshes'].append({"primitives": [primitive], "name": "Mesh_{0}".format(subindex)})
                if skel_present and not skip_weights and not submesh_lod['clothID'] == 2:
                    gltf_data['nodes'][-1]['skin'] = len(gltf_data['skins'])
                    skin_bones = list_of_utilized_bones(submesh, model_skel_data)
                    inv_mtx_buffer = bytes()
                    for i in range(len(skin_bones)):
                        mtx = Quaternion(model_skel_data['boneList'][skin_bones[i]]['abs_q']).transformation_matrix
                        [mtx[0,3],mtx[1,3],mtx[2,3]] = model_skel_data['boneList'][skin_bones[i]]['abs_p']
                        inv_bind_mtx = numpy.linalg.inv(mtx)
                        inv_bind_mtx = numpy.ndarray.transpose(inv_bind_mtx)
                        inv_mtx_buffer += struct.pack(e+"16f", *[num for row in inv_bind_mtx for num in row])
                    gltf_data['skins'].append({"inverseBindMatrices": len(gltf_data['accessors']), "joints": skin_bones})
                    gltf_data['accessors'].append({"bufferView" : buffer_view,\
                        "componentType": 5126,\
                        "count": len(skin_bones),\
                        "type": "MAT4"})
                    gltf_data['bufferViews'].append({"buffer": 0,\
                        "byteOffset": len(giant_buffer),\
                        "byteLength": len(inv_mtx_buffer)})
                    buffer_view += 1
                    giant_buffer += inv_mtx_buffer
                del(submesh)
    gltf_data['scenes'][0]['nodes'].extend(mesh_nodes)
    gltf_data['buffers'].append({"byteLength": len(giant_buffer), "uri": g1m_name+'.bin'})
    with open(g1m_name+'.bin', 'wb') as f:
        f.write(giant_buffer)
    with open(g1m_name+'.gltf', 'wb') as f:
        f.write(json.dumps(gltf_data, indent=4).encode("utf-8"))

# The argument passed (g1m_name) is actually the folder name
def G1M2glTF(g1m_name, overwrite = False, keep_color = False):
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
        transform_cloth = True
        file["file_version"], = struct.unpack(e+"I", f.read(4))
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
            elif chunk["magic"] in ['NUNO', 'ONUN'] and transform_cloth == True: # NUNO
                f.seek(chunk["start_offset"],0)
                nun_struct["nuno"] = parseNUNO(f.read(chunk["size"]),e)
            elif chunk["magic"] in ['NUNV', 'VNUN'] and transform_cloth == True: # NUNV
                f.seek(chunk["start_offset"],0)
                nun_struct["nunv"] = parseNUNV(f.read(chunk["size"]),e)
            elif chunk["magic"] in ['NUNS', 'SNUN'] and transform_cloth == True: # NUNS
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
        if len(nun_struct) > 0 and model_skel_data['jointCount'] > 1 and transform_cloth == True:
            nun_data = stack_nun(nun_struct)
            nun_maps = calc_nun_maps(nun_data, model_skel_data)
            if not nun_maps == False:
                nun_maps['nun_data'] = nun_data
        if os.path.exists(g1m_name + '.gltf') and (overwrite == False):
            if str(input(g1m_name + ".gltf exists! Overwrite? (y/N) ")).lower()[0:1] == 'y':
                overwrite = True
        if (overwrite == True) or not os.path.exists(g1m_name + '.gltf'):
            write_glTF(g1m_name, g1mg_stream, model_mesh_metadata, model_skel_data, nun_maps, e=e, keep_color = keep_color)
    return(True)

if __name__ == "__main__":
    # Set current directory
    if getattr(sys, 'frozen', False):
        os.chdir(os.path.dirname(sys.executable))
    else:
        os.chdir(os.path.abspath(os.path.dirname(__file__)))
    if len(sys.argv) > 1:
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument('-o', '--overwrite', help="Overwrite existing files", action="store_true")
        parser.add_argument('-k', '--keep_color', help="Preserve vertex color attribute", action="store_true")
        parser.add_argument('g1m_filename', help="Name of g1m file to build glTF (required).")
        args = parser.parse_args()
        if os.path.exists(args.g1m_filename) and args.g1m_filename[-4:].lower() == '.g1m':
            G1M2glTF(args.g1m_filename[:-4], overwrite = args.overwrite, keep_color = args.keep_color)
    else:
        # When run without command line arguments, it will attempt to obtain data from all models
        models = []
        if os.path.exists('elixir.json'):
            try:
                with open('elixir.json','r') as f:
                    elixir = json.loads(re.sub('0x[0-9a-zA-Z]+','0',f.read()))
                models = [x for x in elixir['files'] if x[-4:] == '.g1m'][1:]
            except:
                pass
        elif os.path.exists('gmpk.json'):
            if 1:
                with open('gmpk.json','r') as f:
                    gmpk = json.loads(re.sub('0x[0-9a-zA-Z]+','0',f.read()))
                models = [x['name']+'.g1m' for x in gmpk['SDP']['NID']['names']][1:]
        if len(models) > 0:
            for i in range(len(models)):
                G1M2glTF(models[i][:-4])
        else:
            models = glob.glob('*_MODEL_*.g1m')
            if len(models) > 0:
                for i in range(len(models)):
                    G1M2glTF(models[i][:-4])
            else:
                g1m_files = glob.glob('*.g1m')
                if len(g1m_files) == 1:
                    G1M2glTF(g1m_files[0][:-4])
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
                        G1M2glTF(g1m_files[g1m_file_choice][:-4])
