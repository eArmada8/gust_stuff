# Short script to lock common groups based on vgmap diff file in JSON. Run inside Blender.
#
# GitHub eArmada8/gust_stuff

bl_info = {
    "name": "Lock vertex groups present in VGMap",
    "description": "Small tool to find and lock vertex groups that are present in a VGMap.  Only the joint names are used, not the index numbers.",
    "author": "github.com/eArmada8/gust_stuff",
    "version": (1, 0),
    "blender": (2, 80, 0),
    "location": "Object Data Properties > Vertex Groups > Vertex Group Specials",
    "tracker_url": "https://github.com/eArmada8/gust_stuff/issues",
    "category": "Mesh",
}

import bpy, os, json
from bpy.props import StringProperty, BoolProperty, CollectionProperty
from bpy_extras.io_utils import ImportHelper
from bpy.types import Operator

class GroupLocker(Operator, ImportHelper):

    bl_idname = "grouplocker.open_filebrowser"
    bl_label = "Select File"
    bl_description = "Select VGMap file"
    bl_options = {'REGISTER', 'UNDO'}
    files: CollectionProperty(name = 'File paths', type = bpy.types.OperatorFileListElement)
    filter_glob: StringProperty(default = '*.vgmap', options = {'HIDDEN'})
    unlock_if_not_in_vgmap: bpy.props.BoolProperty(name = "Replace current locks",\
        description = 'Default behavior is to replace the current locks, uncheck to add to the current locks instead', default = True)

    def execute(self, context):
        ob = bpy.context.object
        if ob.type == 'MESH':
            bpy.ops.object.mode_set(mode='OBJECT')
            mesh = ob
            mesh.update_from_editmode()
            vg = {i:mesh.vertex_groups[i].name for i in range(len(mesh.vertex_groups))}
            vgmapbones = []
            for file in self.files:
                with open(os.path.join(os.path.dirname(self.filepath),file.name), 'r') as f:
                    vgmapdata = json.loads(f.read())
                    vgmapbones.extend(vgmapdata.keys())

            for group in ob.vertex_groups:
                if group.name in vgmapbones:
                    group.lock_weight = True
                elif self.unlock_if_not_in_vgmap == True:
                    group.lock_weight = False

        return {'FINISHED'}

class GroupLockerMenu(bpy.types.Operator):
    bl_idname = "object.group_lock"
    bl_label = "Lock groups using VGMap"
    bl_description = "Lock weight groups that exist in a VGMap.  Only the joint names are used, not the index numbers"
    bl_options = {'REGISTER'}
    
    def execute (self, context):
        bpy.ops.grouplocker.open_filebrowser('INVOKE_DEFAULT')
        return {'FINISHED'}

def menu_func(self, context):
    self.layout.operator(GroupLockerMenu.bl_idname)

def register():
    bpy.utils.register_class(GroupLocker)
    bpy.utils.register_class(GroupLockerMenu)
    bpy.types.MESH_MT_vertex_group_context_menu.append(menu_func)

def unregister():
    bpy.utils.unregister_class(GroupLocker)
    bpy.utils.unregister_class(GroupLockerMenu)
    bpy.types.MESH_MT_vertex_group_context_menu.remove(menu_func)

if __name__ == "__main__":
    register()
    bpy.ops.grouplocker.open_filebrowser('INVOKE_DEFAULT')
