# A small library of functions to read and write .fmt / .ib / .vb files into and out of
# python structures that are JSON serializable.
#
# GitHub eArmada8/gust_stuff

import io, re, struct, json

# Currently only simple formats (8-, 16-, and 32-bit) are supported.  Floats must be 32-bit.
# Attempting to read an unsupported format will return a raw bytes object.
def unpack_dxgi_vector(f, stride, dxgi_format, e = '<'):
    dxgi_format = dxgi_format.split('DXGI_FORMAT_')[-1]
    dxgi_format_split = dxgi_format.split('_')
    if len(dxgi_format_split) == 2:
        numtype = dxgi_format_split[1]
        vec_format = re.findall("[0-9]+",dxgi_format_split[0])
        if len(vec_format) > 0:
            vec_bits = int(vec_format[0])
            vec_elements = len(vec_format)
        else:
            vec_bits = 0
            vec_elements = 0
    else:
        numtype = 'UNSUPPORTED'

    if numtype == 'FLOAT' and (vec_elements * vec_bits / 8 == stride):
        if vec_bits == 32:
            read = list(struct.unpack(e+str(vec_elements)+"f", f.read(stride)))
        elif vec_bits == 16:
            read = list(struct.unpack(e+str(vec_elements)+"e", f.read(stride)))
    elif numtype == 'UINT' and (vec_elements * vec_bits / 8 == stride):
        if vec_bits == 32:
            read = list(struct.unpack(e+str(vec_elements)+"I", f.read(stride)))
        elif vec_bits == 16:
            read = list(struct.unpack(e+str(vec_elements)+"H", f.read(stride)))
        elif vec_bits == 8:
            read = list(struct.unpack(e+str(vec_elements)+"B", f.read(stride)))
    elif numtype == "SINT" and (vec_elements * vec_bits / 8 == stride):
        if vec_bits == 32:
            read = list(struct.unpack(e+str(vec_elements)+"i", f.read(stride)))
        elif vec_bits == 16:
            read = list(struct.unpack(e+str(vec_elements)+"h", f.read(stride)))
        elif vec_bits == 8:
            read = list(struct.unpack(e+str(vec_elements)+"b", f.read(stride)))
    elif numtype == "UNORM" and (vec_elements * vec_bits / 8 == stride):
        # First read as integers
        if vec_bits == 32:
            read = list(struct.unpack(e+str(vec_elements)+"I", f.read(stride)))
        elif vec_bits == 16:
            read = list(struct.unpack(e+str(vec_elements)+"H", f.read(stride)))
        elif vec_bits == 8:
            read = list(struct.unpack(e+str(vec_elements)+"B", f.read(stride)))
        # Convert to normalized floats
        float_max = ((2**vec_bits)-1)
        for i in range(len(read)):
            read[i] = read[i] / float_max
    elif numtype == "SNORM" and (vec_elements * vec_bits / 8 == stride):
        # First read as integers
        if vec_bits == 32:
            read = list(struct.unpack(e+str(vec_elements)+"i", f.read(stride)))
        elif vec_bits == 16:
            read = list(struct.unpack(e+str(vec_elements)+"h", f.read(stride)))
        elif vec_bits == 8:
            read = list(struct.unpack(e+str(vec_elements)+"b", f.read(stride)))
        # Convert to normalized floats
        float_max = ((2**(vec_bits-1))-1)
        for i in range(len(read)):
            read[i] = read[i] / float_max
    else:
        read = f.read(stride)
    return (read)

def pack_dxgi_vector(f, data, stride, dxgi_format, e = '<'):
    dxgi_format = dxgi_format.split('DXGI_FORMAT_')[-1]
    dxgi_format_split = dxgi_format.split('_')
    if len(dxgi_format_split) == 2:
        numtype = dxgi_format_split[1]
        vec_format = re.findall("[0-9]+",dxgi_format_split[0])
        if len(vec_format) > 0:
            vec_bits = int(vec_format[0])
            vec_elements = len(vec_format)
        else:
            vec_bits = 0
            vec_elements = 0
    else:
        numtype = 'UNSUPPORTED'

    if numtype == 'FLOAT' and (vec_elements * vec_bits / 8 == stride):
        for i in range(vec_elements):
            if vec_bits == 32:
                f.write(struct.pack(e+"f", data[i]))
            elif vec_bits == 16:
                f.write(struct.pack(e+"e", data[i]))
    elif numtype == 'UINT' and (vec_elements * vec_bits / 8 == stride):
        for i in range(vec_elements):
            if vec_bits == 32:
                f.write(struct.pack(e+"I", data[i]))
            elif vec_bits == 16:
                f.write(struct.pack(e+"H", data[i]))
            elif vec_bits == 8:
                f.write(struct.pack(e+"B", data[i]))
    elif numtype == "SINT" and (vec_elements * vec_bits / 8 == stride):
        for i in range(vec_elements):
            if vec_bits == 32:
                f.write(struct.pack(e+"i", data[i]))
            elif vec_bits == 16:
                f.write(struct.pack(e+"h", data[i]))
            elif vec_bits == 8:
                f.write(struct.pack(e+"b", data[i]))
    elif numtype == 'UNORM' and (vec_elements * vec_bits / 8 == stride):
        converted_data = []
        for i in range(vec_elements):
            #First convert back to unsigned integers, then pack
            float_max = ((2**vec_bits)-1)
            converted_data.append(int(round(min(max(data[i],0), 1) * float_max)))
            if vec_bits == 32:
                f.write(struct.pack(e+"I", converted_data[i]))
            elif vec_bits == 16:
                f.write(struct.pack(e+"H", converted_data[i]))
            elif vec_bits == 8:
                f.write(struct.pack(e+"B", converted_data[i]))
    elif numtype == 'SNORM' and (vec_elements * vec_bits / 8 == stride):
        converted_data = []
        for i in range(vec_elements):
            #First convert back to unsigned integers, then pack
            float_max = ((2**(vec_bits-1))-1)
            converted_data.append(int(round(min(max(data[i],-1), 1) * float_max)))
            if vec_bits == 32:
                f.write(struct.pack(e+"i", converted_data[i]))
            elif vec_bits == 16:
                f.write(struct.pack(e+"h", converted_data[i]))
            elif vec_bits == 8:
                f.write(struct.pack(e+"b", converted_data[i]))
    else:
        write = f.write(data)
    return

def get_stride_from_dxgi_format(dxgi_format):
    dxgi_format = dxgi_format.split('DXGI_FORMAT_')[-1]
    dxgi_format_split = dxgi_format.split('_')
    if len(dxgi_format_split) == 2:
        numtype = dxgi_format_split[1]
        vec_format = re.findall("[0-9]+",dxgi_format_split[0])
        if len(vec_format) > 0:
            return(int(len(vec_format) * int(vec_format[0]) / 8))
        else:
            return False
    else:
        return False

def read_fmt(fmt_filename):
    fmt_struct = {}
    with open(fmt_filename, 'r') as f:
        elements = []
        while True:
            line = f.readline().strip()
            if line[0:7] == 'element':
                element = {}
                element['id'] = line.split('[')[-1][:-2]
                while True:
                    line_offset = f.tell()
                    line = f.readline().strip()
                    if line[0:7] == 'element' or line == "":
                        f.seek(line_offset)
                        elements.append(element)
                        break
                    else:
                        element[line.split(': ')[0]] = line.split(': ')[1]
            else:
                if line == "":
                    break
                fmt_struct[line.split(': ')[0]] = line.split(': ')[1]
        fmt_struct['elements'] = elements
    return(fmt_struct)

def write_fmt(fmt_struct, fmt_filename):
    output = bytearray()
    for key in fmt_struct:
        if key == "elements":
            for i in range(len(fmt_struct["elements"])):
                for key in fmt_struct["elements"][i]:
                    if key == "id":
                        output.extend(("element[" + fmt_struct["elements"][i][key] + "]:\r\n").encode())
                    else:
                        output.extend(("  " + key + ": " + fmt_struct["elements"][i][key] + "\r\n").encode())
        else:
            output.extend((key + ": " + fmt_struct[key] + "\r\n").encode())
    with open(fmt_filename, "wb") as f:
        f.write(output)
    return

def read_ib_stream(ib_stream, fmt_struct, e = '<'):
    ib_data = []
    # Cheating a bit here, since all index buffers I've seen are single numbers, but fmt doesn't have a stride for IB
    ib_stride = int(int(re.findall("[0-9]+", fmt_struct["format"])[0])/8)
    with io.BytesIO(ib_stream) as f:
        length = f.seek(0,2)
        f.seek(0)
        vertex_num = 0
        triangle = []
        while f.tell() < length:
            triangle.extend(unpack_dxgi_vector(f, ib_stride, fmt_struct["format"], e))
            vertex_num += 1
            if vertex_num % 3 == 0 or f.tell() == length:
                ib_data.append(triangle)
                triangle = []
    return(ib_data)

def read_ib(ib_filename, fmt_struct, e = '<'):
    with open(ib_filename, 'rb') as f:
        ib_stream = f.read()
    return(read_ib_stream(ib_stream, fmt_struct, e))

def write_ib_stream(ib_data, ib_stream, fmt_struct, e = '<'):
    # See above about cheating
    ib_stride = int(int(re.findall("[0-9]+", fmt_struct["format"])[0])/8)
    if len(ib_data) > 0:
        if type(ib_data[0]) == list: # Flatten list for legacy code
            new_ib_data = [x for y in ib_data for x in y]
        else:
            new_ib_data = ib_data
    else:
        new_ib_data = ib_data
    for i in range(len(new_ib_data)):
        pack_dxgi_vector(ib_stream, [new_ib_data[i]], ib_stride, fmt_struct["format"], e)
    return

def write_ib(ib_data, ib_filename, fmt_struct, e = '<'):
    with open(ib_filename, 'wb') as f:
        write_ib_stream(ib_data, f, fmt_struct, e)
    return

def read_vb_stream(vb_stream, fmt_struct, e = '<'):
    vb_data = []
    with io.BytesIO(vb_stream) as f:
        length = f.seek(0,2)
        f.seek(0)
        num_vertex = int(length / int(fmt_struct["stride"]))
        buffer_strides = []
        # Calculate individual buffer strides
        for i in range(len(fmt_struct["elements"])):
            if i == len(fmt_struct["elements"]) - 1:
                buffer_strides.append(int(fmt_struct["stride"]) - int(fmt_struct["elements"][i]["AlignedByteOffset"]))
            else:
                buffer_strides.append(int(fmt_struct["elements"][i+1]["AlignedByteOffset"]) \
                    - int(fmt_struct["elements"][i]["AlignedByteOffset"]))
        # Read in the buffers
        for i in range(len(fmt_struct["elements"])):
            element = {}
            element["SemanticName"] = fmt_struct["elements"][i]["SemanticName"]
            element["SemanticIndex"] = fmt_struct["elements"][i]["SemanticIndex"]
            element_buffer = []
            for j in range(num_vertex):
                f.seek(j * int(fmt_struct["stride"]) + int(fmt_struct["elements"][i]["AlignedByteOffset"]),0)
                element_buffer.append(unpack_dxgi_vector(f, buffer_strides[i], fmt_struct["elements"][i]["Format"], e))
            element["Buffer"] = element_buffer
            vb_data.append(element)
    return(vb_data)

def read_seg_vb_stream(vb_stream, fmt_struct, input_slot, e = '<'):
    seg_stride = "vb{} stride".format(input_slot)
    seg_elements = [x for x in fmt_struct['elements'] if x['InputSlot'] == input_slot]
    vb_data = []
    with io.BytesIO(vb_stream) as f:
        length = f.seek(0,2)
        f.seek(0)
        num_vertex = int(length / int(fmt_struct[seg_stride]))
        buffer_strides = []
        # Calculate individual buffer strides
        for i in range(len(seg_elements)):
            if i == len(seg_elements) - 1:
                buffer_strides.append(int(fmt_struct[seg_stride]) - int(seg_elements[i]["AlignedByteOffset"]))
            else:
                buffer_strides.append(int(seg_elements[i+1]["AlignedByteOffset"]) \
                    - int(seg_elements[i]["AlignedByteOffset"]))
        # Read in the buffers
        for i in range(len(seg_elements)):
            element = {}
            element["SemanticName"] = seg_elements[i]["SemanticName"]
            element["SemanticIndex"] = seg_elements[i]["SemanticIndex"]
            element["InputSlot"] = seg_elements[i]["InputSlot"]
            element_buffer = []
            for j in range(num_vertex):
                f.seek(j * int(fmt_struct[seg_stride]) + int(seg_elements[i]["AlignedByteOffset"]),0)
                element_buffer.append(unpack_dxgi_vector(f, buffer_strides[i], seg_elements[i]["Format"], e))
            element["Buffer"] = element_buffer
            vb_data.append(element)
    return(vb_data)

def read_vb(vb_filename, fmt_struct, e = '<'):
    if 'stride' in fmt_struct:
        with open(vb_filename, 'rb') as f:
            vb_stream = f.read()
        return(read_vb_stream(vb_stream, fmt_struct, e))
    elif 'vb0 stride' in fmt_struct:
        vb = []
        for input_slot in [x[2:-7] for x in fmt_struct if len(x.split('stride')) > 1]:
            with open(vb_filename + input_slot, 'rb') as f:
                vb_stream = f.read()
            vb.extend(read_seg_vb_stream(vb_stream, fmt_struct, input_slot, e))
        return(vb)
    else:
        print("Decoding error when trying to interpret fmt file for {0}!\r\n".format(vb_filename))
        input("Press Enter to abort.")
        raise

def write_vb_stream(vb_data, vb_stream, fmt_struct, e = '<', interleave = True):
    buffer_strides = []
    # Calculate individual buffer strides
    for i in range(len(fmt_struct["elements"])):
        if i == len(fmt_struct["elements"]) - 1:
            buffer_strides.append(int(fmt_struct["stride"]) - int(fmt_struct["elements"][i]["AlignedByteOffset"]))
        else:
            buffer_strides.append(int(fmt_struct["elements"][i+1]["AlignedByteOffset"]) \
                - int(fmt_struct["elements"][i]["AlignedByteOffset"]))
    if interleave == True:
        # Write out the buffers, vertex by vertex.
        for j in range(len(vb_data[0]["Buffer"])):
            for i in range(len(fmt_struct["elements"])):
                pack_dxgi_vector(vb_stream, vb_data[i]["Buffer"][j], buffer_strides[i], fmt_struct["elements"][i]["Format"], e)
    else:
        # Write out the buffers, element by element.
        for i in range(len(fmt_struct["elements"])):
            for j in range(len(vb_data[0]["Buffer"])):
                pack_dxgi_vector(vb_stream, vb_data[i]["Buffer"][j], buffer_strides[i], fmt_struct["elements"][i]["Format"], e)
    return

def write_seg_vb_stream(vb_data, vb_stream, fmt_struct, input_slot, e = '<', interleave = True):
    buffer_strides = []
    seg_stride = fmt_struct["vb{} stride".format(input_slot)]
    seg_vb_data = [x for x in vb_data if x['InputSlot'] == input_slot]
    seg_elements = [x for x in fmt_struct['elements'] if x['InputSlot'] == input_slot]
    # Calculate individual buffer strides
    for i in range(len(seg_elements)):
        if i == len(seg_elements) - 1:
            buffer_strides.append(int(seg_stride) - int(seg_elements[i]["AlignedByteOffset"]))
        else:
            buffer_strides.append(int(seg_elements[i+1]["AlignedByteOffset"]) \
                - int(seg_elements[i]["AlignedByteOffset"]))
    if interleave == True:
        # Write out the buffers, vertex by vertex.
        for j in range(len(seg_vb_data[0]["Buffer"])):
            for i in range(len(seg_elements)):
                pack_dxgi_vector(vb_stream, seg_vb_data[i]["Buffer"][j], buffer_strides[i], seg_elements[i]["Format"], e)
    else:
        # Write out the buffers, element by element.
        for i in range(len(seg_elements)):
            for j in range(len(seg_vb_data[0]["Buffer"])):
                pack_dxgi_vector(vb_stream, seg_vb_data[i]["Buffer"][j], buffer_strides[i], seg_elements[i]["Format"], e)
    return

def write_vb(vb_data, vb_filename, fmt_struct, e = '<', interleave = True):
    if 'stride' in fmt_struct:
        with open(vb_filename, 'wb') as f:
            write_vb_stream(vb_data, f, fmt_struct, e=e, interleave=interleave)
    elif 'vb0 stride' in fmt_struct:
        for input_slot in [x[2:-7] for x in fmt_struct if len(x.split('stride')) > 1]:
            with open(vb_filename + input_slot, 'wb') as f:
                write_seg_vb_stream(vb_data, f, fmt_struct, input_slot, e=e, interleave=interleave)
    else:
        print("Decoding error when trying to interpret fmt file for {0}!\r\n".format(vb_filename))
        input("Press Enter to abort.")
        raise
    return

# The following two functions are purely for convenience
def read_struct_from_json(filename, raise_on_fail = True):
    with open(filename, 'r') as f:
        try:
            return(json.loads(f.read()))
        except json.JSONDecodeError as e:
            print("Decoding error when trying to read JSON file {0}!\r\n".format(filename))
            print("{0} at line {1} column {2} (character {3})\r\n".format(e.msg, e.lineno, e.colno, e.pos))
            if raise_on_fail == True:
                input("Press Enter to abort.")
                raise
            else:
                return(False)

def write_struct_to_json(struct, filename):
    if not filename[:-5] == '.json':
        filename += '.json'
    with open(filename, "wb") as f:
        f.write(json.dumps(struct, indent=4).encode("utf-8"))
    return
