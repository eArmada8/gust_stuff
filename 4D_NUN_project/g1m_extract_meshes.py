# Mesh extractor for G1M files.
# Based off the work of Joschuka (fmt_g1m / Project G1M), huge thank you to Joschuka!
#
# GitHub eArmada8/gust_stuff

import glob, os, io, sys, struct, json
from lib_fmtibvb import *

def parseG1MG(g1mg_chunk,e):
    g1mg_section = {}
    with io.BytesIO(g1mg_chunk) as f:
        g1mg_section["magic"] = f.read(4).decode("utf-8")
        g1mg_section["version"], g1mg_section["size"], = struct.unpack(e+"II", f.read(8))
        g1mg_section["platform"] = f.read(4).decode("utf-8")
        g1mg_section["reserved"], min_x, min_y, min_z, max_x, max_y, max_z = struct.unpack(e+"I6f", f.read(28))
        g1mg_section["bounding_box"] = {'min_x': min_x, 'min_y': min_y, 'min_z': min_z, 'max_x': max_x, 'max_y': max_y, 'max_z': max_z}
        g1mg_section["sectionCount"], = struct.unpack(e+"I", f.read(4))

        sections = []
        for i in range(g1mg_section["sectionCount"]):
            section = {}
            section['offset'] = f.tell()
            section['type'] = ''
            section['magic'], section['size'], section['count'] = struct.unpack(e+"3I", f.read(12))
            match section['magic']:
                case 0x00010001:
                    section['type'] = 'SECTION1'
                    # Unused
                case 0x00010002:
                    section['type'] = 'MATERIALS'
                    section_data = {}
                    texture_block = []
                    for j in range(section['count']):
                        texture_section = {}
                        f.seek(4,1) #unknown
                        texture_section['textureCount'], = struct.unpack(e+"I", f.read(4))
                        textures = []
                        f.seek(8,1) #unknown
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
                    section['type'] = 'SHADER_SECTION'
                    # Unreversed by project G1M, use G1M tools to analyze
                case 0x00010004:
                    section['type'] = 'VERTEX_BUFFERS'
                    section_data = {}
                    vertex_block = []
                    for j in range(section['count']):
                        buffer = {}
                        f.seek(4,1) #unknown
                        buffer["stride"], buffer["count"] = struct.unpack(e+"II", f.read(8))
                        if g1mg_section["version"] > 0x30303430:
                            f.seek(4,1) #unknown
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
                    section_data = {}
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
                            data_type, dummy_var, semantic, attr['layer'] = struct.unpack(e+"4B", f.read(4))
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
                    section_data = {}
                    joint_block = []
                    for j in range(section['count']):
                        joint_info = {}
                        joint_info['joint_count'], = struct.unpack(e+"I", f.read(4))
                        joints = []
                        for k in range(joint_info['joint_count']):
                            joint = {}
                            f.seek(4,1) #unknown
                            joint['physicsIndex'], joint['jointIndex'] = struct.unpack(e+"2I", f.read(8))
                            joints.append(joint)
                        joint_info['joints'] = joints
                        joint_block.append(joint_info)
                    section['data'] = joint_block
                case 0x00010007:
                    section['type'] = 'INDEX_BUFFER'
                    section_data = {}
                    index_block = []
                    for j in range(section['count']):
                        buffer = {}
                        buffer["count"], data_type = struct.unpack(e+"II", f.read(8))
                        if g1mg_section["version"] > 0x30303430:
                            f.seek(4,1) #unknown
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
                        submesh_info["submeshType"], submesh_info["vertexBufferIndex"], submesh_info["bonePaletteIndex"],\
                        submesh_info["unknown_possibly_mat.palID"], submesh_info["unknown2"], submesh_info["unknown3"],\
                        submesh_info["materialIndex"], submesh_info["indexBufferIndex"], submesh_info["unknown4"],\
                        submesh_info["indexBufferPrimType"], submesh_info["vertexBufferOffset"], submesh_info["vertexCount"],\
                        submesh_info["indexBufferOffset"], submesh_info["indexCount"] = struct.unpack(e+"14I", f.read(56))
                        submesh_blocks.append(submesh_info)
                    section['data'] = submesh_blocks
                case 0x00010009:
                    #LOD
                    section['type'] = 'MESH'
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
                            lod_block["lodRangeStart"], lod_block["lodRangeLength"] = struct.unpack(e+"2I", f.read(8))
                            f.seek(8,1)
                        else:
                            lod_block["lodRangeStart"] = 0
                            lod_block["lodRangeLength"] = 0
                        lods = []
                        for k in range(lod_block["submeshCount1"] + lod_block["submeshCount2"]):
                            lod = {}
                            lod["name"] = f.read(16).replace(b'\x00',b'').decode("ASCII")
                            # In Project G1M, clothID is meshType, and NUNID is externalID
                            lod["clothID"], unknown, lod["NUNID"], lod["indexCount"] = struct.unpack(e+"2H2I", f.read(12))
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

def generate_fmts(model_mesh_metadata):
    # Grab metadata
    vb = [x for x in model_mesh_metadata['sections'] if x['type'] == "VERTEX_BUFFERS"][0]
    vb_attr = [x for x in model_mesh_metadata['sections'] if x['type'] == "VERTEX_ATTRIBUTES"][0]
    ib = [x for x in model_mesh_metadata['sections'] if x['type'] == "INDEX_BUFFER"][0]
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
        fmt_struct["topology"] = "trianglelist"
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

def generate_submesh(subindex, g1mg_stream, model_mesh_metadata, fmts, e = '<'):
    subvbs = [x for x in model_mesh_metadata['sections'] if x['type'] == "SUBMESH"][0]
    ibindex = subvbs['data'][subindex]['indexBufferIndex']
    vbindex = subvbs['data'][subindex]['vertexBufferIndex']
    submesh = {}
    submesh["fmt"] = fmts[vbindex]
    # When inputting index buffer offsets, divide by 3 as library returns triplets and g1m uses single index counts
    submesh["ib"] = generate_ib(ibindex, g1mg_stream, model_mesh_metadata, fmts, e = '<')\
        [int(subvbs['data'][subindex]['indexBufferOffset']/3):int(subvbs['data'][subindex]['indexBufferOffset']+subvbs['data'][subindex]['indexCount']/3)]
    submesh["vb"] = generate_vb(vbindex, g1mg_stream, model_mesh_metadata, fmts, e = '<')
    submesh = cull_vb(submesh) #Comment out this line to produce submeshes identical to G1M Tools
    return(submesh)

def write_submeshes(g1mg_stream, model_mesh_metadata, path = '', e = '<'):
    fmts = generate_fmts(model_mesh_metadata)
    subvbs = [x for x in model_mesh_metadata['sections'] if x['type'] == "SUBMESH"][0]
    for subindex in range(len(subvbs['data'])):
        submesh = generate_submesh(subindex, g1mg_stream, model_mesh_metadata, fmts, e)
        write_fmt(submesh['fmt'],'{0}{1}.fmt'.format(path, subindex))
        write_ib(submesh['ib'],'{0}{1}.ib'.format(path, subindex), submesh['fmt'])
        write_vb(submesh['vb'],'{0}{1}.vb'.format(path, subindex), submesh['fmt'])

# The argument passed (g1m_name) is actually the folder name
def parseG1M(g1m_name, write_buffers = True):
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
            if chunk["magic"] in ['G1MG', 'GM1G']:
                f.seek(chunk["start_offset"],0)
                g1mg_stream = f.read(chunk["size"])
                model_mesh_metadata = parseG1MG(g1mg_stream,e)
                if write_buffers == True:
                    if not os.path.exists(g1m_name):
                        os.mkdir(g1m_name)
                    write_submeshes(g1mg_stream, model_mesh_metadata, path = g1m_name+'/', e=e)
            else:
                f.seek(chunk["start_offset"] + chunk["size"],0) # Move to next chunk
            file["chunks"] = chunks
    return(model_mesh_metadata)

if __name__ == "__main__":
    # Set current directory
    os.chdir(os.path.abspath(os.path.dirname(__file__)))
    if len(sys.argv) > 1:
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument('-o', '--overwrite', help="Overwrite existing files", action="store_true")
        parser.add_argument('g1m_filename', help="Name of g1m file to extract G1MG metadata (required).")
        args = parser.parse_args()
        if os.path.exists(args.g1m_filename) and args.g1m_filename[-4:].lower() == '.g1m':
            model_mesh_metadata = parseG1M(args.g1m_filename[:-4])
            with open(args.g1m_filename[:-4]+"/mesh_metadata.json", "wb") as f:
                f.write(json.dumps(model_mesh_metadata, indent=4).encode("utf-8"))
    else:
        # When run without command line arguments, it will attempt to obtain data from all models
        models = glob.glob('*_MODEL_*.g1m')
        if len(models) > 0:
            for i in range(len(models)):
                model_mesh_metadata = parseG1M(models[i][:-4])
                with open(models[i][:-4]+"/mesh_metadata.json", "wb") as f:
                    f.write(json.dumps(model_mesh_metadata, indent=4).encode("utf-8"))
