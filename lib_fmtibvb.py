# A small library of functions to read and write .fmt / .ib / .vb files into and out of
# python structures that are JSON serializable.
#
# GitHub eArmada8/gust_stuff

try:
    import io, re, struct, json
    from functools import lru_cache
except ModuleNotFoundError as e:
    print("Python module missing! {}".format(e.msg))
    input("Press Enter to abort.")
    raise

try: # For backwards compatibility
    import numpy
except ImportError:
    numpy = None

@lru_cache(maxsize=128, typed=False)
def _dxgi_format_split(dxgi_format):
    numtype, vec_bits, vec_elements, vec_stride = 'UNSUPPORTED', 0, 0, 0
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
        vec_stride = vec_elements * vec_bits / 8 
    return (numtype, vec_bits, vec_elements, vec_stride)

@lru_cache(maxsize=128, typed=False)
def _dxgi_info(dxgi_format, stride, e = '<'):
    numtype, vec_bits, vec_elements, vec_stride = _dxgi_format_split(dxgi_format)
    float_max = 0
    n_code, s_code = None, None
    if int(stride) == vec_stride:
        if numtype == 'FLOAT':
            if vec_bits == 32:
                n_code, s_code = e + 'f4', 'f'
            elif vec_bits == 16:
                n_code, s_code = e + 'f2', 'e'
        elif numtype in ['UINT', 'UNORM']:
            if vec_bits == 32:
                n_code, s_code = e + 'u4', 'I'
            elif vec_bits == 16:
                n_code, s_code = e + 'u2', 'H'
            elif vec_bits == 8:
                n_code, s_code = e + 'u1', 'B'
            if numtype == "UNORM":
                float_max = ((2**vec_bits)-1)
        elif numtype in ['SINT', 'SNORM']:
            if vec_bits == 32:
                n_code, s_code = e + 'i4', 'i'
            elif vec_bits == 16:
                n_code, s_code = e + 'i2', 'h'
            elif vec_bits == 8:
                n_code, s_code = e + 'i1', 'b'
            if numtype == "SNORM":
                float_max = ((2**(vec_bits-1))-1)
    return (n_code, s_code, vec_elements, numtype, float_max)

# Currently only simple formats (8-, 16-, and 32-bit) are supported.  Floats must be 16- or 32-bit.
# Attempting to read an unsupported format will return a raw bytes object.
def unpack_dxgi_vector(f, stride, dxgi_format, e = '<'):
    n_code, s_code, vec_elements, numtype, float_max = _dxgi_info(dxgi_format, stride, e)
    if not n_code == None:
        read = list(struct.unpack(e+str(vec_elements)+s_code, f.read(stride)))
        if numtype in ['UNORM', 'SNORM']:
            # Convert to normalized floats
            read = [x / float_max for x in read]
    else:
        read = f.read(stride)
    return (read)

def pack_dxgi_vector(f, data, stride, dxgi_format, e = '<'):
    n_code, s_code, vec_elements, numtype, float_max = _dxgi_info(dxgi_format, stride, e)
    if not n_code == None:
        # Convert normalized floats to integers
        if numtype == 'UNORM':
            data = [int(round(min(max(x,0), 1) * float_max)) for x in data]
        elif numtype == 'SNORM':
            data = [int(round(min(max(x,-1), 1) * float_max)) for x in data]
        f.write(struct.pack(e+"{}{}".format(vec_elements, s_code), *data[:vec_elements]))
    else:
        write = f.write(data)
    return

@lru_cache(maxsize=128, typed=False)
def get_stride_from_dxgi_format(dxgi_format):
    _, _, _, vec_stride = _dxgi_format_split(dxgi_format)
    return int(vec_stride) if vec_stride else False

def _calc_individual_buffer_strides (elements, stride):
    buffer_strides = []
    # Calculate individual buffer strides
    for i in range(len(elements)):
        if i == len(elements) - 1:
            buffer_strides.append(int(stride) - int(elements[i]["AlignedByteOffset"]))
        else:
            buffer_strides.append(int(elements[i+1]["AlignedByteOffset"]) \
                - int(elements[i]["AlignedByteOffset"]))
    return buffer_strides

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
    ib_stride = get_stride_from_dxgi_format(fmt_struct["format"])
    n_code, s_code, vec_elements, _, _ = _dxgi_info(fmt_struct["format"], ib_stride, e)
    if numpy:
        raw_data = numpy.frombuffer(ib_stream, dtype=n_code).tolist()
    else:
        raw_data = list(struct.unpack(e+str(len(ib_stream) // ib_stride)+s_code, ib_stream))
    ib_data = [raw_data[i:i+3] for i in range(0, len(raw_data), 3)]
    return(ib_data)

def read_ib(ib_filename, fmt_struct, e = '<'):
    with open(ib_filename, 'rb') as f:
        ib_stream = f.read()
    return(read_ib_stream(ib_stream, fmt_struct, e))

def write_ib_stream(ib_data, ib_stream, fmt_struct, e = '<'):
    ib_stride = get_stride_from_dxgi_format(fmt_struct["format"])
    n_code, s_code, vec_elements, _, _ = _dxgi_info(fmt_struct["format"], ib_stride, e)
    if len(ib_data) > 0 and isinstance(ib_data[0], list):
        new_ib_data = [x for y in ib_data for x in y]
    else:
        new_ib_data = ib_data
    if numpy:
        new_ib_array = numpy.asarray(new_ib_data, dtype=numpy.int64)
        info = numpy.iinfo(n_code)
        if (new_ib_array < info.min).any() or (new_ib_array > info.max).any():
            raise OverflowError(f"Values exceed {n_code} range [{info.min}, {info.max}]")
        ib_stream.write(new_ib_array.astype(n_code).tobytes())
    else:
        ib_stream.write(struct.pack(e+"{}{}".format(len(new_ib_data), s_code), *new_ib_data))
    return

def write_ib(ib_data, ib_filename, fmt_struct, e = '<'):
    with open(ib_filename, 'wb') as f:
        write_ib_stream(ib_data, f, fmt_struct, e)
    return

def _read_elements(vb_stream, fmt_struct, input_slot = None, e = '<'):
    vb_data = []
    stride_sem = "vb{} stride".format(input_slot) if not input_slot == None else "stride"
    stride = int(fmt_struct[stride_sem])
    num_vertex = len(vb_stream) // stride
    if not input_slot == None:
        elements = [x for x in fmt_struct['elements'] if x['InputSlot'] == str(input_slot)]
    else:
        elements = fmt_struct['elements']
    buffer_strides = _calc_individual_buffer_strides(elements, stride)
    # Read in the buffers
    if numpy:
        raw_vals = numpy.frombuffer(vb_stream, numpy.uint8, count=num_vertex*stride).reshape(num_vertex, stride)
    for i in range(len(elements)):
        new_element = {}
        new_element["SemanticName"] = elements[i]["SemanticName"]
        new_element["SemanticIndex"] = elements[i]["SemanticIndex"]
        if not input_slot == None:
            new_element["InputSlot"] = str(input_slot)
        new_element_buffer = []
        n_code, s_code, vec_elements, numtype, float_max = _dxgi_info(elements[i]["Format"], buffer_strides[i], e)
        if numpy:
            cols = raw_vals[:, int(elements[i]["AlignedByteOffset"])
                :int(elements[i]["AlignedByteOffset"])+buffer_strides[i]]
            if not n_code == None:
                new_element_buffer = numpy.ascontiguousarray(cols).view(n_code).reshape(num_vertex, vec_elements)
                if numtype in ['UNORM', 'SNORM']:
                    new_element_buffer = new_element_buffer / float_max
                new_element_buffer = new_element_buffer.tolist()
            else:
                new_element_buffer = [bytes(r) for r in cols]
        else:
            with io.BytesIO(vb_stream) as f:
                for j in range(num_vertex):
                    f.seek(j * stride + int(elements[i]["AlignedByteOffset"]),0)
                    new_element_buffer.append(unpack_dxgi_vector(f, buffer_strides[i], elements[i]["Format"], e))
        new_element["Buffer"] = new_element_buffer
        vb_data.append(new_element)
    return(vb_data)

def read_vb_stream(vb_stream, fmt_struct, e = '<'):
    return(_read_elements(vb_stream, fmt_struct, None, e))

def read_seg_vb_stream(vb_stream, fmt_struct, input_slot, e = '<'):
    return(_read_elements(vb_stream, fmt_struct, input_slot, e))

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

def _write_elements(vb_data, vb_stream, fmt_struct, input_slot = None, e = '<', interleave = True):
    stride_sem = "vb{} stride".format(input_slot) if not input_slot == None else "stride"
    stride = int(fmt_struct[stride_sem])
    if not input_slot == None:
        vb_data = [x for x in vb_data if x['InputSlot'] == input_slot]
        elements = [x for x in fmt_struct['elements'] if x['InputSlot'] == str(input_slot)]
    else:
        elements = fmt_struct['elements']
    num_vertex = len(vb_data[0]["Buffer"])
    buffer_strides = _calc_individual_buffer_strides(elements, stride)
    # Write out the buffers
    if numpy:
        array_stack = []
        for i in range(len(elements)):
            n_code, s_code, vec_elements, numtype, float_max = _dxgi_info(elements[i]["Format"], buffer_strides[i], e)
            if not n_code is None:
                n_array = numpy.array([row[:vec_elements] for row in vb_data[i]["Buffer"]]).reshape(num_vertex, vec_elements)
                if numtype == 'UNORM':
                    n_array = numpy.rint(numpy.clip(n_array, 0, 1) * float_max)
                elif numtype == 'SNORM':
                    n_array = numpy.rint(numpy.clip(n_array, -1, 1) * float_max)
                if numtype in ['UINT', 'SINT']:
                    if (n_array.size > 0) and numpy.issubdtype(n_array.dtype, numpy.floating):
                        raise TypeError(f"Expected integer array, got float dtype {n_array.dtype}")
                if numtype == 'FLOAT':
                    info = numpy.finfo(n_code)
                else:
                    info = numpy.iinfo(n_code)
                if (n_array.size > 0) and ((n_array < info.min).any() or (n_array > info.max).any()):
                    raise OverflowError(f"Values exceed {n_code} range [{info.min}, {info.max}]")
                array_stack.append(n_array.astype(n_code).view(numpy.uint8).reshape(num_vertex, buffer_strides[i]))
            else:
                array_stack.append(numpy.frombuffer(b''.join(vb_data[i]["Buffer"]),
                    numpy.uint8).reshape(num_vertex, buffer_strides[i]))
        if interleave == True:
            # Write out the buffers, vertex by vertex.
            vb_stream.write(numpy.hstack(array_stack).tobytes())
        else:
            # Write out the buffers, element by element.
            for i in range(len(array_stack)):
                vb_stream.write(array_stack[i].tobytes())
    else:
        if interleave == True:
            # Write out the buffers, vertex by vertex.
            for j in range(len(vb_data[0]["Buffer"])):
                for i in range(len(elements)):
                    pack_dxgi_vector(vb_stream, vb_data[i]["Buffer"][j], buffer_strides[i], elements[i]["Format"], e)
        else:
            # Write out the buffers, element by element.
            for i in range(len(elements)):
                for j in range(len(vb_data[0]["Buffer"])):
                    pack_dxgi_vector(vb_stream, vb_data[i]["Buffer"][j], buffer_strides[i], elements[i]["Format"], e)

def write_vb_stream(vb_data, vb_stream, fmt_struct, e = '<', interleave = True):
    _write_elements(vb_data, vb_stream, fmt_struct, None, e, interleave)

def write_seg_vb_stream(vb_data, vb_stream, fmt_struct, input_slot, e = '<', interleave = True):
    _write_elements(vb_data, vb_stream, fmt_struct, input_slot, e, interleave)

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
