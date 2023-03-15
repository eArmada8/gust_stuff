# Short script to select vertices included in vgmap file. Run inside Blender.
# GitHub eArmada8/gust_stuff

import bpy, os, json
from bpy.props import StringProperty, BoolProperty
from bpy_extras.io_utils import ImportHelper
from bpy.types import Operator

class BoneRemover(Operator, ImportHelper):

    bl_idname = "vgmapfinder.open_filebrowser"
    bl_label = "Select File"
    unselect_if_not_in_vgmap = True

    filter_glob: StringProperty(
        default='*.vgmap',
        options={'HIDDEN'}
    )

    def execute(self, context):
        ob = bpy.context.object
        if ob.type == 'MESH':
            mesh = ob
            mesh.update_from_editmode()
            vg = {i:mesh.vertex_groups[i].name for i in range(len(mesh.vertex_groups))}
            with open(self.filepath, 'r') as f:
                vgmapdata = json.loads(f.read())
                vgmapbones = list(vgmapdata.keys())
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_mode(type='VERT')
            if self.unselect_if_not_in_vgmap == True:
                bpy.ops.mesh.select_all(action='DESELECT')
            bpy.ops.object.mode_set(mode='OBJECT')
            for i in range(len(mesh.data.vertices)):
                if all(x in vgmapbones for x in [vg[x.group] for x in mesh.data.vertices[i].groups]):
                    mesh.data.vertices[i].select = True
            bpy.ops.object.mode_set(mode='EDIT')
        return {'FINISHED'}

def register():
    bpy.utils.register_class(BoneRemover)

def unregister():
    bpy.utils.unregister_class(BoneRemover)

if __name__ == "__main__":
    register()

    bpy.ops.vgmapfinder.open_filebrowser('INVOKE_DEFAULT')
