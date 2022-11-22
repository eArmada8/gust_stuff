# Driver Mesh generator code fragment; requires skeleton and NUN data as JSON.
# Based entirely off the work of Joschuka (fmt_g1m / Project G1M), huge thank you to Joschuka!
#
# Requires pyquaternion and numpy.
# These can be installed by:
# /path/to/python3 -m pip install pyquaternion
#
# GitHub eArmada8/gust_stuff

import glob, os, io, sys, struct, json, numpy
from pyquaternion import Quaternion
from lib_fmtibvb import *

def make_drivermesh_fmt():
    return({'stride': '36', 'topology': 'trianglelist', 'format': 'DXGI_FORMAT_R16_UINT',\
    'elements': [{'id': '0', 'SemanticName': 'POSITION', 'SemanticIndex': '0', 'Format': 'R32G32B32_FLOAT',\
    'InputSlot': '0', 'AlignedByteOffset': '0', 'InputSlotClass': 'per-vertex', 'InstanceDataStepRate': '0'},\
    {'id': '1', 'SemanticName': 'BLENDWEIGHT', 'SemanticIndex': '0', 'Format': 'R32G32B32A32_FLOAT',\
    'InputSlot': '0', 'AlignedByteOffset': '12', 'InputSlotClass': 'per-vertex', 'InstanceDataStepRate': '0'},\
    {'id': '2', 'SemanticName': 'BLENDINDICES', 'SemanticIndex': '0', 'Format': 'R16G16B16A16_UINT',\
    'InputSlot': '0', 'AlignedByteOffset': '28', 'InputSlotClass': 'per-vertex', 'InstanceDataStepRate': '0'}]})

def calc_nun_maps(nun_data, skel_data):
    try:
        nunvOffset = 0
        nunsOffset = 0
        clothMap = []
        clothParentIDMap = []
        driverMeshList = []
        for i in range(len(nun_data)):
            boneStart = len(skel_data['boneList'])
            parentBone = skel_data['boneIDList'][nun_data[i]['parentBoneID']]
            nunoMap = {}
            vertices = []
            skinWeightList = []
            skinIndiceList = []
            triangles = []
            vertCount = 0
            transform_info = []
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
                    q_wxyz = Quaternion(parent_bone['abs_q']) * Quaternion(parentID_bone['abs_q']).inverse
                    tm_temp = Quaternion(parentID_bone['abs_q']).transformation_matrix
                    tm_temp[0:3,3] = parentID_bone['abs_p'] # Insert into 4th column of matrix
                    pIDinv_pos_xyz = numpy.linalg.inv(tm_temp)[0:3,3] # Read 4th column after inversion
                    temp_p = (numpy.array(Quaternion(parentID_bone['abs_q']).inverse.rotate(parent_bone['abs_p'])) + pIDinv_pos_xyz).tolist()
                    pos_xyz = (numpy.array(q_wxyz.rotate(p)) + temp_p).tolist()
                    if (i==1 and pointIndex==2):
                        write_struct_to_json({'pointIndex': pointIndex,\
                        'parentID': parentID,\
                        'parent_bone': parent_bone,\
                        'parentID_bone': parentID_bone,\
                        'q_wxyz': list(q_wxyz),\
                        'pIDinv_pos_xyz': pIDinv_pos_xyz.tolist(),\
                        'temp_p': temp_p,\
                        'pos_xyz': pos_xyz\
                        }, 'temp')
                bone = {}
                bone['i'] = len(skel_data['boneList'])
                bone['bone_id'] = nun_data[0]['name'] + 'bone_p' + str(parentBone) + "_" + str(len(skel_data['boneList']))
                bone['parentBone'] = parentBone
                bone['parentID'] = parentID
                bone['q_wxyz'] = list(q_wxyz)
                bone['pos_xyz'] = pos_xyz
                parent_bone = [x for x in skel_data['boneList'] if x['i'] == parentID][0]
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
        return({'clothMap': clothMap, 'clothParentIDMap': clothParentIDMap, 'driverMeshList': driverMeshList})
    except:
        return(False)

def write_drivermeshes(driver_struct):         
    driverMesh_fmt = make_drivermesh_fmt()
    for i in range(len(driver_struct['driverMeshList'])):
        write_fmt(driverMesh_fmt, 'drivermesh'+str(i)+'.fmt')
        write_ib(driver_struct['driverMeshList'][i]["indices"], 'drivermesh'+str(i)+'.ib', driverMesh_fmt)
        write_vb(driver_struct['driverMeshList'][i]["vertices"], 'drivermesh'+str(i)+'.vb', driverMesh_fmt)
    return()

if __name__ == "__main__":
    # Set current directory
    os.chdir(os.path.abspath(os.path.dirname(__file__)))
    if os.path.exists('nun_data.json') and os.path.exists('skel_data.json'):
        nun_data = read_struct_from_json('nun_data.json')
        skel_data = read_struct_from_json('skel_data.json')
        nun_maps = calc_nun_maps(nun_data, skel_data)
        write_drivermeshes(nun_maps)
        write_struct_to_json(nun_maps,'drivermeshinfo')
