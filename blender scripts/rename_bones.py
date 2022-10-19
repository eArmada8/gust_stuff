# Short script to rename bones. Run inside Blender.
# Thank you to scurest (StackExchange answer)
# GitHub eArmada8/gust_stuff

import bpy
ob = bpy.context.active_object
assert ob.type == "ARMATURE"
assert bpy.context.mode == 'OBJECT'
for bone in [ob, ob.data, *ob.data.bones]:
    bone.name = bone.name.replace("UnnamedBone#","ExternalBone")