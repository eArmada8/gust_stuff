# Small add-on to select vertices included in vgmap file. Run inside Blender.
# GitHub eArmada8/gust_stuff

bl_info = {
    "name": "Select vertices using VGMap",
    "blender": (2, 80, 0),
    "author": "github.com/eArmada8/gust_stuff",
    "location": "Edit Mode > Select Menu",
    "description": "Small tool to select vertices that belong to weight groups detailed in a VGMap.  Only the joint names are used, not the index numbers.",
    "category": "Mesh",
    "tracker_url": "https://github.com/eArmada8/gust_stuff/issues",
}

import bpy, os, json
from bpy.props import StringProperty, CollectionProperty
from bpy_extras.io_utils import ImportHelper
from bpy.types import Operator

class VertexMatch(Operator, ImportHelper):

    bl_idname = "vgmapfinder.open_filebrowser"
    bl_label = "Select File"
    bl_description = "Select VGMap file"
    bl_options = {'REGISTER', 'UNDO'}
    files: CollectionProperty(name = 'File paths', type = bpy.types.OperatorFileListElement)
    filter_glob: StringProperty(default = '*.vgmap', options = {'HIDDEN'})
    unselect_if_not_in_vgmap: bpy.props.BoolProperty(name = "Replace current selection",\
        description = 'Default behavior is to replace the current selection, uncheck to add to the current selection instead', default = True)
    select_only_if_all_present: bpy.props.BoolProperty(name="Select vertex only if ALL groups present", \
        description = 'Default behavior is to select vertex only if every group it belongs to is present in the VGMap.  '\
            + 'Uncheck to select if ANY group is in the map instead', default=True)
    reverse_select: bpy.props.BoolProperty(name="Select if non-matching (reverse select)",\
        description = 'Checking this box will reverse the search results', default=False)
    combine_maps: bpy.props.BoolProperty(name="Combine multiple VGMaps into one",\
        description = 'By default, vertices are checked against each map if multiple are selected.  '\
            + 'This combines all maps into one before checking', default=False)
    
    def execute(self, context):
        ob = bpy.context.object
        if ob.type == 'MESH':
            mesh = ob
            mesh.update_from_editmode()
            vg = {i:mesh.vertex_groups[i].name for i in range(len(mesh.vertex_groups))}
            vgmapbones = []
            for file in self.files:
                with open(os.path.join(os.path.dirname(self.filepath),file.name), 'r') as f:
                    vgmapdata = json.loads(f.read())
                    vgmapbones.append(vgmapdata.keys())
            if self.combine_maps == True:
                vgmapbones = [[x for y in vgmapbones for x in y]]
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_mode(type='VERT')
            if self.unselect_if_not_in_vgmap == True:
                bpy.ops.mesh.select_all(action='DESELECT')
            bpy.ops.object.mode_set(mode='OBJECT')
            for i in range(len(mesh.data.vertices)):
                if self.reverse_select == False and self.select_only_if_all_present == True:
                    if any([all(x in vgmapbones[j] for x in [vg[x.group] for x in mesh.data.vertices[i].groups])\
                            for j in range(len(vgmapbones))]):
                        mesh.data.vertices[i].select = True
                elif self.reverse_select == False and self.select_only_if_all_present == False:
                    if any([any(x in vgmapbones[j] for x in [vg[x.group] for x in mesh.data.vertices[i].groups])\
                            for j in range(len(vgmapbones))]):
                        mesh.data.vertices[i].select = True
                elif self.reverse_select == True and self.select_only_if_all_present == True:
                    if not any([all(x in vgmapbones[j] for x in [vg[x.group] for x in mesh.data.vertices[i].groups])\
                            for j in range(len(vgmapbones))]):
                        mesh.data.vertices[i].select = True
                elif self.reverse_select == True and self.select_only_if_all_present == False:
                    if not any([any(x in vgmapbones[j] for x in [vg[x.group] for x in mesh.data.vertices[i].groups])\
                            for j in range(len(vgmapbones))]):
                        mesh.data.vertices[i].select = True
            bpy.ops.object.mode_set(mode='EDIT')
        return {'FINISHED'}

class VertexMatchMenu(bpy.types.Operator):
    bl_idname = "object.vertex_match"
    bl_label = "Select vertices using VGMap"
    bl_description = "Select vertices that belong to weight groups detailed in a VGMap.  Only the joint names are used, not the index numbers"
    bl_options = {'REGISTER'}
    
    def execute (self, context):
        bpy.ops.vgmapfinder.open_filebrowser('INVOKE_DEFAULT')
        return {'FINISHED'}

def menu_func(self, context):
    self.layout.operator(VertexMatchMenu.bl_idname)

def register():
    bpy.utils.register_class(VertexMatch)
    bpy.utils.register_class(VertexMatchMenu)
    bpy.types.VIEW3D_MT_select_edit_mesh.append(menu_func)

def unregister():
    bpy.utils.unregister_class(VertexMatch)
    bpy.utils.unregister_class(VertexMatchMenu)
    bpy.types.VIEW3D_MT_select_edit_mesh.remove(menu_func)

if __name__ == "__main__":
    register()
    bpy.ops.vgmapfinder.open_filebrowser('INVOKE_DEFAULT')
