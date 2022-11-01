# G1M table of contents extractor for G1M files.
# Based entirely off the work of Joschuka (fmt_g1m / Project G1M), huge thank you to Joschuka!
#
# GitHub eArmada8/gust_stuff

import glob, os, io, sys, struct, json

# The argument passed (g1m_name) is actually the folder name
def parseG1M(g1m_name):
    with open(g1m_name + '.g1m', "rb") as f:
        file = {}
        file["file_magic"], = struct.unpack(">I", f.read(4))
        if file["file_magic"] == 0x5F4D3147:
            e = '<' # Little Endian
        elif file["file_magic"] == 0x47314D5F:
            e = '>' # Big Endian
        else:
            print("not G1M!") # Figure this out later
            sys.exit()
        file["file_version"] = f.read(4).hex()
        file["file_size"], = struct.unpack(e+"I", f.read(4))
        chunks = {}
        chunks["starting_offset"], chunks["reserved"], chunks["count"] = struct.unpack(e+"III", f.read(12))
        chunks["chunks"] = []
        f.seek(chunks["starting_offset"])
        nun_data = {}
        have_skeleton = False
        for i in range(chunks["count"]):
            chunk = {}
            chunk["start_offset"] = f.tell()
            chunk["magic"] = f.read(4).decode("utf-8")
            if e == '<':
                chunk["magic"] = chunk["magic"][::-1]
            chunk["version"] = f.read(4).hex()
            chunk["size"], = struct.unpack(e+"I", f.read(4))
            chunks["chunks"].append(chunk)
            f.seek(chunk["start_offset"] + chunk["size"],0) # Move to next chunk
        file["chunks"] = chunks
    return(file)

if __name__ == "__main__":
    # Set current directory
    os.chdir(os.path.abspath(os.path.dirname(__file__)))
    if len(sys.argv) > 1:
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument('-o', '--overwrite', help="Overwrite existing files", action="store_true")
        parser.add_argument('g1m_filename', help="Name of g1m file to extract G1MG metadata (required).")
        args = parser.parse_args()
        if os.path.exists(args.g1m_filename) and args.g1m_filename[-4:].lower() == '.g1m':
            model_metadata = parseG1M(args.g1m_filename[:-4])
            with open(args.g1m_filename+"_toc.json", "wb") as f:
                f.write(json.dumps(model_metadata, indent=4).encode("utf-8"))
    else:
        # When run without command line arguments, it will read all models
        modeldirs = [x for x in glob.glob('*_MODEL_*') if os.path.isdir(x)]
        models = [value for value in modeldirs if value in [x[:-4] for x in glob.glob('*_MODEL_*.g1m')]]
        if len(models) > 0:
            for i in range(len(models)):
                model_metadata = parseG1M(models[i])
                with open(models[i]+"/toc.json", "wb") as f:
                    f.write(json.dumps(model_metadata, indent=4).encode("utf-8"))
