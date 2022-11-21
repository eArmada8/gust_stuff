# Very basic glTF builder for G1M files, still kind of broken and no skeleton code.
#
# Based primarily off the work of GitHub/Joschuka and GitHub/three-houses-research-team,
# huge thank you!  Also many thanks to eterniti for sharing code with me to reference.
# Credit also to the Khronos group tutorial.
#
# This code depends on g1m_export_meshes.py, g1m_import_meshes.py and lib_fmtibvb.py being in the same folder.
#
# This code requires both numpy and pyquaternion for skeletal manipulation.
#
# These can be installed by:
# /path/to/python3 -m pip install pyquaternion
#
# Steps:
# 1. Use Gust Tools to extract G1M from the .elixir.gz file.
# 2. Run this script (in the folder with the g1m file).
#
# For command line options:
# /path/to/python3 g1m_to_basic_gltf.py --help
#
# GitHub eArmada8/gust_stuff

import glob, os, io, sys, copy, json
from g1m_export_meshes import *
from g1m_import_meshes import *

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
    for i in range(len(fmt['elements'])):
        new_info = convert_format_for_gltf(fmt['elements'][i]['Format'])
        new_fmt['elements'][i]['Format'] = new_info['format']
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

def write_glTF(g1m_name, g1mg_stream, model_mesh_metadata, model_skel_data, e = '<'):
    subvbs = [x for x in model_mesh_metadata['sections'] if x['type'] == "SUBMESH"][0]
    fmts = generate_fmts(model_mesh_metadata)
    # Reformat variables for glTF (change half-floats, unorms, etc)
    gltf_fmts = []
    for i in range(len(fmts)):
        gltf_fmts.append(convert_fmt_for_gltf(fmts[i]))
    gltf_data = {}
    gltf_data['asset'] = { 'version': '2.0' }
    gltf_data['accessors'] = []
    gltf_data['bufferViews'] = []
    gltf_data['buffers'] = []
    gltf_data['meshes'] = []
    gltf_data['nodes'] = []
    gltf_data['scenes'] = [{}]
    gltf_data['scene'] = 0
    giant_buffer = bytes()
    mesh_nodes = []
    buffer_view = 0
    for subindex in range(len(subvbs['data'])):
        # Skip mesh if 4D
        if [x for x in gltf_fmts[subvbs['data'][subindex]['vertexBufferIndex']]['elements'] if x['SemanticName'] == 'POSITION'][0]['accessor_type'] == 'VEC3':
            primitive = {"attributes":{}}
            submesh = generate_submesh(subindex, g1mg_stream, model_mesh_metadata, model_skel_data, fmts, e=e, cull_vertices = True)
            mesh_stream = io.BytesIO()
            write_vb_stream(submesh['vb'], mesh_stream, gltf_fmts[subvbs['data'][subindex]['vertexBufferIndex']], e=e, stripe = False)
            block_offset = 0
            for element in range(len(gltf_fmts[subvbs['data'][subindex]['vertexBufferIndex']]['elements'])):
                if len([x for x in gltf_fmts[subvbs['data'][subindex]['vertexBufferIndex']]['elements'] if x['SemanticName'] ==\
                    gltf_fmts[subvbs['data'][subindex]['vertexBufferIndex']]['elements'][element]['SemanticName']]) > 1:
                    primitive["attributes"]["{0}_{1}".format(\
                        gltf_fmts[subvbs['data'][subindex]['vertexBufferIndex']]['elements'][element]['SemanticName'],\
                        gltf_fmts[subvbs['data'][subindex]['vertexBufferIndex']]['elements'][element]['SemanticIndex'])] =\
                        len(gltf_data['accessors'])
                else:
                    primitive["attributes"][gltf_fmts[subvbs['data'][subindex]['vertexBufferIndex']]['elements'][element]['SemanticName']]\
                        = len(gltf_data['accessors'])
                gltf_data['accessors'].append({"bufferView" : buffer_view,\
                    "byteOffset": block_offset,\
                    "componentType": gltf_fmts[subvbs['data'][subindex]['vertexBufferIndex']]['elements'][element]['componentType'],\
                    "count": len(submesh['vb'][element]['Buffer']),\
                    "type": gltf_fmts[subvbs['data'][subindex]['vertexBufferIndex']]['elements'][element]['accessor_type']})
                block_offset += len(submesh['vb'][element]['Buffer']) *\
                    gltf_fmts[subvbs['data'][subindex]['vertexBufferIndex']]['elements'][element]['componentStride']
            write_ib_stream(submesh['ib'], mesh_stream, gltf_fmts[subvbs['data'][subindex]['indexBufferIndex']], e=e)
            # IB is 16-bit so can be misaligned, unlike VB (which only has 32-, 64- and 128-bit types in G1M)
            while (mesh_stream.tell() % 4) > 0:
                mesh_stream.write(b'\x00')
            primitive["indices"] = len(gltf_data['accessors'])
            gltf_data['accessors'].append({"bufferView" : buffer_view,\
                "byteOffset": block_offset,\
                "componentType": gltf_fmts[subvbs['data'][subindex]['indexBufferIndex']]['componentType'],\
                "count": len([index for triangle in submesh['ib'] for index in triangle]),\
                "type": gltf_fmts[subvbs['data'][subindex]['indexBufferIndex']]['accessor_type']})
            gltf_data['bufferViews'].append({"buffer": 0,\
                "byteOffset": len(giant_buffer),\
                "byteLength": mesh_stream.tell()})
            mesh_stream.seek(0)
            giant_buffer += mesh_stream.read()
            mesh_stream.close()
            del(mesh_stream)
            if subvbs['data'][subindex]["indexBufferPrimType"] == 3:
                primitive["mode"] = 4 #TRIANGLES
            elif subvbs['data'][subindex]["indexBufferPrimType"] == 4:
                primitive["mode"] = 5 #TRIANGLE_STRIP
            else:
                primitive["mode"] = 0 #POINTS
            gltf_data['meshes'].append({"primitives": [primitive], "name": "Mesh_{0}".format(subindex)})
            mesh_nodes.append(len(gltf_data['nodes']))
            gltf_data['nodes'].append({'mesh': buffer_view})
            buffer_view += 1
    gltf_data['scenes'][0]['nodes'] = mesh_nodes
    gltf_data['buffers'].append({"byteLength": len(giant_buffer), "uri": g1m_name+'.bin'})
    with open(g1m_name+'.bin', 'wb') as f:
        f.write(giant_buffer)
    with open(g1m_name+'.gltf', 'wb') as f:
        f.write(json.dumps(gltf_data, indent=4).encode("utf-8"))

# The argument passed (g1m_name) is actually the folder name
def G1M2glTF(g1m_name, overwrite = False):
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
        if os.path.exists(g1m_name + '.gltf') and (overwrite == False):
            if str(input(g1m_name + ".gltf exists! Overwrite? (y/N) ")).lower()[0:1] == 'y':
                overwrite = True
        if (overwrite == True) or not os.path.exists(g1m_name):
            write_glTF(g1m_name, g1mg_stream, model_mesh_metadata, model_skel_data, e=e)
    return(True)

if __name__ == "__main__":
    # Set current directory
    os.chdir(os.path.abspath(os.path.dirname(__file__)))
    if len(sys.argv) > 1:
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument('-o', '--overwrite', help="Overwrite existing files", action="store_true")
        parser.add_argument('g1m_filename', help="Name of g1m file to build glTF (required).")
        args = parser.parse_args()
        if os.path.exists(args.g1m_filename) and args.g1m_filename[-4:].lower() == '.g1m':
            G1M2glTF(args.g1m_filename[:-4], overwrite = args.overwrite)
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
