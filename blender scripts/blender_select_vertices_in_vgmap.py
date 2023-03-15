# Small add-on to select vertices included in vgmap file. Run inside Blender.
# GitHub eArmada8/gust_stuff

bl_info = {
    "name": "Select vertices using VGMap",
    "blender": (2, 80, 0),
    "category": "Mesh",
}

import bpy, os, json
from bpy.props import StringProperty, CollectionProperty
from bpy_extras.io_utils import ImportHelper
from bpy.types import Operator

class VertexMatch(Operator, ImportHelper):

    bl_idname = "vgmapfinder.open_filebrowser"
    bl_label = "Select File"
    files: CollectionProperty(name = 'File paths', type = bpy.types.OperatorFileListElement)
    filter_glob: StringProperty(default = '*.vgmap', options = {'HIDDEN'})
    unselect_if_not_in_vgmap: bpy.props.BoolProperty(name="Replace current selection", default=True)
    select_only_if_all_present: bpy.props.BoolProperty(name="Select vertex only if ALL groups present", default=True)
    reverse_select: bpy.props.BoolProperty(name="Select if non-matching (reverse select)", default=False)
    
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
                    vgmapbones.extend(vgmapdata.keys())
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_mode(type='VERT')
            if self.unselect_if_not_in_vgmap == True:
                bpy.ops.mesh.select_all(action='DESELECT')
            bpy.ops.object.mode_set(mode='OBJECT')
            for i in range(len(mesh.data.vertices)):
                if self.reverse_select == False and self.select_only_if_all_present == True:
                    if all(x in vgmapbones for x in [vg[x.group] for x in mesh.data.vertices[i].groups]):
                        mesh.data.vertices[i].select = True
                elif self.reverse_select == False and self.select_only_if_all_present == False:
                    if any(x in vgmapbones for x in [vg[x.group] for x in mesh.data.vertices[i].groups]):
                        mesh.data.vertices[i].select = True
                elif self.reverse_select == True and self.select_only_if_all_present == True:
                    if not all(x in vgmapbones for x in [vg[x.group] for x in mesh.data.vertices[i].groups]):
                        mesh.data.vertices[i].select = True
                elif self.reverse_select == True and self.select_only_if_all_present == False:
                    if not any(x in vgmapbones for x in [vg[x.group] for x in mesh.data.vertices[i].groups]):
                        mesh.data.vertices[i].select = True
            bpy.ops.object.mode_set(mode='EDIT')
        return {'FINISHED'}

class VertexMatchMenu(bpy.types.Operator):
    bl_idname = "object.vertex_match"
    bl_label = "Select vertices using VGMap"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute (self, context):
        bpy.ops.vgmapfinder.open_filebrowser('INVOKE_DEFAULT')
        return {'FINISHED'}

def menu_func(self, context):
    self.layout.operator(VertexMatchMenu.bl_idname)

def register():
    bpy.utils.register_class(VertexMatch)
    bpy.utils.register_class(VertexMatchMenu)
    bpy.types.VIEW3D_MT_edit_mesh.append(menu_func)

def unregister():
    bpy.utils.unregister_class(VertexMatch)
    bpy.utils.unregister_class(VertexMatchMenu)
    bpy.types.VIEW3D_MT_edit_mesh.remove(menu_func)

if __name__ == "__main__":
    register()
    bpy.ops.vgmapfinder.open_filebrowser('INVOKE_DEFAULT')
    unregister()
