# Mesh metadata extractor for G1M files.
# Based entirely off the work of Joschuka (fmt_g1m / Project G1M), huge thank you to Joschuka!
#
# GitHub eArmada8/gust_stuff

import glob, os, io, sys, struct, json

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
                    semantic_list = ['Position', 'JointWeight', 'JointIndex', 'Normal', 'PSize', 'UV',\
                    'Tangent', 'Binormal', 'TessalationFactor', 'PosTransform', 'Color', 'Fog', 'Depth', 'Sample']
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
                                    attr['dataType'] = 'Float_x1'
                                case 0x01:
                                    attr['dataType'] = 'Float_x2'
                                case 0x02:
                                    attr['dataType'] = 'Float_x3'
                                case 0x03:
                                    attr['dataType'] = 'Float_x4'
                                case 0x05:
                                    attr['dataType'] = 'UByte_x4'
                                case 0x07:
                                    attr['dataType'] = 'UShort_x4'
                                case 0x09:
                                    attr['dataType'] = 'UInt_x4' #Need confirmation per Project G1M
                                case 0x0A:
                                    attr['dataType'] = 'HalfFloat_x2'
                                case 0x0B:
                                    attr['dataType'] = 'HalfFloat_x4'
                                case 0x0D:
                                    attr['dataType'] = 'NormUByte_x4'
                                case 0xFF:
                                    attr['dataType'] = 'Dummy'
                                case _:
                                    attr['dataType'] = 'Unknown'
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
            if chunk["magic"] in ['G1MG', 'GM1G']:
                f.seek(chunk["start_offset"],0)
                g1mg_data = parseG1MG(f.read(chunk["size"]),e)
            else:
                f.seek(chunk["start_offset"] + chunk["size"],0) # Move to next chunk
            file["chunks"] = chunks
    return(g1mg_data)

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
            with open(args.g1m_filename+"_mesh_metadata.json", "wb") as f:
                f.write(json.dumps(model_mesh_metadata, indent=4).encode("utf-8"))
    else:
        # When run without command line arguments, it will attempt to obtain data from all models (skipping skeleton file)
        modeldirs = [x for x in glob.glob('*_MODEL_*') if os.path.isdir(x)]
        models = [value for value in modeldirs if value in [x[:-4] for x in glob.glob('*_MODEL_*.g1m')]]
        if len(models) > 0:
            for i in range(len(models)):
                model_mesh_metadata = parseG1M(models[i])
                with open(models[i]+"/mesh_metadata.json", "wb") as f:
                    f.write(json.dumps(model_mesh_metadata, indent=4).encode("utf-8"))