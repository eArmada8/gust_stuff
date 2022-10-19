# Short script to rename bones and remove unneeded bones based on vgmap file. Run inside Blender.
# Thank you to scurest (StackExchange answer), Sinestesia
# GitHub eArmada8/gust_stuff

import bpy, os
from bpy.props import StringProperty, BoolProperty
from bpy_extras.io_utils import ImportHelper
from bpy.types import Operator

class BoneRemover(Operator, ImportHelper):

    bl_idname = "vgmapfinder.open_filebrowser"
    bl_label = "Select File"

    filter_glob: StringProperty(
        default='*.vgmap',
        options={'HIDDEN'}
    )

    def execute(self, context):
        ob = bpy.context.object
        if ob.type == 'ARMATURE':
            armature = ob.data

        bpy.ops.object.mode_set(mode='OBJECT')
        for bone in [ob, ob.data, *ob.data.bones]:
            bone.name = bone.name.replace("UnnamedBone#","ExternalBone")

        with open(self.filepath, 'r') as f:
            vgmapdata = f.read()
        bonelist = [x for x in vgmapdata.split("\"") if 'Bone' in x]
        bpy.ops.object.mode_set(mode='EDIT')

        for bone in armature.edit_bones:
            if bone.name not in bonelist: 
                armature.edit_bones.remove(bone)
        return {'FINISHED'}

def register():
    bpy.utils.register_class(BoneRemover)

def unregister():
    bpy.utils.unregister_class(BoneRemover)

if __name__ == "__main__":
    register()

    bpy.ops.vgmapfinder.open_filebrowser('INVOKE_DEFAULT')
