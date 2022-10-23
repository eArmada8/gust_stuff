# Small tool to rename all the vgmaps for a model in Atelier Ryza (and probably other
# Gust / KT games).  Requires G1M tools and FBX2glTF.
#
# Steps:
# 1. Convert the binary oid to the text format recognized by g1m2fbx
# 2. Run g1m2fbx on skeleton (included in G1M Tools)
# 3. Run g1m2fbx on model (included in G1M Tools)
# 4. Run g1m_export_with_vgmap.bat on model (included in G1M Tools)
# 5. Run this script
#
# GitHub eArmada8/gust_stuff
import os, json, glob

def obtain_model_data(gltf_filename):
    with open(gltf_filename, 'r') as f:
        model_data = json.loads(f.read())
        # model_data.pop("buffers")
    return(model_data)

def make_bone_dictionary(model_name):
    skeleton_model = model_name.split("MODEL")[0]+"MODEL.gltf"
    # G1M Tools writes the oid properly to the skeleton FBX but not the model FBX,
    # so we will grab the correct names from the skeleton FBX
    skeleton_model_data = obtain_model_data(skeleton_model)
    # We will grab the "UnnamedBone" names from the model FBX
    model_data = obtain_model_data(model_name)
    bone_dictionary = []
    for i in range(len(skeleton_model_data["nodes"])):
        bone = {}
        bone["g1mtool_name"] = model_data["nodes"][i]["name"]
        bone["oid_name"] = skeleton_model_data["nodes"][i]["name"]
        bone_dictionary.append(bone)
    with open(skeleton_model[:-5]+'_bonedict.json', 'wb') as f:
        f.write(json.dumps(bone_dictionary, indent=4).encode("utf-8"))
    return(bone_dictionary)

def rename_bones_in_gltf(model_name):
    skeleton_model = model_name.split("MODEL")[0]+"MODEL.gltf"
    skeleton_model_data = obtain_model_data(skeleton_model)
    model_data = obtain_model_data(model_name)
    for i in range(len(skeleton_model_data["nodes"])):
        model_data["nodes"][i]["name"] = skeleton_model_data["nodes"][i]["name"]
    with open(model_name, 'wb') as f:
        f.write(json.dumps(model_data, indent=4).encode("utf-8"))
    return

def retrieve_meshes(meshdir):
    # Make a list of all mesh groups in the current folder, both fmt and vb files are necessary for processing
    fmts = [x[:-4] for x in glob.glob(meshdir + '/*fmt',recursive=True)]
    vbs = [x[:-3] for x in glob.glob(meshdir + '/*vb',recursive=True)]
    return [value for value in fmts if value in vbs]

def rename_bones_in_vgmap(vgmap, bone_dictionary):
    newvgmap = {}
    for key in vgmap:
        newvgmap[[x for x in bone_dictionary if x["g1mtool_name"] == key.replace("ExternalBone","UnnamedBone#")][0]['oid_name']] = vgmap[key]
    return(newvgmap)

if __name__ == "__main__":
    os.chdir(os.path.abspath(os.path.dirname(__file__)))
    
    meshdirs = [x for x in glob.glob('*_MODEL_*') if os.path.isdir(x)]
    if len(meshdirs) > 0:
        for i in range(len(meshdirs)):
            # Convert model from FBX to GLTF
            model_name = meshdirs[i]
            if os.path.exists(model_name+'.fbx') and not os.path.exists(model_name+'.gltf'):
                os.system("FBX2glTF-windows-x64.exe -e -i " + model_name + ".fbx -o " + model_name + ".gltf")
            # Convert skeleton from FBX to GLTF
            skeleton_model_name = model_name.split("MODEL")[0]+"MODEL"
            if os.path.exists(skeleton_model_name+'.fbx') and not os.path.exists(skeleton_model_name+'.gltf'):
                os.system("FBX2glTF-windows-x64.exe -e -i " + skeleton_model_name + ".fbx -o " + skeleton_model_name + ".gltf")
            # Make a bone dictionary, then rename all the bones in the model GLTF
            bone_dictionary = make_bone_dictionary(model_name+'.gltf')
            rename_bones_in_gltf(model_name+'.gltf')
            # Find all the meshes in the selected model directory, open each vgmap and rename the bones
            meshes = retrieve_meshes(meshdirs[i])
            for j in range(len(meshes)):
                if os.path.exists(meshes[j]+'.vgmap'):
                    with open(meshes[j]+'.vgmap','r') as f:
                        vgmap = json.loads(f.read())
                    vgmap = rename_bones_in_vgmap(vgmap, bone_dictionary)
                    with open(meshes[j]+'.vgmap', 'wb') as f:
                        f.write(json.dumps(vgmap, indent=4).encode("utf-8"))

